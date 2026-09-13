from __future__ import annotations
from typing import Any

from sqlalchemy import BigInteger, String, text
from sqlalchemy.orm import Mapped, mapped_column

from src.db.session import Base, get_session


async def list_commander_flags(commander_id: int) -> list[dict[str, Any]]:
    async with get_session() as session:
        result = await session.execute(
            text("SELECT flag_id, value, updated_at FROM commander_flags WHERE commander_id = :cid"),
            {"cid": commander_id},
        )
        return [dict(r) for r in result.mappings().all()]


async def upsert_commander_flag(commander_id: int, flag_id: int, value: str, updated_at: str) -> None:
    async with get_session() as session:
        await session.execute(
            text("INSERT INTO commander_flags (commander_id, flag_id, value, updated_at) "
                 "VALUES (:cid, :fid, :val, :uat) "
                 "ON CONFLICT (commander_id, flag_id) DO UPDATE SET value = :val, updated_at = :uat"),
            {"cid": commander_id, "fid": flag_id, "val": value, "uat": updated_at},
        )
        await session.commit()


async def delete_commander_flag(commander_id: int, flag_id: int) -> None:
    async with get_session() as session:
        await session.execute(
            text("DELETE FROM commander_flags WHERE commander_id = :cid AND flag_id = :fid"),
            {"cid": commander_id, "fid": flag_id},
        )
        await session.commit()


class CommanderFlag(Base):
    __tablename__ = 'commander_flags'
    commander_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    flag_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    value: Mapped[str] = mapped_column(String, default='')
    updated_at = None
