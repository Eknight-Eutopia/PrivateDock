from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import BigInteger, DateTime, select, text
from sqlalchemy.orm import Mapped, mapped_column

from src.db.session import Base, get_sync_session
from src.region.region import local_now


class CommanderBoxDaily(Base):
    __tablename__ = 'commander_box_daily'
    commander_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    usage_count: Mapped[int] = mapped_column(BigInteger, default=0)
    reset_day: Mapped[int] = mapped_column(BigInteger, default=0)
    last_reset_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


def _ensure_table():
    with get_sync_session() as session:
        session.execute(
            text(
                "CREATE TABLE IF NOT EXISTS commander_box_daily ("
                "commander_id bigint NOT NULL PRIMARY KEY, "
                "usage_count bigint NOT NULL DEFAULT 0, "
                "reset_day bigint NOT NULL DEFAULT 0, "
                "last_reset_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP)"
            )
        )
        try:
            session.execute(
                text("ALTER TABLE commander_box_daily ADD COLUMN reset_day bigint NOT NULL DEFAULT 0")
            )
        except Exception:
            pass
        session.commit()


def _today_key() -> int:
    dt = local_now()
    return dt.year * 10000 + dt.month * 100 + dt.day


def get_commander_box_daily_usage(commander_id: int) -> int:
    _ensure_table()
    today = _today_key()
    with get_sync_session() as session:
        row = session.execute(
            select(CommanderBoxDaily).where(CommanderBoxDaily.commander_id == commander_id)
        ).scalar_one_or_none()
        if row is None:
            return 0
        if getattr(row, "reset_day", 0) != today:
            row.usage_count = 0
            row.reset_day = today
            session.commit()
            return 0
        return int(row.usage_count or 0)


def increment_commander_box_daily_usage(commander_id: int, count: int) -> int:
    _ensure_table()
    today = _today_key()
    now = local_now()
    with get_sync_session() as session:
        row = session.execute(
            select(CommanderBoxDaily).where(CommanderBoxDaily.commander_id == commander_id)
        ).scalar_one_or_none()
        if row is None:
            row = CommanderBoxDaily(
                commander_id=commander_id,
                usage_count=count,
                reset_day=today,
                last_reset_at=now,
            )
            session.add(row)
        else:
            if getattr(row, "reset_day", 0) != today:
                row.usage_count = count
            else:
                row.usage_count += count
            row.reset_day = today
            row.last_reset_at = now
        session.commit()
        return int(row.usage_count)


def reset_commander_box_daily_usage(commander_id: int) -> None:
    _ensure_table()
    today = _today_key()
    now = local_now()
    with get_sync_session() as session:
        row = session.execute(
            select(CommanderBoxDaily).where(CommanderBoxDaily.commander_id == commander_id)
        ).scalar_one_or_none()
        if row is not None:
            row.usage_count = 0
            row.reset_day = today
            row.last_reset_at = now
            session.commit()
