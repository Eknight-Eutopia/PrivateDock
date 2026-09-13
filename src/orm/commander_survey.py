from __future__ import annotations
from datetime import datetime
from typing import Optional

from sqlalchemy import BigInteger, DateTime, select
from sqlalchemy.orm import Mapped, mapped_column

from src.db.session import Base, get_session, get_sync_session


async def list_commander_surveys(commander_id: int) -> list:
    async with get_session() as session:
        result = await session.execute(
            select(CommanderSurvey).where(
                CommanderSurvey.commander_id == commander_id,
            )
        )
        return list(result.scalars().all())


async def complete_survey(commander_id: int, survey_id: int):
    async with get_session() as session:
        session.add(
            CommanderSurvey(commander_id=commander_id, survey_id=survey_id)
        )
        await session.commit()


def _sync_list_commander_surveys(commander_id: int) -> list:
    with get_sync_session() as session:
        result = session.execute(
            select(CommanderSurvey).where(
                CommanderSurvey.commander_id == commander_id,
            )
        )
        return list(result.scalars().all())


list_commander_surveys = _sync_list_commander_surveys


class CommanderSurvey(Base):
    __tablename__ = 'commander_surveys'
    commander_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    survey_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
