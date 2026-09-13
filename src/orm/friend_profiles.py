from __future__ import annotations

from sqlalchemy import text

from src.db.session import get_session, get_sync_session


async def get_commander_social_profiles_by_ids(commander_ids: list[int]):
    async with get_session() as session:
        result = await session.execute(
            text("""
                SELECT commander_id, name, level, last_login, display_skin_id, display_icon_id
                FROM commanders
                WHERE commander_id = ANY(:ids) AND deleted_at IS NULL
            """),
            {"ids": commander_ids},
        )
        profiles = {}
        for row in result.fetchall():
            profiles[row[0]] = row
        return profiles


async def list_friend_profiles(commander_id: int):
    async with get_session() as session:
        result = await session.execute(
            text("""
                SELECT c.commander_id, c.name, c.level, c.last_login,
                       c.display_skin_id, c.display_icon_id
                FROM commanders c
                JOIN friend_relationships f ON (f.commander_id = :cid AND f.friend_id = c.commander_id)
                                           OR (f.friend_id = :cid AND f.commander_id = c.commander_id)
                WHERE c.deleted_at IS NULL
            """),
            {"cid": commander_id},
        )
        return result.fetchall()


def sync_get_commander_social_profiles_by_ids(commander_ids: list[int]) -> dict:
    with get_sync_session() as session:
        result = session.execute(
            text("""
                SELECT commander_id, name, level, last_login, display_skin_id, display_icon_id
                FROM commanders
                WHERE commander_id = ANY(:ids) AND deleted_at IS NULL
            """),
            {"ids": commander_ids},
        )
        profiles = {}
        for row in result.fetchall():
            profiles[row[0]] = row
        return profiles


def sync_list_friend_profiles(commander_id: int) -> list:
    with get_sync_session() as session:
        result = session.execute(
            text("""
                SELECT c.commander_id, c.name, c.level, c.last_login,
                       c.display_skin_id, c.display_icon_id
                FROM commanders c
                JOIN friend_relationships f ON (f.commander_id = :cid AND f.friend_id = c.commander_id)
                                           OR (f.friend_id = :cid AND f.commander_id = c.commander_id)
                WHERE c.deleted_at IS NULL
            """),
            {"cid": commander_id},
        )
        return result.fetchall()
