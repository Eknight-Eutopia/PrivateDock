from __future__ import annotations

from sqlalchemy import select, text

from src.db.session import get_session, get_sync_session
from src.orm.friend_request import FriendRequest


async def list_commander_friend_ids(commander_id: int) -> list[int]:
    async with get_session() as session:
        result = await session.execute(
            text("""
                SELECT CASE WHEN commander_id = :cid THEN friend_id ELSE commander_id END
                FROM friend_relationships
                WHERE commander_id = :cid OR friend_id = :cid
            """),
            {"cid": commander_id},
        )
        return [row[0] for row in result.fetchall()]


async def list_incoming_friend_requests(commander_id: int) -> list:
    async with get_session() as session:
        result = await session.execute(
            text("SELECT * FROM friend_requests WHERE target_id = :cid AND status = 'pending'"),
            {"cid": commander_id},
        )
        return result.fetchall()


def _sync_list_commander_friend_ids(commander_id: int) -> list[int]:
    from src.orm.social_misc import list_friends
    return [f["friend_id"] for f in list_friends(commander_id)]


def _sync_list_incoming_friend_requests(commander_id: int) -> list[FriendRequest]:
    with get_sync_session() as session:
        rows = session.execute(
            select(FriendRequest).where(
                FriendRequest.target_id == commander_id,
                FriendRequest.status == "pending",
            )
        ).scalars().all()
        return list(rows)


list_commander_friend_ids = _sync_list_commander_friend_ids
list_incoming_friend_requests = _sync_list_incoming_friend_requests
