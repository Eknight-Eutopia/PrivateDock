from __future__ import annotations

from src.db.session import Base

from typing import Optional, Tuple

from sqlalchemy import select

from src.db.session import get_sync_session
from sqlalchemy import select

from sqlalchemy import BigInteger, Boolean
from sqlalchemy.orm import Mapped, mapped_column

DEFAULT_SLOT_COUNT = 4
# Client does pg.commander_home[level]; levels start at 1 (level 0 has no config row
# and crashes BaseVO.getConfigTable with "attempt to index a nil value").
MIN_HOME_LEVEL = 1


def ensure_commander_home(commander_id: int) -> Tuple[dict, list]:
    with get_sync_session() as session:
        existing = session.execute(
            select(CommanderHome).where(CommanderHome.commander_id == commander_id)
        ).scalar_one_or_none()
        if existing is None:
            session.add(CommanderHome(commander_id=commander_id, level=MIN_HOME_LEVEL))
            session.flush()
            for i in range(1, DEFAULT_SLOT_COUNT + 1):
                session.add(CommanderHomeSlot(
                    commander_id=commander_id,
                    slot_id=i,
                    op_flag=0,
                    exp_time=0,
                    assigned_commander_id=0,
                    style=1,
                    cache_exp=0,
                ))
            session.commit()
            existing = session.execute(
                select(CommanderHome).where(CommanderHome.commander_id == commander_id)
            ).scalar_one_or_none()
    return _home_data(existing), _list_slots(session, commander_id)


def get_commander_home(commander_id: int) -> Tuple[Optional[dict], list]:
    with get_sync_session() as session:
        existing = session.execute(
            select(CommanderHome).where(CommanderHome.commander_id == commander_id)
        ).scalar_one_or_none()
        if existing is None:
            return None, _list_slots(session, commander_id)
        return _home_data(existing), _list_slots(session, commander_id)


def update_commander_home(commander_id: int, data: dict):
    with get_sync_session() as session:
        home = session.execute(
            select(CommanderHome).where(CommanderHome.commander_id == commander_id)
        ).scalar_one_or_none()
        if home is None:
            home = CommanderHome(commander_id=commander_id, level=MIN_HOME_LEVEL)
            session.add(home)
        for key, value in data.items():
            if hasattr(home, key):
                setattr(home, key, value)
        session.commit()


def update_commander_home_slot(commander_id: int, slot_id: int, style_id: int):
    with get_sync_session() as session:
        slot = session.execute(
            select(CommanderHomeSlot).where(
                CommanderHomeSlot.commander_id == commander_id,
                CommanderHomeSlot.slot_id == slot_id,
            )
        ).scalar_one_or_none()
        if slot is None:
            slot = CommanderHomeSlot(
                commander_id=commander_id,
                slot_id=slot_id,
                op_flag=0,
                exp_time=0,
                assigned_commander_id=0,
                style=style_id,
                cache_exp=0,
            )
            session.add(slot)
        else:
            slot.style = style_id
        session.commit()


def get_commander_home_style_list() -> list:
    return []


def get_commander_home_feed_exp(_commander_id: int) -> int:
    return 0


def clear_commander_home_cache_exp(commander_id: int):
    pass


def sync_update_home_slot(slot: dict):
    commander_id = slot.get("commander_id", 0)
    slot_id = slot.get("slot_id", 0)
    style_id = slot.get("style_id", 0)
    update_commander_home_slot(commander_id, slot_id, style_id)


def sync_update_home(data: dict):
    commander_id = data.pop("commander_id", 0)
    update_commander_home(commander_id, data)


def _home_data(home) -> dict:
    if home is None:
        return {}
    return {
        "level": max(MIN_HOME_LEVEL, home.level),
        "exp": home.exp,
        "clean": home.clean,
    }


def _list_slots(session, commander_id: int) -> list:
    rows = session.execute(
        select(CommanderHomeSlot).where(CommanderHomeSlot.commander_id == commander_id).order_by(CommanderHomeSlot.slot_id)
    ).scalars().all()
    return [
        {
            "slot_id": r.slot_id,
            "op_flag": r.op_flag,
            "exp_time": r.exp_time,
            "assigned_commander_id": r.assigned_commander_id,
            "style": r.style,
            "cache_exp": r.cache_exp,
        }
        for r in rows
    ]


class CommanderHome(Base):
    __tablename__ = 'commander_homes'
    commander_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    level: Mapped[int] = mapped_column(BigInteger, default=MIN_HOME_LEVEL)
    exp: Mapped[int] = mapped_column(BigInteger, default=0)
    clean: Mapped[int] = mapped_column(BigInteger, default=0)
    scene_open: Mapped[bool] = mapped_column(Boolean, default=False)


class CommanderHomeSlot(Base):
    __tablename__ = 'commander_home_slots'
    commander_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    slot_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    op_flag: Mapped[int] = mapped_column(BigInteger, default=0)
    exp_time: Mapped[int] = mapped_column(BigInteger, default=0)
    assigned_commander_id: Mapped[int] = mapped_column(BigInteger, default=0)
    style: Mapped[int] = mapped_column(BigInteger, default=1)
    cache_exp: Mapped[int] = mapped_column(BigInteger, default=0)
