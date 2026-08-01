"""SQLite connection and data access for Outpost.

Tenant isolation rule: every function that reads or writes tenant data takes
workspace_id as a required parameter, and every query filters by it. This is
deliberate over middleware/global-state approaches — forgetting to pass it is
a TypeError at call time, not a silent cross-tenant data leak.
"""

import json
import sqlite3
from dataclasses import asdict
from pathlib import Path

from app import audit_banners
from app.agent.routing import RoutingOutcome
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


class EvalAlreadyExists(Exception):
    """The eval.draft_id UNIQUE constraint (exactly one eval per draft,
    SPEC.md §3) was violated -> a bug in the caller, never a normal race
    (create_draft_with_routing is the only writer, and it inserts the draft
    and its eval together in the same transaction)."""


class InvalidTransition(Exception):
    """Illegal state change -> route returns 409."""


class InvalidDraftBody(Exception):
    """Blank/over-long human-submitted body -> route returns 422."""


class ActiveDraftExists(Exception):
    """The one_active_draft_per_target race -> route redirects to /approvals."""


class GenerationInProgress(Exception):
    """Another draft generation (routing.route_and_draft, which issues the
    real Gemini calls) is already active for this workspace/target ->
    route redirects rather than issuing a second, wasted set of provider
    calls. See try_acquire_draft_generation's docstring."""


# How long a reservation is honored before it is treated as abandoned and
# reclaimable (e.g. the process that held it crashed before releasing it).
# Comfortably above the worst realistic case: up to four model-backed
# stages (default draft, default eval, escalated draft, escalated eval),
# each with a validation retry, each bounded by llm.REQUEST_TIMEOUT_SECS
# (30s) -> 8 * 30s = 240s. 300s leaves headroom without blocking a target
# for long after a genuine crash.
DRAFT_GENERATION_TTL_SECONDS = 300


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

        # Slice 6: paid-tier opt-in (default off, so every pre-existing
        # workspace stays opted out after this migration) and per-draft cost
        # columns, added idempotently so re-running init() on an already
        # migrated database is always a no-op.
        _add_column_if_missing(
            conn, "workspace", "paid_tier_enabled", "INTEGER NOT NULL DEFAULT 0"
        )
        _add_column_if_missing(conn, "draft", "cost_breakdown_json", "TEXT")
        _add_column_if_missing(conn, "draft", "estimated_cost_microusd", "INTEGER")

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS eval (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                workspace_id  INTEGER NOT NULL REFERENCES workspace(id),
                draft_id      INTEGER NOT NULL UNIQUE REFERENCES draft(id),
                rubric_json   TEXT    NOT NULL,
                score         INTEGER NOT NULL,
                created_at    TEXT    NOT NULL DEFAULT (datetime('now'))
            )
            """
        )

        # A durable, workspace-scoped reservation that a draft generation
        # (routing.route_and_draft's Gemini calls) is in progress for one
        # target, so a second concurrent request can be turned away BEFORE
        # it issues any provider call, not just after — the pre-existing
        # one_active_draft_per_target unique index only ever catches the
        # loser after both requests have already paid for their own
        # generation. UNIQUE(workspace_id, target_id) is the authoritative
        # single-winner guard; expires_at bounds how long a crashed
        # holder's row can block the target (see release_draft_generation
        # and try_acquire_draft_generation).
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS draft_generation (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                workspace_id  INTEGER NOT NULL REFERENCES workspace(id),
                target_id     INTEGER NOT NULL REFERENCES target(id),
                started_at    TEXT    NOT NULL DEFAULT (datetime('now')),
                expires_at    TEXT    NOT NULL,
                UNIQUE(workspace_id, target_id)
            )
            """
        )

        conn.commit()
    finally:
        conn.close()


def _add_column_if_missing(conn: sqlite3.Connection, table: str, column: str, ddl: str) -> None:
    """Idempotent ALTER TABLE ... ADD COLUMN, guarded by PRAGMA table_info
    since SQLite has no "ADD COLUMN IF NOT EXISTS" — safe to call on every
    startup against an already-migrated database (CLAUDE.md's Local data
    rule: schema initialization never resets or loses existing rows)."""
    existing = {row["name"] for row in conn.execute(f"PRAGMA table_info({table})")}
    if column not in existing:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}")


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


def get_paid_tier_enabled(workspace_id: int) -> bool:
    """Whether this workspace has opted into the stronger paid Gemini tier.
    Defaults to False for a missing/unknown workspace_id rather than raising,
    matching every other workspace-scoped read's "not found -> falsy" shape."""
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT paid_tier_enabled FROM workspace WHERE id = ?", (workspace_id,)
        ).fetchone()
        return bool(row["paid_tier_enabled"]) if row is not None else False
    finally:
        conn.close()


def set_paid_tier_enabled(workspace_id: int, enabled: bool) -> None:
    """Set this workspace's paid-tier opt-in. The only writer of this
    column — never touched by app.agent.routing, which takes the resolved
    boolean as a plain argument instead of reading it itself."""
    conn = get_connection()
    try:
        conn.execute(
            "UPDATE workspace SET paid_tier_enabled = ? WHERE id = ?",
            (1 if enabled else 0, workspace_id),
        )
        conn.commit()
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


def _usage_to_dict(usage) -> dict:
    """One TokenUsage dataclass -> a plain dict for cost_breakdown_json.
    Every field is a model name, plain int/None, or bool — never a provider
    payload, header, or credential (app.llm's usage-accounting guarantee)."""
    return asdict(usage)


def try_acquire_draft_generation(workspace_id: int, target_id: int) -> int | None:
    """Reserve the right to run one draft generation (routing.route_and_draft's
    Gemini calls) for this workspace/target, or return None if another
    reservation is already active and unexpired.

    Callers must call this BEFORE issuing any provider call, and must
    release the reservation (release_draft_generation) once generation
    finishes, in a `finally` block, so a failed generation never leaves the
    target permanently blocked.

    This is the authoritative concurrency guard, not merely advisory: the
    UNIQUE(workspace_id, target_id) index on draft_generation makes a
    second concurrent INSERT for the same target fail with IntegrityError
    while this one's transaction is open, and SQLite serializes writers —
    two callers racing to acquire the same target can never both succeed.
    It is durable (a real table, not an in-process lock) so it works
    identically across threads and separate OS processes sharing the same
    outpost.db file, and workspace-scoped by construction (workspace_id is
    part of the unique key and every query).

    Tenancy is enforced by the INSERT itself, exactly like add_draft:
    INSERT ... SELECT only produces a row when the subquery finds
    `target_id` inside THIS workspace, so a target belonging to another
    workspace — or a target_id that doesn't exist at all — reserves
    nothing and returns None, the same as an already-active reservation.
    This is authoritative independent of any earlier get_target() lookup
    the caller may have already done; SQLite proving both IDs exist
    independently is not the same as proving the target belongs to the
    workspace, which is what actually matters here.

    The transaction held here is intentionally tiny — one DELETE (clearing
    a stale reservation) and one INSERT, committed immediately — never held
    open across a network call. All the actual Gemini calls happen after
    this function has already returned and closed its connection.
    """
    conn = get_connection()
    try:
        conn.execute("BEGIN IMMEDIATE")
        # Reclaim a reservation whose holder never released it (a crash
        # mid-generation) rather than blocking this target forever.
        conn.execute(
            """
            DELETE FROM draft_generation
            WHERE workspace_id = ? AND target_id = ? AND expires_at < datetime('now')
            """,
            (workspace_id, target_id),
        )
        try:
            cursor = conn.execute(
                """
                INSERT INTO draft_generation (workspace_id, target_id, expires_at)
                SELECT ?, target.id, datetime('now', ?)
                FROM target
                WHERE target.workspace_id = ? AND target.id = ?
                """,
                (workspace_id, f"+{DRAFT_GENERATION_TTL_SECONDS} seconds", workspace_id, target_id),
            )
        except sqlite3.IntegrityError:
            conn.rollback()
            return None
        if cursor.rowcount == 0:
            # No target row matched (workspace_id, target_id) together —
            # either the target doesn't exist, or it belongs to a
            # different workspace. Either way, nothing to reserve.
            conn.rollback()
            return None
        conn.commit()
        return cursor.lastrowid
    finally:
        conn.close()


def release_draft_generation(workspace_id: int, target_id: int, reservation_id: int) -> None:
    """Release a reservation acquired by try_acquire_draft_generation.

    Scoped by workspace_id/target_id/id together so a caller can never
    accidentally release a different workspace's or a superseded
    reservation. Idempotent: releasing an already-released or expired-and-
    reclaimed reservation deletes zero rows and is not an error.
    """
    conn = get_connection()
    try:
        conn.execute(
            "DELETE FROM draft_generation WHERE workspace_id = ? AND target_id = ? AND id = ?",
            (workspace_id, target_id, reservation_id),
        )
        conn.commit()
    finally:
        conn.close()


def create_draft_with_routing(
    workspace_id: int, target_id: int, outcome: RoutingOutcome, actor: str = "agent"
) -> int:
    """Insert the routed draft (with its cost columns), its eval row, and
    every required audit row (draft.created, eval.scored, and a
    routing-decision row when one applies) in one transaction — all or
    nothing (non-negotiable #7/SLICE_6_PLAN.md §3).

    `outcome` is an app.agent.routing.RoutingOutcome. Tenancy is enforced by
    the draft INSERT itself, exactly like add_draft: INSERT ... SELECT only
    produces a row when target_id resolves inside THIS workspace.
    """
    draft_detail = (
        outcome.draft_status.value
        if outcome.draft_reason is None
        else f"{outcome.draft_status.value}: {outcome.draft_reason}"
    )
    cost_breakdown_json = json.dumps([_usage_to_dict(u) for u in outcome.cost_breakdown])

    conn = get_connection()
    try:
        cursor = conn.execute(
            """
            INSERT INTO draft
                (workspace_id, target_id, body, status, model_used,
                 cost_tokens, cost_breakdown_json, estimated_cost_microusd)
            SELECT ?, target.id, ?, 'pending', ?, ?, ?, ?
            FROM target
            WHERE target.workspace_id = ? AND target.id = ?
            """,
            (
                workspace_id, outcome.body, outcome.model_used, outcome.cost_tokens,
                cost_breakdown_json, outcome.estimated_cost_microusd, workspace_id, target_id,
            ),
        )
        if cursor.rowcount == 0:
            conn.rollback()
            raise NotFound
        draft_id = cursor.lastrowid
        campaign_id = conn.execute(
            "SELECT campaign_id FROM target WHERE id = ?", (target_id,)
        ).fetchone()["campaign_id"]

        _insert_audit(
            conn, workspace_id, campaign_id, actor, "draft.created", draft_detail, target_id, draft_id
        )

        eval_audit_detail = audit_banners.eval_detail(
            outcome.eval_status, outcome.eval_reason, outcome.eval_result.score
        )
        conn.execute(
            "INSERT INTO eval (workspace_id, draft_id, rubric_json, score) VALUES (?, ?, ?, ?)",
            (workspace_id, draft_id, outcome.eval_result.rubric.model_dump_json(), outcome.eval_result.score),
        )
        _insert_audit(
            conn, workspace_id, campaign_id, "agent", audit_banners.EVAL_SCORED,
            eval_audit_detail, target_id, draft_id,
        )

        routing_action = audit_banners.ROUTING_ACTION_FOR.get(outcome.routing_action)
        if routing_action is not None:
            _insert_audit(
                conn, workspace_id, campaign_id, "agent", routing_action,
                outcome.routing_detail, target_id, draft_id,
            )

        conn.commit()
        return draft_id
    except sqlite3.IntegrityError as exc:
        conn.rollback()
        if _is_active_draft_conflict(exc):
            raise ActiveDraftExists from exc
        if "eval.draft_id" in str(exc) and "UNIQUE constraint failed" in str(exc):
            raise EvalAlreadyExists from exc
        raise
    finally:
        conn.close()


def get_eval_for_draft(workspace_id: int, draft_id: int) -> sqlite3.Row | None:
    """Return the eval row for one draft, scoped to this workspace, or None."""
    conn = get_connection()
    try:
        return conn.execute(
            """
            SELECT eval.* FROM eval
            JOIN draft ON draft.id = eval.draft_id AND draft.workspace_id = eval.workspace_id
            WHERE eval.workspace_id = ? AND eval.draft_id = ?
            """,
            (workspace_id, draft_id),
        ).fetchone()
    finally:
        conn.close()


def outreach_cost_summary(workspace_id: int) -> dict:
    """A running cost-per-outreach figure for this workspace: the average
    estimated_cost_microusd among drafts with a KNOWN cost, plus how many
    drafts have an unknown cost (so the average is never silently computed
    over a partial, misleadingly-labeled set) and the total draft count."""
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT estimated_cost_microusd FROM draft WHERE workspace_id = ?",
            (workspace_id,),
        ).fetchall()
    finally:
        conn.close()

    known = [r["estimated_cost_microusd"] for r in rows if r["estimated_cost_microusd"] is not None]
    unknown_count = len(rows) - len(known)
    average_microusd = round(sum(known) / len(known)) if known else None
    return {
        "draft_count": len(rows),
        "known_cost_count": len(known),
        "unknown_cost_count": unknown_count,
        "average_cost_microusd": average_microusd,
    }


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
    docs/plans/completed/SLICE_4_PLAN.md) — whether any draft has ever existed for this target,
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
    for name/fit/campaign context, plus this draft's eval (Slice 6), if one
    exists — a draft created before Slice 6 has no eval row, hence LEFT JOIN.
    Both workspace_ids qualified throughout."""
    conn = get_connection()
    try:
        return conn.execute(
            """
            SELECT draft.*, target.name AS target_name, target.fit_score AS target_fit_score,
                   target.campaign_id AS campaign_id,
                   eval.score AS eval_score, eval.rubric_json AS eval_rubric_json
            FROM draft
            JOIN target ON target.id = draft.target_id AND target.workspace_id = draft.workspace_id
            LEFT JOIN eval ON eval.draft_id = draft.id AND eval.workspace_id = draft.workspace_id
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
    guard (§5.1 of docs/plans/completed/SLICE_4_PLAN.md): two concurrent terminal actions on the
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
    immutable body column (never a prior read of mutable edited_body). When
    the submitted text equals the original body it clears any prior saved
    edit; otherwise it stores the submitted text. This makes the approved
    effective body exactly what the human submitted while computing "was
    this edited at approval" race-free in the same conditional UPDATE that
    performs the approval.
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
                edited_body = CASE WHEN ? = body THEN NULL ELSE ? END
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
    drafts, and its text is COALESCE(edited_body, body). Also carries that
    draft's eval score and cost (Slice 6), LEFT JOINed since a pre-Slice-6
    draft has neither an eval row nor cost columns populated. Both
    workspace_ids qualified in every join."""
    conn = get_connection()
    try:
        return conn.execute(
            """
            SELECT target.id AS target_id, target.name AS target_name,
                   target.fit_score AS target_fit_score, target.campaign_id AS campaign_id,
                   target.stage AS stage,
                   d.id AS draft_id, COALESCE(d.edited_body, d.body) AS draft_text,
                   d.cost_tokens AS cost_tokens, d.estimated_cost_microusd AS estimated_cost_microusd,
                   d.cost_breakdown_json AS cost_breakdown_json, eval.score AS eval_score
            FROM target
            JOIN (
                SELECT target_id, MAX(id) AS draft_id
                FROM draft
                WHERE workspace_id = ? AND status = 'approved'
                GROUP BY target_id
            ) latest ON latest.target_id = target.id
            JOIN draft d ON d.id = latest.draft_id AND d.workspace_id = target.workspace_id
            LEFT JOIN eval ON eval.draft_id = d.id AND eval.workspace_id = d.workspace_id
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
    draft — finding 8 of docs/plans/completed/SLICE_4_PLAN.md), transition validation, update,
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
