from __future__ import annotations
from datetime import datetime
from typing import Any, Optional

from sqlalchemy import BigInteger, Boolean, DateTime, text
from sqlalchemy.orm import Mapped, mapped_column

from src.db.session import Base, get_session


# ── Async ORM query functions (for api/handlers) ──


async def list_commander_living_area_covers_rows(commander_id: int) -> list[dict[str, Any]]:
    async with get_session() as session:
        result = await session.execute(
            text("SELECT cover_id, is_new FROM commander_living_area_covers WHERE commander_id = :cid ORDER BY cover_id"),
            {"cid": commander_id},
        )
        return [dict(r) for r in result.mappings().all()]


async def insert_living_area_cover(commander_id: int, cover_id: int) -> None:
    async with get_session() as session:
        await session.execute(
            text("INSERT INTO commander_living_area_covers (commander_id, cover_id, unlocked_at, is_new) "
                 "VALUES (:cid, :cov, NOW(), true) ON CONFLICT (commander_id, cover_id) DO NOTHING"),
            {"cid": commander_id, "cov": cover_id},
        )
        await session.commit()


async def update_commander_living_area_cover(commander_id: int, cover_id: int) -> None:
    async with get_session() as session:
        await session.execute(
            text("UPDATE commanders SET living_area_cover_id = :cov WHERE commander_id = :cid"),
            {"cov": cover_id, "cid": commander_id},
        )
        await session.commit()


async def has_living_area_cover(commander_id: int, cover_id: int) -> bool:
    async with get_session() as session:
        result = await session.execute(
            text("SELECT 1 FROM commander_living_area_covers WHERE commander_id = :cid AND cover_id = :cov"),
            {"cid": commander_id, "cov": cover_id},
        )
        return result.first() is not None


async def delete_living_area_cover_row(commander_id: int, cover_id: int) -> bool:
    async with get_session() as session:
        result = await session.execute(
            text("DELETE FROM commander_living_area_covers WHERE commander_id = :cid AND cover_id = :cov"),
            {"cid": commander_id, "cov": cover_id},
        )
        await session.commit()
        return result.rowcount > 0


async def update_living_area_cover_is_new(commander_id: int, cover_id: int, is_new: bool) -> None:
    async with get_session() as session:
        await session.execute(
            text("UPDATE commander_living_area_covers SET is_new = :new WHERE commander_id = :cid AND cover_id = :cov"),
            {"new": is_new, "cid": commander_id, "cov": cover_id},
        )
        await session.commit()


class CommanderLivingAreaCover(Base):
    __tablename__ = 'commander_living_area_covers'
    __table_args__ = {}
    commander_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    cover_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    unlocked_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    is_new: Mapped[bool] = mapped_column(Boolean, default=False)
