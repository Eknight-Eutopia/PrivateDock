from __future__ import annotations

from sqlalchemy import select

from src.db.session import get_sync_session
from src.orm.guild_chat_message import GuildChatMessage


def list_guild_chat_messages(guild_id: int, limit: int = 50) -> list:
    with get_sync_session() as session:
        result = session.execute(
            select(GuildChatMessage)
            .where(GuildChatMessage.guild_id == guild_id)
            .order_by(GuildChatMessage.id.desc())
            .limit(limit)
        )
        return list(result.scalars().all())
