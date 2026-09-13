from __future__ import annotations

from typing import Optional

from sqlalchemy import text

from src.db.session import get_sync_session

MSG_TYPE_BANNED = 100
MSG_ACTOBSS_WORD = 1000
MSG_TYPE_NORMAL = 1


def create_message(sender_id: int, room_id: int, content: str) -> Optional[dict]:
    with get_sync_session() as session:
        row = session.execute(
            text("""
                INSERT INTO messages (sender_id, room_id, content)
                VALUES (:sid, :rid, :content)
                RETURNING id, sent_at
            """),
            {"sid": sender_id, "rid": room_id, "content": content},
        ).fetchone()
        session.commit()
        if row is None:
            return None
        return {
            "id": row[0],
            "sender_id": sender_id,
            "room_id": room_id,
            "content": content,
            "sent_at": row[1],
        }


def update_message(msg_id: int, content: str) -> None:
    with get_sync_session() as session:
        session.execute(
            text("UPDATE messages SET content = :content WHERE id = :id"),
            {"id": msg_id, "content": content},
        )
        session.commit()


def delete_message(msg_id: int) -> bool:
    with get_sync_session() as session:
        result = session.execute(
            text("DELETE FROM messages WHERE id = :id"),
            {"id": msg_id},
        )
        session.commit()
        return result.rowcount > 0


def get_room_history(room_id: int, limit: int = 50) -> list[dict]:
    with get_sync_session() as session:
        rows = session.execute(
            text("""
                SELECT id, sender_id, room_id, sent_at, content
                FROM messages
                WHERE room_id = :rid
                ORDER BY sent_at DESC
                LIMIT :lim
            """),
            {"rid": room_id, "lim": limit},
        ).fetchall()
        result = []
        for r in rows:
            result.append({
                "id": r[0],
                "sender_id": r[1],
                "room_id": r[2],
                "sent_at": r[3],
                "content": r[4],
            })
        return result


def send_message(room_id: int, content: str, sender_id: int) -> Optional[dict]:
    return create_message(sender_id, room_id, content)


create_message_sync = create_message
update_message_sync = update_message
delete_message_sync = delete_message
get_room_history_sync = get_room_history
send_message_sync = send_message
