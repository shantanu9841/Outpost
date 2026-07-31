"""SQLite connection and data access for Outpost.

Tenant isolation rule: every function that reads or writes tenant data takes
workspace_id as a required parameter, and every query filters by it. This is
deliberate over middleware/global-state approaches — forgetting to pass it is
a TypeError at call time, not a silent cross-tenant data leak.
"""

import json
import sqlite3
from pathlib import Path

from app.agent.scoring import TargetScore
from app.models import Candidate, validate_draft_body

# The database is a single file at the project root, per SPEC.md.
DB_PATH = Path(__file__).resolve().parent.parent / "outpost.db"

# Key names accepted by workspace_setting, per SPEC.md.
SETTING_KEYS = ("youtube", "apify", "apollo", "gemini")

# Two separate state machines (Slice 4). Both are module constants so the DB
# guard, the routes, and the tests share one source of truth.
DRAFT_STATUSES = ("pending", "edited", "approved", "rejected")

DRAFT_TRANSITIONS = {
    "pending": {"edited", "approved", "rejected"},
    "edited": {"edited", "approved", "rejected"},
    "approved": set(),  # terminal for that draft
    "rejected": set(),  # terminal for that draft
}

STAGES = ("queued", "contacted", "replied", "live", "declined")
STAGE_SET = set(STAGES)

STAGE_TRANSITIONS = {
    "queued": {"contacted", "declined"},
    "contacted": {"replied", "declined"},
    "replied": {"live", "declined"},
    "live": set(),  # terminal this slice
    "declined": set(),  # terminal this slice
}


class NotFound(Exception):
    """id absent, in another workspace, or (for a stage change) not yet
    admitted to the pipeline -> route redirects."""


class InvalidTransition(Exception):
    """Illegal state change -> route returns 409."""


class InvalidDraftBody(Exception):
    """Blank/over-long human-submitted body -> route returns 422."""


class ActiveDraftExists(Exception):
    """The one_active_draft_per_target race -> route redirects to /approvals."""


def get_connection() -> sqlite3.Connection:
    """Open a connection to the Outpost database.

    Foreign keys are enforced because every tenant table (starting with
    workspace_setting) references workspace_id.
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init() -> None:
    """Create tables if they do not exist. Safe to call on every startup."""
    conn = get_connection()
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS workspace (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                name        TEXT    NOT NULL,
                created_at  TEXT    NOT NULL DEFAULT (datetime('now'))
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS workspace_setting (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                workspace_id  INTEGER NOT NULL REFERENCES workspace(id),
                key_name      TEXT    NOT NULL,
                key_value     TEXT    NOT NULL,
                created_at    TEXT    NOT NULL DEFAULT (datetime('now')),
                UNIQUE(workspace_id, key_name)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS campaign (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                workspace_id    INTEGER NOT NULL REFERENCES workspace(id),
                promoting_what  TEXT    NOT NULL,
                brief_json      TEXT    NOT NULL,
                target_type     TEXT    NOT NULL,
                created_at      TEXT    NOT NULL DEFAULT (datetime('now'))
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS target (
                id                INTEGER PRIMARY KEY AUTOINCREMENT,
                workspace_id      INTEGER NOT NULL REFERENCES workspace(id),
                campaign_id       INTEGER NOT NULL REFERENCES campaign(id),
                source            TEXT    NOT NULL,
                external_id       TEXT,
                name              TEXT    NOT NULL,
                handle_or_domain  TEXT,
                reach             INTEGER,
                location          TEXT,
                raw_json          TEXT,
                fit_score         INTEGER,
                fit_reasons_json  TEXT,
                stage             TEXT    NOT NULL DEFAULT 'queued',
                created_at        TEXT    NOT NULL DEFAULT (datetime('now'))
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS audit (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                workspace_id  INTEGER NOT NULL REFERENCES workspace(id),
                campaign_id   INTEGER REFERENCES campaign(id),
                actor         TEXT    NOT NULL,
                action        TEXT    NOT NULL,
                target_id     INTEGER,
                draft_id      INTEGER,
                detail        TEXT,
                created_at    TEXT    NOT NULL DEFAULT (datetime('now'))
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS draft (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                workspace_id  INTEGER NOT NULL REFERENCES workspace(id),
                target_id     INTEGER NOT NULL REFERENCES target(id),
                body          TEXT    NOT NULL,
                status        TEXT    NOT NULL DEFAULT 'pending',
                edited_body   TEXT,
                model_used    TEXT,
                cost_tokens   INTEGER,
                created_at    TEXT    NOT NULL DEFAULT (datetime('now'))
            )
            """
        )
        # At most one non-rejected (active) draft per target — the
        # authoritative guard under a double-submit race. A rejected draft
        # is excluded, so re-drafting after a rejection is always allowed.
        conn.execute(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS one_active_draft_per_target
                ON draft (workspace_id, target_id)
                WHERE status != 'rejected'
            """
        )
        # Idempotent migration: the workspace setting was originally named
        # "llm" but the code only ever calls Gemini — rename it, preserving
        # any existing rows (CLAUDE.md's Local data rule).
        conn.execute(
            "UPDATE workspace_setting SET key_name = 'gemini' WHERE key_name = 'llm'"
        )
        conn.commit()
    finally:
        conn.close()


# --- Workspaces ---------------------------------------------------------


def create_workspace(name: str) -> int:
    """Create a workspace and return its id."""
    conn = get_connection()
    try:
        cursor = conn.execute(
            "INSERT INTO workspace (name) VALUES (?)", (name,)
        )
        conn.commit()
        return cursor.lastrowid
    finally:
        conn.close()


def list_workspaces() -> list[sqlite3.Row]:
    """Return all workspaces, most recently created first."""
    conn = get_connection()
    try:
        return conn.execute(
            "SELECT * FROM workspace ORDER BY id DESC"
        ).fetchall()
    finally:
        conn.close()


def get_workspace(workspace_id: int) -> sqlite3.Row | None:
    """Return one workspace by id, or None if it does not exist."""
    conn = get_connection()
    try:
        return conn.execute(
            "SELECT * FROM workspace WHERE id = ?", (workspace_id,)
        ).fetchone()
    finally:
        conn.close()


# --- Workspace settings (BYO-keys) --------------------------------------


def get_settings(workspace_id: int) -> dict[str, str]:
    """Return {key_name: key_value} for this workspace only."""
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT key_name, key_value FROM workspace_setting WHERE workspace_id = ?",
            (workspace_id,),
        ).fetchall()
        return {row["key_name"]: row["key_value"] for row in rows}
    finally:
        conn.close()


def save_setting(workspace_id: int, key_name: str, key_value: str) -> None:
    """Save (insert or replace) one key for this workspace."""
    conn = get_connection()
    try:
        conn.execute(
            """
            INSERT INTO workspace_setting (workspace_id, key_name, key_value)
            VALUES (?, ?, ?)
            ON CONFLICT(workspace_id, key_name)
            DO UPDATE SET key_value = excluded.key_value
            """,
            (workspace_id, key_name, key_value),
        )
        conn.commit()
    finally:
        conn.close()


def delete_setting(workspace_id: int, key_name: str) -> None:
    """Remove a key for this workspace."""
    conn = get_connection()
    try:
        conn.execute(
            "DELETE FROM workspace_setting WHERE workspace_id = ? AND key_name = ?",
            (workspace_id, key_name),
        )
        conn.commit()
    finally:
        conn.close()


# --- Campaigns -----------------------------------------------------------


def create_campaign(
    workspace_id: int, promoting_what: str, brief_json: str, target_type: str
) -> int:
    """Create a campaign for this workspace and return its id."""
    conn = get_connection()
    try:
        cursor = conn.execute(
            """
            INSERT INTO campaign (workspace_id, promoting_what, brief_json, target_type)
            VALUES (?, ?, ?, ?)
            """,
            (workspace_id, promoting_what, brief_json, target_type),
        )
        conn.commit()
        return cursor.lastrowid
    finally:
        conn.close()


def list_campaigns(workspace_id: int) -> list[sqlite3.Row]:
    """Return this workspace's campaigns, most recently created first."""
    conn = get_connection()
    try:
        return conn.execute(
            "SELECT * FROM campaign WHERE workspace_id = ? ORDER BY id DESC",
            (workspace_id,),
        ).fetchall()
    finally:
        conn.close()


def get_campaign(workspace_id: int, campaign_id: int) -> sqlite3.Row | None:
    """Return one campaign scoped to this workspace, or None if it isn't found."""
    conn = get_connection()
    try:
        return conn.execute(
            "SELECT * FROM campaign WHERE workspace_id = ? AND id = ?",
            (workspace_id, campaign_id),
        ).fetchone()
    finally:
        conn.close()


# --- Targets ---------------------------------------------------------------


def add_targets(
    workspace_id: int, campaign_id: int, candidates: list[Candidate], source_name: str
) -> None:
    """Bulk-insert discovered candidates as target rows for this campaign."""
    conn = get_connection()
    try:
        conn.executemany(
            """
            INSERT INTO target
                (workspace_id, campaign_id, source, external_id, name,
                 handle_or_domain, reach, location, raw_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    workspace_id,
                    campaign_id,
                    source_name,
                    c.external_id,
                    c.name,
                    c.handle_or_domain,
                    c.reach,
                    c.location,
                    json.dumps(c.raw),
                )
                for c in candidates
            ],
        )
        conn.commit()
    finally:
        conn.close()


def add_scored_targets(
    workspace_id: int,
    campaign_id: int,
    candidates: list[Candidate],
    source_name: str,
    scores: list[TargetScore],
) -> None:
    """Insert discovered targets together with their fit scores, atomically.

    candidates and scores must be 1:1 and in the same order. Checked before
    any connection is opened: a length mismatch raises and writes zero rows,
    rather than a zip()-based insert silently dropping the longer list's
    tail. One connection, one executemany, one commit — a campaign is never
    left with some targets scored and others not.
    """
    if len(candidates) != len(scores):
        raise ValueError("candidates and scores must be the same length")

    conn = get_connection()
    try:
        conn.executemany(
            """
            INSERT INTO target
                (workspace_id, campaign_id, source, external_id, name,
                 handle_or_domain, reach, location, raw_json,
                 fit_score, fit_reasons_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    workspace_id,
                    campaign_id,
                    source_name,
                    c.external_id,
                    c.name,
                    c.handle_or_domain,
                    c.reach,
                    c.location,
                    json.dumps(c.raw),
                    score.fit_score,
                    json.dumps([r.model_dump() for r in score.reasons]),
                )
                for c, score in zip(candidates, scores)
            ],
        )
        conn.commit()
    finally:
        conn.close()


def list_targets(workspace_id: int, campaign_id: int) -> list[sqlite3.Row]:
    """Return targets for one campaign, scoped to this workspace."""
    conn = get_connection()
    try:
        return conn.execute(
            """
            SELECT * FROM target
            WHERE workspace_id = ? AND campaign_id = ?
            ORDER BY id
            """,
            (workspace_id, campaign_id),
        ).fetchall()
    finally:
        conn.close()


# --- Audit -----------------------------------------------------------------


def _insert_audit(
    conn: sqlite3.Connection,
    workspace_id: int,
    campaign_id: int | None,
    actor: str,
    action: str,
    detail: str | None = None,
    target_id: int | None = None,
    draft_id: int | None = None,
) -> None:
    """Write one audit row on an already-open connection, without committing.

    Every Slice 4 mutation calls this inside its own transaction so the
    state change and its audit row are all-or-nothing (non-negotiable #4).
    The standalone add_audit() below delegates to this for the Slice 2/3
    call sites, which commit separately right after their own mutation.
    """
    conn.execute(
        """
        INSERT INTO audit (workspace_id, campaign_id, actor, action, target_id, draft_id, detail)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (workspace_id, campaign_id, actor, action, target_id, draft_id, (detail or "")[:500] or None),
    )


def add_audit(
    workspace_id: int,
    campaign_id: int | None,
    actor: str,
    action: str,
    detail: str | None = None,
    target_id: int | None = None,
    draft_id: int | None = None,
) -> None:
    """Record one audit row. Every action taken by human or agent is audited."""
    conn = get_connection()
    try:
        _insert_audit(conn, workspace_id, campaign_id, actor, action, detail, target_id, draft_id)
        conn.commit()
    finally:
        conn.close()


def list_audit(workspace_id: int, campaign_id: int) -> list[sqlite3.Row]:
    """Return audit rows for one campaign, scoped to this workspace, oldest first."""
    conn = get_connection()
    try:
        return conn.execute(
            """
            SELECT * FROM audit
            WHERE workspace_id = ? AND campaign_id = ?
            ORDER BY id
            """,
            (workspace_id, campaign_id),
        ).fetchall()
    finally:
        conn.close()


# --- Drafts (Slice 4) --------------------------------------------------------


def get_target(workspace_id: int, target_id: int) -> sqlite3.Row | None:
    """Return one target scoped to this workspace, or None if it isn't found.

    Used by the draft-creation route to load the target and (via
    get_campaign) the Brief that app.agent.drafting needs.
    """
    conn = get_connection()
    try:
        return conn.execute(
            "SELECT * FROM target WHERE workspace_id = ? AND id = ?",
            (workspace_id, target_id),
        ).fetchone()
    finally:
        conn.close()


def _is_active_draft_conflict(exc: sqlite3.IntegrityError) -> bool:
    """True iff this IntegrityError is the one_active_draft_per_target
    unique-index violation, identified by matching the offending columns in
    SQLite's error message (SQLite does not raise a distinctly typed
    exception per constraint, and this is the only unique constraint on
    draft). Any other IntegrityError is not this — a future foreign-key
    violation, for example, must never be silently treated as a harmless
    double-submit."""
    msg = str(exc)
    return "UNIQUE constraint failed" in msg and "draft.workspace_id" in msg and "draft.target_id" in msg


def add_draft(
    workspace_id: int,
    target_id: int,
    body: str,
    model_used: str,
    status,
    reason: str | None = None,
    actor: str = "agent",
) -> int:
    """Create a pending draft for a target in this workspace, atomically
    with its draft.created audit row.

    Tenancy is enforced by the INSERT itself: INSERT ... SELECT only
    produces a row when the subquery finds `target_id` inside THIS
    workspace, so a target in another workspace inserts zero rows and
    never becomes an orphan draft (raises NotFound instead).

    `status`/`reason` are the DraftResult's drafting outcome (llm_ok /
    no_gemini_key / invalid_gemini_key / gemini_error / heuristic_fallback,
    plus a sanitized reason when one is set) — used only to build the
    draft.created audit detail, never the new row's own ('pending') status.
    """
    detail = status.value if reason is None else f"{status.value}: {reason}"
    conn = get_connection()
    try:
        cursor = conn.execute(
            """
            INSERT INTO draft (workspace_id, target_id, body, status, model_used)
            SELECT ?, target.id, ?, 'pending', ?
            FROM target
            WHERE target.workspace_id = ? AND target.id = ?
            """,
            (workspace_id, body, model_used, workspace_id, target_id),
        )
        if cursor.rowcount == 0:
            conn.rollback()
            raise NotFound
        draft_id = cursor.lastrowid
        campaign_id = conn.execute(
            "SELECT campaign_id FROM target WHERE id = ?", (target_id,)
        ).fetchone()["campaign_id"]
        _insert_audit(
            conn, workspace_id, campaign_id, actor, "draft.created", detail, target_id, draft_id
        )
        conn.commit()
        return draft_id
    except sqlite3.IntegrityError as exc:
        conn.rollback()
        if _is_active_draft_conflict(exc):
            raise ActiveDraftExists from exc
        raise
    finally:
        conn.close()


def get_draft(workspace_id: int, draft_id: int) -> sqlite3.Row | None:
    """Return one draft scoped to this workspace, or None if it isn't found."""
    conn = get_connection()
    try:
        return conn.execute(
            "SELECT * FROM draft WHERE workspace_id = ? AND id = ?",
            (workspace_id, draft_id),
        ).fetchone()
    finally:
        conn.close()


def get_active_draft_for_target(workspace_id: int, target_id: int) -> sqlite3.Row | None:
    """The latest non-rejected draft for a target, or None.

    This is the friendly UX check the draft-creation route uses to avoid
    offering a second "Draft outreach" for a target that already has one —
    the partial unique index (one_active_draft_per_target) is the
    authoritative guard behind it, not this read.
    """
    conn = get_connection()
    try:
        return conn.execute(
            """
            SELECT * FROM draft
            WHERE workspace_id = ? AND target_id = ? AND status != 'rejected'
            ORDER BY id DESC
            LIMIT 1
            """,
            (workspace_id, target_id),
        ).fetchone()
    finally:
        conn.close()


def get_latest_draft_for_target(workspace_id: int, target_id: int) -> sqlite3.Row | None:
    """The most recent draft for a target regardless of status, or None.

    Used only for the campaign-detail lifecycle CTA (§6.2 of
    SLICE_4_PLAN.md) — whether any draft has ever existed for this target,
    and what its latest status is, including a rejected one (which
    get_active_draft_for_target deliberately excludes).
    """
    conn = get_connection()
    try:
        return conn.execute(
            """
            SELECT * FROM draft
            WHERE workspace_id = ? AND target_id = ?
            ORDER BY id DESC
            LIMIT 1
            """,
            (workspace_id, target_id),
        ).fetchone()
    finally:
        conn.close()


def has_approved_draft(workspace_id: int, target_id: int) -> bool:
    """True iff this target has an approved draft in this workspace.

    Public and independently testable: set_target_stage performs the
    equivalent check inside its own BEGIN IMMEDIATE transaction rather than
    calling this and reopening a connection, but the two must (and are
    tested to) agree.
    """
    conn = get_connection()
    try:
        row = conn.execute(
            """
            SELECT 1 FROM draft
            WHERE workspace_id = ? AND target_id = ? AND status = 'approved'
            LIMIT 1
            """,
            (workspace_id, target_id),
        ).fetchone()
        return row is not None
    finally:
        conn.close()


def list_pending_drafts(workspace_id: int) -> list[sqlite3.Row]:
    """The Approvals queue: pending/edited drafts joined with their target
    for name/fit/campaign context. Both workspace_ids qualified."""
    conn = get_connection()
    try:
        return conn.execute(
            """
            SELECT draft.*, target.name AS target_name, target.fit_score AS target_fit_score,
                   target.campaign_id AS campaign_id
            FROM draft
            JOIN target ON target.id = draft.target_id AND target.workspace_id = draft.workspace_id
            WHERE draft.workspace_id = ? AND draft.status IN ('pending', 'edited')
            ORDER BY draft.id
            """,
            (workspace_id,),
        ).fetchall()
    finally:
        conn.close()


def _diagnose_draft_failure(conn: sqlite3.Connection, workspace_id: int, draft_id: int) -> None:
    """After a conditional draft UPDATE affects 0 rows, distinguish a
    missing/cross-workspace draft (NotFound) from an existing draft whose
    current status made the transition illegal (InvalidTransition). Reads
    on the same connection right after that UPDATE's rollback — a read-only
    SELECT there cannot retroactively change the failed conditional update."""
    row = conn.execute(
        "SELECT status FROM draft WHERE workspace_id = ? AND id = ?",
        (workspace_id, draft_id),
    ).fetchone()
    if row is None:
        raise NotFound
    raise InvalidTransition(f"draft is {row['status']}")


def _target_campaign_id(conn: sqlite3.Connection, target_id: int) -> int | None:
    row = conn.execute("SELECT campaign_id FROM target WHERE id = ?", (target_id,)).fetchone()
    return row["campaign_id"] if row else None


def save_draft_body(workspace_id: int, draft_id: int, edited_body: str, actor: str = "human") -> None:
    """Save an in-progress edit without approving or rejecting.

    Validates the body (InvalidDraftBody on blank/over-long) before
    touching the database. The UPDATE's WHERE clause is the concurrency
    guard (§5.1 of SLICE_4_PLAN.md): two concurrent terminal actions on the
    same draft cannot both match it, since SQLite serializes writers and
    re-evaluates WHERE when the write lock is granted.
    """
    try:
        cleaned = validate_draft_body(edited_body)
    except ValueError as exc:
        raise InvalidDraftBody(str(exc)) from exc

    conn = get_connection()
    try:
        cursor = conn.execute(
            """
            UPDATE draft
            SET status = 'edited', edited_body = ?
            WHERE workspace_id = ? AND id = ? AND status IN ('pending', 'edited')
            """,
            (cleaned, workspace_id, draft_id),
        )
        if cursor.rowcount != 1:
            conn.rollback()
            _diagnose_draft_failure(conn, workspace_id, draft_id)
            return  # unreachable; _diagnose_draft_failure always raises
        target_id = conn.execute(
            "SELECT target_id FROM draft WHERE id = ?", (draft_id,)
        ).fetchone()["target_id"]
        campaign_id = _target_campaign_id(conn, target_id)
        _insert_audit(conn, workspace_id, campaign_id, actor, "draft.edited", None, target_id, draft_id)
        conn.commit()
    finally:
        conn.close()


def approve_draft(workspace_id: int, draft_id: int, submitted_body: str, actor: str = "human") -> None:
    """Approve a draft, committing whatever text is currently in the
    textarea — a human never loses an unsaved edit by forgetting to press
    Save first. The CASE compares submitted_body against the draft's own
    immutable body column (never a prior read of mutable edited_body), so
    "was this edited at approval" is computed race-free in the same
    conditional UPDATE that performs the approval.
    """
    try:
        cleaned = validate_draft_body(submitted_body)
    except ValueError as exc:
        raise InvalidDraftBody(str(exc)) from exc

    conn = get_connection()
    try:
        cursor = conn.execute(
            """
            UPDATE draft
            SET status = 'approved',
                edited_body = CASE WHEN ? = body THEN edited_body ELSE ? END
            WHERE workspace_id = ? AND id = ? AND status IN ('pending', 'edited')
            """,
            (cleaned, cleaned, workspace_id, draft_id),
        )
        if cursor.rowcount != 1:
            conn.rollback()
            _diagnose_draft_failure(conn, workspace_id, draft_id)
            return  # unreachable; _diagnose_draft_failure always raises
        row = conn.execute(
            "SELECT target_id, body FROM draft WHERE id = ?", (draft_id,)
        ).fetchone()
        campaign_id = _target_campaign_id(conn, row["target_id"])
        detail = "approved with inline edits" if cleaned != row["body"] else None
        _insert_audit(
            conn, workspace_id, campaign_id, actor, "draft.approved", detail, row["target_id"], draft_id
        )
        conn.commit()
    finally:
        conn.close()


def reject_draft(workspace_id: int, draft_id: int, actor: str = "human") -> None:
    """Reject a draft. The submitted textarea body is never inspected or
    validated here — rejecting discards whatever text was there."""
    conn = get_connection()
    try:
        cursor = conn.execute(
            """
            UPDATE draft
            SET status = 'rejected'
            WHERE workspace_id = ? AND id = ? AND status IN ('pending', 'edited')
            """,
            (workspace_id, draft_id),
        )
        if cursor.rowcount != 1:
            conn.rollback()
            _diagnose_draft_failure(conn, workspace_id, draft_id)
            return  # unreachable; _diagnose_draft_failure always raises
        target_id = conn.execute(
            "SELECT target_id FROM draft WHERE id = ?", (draft_id,)
        ).fetchone()["target_id"]
        campaign_id = _target_campaign_id(conn, target_id)
        _insert_audit(conn, workspace_id, campaign_id, actor, "draft.rejected", None, target_id, draft_id)
        conn.commit()
    finally:
        conn.close()


def list_pipeline_targets(workspace_id: int) -> list[sqlite3.Row]:
    """Targets with an approved draft, each appearing at most once. The
    shown draft is the most recent (MAX id) among that target's approved
    drafts, and its text is COALESCE(edited_body, body). Both
    workspace_ids qualified in every join."""
    conn = get_connection()
    try:
        return conn.execute(
            """
            SELECT target.id AS target_id, target.name AS target_name,
                   target.fit_score AS target_fit_score, target.campaign_id AS campaign_id,
                   target.stage AS stage,
                   d.id AS draft_id, COALESCE(d.edited_body, d.body) AS draft_text
            FROM target
            JOIN (
                SELECT target_id, MAX(id) AS draft_id
                FROM draft
                WHERE workspace_id = ? AND status = 'approved'
                GROUP BY target_id
            ) latest ON latest.target_id = target.id
            JOIN draft d ON d.id = latest.draft_id AND d.workspace_id = target.workspace_id
            WHERE target.workspace_id = ?
            ORDER BY target.id
            """,
            (workspace_id, workspace_id),
        ).fetchall()
    finally:
        conn.close()


def set_target_stage(workspace_id: int, target_id: int, new_stage: str, actor: str = "human") -> bool:
    """Advance a target's pipeline stage, requiring an approved draft first.

    Uses BEGIN IMMEDIATE, not the conditional-UPDATE strategy the three
    draft mutations use above, because the audit detail needs the
    authoritative mutable OLD stage and more than one source stage can
    legally lead to "declined" — a conditional UPDATE only exposes whether
    a row changed, not which stage it changed from. The writer reservation
    is held through the scoped read (which also requires an approved
    draft — finding 8 of SLICE_4_PLAN.md), transition validation, update,
    and audit insert, so a concurrent request waits and is evaluated
    against the state this transaction commits.

    A target with no approved draft resolves to the same NotFound as a
    missing/cross-workspace target (never a distinguishable response) so
    the not-found path never confirms a target exists in another state.
    Returns False (no audit row) on an idempotent same-stage no-op.
    """
    conn = get_connection()
    try:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute(
            """
            SELECT target.stage AS stage, target.campaign_id AS campaign_id
            FROM target
            WHERE target.workspace_id = ? AND target.id = ?
              AND EXISTS (
                SELECT 1 FROM draft
                WHERE draft.workspace_id = target.workspace_id
                  AND draft.target_id = target.id
                  AND draft.status = 'approved'
              )
            """,
            (workspace_id, target_id),
        ).fetchone()

        if row is None:
            conn.rollback()
            raise NotFound

        old_stage = row["stage"]
        if old_stage == new_stage:
            conn.rollback()
            return False
        if new_stage not in STAGE_TRANSITIONS.get(old_stage, set()):
            conn.rollback()
            raise InvalidTransition(f"cannot move from {old_stage} to {new_stage}")

        conn.execute(
            "UPDATE target SET stage = ? WHERE workspace_id = ? AND id = ?",
            (new_stage, workspace_id, target_id),
        )
        _insert_audit(
            conn,
            workspace_id,
            row["campaign_id"],
            actor,
            "target.stage_changed",
            f"{old_stage} -> {new_stage}",
            target_id,
            None,
        )
        conn.commit()
        return True
    finally:
        conn.close()
