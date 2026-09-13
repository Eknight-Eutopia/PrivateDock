from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import BigInteger, DateTime, select, func
from sqlalchemy.orm import Mapped, mapped_column

from src.db.session import Base, get_session, get_sync_session


async def get_or_create_active_event(commander_id: int, event_id: int):
    async with get_session() as session:
        result = await session.execute(
            select(ActiveEvent).where(
                ActiveEvent.commander_id == commander_id,
                ActiveEvent.event_id == event_id,
            )
        )
        event = result.scalar_one_or_none()
        if event is None:
            event = ActiveEvent(commander_id=commander_id, event_id=event_id)
            session.add(event)
            await session.commit()
        return event


async def get_active_event_count(commander_id: int) -> int:
    async with get_session() as session:
        result = await session.execute(
            select(func.count()).select_from(ActiveEvent).where(
                ActiveEvent.commander_id == commander_id
            )
        )
        return result.scalar() or 0


async def get_busy_event_ship_ids(commander_id: int) -> list[int]:
    async with get_session() as session:
        result = await session.execute(
            select(ActiveEvent.event_id).where(ActiveEvent.commander_id == commander_id)
        )
        return [row[0] for row in result.fetchall()]


def get_or_create_active_event_sync(commander_id: int, event_id: int):
    with get_sync_session() as session:
        result = session.execute(
            select(ActiveEvent).where(
                ActiveEvent.commander_id == commander_id,
                ActiveEvent.event_id == event_id,
            )
        )
        event = result.scalar_one_or_none()
        if event is None:
            event = ActiveEvent(commander_id=commander_id, event_id=event_id)
            session.add(event)
            session.commit()
        return event


def get_active_event_count_sync(commander_id: int) -> int:
    with get_sync_session() as session:
        result = session.execute(
            select(func.count()).select_from(ActiveEvent).where(
                ActiveEvent.commander_id == commander_id
            )
        )
        return result.scalar() or 0


def get_busy_event_ship_ids_sync(commander_id: int) -> list[int]:
    with get_sync_session() as session:
        result = session.execute(
            select(ActiveEvent.event_id).where(ActiveEvent.commander_id == commander_id)
        )
        return [row[0] for row in result.fetchall()]


class ActiveEvent(Base):
    __tablename__ = 'active_events'
    commander_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    event_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    ship_id: Mapped[int] = mapped_column(BigInteger, default=0)
    created_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
