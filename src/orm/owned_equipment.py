from __future__ import annotations
from typing import Any, Optional

from sqlalchemy import text
from sqlalchemy import BigInteger
from sqlalchemy.orm import Mapped, mapped_column

from src.db.session import Base, get_session, get_sync_session


# ── Sync wrapper helpers (import real impls from equipment.py, NOT by local name) ──


def _sync_get_equipment_by_id(equip_id: int) -> OwnedEquipment | None:
    from src.orm import equipment as _eq
    return _eq.get_equipment_by_id(equip_id)

def _sync_list_owned_ship_equipment(commander_id: int, ship_id: int) -> list:
    from src.orm import equipment as _eq
    return _eq.list_owned_ship_equipment(commander_id, ship_id)

def _sync_upsert_owned_ship_equipment(owner_id: int, ship_id: int, pos: int, equip_id: int, skin_id: int = 0):
    from src.orm import equipment as _eq
    _eq.upsert_owned_ship_equipment(owner_id, ship_id, pos, equip_id, skin_id)

def _sync_delete_owned_ship_equipments(commander_id: int, ship_id: int):
    from src.orm import equipment as _eq
    _eq.delete_owned_ship_equipments(commander_id, ship_id)

def _sync_get_ship_equip_config(config_id: int) -> dict | None:
    from src.orm.game_data import get_ship_equip_config
    return get_ship_equip_config(config_id)

def _sync_get_ship_template_config(ship_id: int) -> dict | None:
    from src.orm.game_data import get_ship_template_config
    return get_ship_template_config(ship_id)


def _sync_add_owned_equipment(commander_id: int, equipment_id: int, count: int = 1) -> None:
    with get_sync_session() as session:
        result = session.execute(
            text("SELECT count FROM owned_equipments WHERE commander_id = :cid AND equipment_id = :eid"),
            {"cid": commander_id, "eid": equipment_id},
        )
        row = result.fetchone()
        if row is None:
            session.execute(
                text("INSERT INTO owned_equipments (commander_id, equipment_id, count) VALUES (:cid, :eid, :cnt)"),
                {"cid": commander_id, "eid": equipment_id, "cnt": count},
            )
        else:
            session.execute(
                text("UPDATE owned_equipments SET count = count + :cnt WHERE commander_id = :cid AND equipment_id = :eid"),
                {"cid": commander_id, "eid": equipment_id, "cnt": count},
            )
        session.commit()
        # Keep the in-memory owned_equipment_map in sync so disassembly / re-equip of
        # returned gear works without a relogin.
        try:
            from src.orm.active_commander import _bump_count_map
            _bump_count_map(commander_id, "owned_equipment_map", equipment_id, count, "equipment_id")
        except Exception:
            pass


# ── Async ORM query functions (for api/handlers) ──


async def list_owned_equipment(commander_id: int) -> list[dict[str, Any]]:
    async with get_session() as session:
        result = await session.execute(
            text("SELECT equipment_id, count FROM owned_equipments WHERE commander_id = :cid"),
            {"cid": commander_id},
        )
        return [dict(r) for r in result.mappings().all()]


async def get_owned_equipment(commander_id: int, equipment_id: int) -> Optional[dict[str, Any]]:
    async with get_session() as session:
        result = await session.execute(
            text("SELECT equipment_id, count FROM owned_equipments WHERE commander_id = :cid AND equipment_id = :eid"),
            {"cid": commander_id, "eid": equipment_id},
        )
        row = result.mappings().first()
        return dict(row) if row else None


async def upsert_owned_equipment(commander_id: int, equipment_id: int, count: int) -> None:
    async with get_session() as session:
        await session.execute(
            text("INSERT INTO owned_equipments (commander_id, equipment_id, count) "
                 "VALUES (:cid, :eid, :cnt) "
                 "ON CONFLICT (commander_id, equipment_id) DO UPDATE SET count = :cnt"),
            {"cid": commander_id, "eid": equipment_id, "cnt": count},
        )
        await session.commit()


async def delete_owned_equipment(commander_id: int, equipment_id: int) -> None:
    async with get_session() as session:
        await session.execute(
            text("DELETE FROM owned_equipments WHERE commander_id = :cid AND equipment_id = :eid"),
            {"cid": commander_id, "eid": equipment_id},
        )
        await session.commit()


add_owned_equipment = _sync_add_owned_equipment
get_equipment_by_id = _sync_get_equipment_by_id
list_owned_ship_equipment = _sync_list_owned_ship_equipment
upsert_owned_ship_equipment = _sync_upsert_owned_ship_equipment
delete_owned_ship_equipments = _sync_delete_owned_ship_equipments
get_ship_equip_config = _sync_get_ship_equip_config
get_ship_template_config = _sync_get_ship_template_config


def list_owned_equipment_sync(commander_id: int) -> list[dict[str, Any]]:
    with get_sync_session() as session:
        result = session.execute(
            text("SELECT equipment_id, count FROM owned_equipments WHERE commander_id = :cid"),
            {"cid": commander_id},
        )
        return [dict(r) for r in result.mappings().all()]


def get_owned_equipment_sync(commander_id: int, equipment_id: int) -> Optional[dict[str, Any]]:
    with get_sync_session() as session:
        result = session.execute(
            text("SELECT equipment_id, count FROM owned_equipments WHERE commander_id = :cid AND equipment_id = :eid"),
            {"cid": commander_id, "eid": equipment_id},
        )
        row = result.mappings().first()
        return dict(row) if row else None


def count_total_owned_equipment_sync(commander_id: int) -> int:
    with get_sync_session() as session:
        row = session.execute(
            text("SELECT COALESCE(SUM(count), 0) FROM owned_equipments WHERE commander_id = :cid"),
            {"cid": commander_id},
        ).scalar()
        return row or 0


def delete_owned_equipment_sync(commander_id: int, equipment_id: int) -> None:
    with get_sync_session() as session:
        session.execute(
            text("DELETE FROM owned_equipments WHERE commander_id = :cid AND equipment_id = :eid"),
            {"cid": commander_id, "eid": equipment_id},
        )
        session.commit()



class OwnedEquipment(Base):
    __tablename__ = 'owned_equipments'
    commander_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    equipment_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    count: Mapped[int] = mapped_column(BigInteger, default=0)


# ── Ship equipment update and upgrade helpers ──

def build_ship_equipment_from_memory(owner_id: int, ship: dict, pos: int) -> dict:
    entry = {
        "owner_id": owner_id,
        "ship_id": ship.get("id", 0),
        "pos": pos,
        "equip_id": 0,
        "skin_id": 0,
    }
    for equip in ship.get("equipments", []):
        if equip.get("pos") == pos:
            entry["equip_id"] = equip.get("equip_id", 0)
            entry["skin_id"] = equip.get("skin_id", 0)
            break
    return entry


def apply_ship_equipment_update(ship: dict, update: dict) -> None:
    for i, equip in enumerate(ship.get("equipments", [])):
        if equip.get("pos") == update.get("pos"):
            ship["equipments"][i] = dict(update)
            return
    ship.setdefault("equipments", []).append(dict(update))


def resolve_equipment_config(cache: dict, equipment_id: int) -> Optional[dict]:
    if equipment_id in cache:
        return cache[equipment_id]
    from src.orm.owned_equipment import get_equipment_by_id
    try:
        raw = get_equipment_by_id(equipment_id)
    except Exception:
        return None
    if raw is None:
        return None
    entry = raw if isinstance(raw, dict) else {
        "id": getattr(raw, "id", 0),
        "base": getattr(raw, "base", None),
        "equip_limit": getattr(raw, "equip_limit", 0),
        "ship_type_forbidden": getattr(raw, "ship_type_forbidden", b"[]"),
        "type": getattr(raw, "type", 0),
    }
    if entry.get("base") is not None:
        base_entry = resolve_equipment_config(cache, entry["base"])
        if base_entry is not None:
            entry = dict(base_entry)
    cache[equipment_id] = entry
    return entry


def load_equipment_config(equip_id: int) -> Optional[dict]:
    if equip_id == 0:
        return None
    from src.orm.owned_equipment import get_equipment_by_id
    try:
        raw = get_equipment_by_id(equip_id)
    except Exception:
        return None
    if raw is None:
        return None
    if isinstance(raw, dict):
        return raw
    return {
        "id": getattr(raw, "id", 0),
        "next": getattr(raw, "next", 0),
        "trans_use_gold": getattr(raw, "trans_use_gold", 0),
        "trans_use_item": getattr(raw, "trans_use_item", None),
    }


def compute_equipment_upgrade_costs(start_id: int, lv: int) -> tuple[Optional[int], dict[int, int], int]:
    from src.answer.trans_use import add_trans_use_items
    current_id = start_id
    item_costs: dict[int, int] = {}
    coin_cost = 0
    for _ in range(lv):
        current = load_equipment_config(current_id)
        if current is None:
            return None, {}, 0
        next_id = current.get("next", 0)
        if next_id == 0:
            return None, {}, 0
        coin_cost += current.get("trans_use_gold", 0)
        err = add_trans_use_items(item_costs, current.get("trans_use_item"))
        if err is not None:
            return None, {}, 0
        current_id = next_id
    return current_id, item_costs, coin_cost
