from typing import Optional

from src.db.store import get_default_store


def send_chat_message(room_id: int, content: str, sender_id: int, sender_name: str, sender_level: int, sender_icon: int) -> Optional[int]:
    store = get_default_store()
    if store is None:
        return None
    row = store.fetchrow(
        "INSERT INTO chat_messages (room_id, sender_id, sender_name, sender_level, sender_icon, content, timestamp) "
        "VALUES ($1, $2, $3, $4, $5, $6, EXTRACT(EPOCH FROM NOW())::BIGINT) "
        "RETURNING id",
        room_id, sender_id, sender_name, sender_level, sender_icon, content
    )
    return row[0] if row else None
