from __future__ import annotations

import datetime
from typing import Optional

from sqlalchemy import BigInteger, select
from sqlalchemy.orm import Mapped, mapped_column

from src.db.session import Base, get_session, get_sync_session
from src.db.store import NotFoundError


def _utc_day_key(ts: int) -> int:
    dt = datetime.datetime.fromtimestamp(ts, tz=datetime.timezone.utc)
    return dt.year * 10000 + dt.month * 100 + dt.day


def get_commander_daily_quick_finish_used_sync(commander_id: int, now_unix: int) -> int:
    with get_sync_session() as session:
        obj = session.execute(
            select(CommanderTacticsQuickFinish).where(
                CommanderTacticsQuickFinish.commander_id == commander_id
            )
        ).scalar_one_or_none()
        if obj is None:
            return 0
        today = _utc_day_key(now_unix)
        if obj.reset_day != today:
            return 0
        return int(obj.used_count)


async def aget_commander_daily_quick_finish_used(commander_id: int, now_unix: int) -> int:
    async with get_session() as session:
        result = await session.execute(
            select(CommanderTacticsQuickFinish).where(
                CommanderTacticsQuickFinish.commander_id == commander_id
            )
        )
        obj = result.scalar_one_or_none()
        if obj is None:
            return 0
        today = _utc_day_key(now_unix)
        if obj.reset_day != today:
            return 0
        return int(obj.used_count)


async def aconsume_commander_quick_finish(
    commander_id: int, allowance: int, now_unix: int
) -> Optional[Exception]:
    today = _utc_day_key(now_unix)
    async with get_session() as session:
        result = await session.execute(
            select(CommanderTacticsQuickFinish).where(
                CommanderTacticsQuickFinish.commander_id == commander_id
            )
        )
        obj = result.scalar_one_or_none()
        if obj is None:
            obj = CommanderTacticsQuickFinish(
                commander_id=commander_id,
                used_count=0,
                reset_day=today,
            )
            session.add(obj)
            await session.flush()

        used_count = obj.used_count
        if obj.reset_day != today:
            used_count = 0
            obj.reset_day = today

        if used_count >= allowance:
            return NotFoundError("no quick finish allowance")

        obj.used_count = used_count + 1
        await session.commit()
        return None


get_commander_daily_quick_finish_used = get_commander_daily_quick_finish_used_sync
consume_commander_quick_finish = aconsume_commander_quick_finish


class CommanderTacticsQuickFinish(Base):
    __tablename__ = "commander_tactics_quick_finishes"
    commander_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    used_count: Mapped[int] = mapped_column(BigInteger, default=0)
    reset_day: Mapped[int] = mapped_column(BigInteger, default=0)
