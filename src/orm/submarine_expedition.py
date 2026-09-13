from __future__ import annotations

from typing import Optional

from sqlalchemy import BigInteger, select, text
from sqlalchemy.orm import Mapped, mapped_column

from src.db.session import Base, get_sync_session


def get_submarine_state(commander_id: int) -> Optional[SubmarineExpeditionState]:
    with get_sync_session() as session:
        result = session.execute(
            select(SubmarineExpeditionState).where(SubmarineExpeditionState.commander_id == commander_id)
        )
        return result.scalar_one_or_none()


def upsert_submarine_state(state: SubmarineExpeditionState) -> None:
    with get_sync_session() as session:
        session.execute(
            text("""
                INSERT INTO submarine_expedition_states (commander_id, last_refresh_time, weekly_refresh_count, active_chapter_id, overall_progress)
                VALUES (:commander_id, :last_refresh_time, :weekly_refresh_count, :active_chapter_id, :overall_progress)
                ON CONFLICT (commander_id)
                DO UPDATE SET
                    last_refresh_time = EXCLUDED.last_refresh_time,
                    weekly_refresh_count = EXCLUDED.weekly_refresh_count,
                    active_chapter_id = EXCLUDED.active_chapter_id,
                    overall_progress = EXCLUDED.overall_progress
            """),
            {
                "commander_id": state.commander_id,
                "last_refresh_time": state.last_refresh_time,
                "weekly_refresh_count": state.weekly_refresh_count,
                "active_chapter_id": state.active_chapter_id,
                "overall_progress": state.overall_progress,
            },
        )
        session.commit()


def reset_weekly_refresh(commander_id: int, refresh_at: int) -> None:
    with get_sync_session() as session:
        session.execute(
            text("""
                UPDATE submarine_expedition_states
                SET weekly_refresh_count = 0, last_refresh_time = :refresh_at
                WHERE commander_id = :commander_id
            """),
            {"commander_id": commander_id, "refresh_at": refresh_at},
        )
        session.commit()


class SubmarineExpeditionState(Base):
    __tablename__ = "submarine_expedition_states"
    commander_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    last_refresh_time: Mapped[int] = mapped_column(BigInteger, default=0)
    weekly_refresh_count: Mapped[int] = mapped_column(BigInteger, default=0)
    active_chapter_id: Mapped[int] = mapped_column(BigInteger, default=0)
    overall_progress: Mapped[int] = mapped_column(BigInteger, default=0)
