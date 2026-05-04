import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

from app.config import settings

DB_PATH = Path(settings.outputs_dir) / "app.db"


def utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def get_connection() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db() -> None:
    with get_connection() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                id TEXT PRIMARY KEY,
                email TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                display_name TEXT NOT NULL,
                is_demo INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS chats (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                title TEXT NOT NULL,
                kind TEXT NOT NULL,
                dataset_name TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                archived INTEGER NOT NULL DEFAULT 0,
                FOREIGN KEY(user_id) REFERENCES users(id)
            );

            CREATE TABLE IF NOT EXISTS messages (
                id TEXT PRIMARY KEY,
                chat_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                blocks_json TEXT,
                metadata_json TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY(chat_id) REFERENCES chats(id)
            );

            CREATE TABLE IF NOT EXISTS artifacts (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                chat_id TEXT,
                message_id TEXT,
                kind TEXT NOT NULL,
                title TEXT NOT NULL,
                filename TEXT NOT NULL,
                path TEXT NOT NULL,
                mime_type TEXT NOT NULL,
                size_bytes INTEGER NOT NULL,
                metadata_json TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY(user_id) REFERENCES users(id)
            );

            CREATE TABLE IF NOT EXISTS datasets (
                id TEXT PRIMARY KEY,
                user_id TEXT,
                name TEXT NOT NULL,
                original_filename TEXT NOT NULL,
                path TEXT NOT NULL,
                source TEXT NOT NULL,
                rows_count INTEGER,
                columns_count INTEGER,
                created_at TEXT NOT NULL,
                FOREIGN KEY(user_id) REFERENCES users(id)
            );

            CREATE INDEX IF NOT EXISTS idx_chats_user ON chats(user_id);
            CREATE INDEX IF NOT EXISTS idx_messages_chat ON messages(chat_id);
            CREATE INDEX IF NOT EXISTS idx_artifacts_user ON artifacts(user_id);
            CREATE INDEX IF NOT EXISTS idx_datasets_user ON datasets(user_id);
            """
        )
        conn.commit()


def fetch_one(conn: sqlite3.Connection, query: str, params: tuple = ()) -> dict | None:
    row = conn.execute(query, params).fetchone()
    return dict(row) if row else None


def fetch_all(conn: sqlite3.Connection, query: str, params: tuple = ()) -> list[dict]:
    rows = conn.execute(query, params).fetchall()
    return [dict(row) for row in rows]


def dumps_json(value: dict | list | None) -> str | None:
    if value is None:
        return None
    return json.dumps(value, ensure_ascii=False)


def loads_json(value: str | None) -> dict | list | None:
    if not value:
        return None
    return json.loads(value)
