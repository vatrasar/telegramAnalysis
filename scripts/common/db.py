"""Database connection and reflection helpers."""

import os
import sqlite3
from typing import Optional, Set
from common.config import get_workspace_root


def get_default_db_path() -> str:
    """Return default path to chat.db in the workspace root."""
    return os.path.join(get_workspace_root(), "chat.db")


def connect_db(db_path: Optional[str] = None) -> sqlite3.Connection:
    """Connect to SQLite database with foreign keys enabled."""
    path = db_path or get_default_db_path()
    conn = sqlite3.connect(path)
    return conn


def table_exists(conn: sqlite3.Connection, table_name: str) -> bool:
    """Check if a table exists in the database."""
    cur = conn.cursor()
    cur.execute("SELECT count(*) FROM sqlite_master WHERE type='table' AND name=?;", (table_name,))
    return cur.fetchone()[0] > 0


def get_table_columns(conn: sqlite3.Connection, table_name: str) -> Set[str]:
    """Get the set of column names for a given table."""
    cur = conn.cursor()
    cur.execute(f"PRAGMA table_info({table_name});")
    return {col[1] for col in cur.fetchall()}
