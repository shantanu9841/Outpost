"""SQLite connection and data access for Outpost.

Tenant isolation rule: every function that reads or writes tenant data takes
workspace_id as a required parameter, and every query filters by it. This is
deliberate over middleware/global-state approaches — forgetting to pass it is
a TypeError at call time, not a silent cross-tenant data leak.
"""

import sqlite3
from pathlib import Path

# The database is a single file at the project root, per SPEC.md.
DB_PATH = Path(__file__).resolve().parent.parent / "outpost.db"

# Key names accepted by workspace_setting, per SPEC.md.
SETTING_KEYS = ("youtube", "apify", "apollo", "llm")


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
