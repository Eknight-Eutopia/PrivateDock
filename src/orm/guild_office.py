from __future__ import annotations

from sqlalchemy import select

from src.db.session import get_sync_session
from src.orm.guild_core import Guild


def get_guild_office_state(guild_id: int) -> dict:
    with get_sync_session() as session:
        result = session.execute(
            select(Guild.office_state).where(Guild.id == guild_id)
        )
        return result.scalar_one_or_none() or {}


def get_guild_weekly_task_state(guild_id: int) -> dict:
    with get_sync_session() as session:
        result = session.execute(
            select(Guild.weekly_task_state).where(Guild.id == guild_id)
        )
        return result.scalar_one_or_none() or {}
