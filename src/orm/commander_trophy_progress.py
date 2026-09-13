from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import BigInteger, DateTime, select
from sqlalchemy.orm import Mapped, mapped_column

from src.db.session import Base, get_sync_session


def get_or_create_trophy_progress(commander_id: int, trophy_id: int):
    with get_sync_session() as session:
        result = session.execute(
            select(CommanderTrophyProgress).where(
                CommanderTrophyProgress.commander_id == commander_id,
                CommanderTrophyProgress.trophy_id == trophy_id,
            )
        )
        p = result.scalar_one_or_none()
        if p is not None:
            return p
        p = CommanderTrophyProgress(commander_id=commander_id, trophy_id=trophy_id)
        session.add(p)
        session.commit()
        return p


def list_commander_trophy_progress(commander_id: int) -> list:
    with get_sync_session() as session:
        rows = session.execute(
            select(CommanderTrophyProgress).where(CommanderTrophyProgress.commander_id == commander_id)
        ).scalars().all()
        return list(rows)


def claim_trophy_progress(commander_id: int, trophy_id: int):
    with get_sync_session() as session:
        result = session.execute(
            select(CommanderTrophyProgress).where(
                CommanderTrophyProgress.commander_id == commander_id,
                CommanderTrophyProgress.trophy_id == trophy_id,
            )
        )
        p = result.scalar_one_or_none()
        if p is not None:
            p.timestamp = 1
            session.commit()


class CommanderTrophyProgress(Base):
    __tablename__ = 'commander_trophy_progresses'
    commander_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    trophy_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    progress: Mapped[int] = mapped_column(BigInteger, default=0)
    timestamp: Mapped[int] = mapped_column(BigInteger, default=0)
    created_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
