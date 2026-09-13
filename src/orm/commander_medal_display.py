from __future__ import annotations


from sqlalchemy import BigInteger, select
from sqlalchemy.orm import Mapped, mapped_column

from src.db.session import Base, get_session, get_sync_session


async def set_commander_medal_display(commander_id: int, medal_ids: list[int]):
    async with get_session() as session:
        old = await session.execute(
            select(CommanderMedalDisplay).where(
                CommanderMedalDisplay.commander_id == commander_id,
            )
        )
        for obj in old.scalars().all():
            await session.delete(obj)
        for i, mid in enumerate(medal_ids):
            session.add(
                CommanderMedalDisplay(
                    commander_id=commander_id, position=i, medal_id=mid,
                )
            )
        await session.commit()


async def list_commander_medal_displays(commander_id: int) -> list:
    async with get_session() as session:
        result = await session.execute(
            select(CommanderMedalDisplay).where(
                CommanderMedalDisplay.commander_id == commander_id,
            )
        )
        return list(result.scalars().all())


def _sync_set_commander_medal_display(commander_id: int, medal_ids: list[int]):
    with get_sync_session() as session:
        old = session.execute(
            select(CommanderMedalDisplay).where(
                CommanderMedalDisplay.commander_id == commander_id,
            )
        )
        for obj in old.scalars().all():
            session.delete(obj)
        for i, mid in enumerate(medal_ids):
            session.add(
                CommanderMedalDisplay(
                    commander_id=commander_id, position=i, medal_id=mid,
                )
            )
        session.commit()


def _sync_list_commander_medal_displays(commander_id: int) -> list:
    with get_sync_session() as session:
        result = session.execute(
            select(CommanderMedalDisplay).where(
                CommanderMedalDisplay.commander_id == commander_id,
            )
        )
        return list(result.scalars().all())


set_commander_medal_display = _sync_set_commander_medal_display
list_commander_medal_displays = _sync_list_commander_medal_displays


class CommanderMedalDisplay(Base):
    __tablename__ = 'commander_medal_displays'
    commander_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    position: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    medal_id: Mapped[int] = mapped_column(BigInteger, default=0)
