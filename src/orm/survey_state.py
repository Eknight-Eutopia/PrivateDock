from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import BigInteger, DateTime, select, text
from sqlalchemy.orm import Mapped, mapped_column

from src.db.session import Base, get_sync_session


def get_survey_state(commander_id: int) -> Optional[SurveyState]:
    with get_sync_session() as session:
        result = session.execute(
            select(SurveyState).where(SurveyState.commander_id == commander_id)
        )
        return result.scalar_one_or_none()


def upsert_survey_state(commander_id: int, survey_id: int, completed_at: datetime) -> None:
    with get_sync_session() as session:
        session.execute(
            text("""
                INSERT INTO survey_states (commander_id, survey_id, completed_at, created_at, updated_at)
                VALUES (:commander_id, :survey_id, :completed_at, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                ON CONFLICT (commander_id)
                DO UPDATE SET
                    survey_id = EXCLUDED.survey_id,
                    completed_at = EXCLUDED.completed_at,
                    updated_at = CURRENT_TIMESTAMP
            """),
            {
                "commander_id": commander_id,
                "survey_id": survey_id,
                "completed_at": completed_at,
            },
        )
        session.commit()


class SurveyState(Base):
    __tablename__ = "survey_states"
    commander_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    survey_id: Mapped[int] = mapped_column(BigInteger, default=0)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), default=None)
    created_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), default=None)
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), default=None)
