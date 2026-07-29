"""SQLite connection for Outpost.

Slice 0 only opens the database file and proves connectivity. Tables and the
per-workspace schema arrive in Slice 1.
"""

import sqlite3
from pathlib import Path

# The database is a single file at the project root, per SPEC.md.
DB_PATH = Path(__file__).resolve().parent.parent / "outpost.db"


def get_connection() -> sqlite3.Connection:
    """Open a connection to the Outpost database.

    Foreign keys are enforced because later slices rely on them for
    multi-tenant integrity (every row belongs to a workspace).
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init() -> None:
    """Create the database file if it does not exist and confirm it opens.

    No tables yet in Slice 0. This runs on app startup so a fresh checkout
    produces a working, connected database with no manual step.
    """
    conn = get_connection()
    try:
        conn.execute("SELECT 1")
    finally:
        conn.close()
