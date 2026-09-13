"""Persistent state for the Military Exercise (PvP / Mock Battles) feature.

Mirrors the existing ``exercise_fleet`` ORM pattern: a SQLAlchemy model plus
synchronous load/upsert helpers used by the exercise answer handlers.
"""

from __future__ import annotations

import time

from sqlalchemy import BigInteger, Integer, Column
from sqlalchemy.orm import Mapped

from src.db.session import Base, get_sync_session


class ExerciseState(Base):
    __tablename__ = "exercise_states"

    commander_id: Mapped[int] = Column(BigInteger, primary_key=True)
    season_id: Mapped[int] = Column(Integer, default=1)
    season_end: Mapped[int] = Column(BigInteger, default=0)
    score: Mapped[int] = Column(Integer, default=0)
    merit: Mapped[int] = Column(Integer, default=0)
    fight_count: Mapped[int] = Column(Integer, default=10)
    next_recover_time: Mapped[int] = Column(BigInteger, default=0)
    refreshes_today: Mapped[int] = Column(Integer, default=5)
    last_refresh_day: Mapped[int] = Column(BigInteger, default=0)
    # Highest rank tier already rewarded this season (rank-up gems via mail).
    rewarded_rank: Mapped[int] = Column(Integer, default=0)
    created_at: Mapped[int] = Column(BigInteger, default=0)
    updated_at: Mapped[int] = Column(BigInteger, default=0)


def get_exercise_state_sync(commander_id: int) -> ExerciseState | None:
    with get_sync_session() as session:
        return session.get(ExerciseState, commander_id)


def upsert_exercise_state_sync(state: ExerciseState) -> None:
    state.updated_at = int(time.time())
    with get_sync_session() as session:
        existing = session.get(ExerciseState, state.commander_id)
        if existing is None:
            state.created_at = int(time.time())
            session.add(state)
        else:
            for col in (
                "season_id",
                "season_end",
                "score",
                "merit",
                "fight_count",
                "next_recover_time",
                "refreshes_today",
                "last_refresh_day",
                "rewarded_rank",
                "updated_at",
            ):
                setattr(existing, col, getattr(state, col))
        session.commit()
