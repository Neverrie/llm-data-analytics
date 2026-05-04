import uuid

from app.db import dumps_json, fetch_all, fetch_one, get_connection, loads_json, utcnow_iso


def workspace_overview(user_id: str) -> dict:
    with get_connection() as conn:
        chats_count = conn.execute("SELECT COUNT(*) FROM chats WHERE user_id = ?", (user_id,)).fetchone()[0]
        datasets_count = conn.execute(
            "SELECT COUNT(*) FROM datasets WHERE user_id = ? OR user_id IS NULL",
            (user_id,),
        ).fetchone()[0]
        artifacts_count = conn.execute("SELECT COUNT(*) FROM artifacts WHERE user_id = ?", (user_id,)).fetchone()[0]

        recent_chats = fetch_all(
            conn,
            "SELECT id, title, kind, dataset_name, created_at, updated_at, archived FROM chats WHERE user_id = ? ORDER BY updated_at DESC LIMIT 10",
            (user_id,),
        )
        recent_artifacts = fetch_all(
            conn,
            "SELECT id, kind, title, filename, mime_type, size_bytes, created_at FROM artifacts WHERE user_id = ? ORDER BY created_at DESC LIMIT 10",
            (user_id,),
        )

    return {
        "counts": {"chats": chats_count, "datasets": datasets_count, "artifacts": artifacts_count},
        "recent_chats": [{**chat, "archived": bool(chat["archived"])} for chat in recent_chats],
        "recent_artifacts": recent_artifacts,
    }


def list_chats(user_id: str, kind: str | None = None, archived: bool | None = None) -> list[dict]:
    query = "SELECT id, title, kind, dataset_name, created_at, updated_at, archived FROM chats WHERE user_id = ?"
    params: list = [user_id]
    if kind:
        query += " AND kind = ?"
        params.append(kind)
    if archived is not None:
        query += " AND archived = ?"
        params.append(int(archived))
    query += " ORDER BY updated_at DESC"

    with get_connection() as conn:
        items = fetch_all(conn, query, tuple(params))
    return [{**item, "archived": bool(item["archived"])} for item in items]


def create_chat(user_id: str, title: str, kind: str, dataset_name: str | None) -> dict:
    chat_id = str(uuid.uuid4())
    now = utcnow_iso()
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO chats (id, user_id, title, kind, dataset_name, created_at, updated_at, archived) VALUES (?, ?, ?, ?, ?, ?, ?, 0)",
            (chat_id, user_id, title, kind, dataset_name, now, now),
        )
        conn.commit()
        return fetch_one(conn, "SELECT * FROM chats WHERE id = ?", (chat_id,))


def get_chat(user_id: str, chat_id: str) -> dict:
    with get_connection() as conn:
        chat = fetch_one(conn, "SELECT * FROM chats WHERE id = ? AND user_id = ?", (chat_id, user_id))
        if not chat:
            raise ValueError("Chat not found")
        messages = fetch_all(
            conn,
            "SELECT id, chat_id, role, content, blocks_json, metadata_json, created_at FROM messages WHERE chat_id = ? ORDER BY created_at ASC",
            (chat_id,),
        )
    for message in messages:
        message["blocks"] = loads_json(message.pop("blocks_json")) or []
        message["metadata"] = loads_json(message.pop("metadata_json")) or {}
    chat["archived"] = bool(chat["archived"])
    return {"chat": chat, "messages": messages}


def add_message(user_id: str, chat_id: str, role: str, content: str, blocks: list | None, metadata: dict | None) -> dict:
    with get_connection() as conn:
        chat = fetch_one(conn, "SELECT id FROM chats WHERE id = ? AND user_id = ?", (chat_id, user_id))
        if not chat:
            raise ValueError("Chat not found")
        message_id = str(uuid.uuid4())
        now = utcnow_iso()
        conn.execute(
            "INSERT INTO messages (id, chat_id, role, content, blocks_json, metadata_json, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (message_id, chat_id, role, content, dumps_json(blocks or []), dumps_json(metadata or {}), now),
        )
        conn.execute("UPDATE chats SET updated_at = ? WHERE id = ?", (now, chat_id))
        conn.commit()
        message = fetch_one(conn, "SELECT * FROM messages WHERE id = ?", (message_id,))
    message["blocks"] = loads_json(message.pop("blocks_json")) or []
    message["metadata"] = loads_json(message.pop("metadata_json")) or {}
    return message


def update_chat(user_id: str, chat_id: str, title: str | None, archived: bool | None, dataset_name: str | None = None) -> dict:
    with get_connection() as conn:
        chat = fetch_one(conn, "SELECT * FROM chats WHERE id = ? AND user_id = ?", (chat_id, user_id))
        if not chat:
            raise ValueError("Chat not found")
        new_title = title if title is not None else chat["title"]
        new_archived = int(archived) if archived is not None else chat["archived"]
        new_dataset_name = dataset_name if dataset_name is not None else chat["dataset_name"]
        now = utcnow_iso()
        conn.execute(
            "UPDATE chats SET title = ?, archived = ?, dataset_name = ?, updated_at = ? WHERE id = ?",
            (new_title, new_archived, new_dataset_name, now, chat_id),
        )
        conn.commit()
        updated = fetch_one(conn, "SELECT * FROM chats WHERE id = ?", (chat_id,))
    updated["archived"] = bool(updated["archived"])
    return updated


def archive_chat(user_id: str, chat_id: str) -> dict:
    return update_chat(user_id, chat_id, title=None, archived=True, dataset_name=None)
