from __future__ import annotations
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from sqlalchemy import BigInteger, Boolean, DateTime, select, text
from sqlalchemy.orm import Mapped, mapped_column

from src.consts.attire import (
    ATTIRE_TYPE_CHAT_FRAME,
    ATTIRE_TYPE_COMBAT_UI,
    ATTIRE_TYPE_ICON_FRAME,
)
from src.db.session import Base, get_session, get_sync_session
from src.orm.commander_living_area_cover import CommanderLivingAreaCover


# ── Attire grants (drop types 14/15/31 → commander_attires rows) ──

# client const.lua DROP_TYPE_ICON_FRAME/CHAT_FRAME/COMBAT_UI_STYLE → attire type
ATTIRE_DROP_TYPE_TO_ATTIRE_TYPE = {
    14: ATTIRE_TYPE_ICON_FRAME,
    15: ATTIRE_TYPE_CHAT_FRAME,
    31: ATTIRE_TYPE_COMBAT_UI,
}

# config_entries mirror of the client's pg.item_data_* tables
_ATTIRE_CONFIG_CATEGORY = {
    ATTIRE_TYPE_ICON_FRAME: "ShareCfg/item_data_frame.json",
    ATTIRE_TYPE_CHAT_FRAME: "ShareCfg/item_data_chat.json",
    ATTIRE_TYPE_COMBAT_UI: "ShareCfg/item_data_battleui.json",
}

_DEFAULT_FRAME_ID = 0  # client pre-creates IconFrame/ChatFrame 0 as owned


def combat_ui_style_is_free(attire_id: int) -> bool:
    """True when the combat UI style is free for everyone (client
    CombatUIStyle.isOwned treats item_data_battleui.is_unlock == 0 as owned)."""
    return attire_id in free_combat_ui_style_ids()


def free_combat_ui_style_ids() -> list[int]:
    """Combat UI style ids granted to every player (item_data_battleui
    is_unlock == 0), read once per process from the config mirror."""
    from src.orm.config_entry import list_config_entries_sync
    return _free_combat_ui_style_ids_cached(list_config_entries_sync(_ATTIRE_CONFIG_CATEGORY[ATTIRE_TYPE_COMBAT_UI]))


def _free_combat_ui_style_ids_cached(entries: list) -> list[int]:
    ids = []
    for entry in entries or []:
        data = entry.data if hasattr(entry, "data") else entry
        if isinstance(data, dict) and int(data.get("is_unlock") or 0) == 0:
            ids.append(int(data.get("id") or 0))
    return sorted(set(ids))


def default_attire_entries() -> list[tuple[int, int]]:
    """(attire_type, attire_id) rows every commander owns from the start:
    the default portrait/chat frames plus all free combat UI styles."""
    entries = [(ATTIRE_TYPE_ICON_FRAME, _DEFAULT_FRAME_ID), (ATTIRE_TYPE_CHAT_FRAME, _DEFAULT_FRAME_ID)]
    entries += [(ATTIRE_TYPE_COMBAT_UI, aid) for aid in free_combat_ui_style_ids()]
    return entries


def _resolve_attire_expiry(attire_type: int, attire_id: int, count: int) -> Optional[datetime]:
    """Expiry for a granted attire: time-limited configs (time_limit_type==1)
    burn ``time_second * count`` from now; everything else is permanent."""
    from src.logger.logger import log_event, LOG_LEVEL_WARN
    from src.orm.config_entry import fetch_config_entry_data

    try:
        cfg = fetch_config_entry_data(_ATTIRE_CONFIG_CATEGORY[attire_type], str(attire_id))
    except Exception as e:
        cfg = None
        log_event("Attire", "ConfigRead", f"attire config {attire_type}/{attire_id} unreadable: {e}", LOG_LEVEL_WARN)
    if not isinstance(cfg, dict):
        return None
    if int(cfg.get("time_limit_type") or 0) != 1:
        return None
    seconds = int(cfg.get("time_second") or 0) * max(int(count), 1)
    if seconds <= 0:
        return None
    return datetime.now(timezone.utc) + timedelta(seconds=seconds)


def grant_commander_attire_drop_sync(commander_id: int, drop_type: int, attire_id: int, count: int = 1) -> bool:
    """Grant an attire from a DROPINFO entry (drop types 14/15/31).

    Returns True when ``drop_type`` is an attire drop type (regardless of the
    outcome), so dispatchers can route the drop away from the item bag. The
    client unlocks the style locally from the same DROPINFO; this only makes
    the ownership persist across re-logins (SC_11003 lists).
    """
    attire_type = ATTIRE_DROP_TYPE_TO_ATTIRE_TYPE.get(int(drop_type))
    if attire_type is None:
        return False
    attire_id = int(attire_id or 0)
    if attire_id == 0:
        return True
    return upsert_commander_attire_sync(commander_id, attire_type, attire_id,
                                        expires_at=_resolve_attire_expiry(attire_type, attire_id, count))


def upsert_commander_attire_sync(commander_id: int, attire_type: int, attire_id: int,
                                 expires_at: Optional[datetime]) -> bool:
    """Insert or refresh one attire row. Permanent grants (expires_at=None)
    never shorten a timed row; a timed re-grant extends a still-live timed row
    the same way the official client merges in AttireProxy.addAttireFrame."""
    now = datetime.now(timezone.utc)
    with get_sync_session() as session:
        row = session.execute(
            text("SELECT expires_at FROM commander_attires "
                 "WHERE commander_id = :cid AND type = :t AND attire_id = :aid"),
            {"cid": commander_id, "t": attire_type, "aid": attire_id},
        ).first()
        new_expires = expires_at
        if row is not None and row[0] is not None:
            existing = row[0]
            if existing.tzinfo is None:
                existing = existing.replace(tzinfo=timezone.utc)
            if expires_at is None:
                new_expires = existing
            elif existing > now:
                new_expires = existing + (expires_at - now)
        session.execute(
            text("INSERT INTO commander_attires (commander_id, type, attire_id, expires_at, is_new) "
                 "VALUES (:cid, :t, :aid, :exp, false) "
                 "ON CONFLICT (commander_id, type, attire_id) "
                 "DO UPDATE SET expires_at = :exp"),
            {"cid": commander_id, "t": attire_type, "aid": attire_id, "exp": new_expires},
        )
        session.commit()
    return True


_INSERT_DEFAULT_ATTIRE = ("INSERT INTO commander_attires (commander_id, type, attire_id) "
                          "VALUES (:cid, :t, :aid) ON CONFLICT DO NOTHING")


async def grant_default_attires(commander_id: int) -> None:
    """Give a freshly created commander the always-available attires."""
    async with get_session() as session:
        for attire_type, attire_id in default_attire_entries():
            await session.execute(
                text(_INSERT_DEFAULT_ATTIRE),
                {"cid": commander_id, "t": attire_type, "aid": attire_id},
            )
        await session.commit()


def grant_default_attires_sync(commander_id: int) -> None:
    with get_sync_session() as session:
        for attire_type, attire_id in default_attire_entries():
            session.execute(
                text(_INSERT_DEFAULT_ATTIRE),
                {"cid": commander_id, "t": attire_type, "aid": attire_id},
            )
        session.commit()


def grant_default_attires_to_all_sync() -> int:
    """One-time backfill for commanders created before the default-grant hook."""
    with get_sync_session() as session:
        commander_ids = [int(r[0]) for r in session.execute(
            text("SELECT commander_id FROM commanders")).all()]
    for cid in commander_ids:
        grant_default_attires_sync(cid)
    return len(commander_ids)


def update_commander_attire_style_sync(commander_id: int, attire_type: int, attire_id: int) -> bool:
    """Persist the selected attire style to the commanders table."""
    col = {
        ATTIRE_TYPE_ICON_FRAME: "selected_icon_frame_id",
        ATTIRE_TYPE_CHAT_FRAME: "selected_chat_frame_id",
        ATTIRE_TYPE_COMBAT_UI: "selected_battle_ui_id",
    }.get(attire_type)
    if not col:
        return False
    with get_sync_session() as session:
        session.execute(
            text(f"UPDATE commanders SET {col} = :aid WHERE commander_id = :cid"),
            {"aid": attire_id, "cid": commander_id},
        )
        session.commit()
    return True


# ── Async ORM query functions (for api/handlers) ──


async def list_commander_attires_rows(commander_id: int) -> list[dict[str, Any]]:
    async with get_session() as session:
        result = await session.execute(
            text("SELECT type, attire_id, expires_at, is_new FROM commander_attires WHERE commander_id = :cid ORDER BY type, attire_id"),
            {"cid": commander_id},
        )
        return [dict(r) for r in result.mappings().all()]


async def get_commander_attire(commander_id: int, attire_type: int, attire_id: int) -> Optional[dict[str, Any]]:
    async with get_session() as session:
        result = await session.execute(
            text("SELECT * FROM commander_attires WHERE commander_id = :cid AND type = :t AND attire_id = :aid"),
            {"cid": commander_id, "t": attire_type, "aid": attire_id},
        )
        row = result.mappings().first()
        return dict(row) if row else None


async def upsert_commander_attire(commander_id: int, attire_type: int, attire_id: int, expires_at: Optional[str] = None, is_new: bool = False) -> None:
    async with get_session() as session:
        if expires_at is not None:
            await session.execute(
                text("INSERT INTO commander_attires (commander_id, type, attire_id, expires_at, is_new) "
                     "VALUES (:cid, :t, :aid, :exp, :new) ON CONFLICT (commander_id, type, attire_id) "
                     "DO UPDATE SET expires_at = EXCLUDED.expires_at, is_new = EXCLUDED.is_new"),
                {"cid": commander_id, "t": attire_type, "aid": attire_id, "exp": expires_at, "new": is_new},
            )
        else:
            await session.execute(
                text("INSERT INTO commander_attires (commander_id, type, attire_id, is_new) "
                     "VALUES (:cid, :t, :aid, :new) ON CONFLICT (commander_id, type, attire_id) "
                     "DO UPDATE SET is_new = EXCLUDED.is_new"),
                {"cid": commander_id, "t": attire_type, "aid": attire_id, "new": is_new},
            )
        await session.commit()


async def update_attire_expires(commander_id: int, attire_type: int, attire_id: int, expires_at: str) -> None:
    async with get_session() as session:
        await session.execute(
            text("UPDATE commander_attires SET expires_at = :exp WHERE commander_id = :cid AND type = :t AND attire_id = :aid"),
            {"exp": expires_at, "cid": commander_id, "t": attire_type, "aid": attire_id},
        )
        await session.commit()


async def update_attire_is_new(commander_id: int, attire_type: int, attire_id: int, is_new: bool) -> None:
    async with get_session() as session:
        await session.execute(
            text("UPDATE commander_attires SET is_new = :new WHERE commander_id = :cid AND type = :t AND attire_id = :aid"),
            {"new": is_new, "cid": commander_id, "t": attire_type, "aid": attire_id},
        )
        await session.commit()


async def delete_commander_attire(commander_id: int, attire_type: int, attire_id: int) -> str:
    async with get_session() as session:
        result = await session.execute(
            text("DELETE FROM commander_attires WHERE commander_id = :cid AND type = :t AND attire_id = :aid"),
            {"cid": commander_id, "t": attire_type, "aid": attire_id},
        )
        await session.commit()
        return f"DELETE {result.rowcount}"


def list_commander_attires(commander_id: int) -> list:
    with get_sync_session() as session:
        result = session.execute(
            select(CommanderAttire).where(
                CommanderAttire.commander_id == commander_id,
            )
        )
        return list(result.scalars().all())


def list_commander_living_area_covers(commander_id: int) -> list:
    with get_sync_session() as session:
        result = session.execute(
            select(CommanderLivingAreaCover).where(
                CommanderLivingAreaCover.commander_id == commander_id,
            )
        )
        return list(result.scalars().all())


class CommanderAttire(Base):
    __tablename__ = 'commander_attires'
    commander_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    type: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    attire_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, default=0)
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    is_new: Mapped[bool] = mapped_column(Boolean, default=False)
