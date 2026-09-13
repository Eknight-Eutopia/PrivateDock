from __future__ import annotations

from typing import Optional

from sqlalchemy import BigInteger, String, select, text
from sqlalchemy.orm import Mapped, mapped_column

from src.db.session import Base, get_sync_session


class FriendRelationship(Base):
    __tablename__ = "friend_relationships"
    commander_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    friend_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    created_at: Mapped[int] = mapped_column(BigInteger, default=0)


class FriendDirectMessage(Base):
    __tablename__ = "friend_direct_messages"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    sender_id: Mapped[int] = mapped_column(BigInteger, default=0)
    receiver_id: Mapped[int] = mapped_column(BigInteger, default=0)
    content: Mapped[str] = mapped_column(String, default="")
    created_at: Mapped[int] = mapped_column(BigInteger, default=0)


class PlayerInform(Base):
    __tablename__ = "player_informs"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    reporter_id: Mapped[int] = mapped_column(BigInteger, default=0)
    target_id: Mapped[int] = mapped_column(BigInteger, default=0)
    info: Mapped[str] = mapped_column(String, default="")
    content: Mapped[str] = mapped_column(String, default="")
    created_at: Mapped[int] = mapped_column(BigInteger, default=0)


def normalize_friend_pair(commander_id: int, friend_id: int) -> tuple:
    if commander_id == friend_id:
        raise ValueError("commander id and friend id cannot match")
    if commander_id < friend_id:
        return commander_id, friend_id
    return friend_id, commander_id


def create_friend_relationship(commander_id: int, friend_id: int, created_at: int) -> None:
    left, right = normalize_friend_pair(commander_id, friend_id)
    with get_sync_session() as session:
        session.execute(
            text("""
                INSERT INTO friend_relationships (commander_id, friend_id, created_at)
                VALUES (:left, :right, :ca)
                ON CONFLICT (commander_id, friend_id) DO NOTHING
            """),
            {"left": left, "right": right, "ca": created_at},
        )
        session.commit()


def delete_friend_relationship(commander_id: int, friend_id: int) -> bool:
    left, right = normalize_friend_pair(commander_id, friend_id)
    with get_sync_session() as session:
        result = session.execute(
            text("""
                DELETE FROM friend_relationships
                WHERE commander_id = :left AND friend_id = :right
            """),
            {"left": left, "right": right},
        )
        session.commit()
        return result.rowcount > 0


def is_friend(commander_id: int, friend_id: int) -> bool:
    if commander_id == friend_id:
        return False
    left, right = normalize_friend_pair(commander_id, friend_id)
    with get_sync_session() as session:
        return session.execute(
            text("""
                SELECT EXISTS(
                    SELECT 1 FROM friend_relationships
                    WHERE commander_id = :left AND friend_id = :right
                )
            """),
            {"left": left, "right": right},
        ).scalar() or False


def list_friends(commander_id: int) -> list[dict]:
    with get_sync_session() as session:
        rows = session.execute(
            text("""
                SELECT fr.commander_id, fr.friend_id, fr.created_at
                FROM friend_relationships fr
                WHERE fr.commander_id = :cid
                   OR fr.friend_id = :cid
                ORDER BY fr.created_at DESC
            """),
            {"cid": commander_id},
        ).fetchall()
        result = []
        for r in rows:
            if r[0] == commander_id:
                friend_id = r[1]
            else:
                friend_id = r[0]
            result.append({
                "commander_id": commander_id,
                "friend_id": friend_id,
                "created_at": r[2],
            })
        return result


def count_common_friends(commander_id: int, other_id: int) -> int:
    with get_sync_session() as session:
        return session.execute(
            text("""
                SELECT COUNT(*)
                FROM (
                    SELECT CASE
                        WHEN fr.commander_id = :cid1 THEN fr.friend_id
                        ELSE fr.commander_id
                    END AS friend_id
                    FROM friend_relationships fr
                    WHERE fr.commander_id = :cid1 OR fr.friend_id = :cid1
                ) cf1
                JOIN (
                    SELECT CASE
                        WHEN fr.commander_id = :cid2 THEN fr.friend_id
                        ELSE fr.commander_id
                    END AS friend_id
                    FROM friend_relationships fr
                    WHERE fr.commander_id = :cid2 OR fr.friend_id = :cid2
                ) cf2 ON cf1.friend_id = cf2.friend_id
            """),
            {"cid1": commander_id, "cid2": other_id},
        ).scalar() or 0


def list_common_friend_page(commander_id: int, other_id: int, offset: int = 0, limit: int = 20) -> list[int]:
    with get_sync_session() as session:
        rows = session.execute(
            text("""
                SELECT cf1.friend_id
                FROM (
                    SELECT CASE
                        WHEN fr.commander_id = :cid1 THEN fr.friend_id
                        ELSE fr.commander_id
                    END AS friend_id
                    FROM friend_relationships fr
                    WHERE fr.commander_id = :cid1 OR fr.friend_id = :cid1
                ) cf1
                JOIN (
                    SELECT CASE
                        WHEN fr.commander_id = :cid2 THEN fr.friend_id
                        ELSE fr.commander_id
                    END AS friend_id
                    FROM friend_relationships fr
                    WHERE fr.commander_id = :cid2 OR fr.friend_id = :cid2
                ) cf2 ON cf1.friend_id = cf2.friend_id
                ORDER BY cf1.friend_id ASC
                OFFSET :off
                LIMIT :lim
            """),
            {"cid1": commander_id, "cid2": other_id, "off": offset, "lim": limit},
        ).fetchall()
        return [r[0] for r in rows]


def create_friend_direct_message(sender_id: int, receiver_id: int, content: str, created_at: int) -> Optional[dict]:
    with get_sync_session() as session:
        row = session.execute(
            text("""
                INSERT INTO friend_direct_messages (sender_id, receiver_id, content, created_at)
                VALUES (:sid, :rid, :content, :ca)
                RETURNING id
            """),
            {"sid": sender_id, "rid": receiver_id, "content": content, "ca": created_at},
        ).fetchone()
        session.commit()
        if row is None:
            return None
        return {
            "id": row[0],
            "sender_id": sender_id,
            "receiver_id": receiver_id,
            "content": content,
            "created_at": created_at,
        }


def list_friend_direct_messages(commander_id: int, friend_id: int, limit: int = 50) -> list[dict]:
    with get_sync_session() as session:
        rows = session.execute(
            text("""
                SELECT id, sender_id, receiver_id, content, created_at
                FROM friend_direct_messages
                WHERE (sender_id = :cid AND receiver_id = :fid)
                   OR (sender_id = :fid2 AND receiver_id = :cid2)
                ORDER BY created_at DESC
                LIMIT :lim
            """),
            {"cid": commander_id, "fid": friend_id, "fid2": friend_id, "cid2": commander_id, "lim": limit},
        ).fetchall()
        result = []
        for r in rows:
            result.append({
                "id": r[0],
                "sender_id": r[1],
                "receiver_id": r[2],
                "content": r[3],
                "created_at": r[4],
            })
        return result


def get_friend_direct_message_by_id(msg_id: int) -> Optional[dict]:
    with get_sync_session() as session:
        row = session.execute(
            select(FriendDirectMessage).where(FriendDirectMessage.id == msg_id)
        ).scalar_one_or_none()
        if row is None:
            return None
        return {
            "id": row.id,
            "sender_id": row.sender_id,
            "receiver_id": row.receiver_id,
            "content": row.content,
            "created_at": row.created_at,
        }


def create_player_inform(reporter_id: int, target_id: int, info: str, content: str, created_at: int) -> Optional[dict]:
    with get_sync_session() as session:
        row = session.execute(
            text("""
                INSERT INTO player_informs (reporter_id, target_id, info, content, created_at)
                VALUES (:rid, :tid, :info, :content, :ca)
                RETURNING id
            """),
            {"rid": reporter_id, "tid": target_id, "info": info, "content": content, "ca": created_at},
        ).fetchone()
        session.commit()
        if row is None:
            return None
        return {
            "id": row[0],
            "reporter_id": reporter_id,
            "target_id": target_id,
            "info": info,
            "content": content,
            "created_at": created_at,
        }


def list_player_informs(limit: int = 50, offset: int = 0) -> list[dict]:
    with get_sync_session() as session:
        rows = session.execute(
            text("""
                SELECT id, reporter_id, target_id, info, content, created_at
                FROM player_informs
                ORDER BY created_at DESC
                LIMIT :lim OFFSET :off
            """),
            {"lim": limit, "off": offset},
        ).fetchall()
        result = []
        for r in rows:
            result.append({
                "id": r[0],
                "reporter_id": r[1],
                "target_id": r[2],
                "info": r[3],
                "content": r[4],
                "created_at": r[5],
            })
        return result


def load_commander_social_display(commander_id: int) -> Optional[dict]:
    with get_sync_session() as session:
        row = session.execute(
            text("""
                SELECT commander_id, name, level,
                    display_icon_id, display_skin_id,
                    selected_icon_frame_id, selected_chat_frame_id,
                    display_icon_theme_id
                FROM commanders
                WHERE commander_id = :cid AND deleted_at IS NULL
            """),
            {"cid": commander_id},
        ).fetchone()
        if row is None:
            return None
        return {
            "commander_id": row[0],
            "name": row[1],
            "level": row[2],
            "display_icon_id": row[3],
            "display_skin_id": row[4],
            "selected_icon_frame_id": row[5],
            "selected_chat_frame_id": row[6],
            "display_icon_theme_id": row[7],
        }


normalize_friend_pair_sync = normalize_friend_pair
create_friend_relationship_sync = create_friend_relationship
delete_friend_relationship_sync = delete_friend_relationship
is_friend_sync = is_friend
list_friends_sync = list_friends
count_common_friends_sync = count_common_friends
list_common_friend_page_sync = list_common_friend_page
create_friend_direct_message_sync = create_friend_direct_message
list_friend_direct_messages_sync = list_friend_direct_messages
get_friend_direct_message_by_id_sync = get_friend_direct_message_by_id
create_player_inform_sync = create_player_inform
list_player_informs_sync = list_player_informs
load_commander_social_display_sync = load_commander_social_display
