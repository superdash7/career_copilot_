"""SQLite-хранилище для auth и пользовательских данных (MVP)."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from config import Config

PROJECT_DIR = Path(__file__).resolve().parent
DB_PATH = Path(Config.DB_PATH)
if not DB_PATH.is_absolute():
    DB_PATH = PROJECT_DIR / DB_PATH
DB_PATH.parent.mkdir(parents=True, exist_ok=True)


def get_db_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _ensure_column(conn: sqlite3.Connection, table: str, column: str, ddl: str) -> None:
    columns = conn.execute(f"PRAGMA table_info({table})").fetchall()
    names = {row["name"] for row in columns}
    if column not in names:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {ddl}")


def init_db() -> None:
    with get_db_connection() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id TEXT PRIMARY KEY,
                email TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        _ensure_column(conn, "users", "experience_level", "experience_level TEXT")
        _ensure_column(conn, "users", "pain_point", "pain_point TEXT")
        _ensure_column(conn, "users", "development_hours_per_week", "development_hours_per_week INTEGER")
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS analyses (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                scenario TEXT,
                current_role TEXT,
                target_role TEXT,
                skills_json TEXT,
                result_json TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY(user_id) REFERENCES users(id)
            )
            """
        )
        conn.execute("CREATE INDEX IF NOT EXISTS idx_analyses_user_id_created_at ON analyses(user_id, created_at DESC)")
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS progress (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                skill_name TEXT NOT NULL,
                status TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY(user_id) REFERENCES users(id),
                UNIQUE(user_id, skill_name)
            )
            """
        )
        conn.execute("CREATE INDEX IF NOT EXISTS idx_progress_user_id ON progress(user_id)")
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS refresh_tokens (
                token_hash TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                created_at TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                FOREIGN KEY(user_id) REFERENCES users(id)
            )
            """
        )
        conn.execute("CREATE INDEX IF NOT EXISTS idx_refresh_tokens_user_id ON refresh_tokens(user_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_refresh_tokens_expires_at ON refresh_tokens(expires_at)")
        conn.commit()
