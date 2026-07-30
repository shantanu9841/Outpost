"""SQLite connection and data access for Outpost.

Tenant isolation rule: every function that reads or writes tenant data takes
workspace_id as a required parameter, and every query filters by it. This is
deliberate over middleware/global-state approaches — forgetting to pass it is
a TypeError at call time, not a silent cross-tenant data leak.
"""

import json
import sqlite3
from pathlib import Path

from app.models import Candidate

# The database is a single file at the project root, per SPEC.md.
DB_PATH = Path(__file__).resolve().parent.parent / "outpost.db"

# Key names accepted by workspace_setting, per SPEC.md.
SETTING_KEYS = ("youtube", "apify", "apollo", "gemini")


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
        conn.execute(
            """
            INSERT INTO audit (workspace_id, campaign_id, actor, action, target_id, draft_id, detail)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (workspace_id, campaign_id, actor, action, target_id, draft_id, (detail or "")[:500] or None),
        )
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
