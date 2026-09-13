from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from sqlalchemy import BigInteger, DateTime, text
from sqlalchemy.orm import Mapped, mapped_column

from src.db.session import Base, get_session

# ── ORM query functions ──


async def get_remaster_state(commander_id: int) -> Optional[dict[str, Any]]:
    async with get_session() as session:
        result = await session.execute(
            text("SELECT ticket_count, daily_count, last_daily_reset_at FROM remaster_states WHERE commander_id = :cid"),
            {"cid": commander_id},
        )
        row = result.mappings().first()
        if row is None:
            return None
        return dict(row)


async def ensure_remaster_state(commander_id: int) -> dict[str, Any]:
    row = await get_remaster_state(commander_id)
    if row is not None:
        return row
    async with get_session() as session:
        await session.execute(
            text("INSERT INTO remaster_states (commander_id, ticket_count, daily_count, last_daily_reset_at) VALUES (:cid, 0, 0, CURRENT_TIMESTAMP)"),
            {"cid": commander_id},
        )
        await session.commit()
    return {"ticket_count": 0, "daily_count": 0, "last_daily_reset_at": None}


async def update_remaster_state_dynamic(commander_id: int, **fields) -> None:
    if not fields:
        return
    set_clause = ", ".join(f"{k} = :{k}" for k in fields)
    params = {"cid": commander_id}
    params.update(fields)
    async with get_session() as session:
        await session.execute(
            text(f"UPDATE remaster_states SET {set_clause} WHERE commander_id = :cid"),
            params,
        )
        await session.commit()


# ── SQLAlchemy model ──

class RemasterState(Base):
    __tablename__ = 'remaster_states'
    commander_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    ticket_count: Mapped[int] = mapped_column(BigInteger, default=0)
    active_chapter_id: Mapped[int] = mapped_column(BigInteger, default=0)
    daily_count: Mapped[int] = mapped_column(BigInteger, default=0)
    last_daily_reset_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
