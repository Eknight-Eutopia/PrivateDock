from __future__ import annotations

from typing import Optional

from sqlalchemy import BigInteger, select

from src.db.session import Base, get_sync_session
from sqlalchemy import JSON
from sqlalchemy.orm import Mapped, mapped_column


def get_or_create_activity_permanent_state(commander_id: int):
    with get_sync_session() as session:
        result = session.execute(
            select(ActivityPermanentState).where(
                ActivityPermanentState.commander_id == commander_id,
            )
        )
        state = result.scalar_one_or_none()
        if state is None:
            state = ActivityPermanentState(commander_id=commander_id)
            session.add(state)
            session.commit()
            session.refresh(state)
        return state


def save_activity_permanent_state(state):
    with get_sync_session() as session:
        session.add(state)
        session.commit()


def save_activity_permanent_state_data(commander_id: int, data: dict):
    with get_sync_session() as session:
        result = session.execute(
            select(ActivityPermanentState).where(
                ActivityPermanentState.commander_id == commander_id,
            )
        )
        state = result.scalar_one_or_none()
        if state is not None:
            state.current_activity_id = data.get("current_activity_id", 0)
            state.finished_activity_ids = data.get("finished_activity_ids")
            session.commit()


class ActivityPermanentState(Base):
    __tablename__ = 'activity_permanent_states'
    commander_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    current_activity_id: Mapped[int] = mapped_column(BigInteger, default=0)
    finished_activity_ids: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
