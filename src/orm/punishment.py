from __future__ import annotations
from datetime import datetime
from typing import Any, Optional

from sqlalchemy import text
from sqlalchemy import BigInteger, Boolean, DateTime
from sqlalchemy.orm import Mapped, mapped_column

from src.db.session import Base, get_session


# ── Async ORM query functions (for api/handlers) ──


async def get_punishment_for_commander(commander_id: int) -> Optional[dict[str, Any]]:
    async with get_session() as session:
        result = await session.execute(
            text("SELECT id, punished_id, lift_timestamp, is_permanent FROM punishments WHERE punished_id = :pid"),
            {"pid": commander_id},
        )
        row = result.mappings().first()
        return dict(row) if row else None


async def list_punishments_for_commander(commander_id: int) -> list[dict[str, Any]]:
    async with get_session() as session:
        result = await session.execute(
            text("SELECT id, punished_id, lift_timestamp, is_permanent FROM punishments WHERE punished_id = :pid ORDER BY id"),
            {"pid": commander_id},
        )
        return [dict(r) for r in result.mappings().all()]


async def insert_punishment(punished_id: int, lift_timestamp: Optional[str], is_permanent: bool) -> None:
    async with get_session() as session:
        await session.execute(
            text("INSERT INTO punishments (punished_id, lift_timestamp, is_permanent) VALUES (:pid, :lt, :perm)"),
            {"pid": punished_id, "lt": lift_timestamp, "perm": is_permanent},
        )
        await session.commit()


async def get_punishment_by_id(punishment_id: int, commander_id: int) -> Optional[dict[str, Any]]:
    async with get_session() as session:
        result = await session.execute(
            text("SELECT * FROM punishments WHERE id = :pid AND punished_id = :cid"),
            {"pid": punishment_id, "cid": commander_id},
        )
        row = result.mappings().first()
        return dict(row) if row else None


async def update_punishment_permanent(punishment_id: int, is_permanent: bool) -> None:
    async with get_session() as session:
        await session.execute(
            text("UPDATE punishments SET is_permanent = :perm WHERE id = :pid"),
            {"perm": is_permanent, "pid": punishment_id},
        )
        await session.commit()


async def clear_punishment_lift(punishment_id: int) -> None:
    async with get_session() as session:
        await session.execute(
            text("UPDATE punishments SET lift_timestamp = NULL WHERE id = :pid"),
            {"pid": punishment_id},
        )
        await session.commit()


async def update_punishment_lift(punishment_id: int, lift_timestamp: Optional[str]) -> None:
    async with get_session() as session:
        await session.execute(
            text("UPDATE punishments SET lift_timestamp = :lt WHERE id = :pid"),
            {"lt": lift_timestamp, "pid": punishment_id},
        )
        await session.commit()

class Punishment(Base):
    __tablename__ = 'punishments'
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    punished_id: Mapped[int] = mapped_column(BigInteger)
    lift_timestamp: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    is_permanent: Mapped[bool] = mapped_column(Boolean, default=False)
