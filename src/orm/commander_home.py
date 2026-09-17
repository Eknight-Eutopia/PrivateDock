from __future__ import annotations

from src.db.session import Base

from typing import Optional, Tuple

from sqlalchemy import select

from src.db.session import get_sync_session
from sqlalchemy import select

from sqlalchemy import BigInteger, Boolean
from sqlalchemy.orm import Mapped, mapped_column

DEFAULT_SLOT_COUNT = 4
MAX_HOME_SLOT_COUNT = 8
# Client does pg.commander_home[level]; levels start at 1 (level 0 has no config row
# and crashes BaseVO.getConfigTable with "attempt to index a nil value").
MIN_HOME_LEVEL = 1
MAX_HOME_LEVEL = 15


def ensure_commander_home(commander_id: int) -> Tuple[dict, list]:
    from src.orm.config_entry import fetch_config_entry_data

    with get_sync_session() as session:
        existing = session.execute(
            select(CommanderHome).where(CommanderHome.commander_id == commander_id)
        ).scalar_one_or_none()
        if existing is None:
            existing = CommanderHome(
                commander_id=commander_id,
                level=MIN_HOME_LEVEL,
                exp=0,
                clean=0,
                scene_open=False,
            )
            session.add(existing)
            session.flush()

        cur_level = max(MIN_HOME_LEVEL, existing.level)
        cfg = fetch_config_entry_data("ShareCfg/commander_home.json", str(cur_level))
        nest_number = cfg.get("nest_number", 1) if isinstance(cfg, dict) else 1
        target_slots = max(DEFAULT_SLOT_COUNT, min(MAX_HOME_SLOT_COUNT, int(nest_number)))

        existing_slots = session.execute(
            select(CommanderHomeSlot).where(CommanderHomeSlot.commander_id == commander_id)
        ).scalars().all()
        existing_slot_ids = {s.slot_id for s in existing_slots}

        for i in range(1, target_slots + 1):
            if i not in existing_slot_ids:
                session.add(CommanderHomeSlot(
                    commander_id=commander_id,
                    slot_id=i,
                    op_flag=7,
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


def update_commander_home(commander_id_or_data, data: Optional[dict] = None):
    if data is None and isinstance(commander_id_or_data, dict):
        data = dict(commander_id_or_data)
        commander_id = data.pop("commander_id", None)
    elif isinstance(commander_id_or_data, int):
        commander_id = commander_id_or_data
        data = dict(data or {})
    else:
        commander_id = getattr(commander_id_or_data, "commander_id", None)
        if data is None:
            data = {
                k: getattr(commander_id_or_data, k)
                for k in ("level", "exp", "clean", "scene_open")
                if hasattr(commander_id_or_data, k)
            }
        else:
            data = dict(data)

    if not commander_id:
        return

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


def update_commander_home_slot(slot_or_commander_id, slot_id: Optional[int] = None, style_id: Optional[int] = None):
    if isinstance(slot_or_commander_id, dict):
        slot_data = slot_or_commander_id
        commander_id = slot_data.get("commander_id")
        slot_id = slot_data.get("slot_id")
        fields = {
            k: v for k, v in slot_data.items()
            if k in ("op_flag", "exp_time", "assigned_commander_id", "style", "cache_exp")
        }
    elif isinstance(slot_or_commander_id, int):
        commander_id = slot_or_commander_id
        fields = {}
        if style_id is not None:
            fields["style"] = style_id
    else:
        commander_id = getattr(slot_or_commander_id, "commander_id", None)
        slot_id = getattr(slot_or_commander_id, "slot_id", None)
        fields = {
            k: getattr(slot_or_commander_id, k)
            for k in ("op_flag", "exp_time", "assigned_commander_id", "style", "cache_exp")
            if hasattr(slot_or_commander_id, k)
        }

    if not commander_id or not slot_id:
        return

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
                op_flag=fields.get("op_flag", 7),
                exp_time=fields.get("exp_time", 0),
                assigned_commander_id=fields.get("assigned_commander_id", 0),
                style=fields.get("style", 1),
                cache_exp=fields.get("cache_exp", 0),
            )
            session.add(slot)
        else:
            for k, v in fields.items():
                setattr(slot, k, v)
        session.commit()


def get_commander_home_style_list(level: int = 1) -> list:
    from src.orm.config_entry import fetch_config_entry_data
    entry = fetch_config_entry_data("ShareCfg/commander_home.json", str(level))
    if entry and isinstance(entry, dict):
        styles = entry.get("nest_appearance", [])
        if styles:
            return [int(s) for s in styles]
    return [1]


def get_commander_home_clean_exp(level: int = 1) -> int:
    from src.orm.config_entry import fetch_config_entry_data
    entry = fetch_config_entry_data("ShareCfg/commander_home.json", str(level))
    if entry and isinstance(entry, dict):
        return int(entry.get("clean_exp", 30))
    return 30


def get_commander_home_feed_exp(level: int = 1) -> int:
    from src.orm.config_entry import fetch_config_entry_data
    entry = fetch_config_entry_data("ShareCfg/commander_home.json", str(level))
    if entry and isinstance(entry, dict):
        feed_level = entry.get("feed_level", [])
        if len(feed_level) >= 2:
            return int(feed_level[1])
    return 250


def get_commander_home_feed_home_exp(level: int = 1) -> int:
    from src.orm.config_entry import fetch_config_entry_data
    entry = fetch_config_entry_data("ShareCfg/commander_home.json", str(level))
    if entry and isinstance(entry, dict):
        feed_level = entry.get("feed_level", [])
        if len(feed_level) >= 3:
            return int(feed_level[2])
    return 10


def get_commander_home_play_home_exp(level: int = 1) -> int:
    from src.orm.config_entry import fetch_config_entry_data
    entry = fetch_config_entry_data("ShareCfg/commander_home.json", str(level))
    if entry and isinstance(entry, dict):
        teast_level = entry.get("teast_level", [])
        if len(teast_level) >= 3:
            return int(teast_level[2])
    return 20


def add_commander_home_exp(commander_id: int, exp_gain: int) -> tuple[int, int]:
    from src.orm.config_entry import fetch_config_entry_data

    with get_sync_session() as session:
        home = session.execute(
            select(CommanderHome).where(CommanderHome.commander_id == commander_id)
        ).scalar_one_or_none()
        if home is None:
            home = CommanderHome(
                commander_id=commander_id,
                level=MIN_HOME_LEVEL,
                exp=0,
                clean=0,
                scene_open=False,
            )
            session.add(home)
            session.flush()

        if exp_gain <= 0:
            return max(MIN_HOME_LEVEL, home.level), home.exp

        cur_level = max(MIN_HOME_LEVEL, home.level)
        cur_exp = home.exp + exp_gain

        while cur_level < MAX_HOME_LEVEL:
            cfg = fetch_config_entry_data("ShareCfg/commander_home.json", str(cur_level))
            need_exp = cfg.get("home_exp", 0) if isinstance(cfg, dict) else 0
            if need_exp <= 0:
                break
            if cur_exp >= need_exp:
                cur_exp -= need_exp
                cur_level += 1
            else:
                break

        if cur_level >= MAX_HOME_LEVEL:
            cur_level = MAX_HOME_LEVEL
            cur_exp = 0

        home.level = cur_level
        home.exp = cur_exp

        # Ensure slots are unlocked up to the new nest_number
        cfg = fetch_config_entry_data("ShareCfg/commander_home.json", str(cur_level))
        nest_number = cfg.get("nest_number", 1) if isinstance(cfg, dict) else 1
        target_slots = max(DEFAULT_SLOT_COUNT, min(MAX_HOME_SLOT_COUNT, int(nest_number)))

        existing_slots = session.execute(
            select(CommanderHomeSlot).where(CommanderHomeSlot.commander_id == commander_id)
        ).scalars().all()
        existing_slot_ids = {s.slot_id for s in existing_slots}

        for i in range(1, target_slots + 1):
            if i not in existing_slot_ids:
                session.add(CommanderHomeSlot(
                    commander_id=commander_id,
                    slot_id=i,
                    op_flag=7,
                    exp_time=0,
                    assigned_commander_id=0,
                    style=1,
                    cache_exp=0,
                ))

        session.commit()
        return cur_level, cur_exp


def clear_commander_home_cache_exp(commander_id: int):
    with get_sync_session() as session:
        slots = session.execute(
            select(CommanderHomeSlot).where(CommanderHomeSlot.commander_id == commander_id)
        ).scalars().all()
        for slot in slots:
            slot.cache_exp = 0
        session.commit()


def sync_update_home_slot(slot: dict):
    update_commander_home_slot(slot)


def sync_update_home(data: dict):
    update_commander_home(data)


def _home_data(home) -> dict:
    if home is None:
        return {}
    return {
        "commander_id": home.commander_id,
        "level": max(MIN_HOME_LEVEL, home.level),
        "exp": home.exp,
        "clean": home.clean,
        "scene_open": bool(home.scene_open),
    }


def _list_slots(session, commander_id: int) -> list:
    from src.shopreset.framework import current_daily_reset_unix

    reset_ts = current_daily_reset_unix()
    rows = session.execute(
        select(CommanderHomeSlot).where(CommanderHomeSlot.commander_id == commander_id).order_by(CommanderHomeSlot.slot_id)
    ).scalars().all()

    dirty = False
    for r in rows:
        if r.exp_time < reset_ts and r.op_flag != 7:
            r.op_flag = 7
            dirty = True
    if dirty:
        session.commit()

    return [
        {
            "commander_id": r.commander_id,
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
