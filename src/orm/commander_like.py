from __future__ import annotations
from typing import Any

from sqlalchemy import BigInteger, text
from sqlalchemy.orm import Mapped, mapped_column

from src.db.session import Base, get_session


async def list_commander_likes(commander_id: int) -> list[dict[str, Any]]:
    async with get_session() as session:
        result = await session.execute(
            text("SELECT group_id, like_id, timestamp FROM commander_likes WHERE commander_id = :cid"),
            {"cid": commander_id},
        )
        return [dict(r) for r in result.mappings().all()]


async def upsert_commander_like(commander_id: int, group_id: int, like_id: int, timestamp: int) -> None:
    async with get_session() as session:
        await session.execute(
            text("INSERT INTO commander_likes (commander_id, group_id, like_id, timestamp) "
                 "VALUES (:cid, :gid, :lid, :ts) "
                 "ON CONFLICT (commander_id, group_id, like_id) DO UPDATE SET timestamp = :ts"),
            {"cid": commander_id, "gid": group_id, "lid": like_id, "ts": timestamp},
        )
        await session.commit()


async def delete_commander_like(commander_id: int, group_id: int) -> None:
    async with get_session() as session:
        await session.execute(
            text("DELETE FROM commander_likes WHERE commander_id = :cid AND group_id = :gid"),
            {"cid": commander_id, "gid": group_id},
        )
        await session.commit()


class CommanderLike(Base):
    __tablename__ = 'commander_likes'
    commander_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    group_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    like_id: Mapped[int] = mapped_column(BigInteger, default=0)
    timestamp: Mapped[int] = mapped_column(BigInteger, default=0)
