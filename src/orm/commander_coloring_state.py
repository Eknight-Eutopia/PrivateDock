from __future__ import annotations
from datetime import datetime
from typing import Optional

from sqlalchemy import BigInteger, DateTime, JSON, select
from sqlalchemy.orm import Mapped, mapped_column

from src.db.session import Base, get_sync_session


def get_or_create_commander_coloring_state(commander_id: int):
    with get_sync_session() as session:
        result = session.execute(
            select(CommanderColoringState).where(
                CommanderColoringState.commander_id == commander_id,
            )
        )
        state = result.scalar_one_or_none()
        if state is None:
            state = CommanderColoringState(commander_id=commander_id)
            session.add(state)
            session.commit()
            session.refresh(state)
        return state


def save_commander_coloring_state(commander_id: int, data: dict):
    with get_sync_session() as session:
        result = session.execute(
            select(CommanderColoringState).where(
                CommanderColoringState.commander_id == commander_id,
            )
        )
        obj = result.scalar_one_or_none()
        if obj is None:
            obj = CommanderColoringState(commander_id=commander_id, data=data)
            session.add(obj)
        else:
            obj.data = data
        session.commit()


class CommanderColoringState(Base):
    __tablename__ = 'commander_coloring_states'
    commander_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    activity_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    start_time: Mapped[int] = mapped_column(BigInteger, default=0)
    cells: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    awards: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
