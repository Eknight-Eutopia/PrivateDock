from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from sqlalchemy import BigInteger, Boolean, DateTime, String
from sqlalchemy import select, func, text
from sqlalchemy.orm import Mapped, mapped_column

from src.db.session import Base, get_session, get_sync_session
from src.orm.commander import create_default_ship_equipments
from src.orm.commander_common_flag import should_auto_lock_new_ship
from src.orm.owned_ship_transform import OwnedShipTransform
from src.orm.owned_skin import OwnedShipShadowSkin
from src.orm.random_flag_ship import RandomFlagShip


# ── Async ORM query functions (for api/handlers) ──


async def list_owned_ships_by_owner(owner_id: int) -> list[dict[str, Any]]:
    async with get_session() as session:
        result = await session.execute(
            text("SELECT os.id AS owned_id, os.ship_id, os.level, os.skin_id, s.rarity_id, s.name "
                 "FROM owned_ships os JOIN ships s ON os.ship_id = s.template_id "
                 "WHERE os.owner_id = :oid AND os.deleted_at IS NULL"),
            {"oid": owner_id},
        )
        return [dict(r) for r in result.mappings().all()]


async def get_owned_ship(owner_id: int, owned_id: int) -> Optional[dict[str, Any]]:
    async with get_session() as session:
        result = await session.execute(
            text("SELECT * FROM owned_ships WHERE owner_id = :oid AND id = :oid2"),
            {"oid": owner_id, "oid2": owned_id},
        )
        row = result.mappings().first()
        return dict(row) if row else None


async def create_owned_ship(commander_id: int, ship_id: int, level: int, intimacy: int, exp: int) -> int:
    """Admin/API ship grant with explicit level/intimacy/exp (players.py).

    Delegates creation to the single ``add_ship`` path (GLOBAL id allocation,
    auto-lock, starter stats, default equipment slots), then applies the
    explicit overrides. ``book_exp`` was never persisted by the previous
    inline INSERT either; it stays in the signature for the API layer.
    """
    obj = _sync_add_ship(commander_id, ship_id)
    sync_update_owned_ship_fields(commander_id, obj.id, level=level, exp=exp, intimacy=intimacy)
    return obj.id


async def update_owned_ship_dynamic(commander_id: int, owned_id: int, **fields) -> None:
    if not fields:
        return
    set_clause = ", ".join(f"{k} = :{k}" for k in fields)
    params = {"cid": commander_id, "oid": owned_id}
    params.update(fields)
    async with get_session() as session:
        await session.execute(
            text(f"UPDATE owned_ships SET {set_clause} WHERE owner_id = :cid AND id = :oid"),
            params,
        )
        await session.commit()


async def delete_owned_ship(commander_id: int, owned_id: int) -> str:
    async with get_session() as session:
        result = await session.execute(
            text("DELETE FROM owned_ships WHERE owner_id = :cid AND id = :oid"),
            {"cid": commander_id, "oid": owned_id},
        )
        await session.commit()
        return f"DELETE {result.rowcount}"


async def list_secretaries(commander_id: int) -> list[dict[str, Any]]:
    async with get_session() as session:
        result = await session.execute(
            text("SELECT id, is_secretary, secretary_position, secretary_phantom_id "
                 "FROM owned_ships WHERE owner_id = :cid AND is_secretary = TRUE "
                 "ORDER BY COALESCE(secretary_position, 999), id"),
            {"cid": commander_id},
        )
        return [dict(r) for r in result.mappings().all()]


async def clear_secretaries(commander_id: int) -> None:
    async with get_session() as session:
        await session.execute(
            text("UPDATE owned_ships SET is_secretary = FALSE WHERE owner_id = :cid"),
            {"cid": commander_id},
        )
        await session.commit()


async def set_secretary(commander_id: int, ship_id: int) -> None:
    async with get_session() as session:
        await session.execute(
            text("UPDATE owned_ships SET is_secretary = TRUE WHERE owner_id = :cid AND id = :sid"),
            {"cid": commander_id, "sid": ship_id},
        )
        await session.commit()


def sync_update_owned_ship_fields(owner_id: int, owned_id: int, **fields) -> None:
    if not fields:
        return
    set_clause = ", ".join(f"{k} = :{k}" for k in fields)
    params = {"oid": owned_id, "owner": owner_id}
    params.update(fields)
    with get_sync_session() as session:
        session.execute(
            text(f"UPDATE owned_ships SET {set_clause} WHERE id = :oid AND owner_id = :owner"),
            params,
        )
        session.commit()


def _sync_add_ship(commander_id: int, ship_id: int, template_id: int = 0) -> OwnedShip:
    with get_sync_session() as session:
        from datetime import timezone
        now = datetime.now(timezone.utc)
        epoch = datetime(1970, 1, 1, tzinfo=timezone.utc)
        max_row = session.execute(
            # owned_ships.id is a GLOBAL primary key (serial sequence);
            # per-owner MAX(id) would collide for a second commander.
            text("SELECT COALESCE(MAX(id), 0) FROM owned_ships"),
        ).fetchone()
        next_id = (max_row[0] or 0) + 1
        auto_lock = should_auto_lock_new_ship(commander_id, template_id or ship_id)
        obj = OwnedShip(
            id=next_id,
            owner_id=commander_id,
            ship_id=template_id or ship_id,
            level=1,
            max_level=70,
            intimacy=5000,
            energy=100,
            state=1,
            is_locked=auto_lock,
            create_time=now,
            change_name_timestamp=epoch,
        )
        session.add(obj)
        session.commit()
        session.refresh(obj)
    create_default_ship_equipments(commander_id, obj.id, template_id or ship_id)
    return obj

def _sync_list_ships_by_owner(commander_id: int) -> list:
    with get_sync_session() as session:
        result = session.execute(
            select(OwnedShip).where(OwnedShip.owner_id == commander_id)
        )
        return list(result.scalars().all())

def _sync_list_dock_ships(commander_id: int) -> list:
    with get_sync_session() as session:
        result = session.execute(
            select(OwnedShip).where(
                OwnedShip.owner_id == commander_id,
                OwnedShip.deleted_at.is_(None),
            )
        )
        return list(result.scalars().all())

def _sync_list_ships_by_ids(ship_ids: list[int]) -> list:
    with get_sync_session() as session:
        result = session.execute(
            select(OwnedShip).where(OwnedShip.id.in_(ship_ids))
        )
        return list(result.scalars().all())

def list_ships_by_ids(commander_id: int, ship_ids: list[int]) -> list:
    from sqlalchemy import text
    with get_sync_session() as session:
        result = session.execute(
            text("SELECT id, ship_id, level, exp, energy, intimacy, skin_id, max_level, "
                 "is_locked, propose, common_flag, activity_npc, create_time, "
                 "custom_name, change_name_timestamp, "
                 "state, state_info1, state_info2, state_info3, state_info4, proficiency "
                 "FROM owned_ships WHERE owner_id = :cid AND id = ANY(:ids) AND deleted_at IS NULL ORDER BY id"),
            {"cid": commander_id, "ids": list(ship_ids)},
        )
        return list(result.fetchall())

def _sync_list_owned_secretaries(commander_id: int) -> list:
    with get_sync_session() as session:
        result = session.execute(
            select(OwnedShip).where(
                OwnedShip.owner_id == commander_id,
                OwnedShip.is_secretary == True,
            # the client renders secretary slots in SC_11003.character order;
            # the main secretary is characters[1], so position 0 must come first
            ).order_by(func.coalesce(OwnedShip.secretary_position, 999), OwnedShip.id)
        )
        return list(result.scalars().all())

def _sync_count_owned_ships(commander_id: int) -> int:
    with get_sync_session() as session:
        result = session.execute(
            select(func.count(OwnedShip.id)).where(
                OwnedShip.owner_id == commander_id,
                OwnedShip.deleted_at.is_(None),
            )
        )
        return result.scalar() or 0

def _sync_count_married_ships(commander_id: int) -> int:
    with get_sync_session() as session:
        result = session.execute(
            select(func.count(OwnedShip.id)).where(
                OwnedShip.owner_id == commander_id,
                OwnedShip.propose.is_(True),
                OwnedShip.deleted_at.is_(None),
            )
        )
        return result.scalar() or 0

async def acount_married_ships(commander_id: int) -> int:
    async with get_session() as session:
        result = await session.execute(
            select(func.count(OwnedShip.id)).where(
                OwnedShip.owner_id == commander_id,
                OwnedShip.propose.is_(True),
                OwnedShip.deleted_at.is_(None),
            )
        )
        return result.scalar() or 0

def _sync_get_owned_ship_transforms(commander_id: int) -> list:
    with get_sync_session() as session:
        result = session.execute(
            select(OwnedShipTransform).where(
                OwnedShipTransform.owner_id == commander_id
            )
        )
        return list(result.scalars().all())

def _sync_list_owned_ship_shadow_skins(commander_id: int, ship_ids: Optional[list] = None) -> list:
    with get_sync_session() as session:
        stmt = select(OwnedShipShadowSkin).where(
            OwnedShipShadowSkin.commander_id == commander_id
        )
        if ship_ids:
            stmt = stmt.where(OwnedShipShadowSkin.ship_id.in_(ship_ids))
        result = session.execute(stmt)
        return list(result.scalars().all())

def _sync_list_random_flag_ship_phantoms(commander_id: int, ship_ids: Optional[list] = None) -> list:
    with get_sync_session() as session:
        stmt = select(RandomFlagShip).where(RandomFlagShip.commander_id == commander_id)
        if ship_ids:
            stmt = stmt.where(RandomFlagShip.ship_id.in_(ship_ids))
        result = session.execute(stmt)
        return list(result.scalars().all())

def _sync_remove_owned_ships(commander, materials: list) -> None:
    ship_ids = [m["id"] for m in materials if isinstance(m, dict)]
    if not ship_ids:
        return
    cid = getattr(commander, "commander_id", commander if isinstance(commander, int) else 0)
    with get_sync_session() as session:
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc)
        for sid in ship_ids:
            obj = session.get(OwnedShip, sid)
            if obj is not None and (cid == 0 or obj.owner_id == cid):
                obj.deleted_at = now
        session.commit()

def _sync_soft_delete_owned_ship(commander_id: int, ship_id: int) -> None:
    with get_sync_session() as session:
        from datetime import datetime, timezone
        obj = session.get(OwnedShip, ship_id)
        if obj is not None and (commander_id == 0 or obj.owner_id == commander_id):
            obj.deleted_at = datetime.now(timezone.utc)
            session.commit()

_SHIP_TYPE_COINS = {
    1: 12,   # destroyer
    2: 14,   # light cruiser
    3: 18,   # heavy cruiser
    4: 22,   # battlecruiser
    5: 26,   # battleship
    6: 16,   # light carrier
    7: 16,   # aircraft carrier
    8: 0,    # submarine
    10: 25,  # aviation battleship
    12: 13,  # repair ship
    13: 13,  # monitor
    17: 10,  # submarine carrier
    18: 19,  # large cruiser
    19: 11,  # munition ship
}

def _sync_retire_ships(commander, ship_ids: list) -> None:
    cid = getattr(commander, "commander_id", commander if isinstance(commander, int) else 0)
    if not ship_ids:
        return
    with get_sync_session() as session:
        ship_rows = session.execute(
            text("SELECT s.id, s.ship_id, st.rarity_id, st.type FROM owned_ships s "
                 "JOIN ships st ON st.template_id = s.ship_id WHERE s.owner_id = :oid AND s.id = ANY(:sids)"),
            {"oid": cid, "sids": list(ship_ids)},
        ).fetchall()
        coins = 0
        medals = 0
        cores = 0
        for row in ship_rows:
            rarity_id = row[2]
            ship_type = row[3]
            coins += _SHIP_TYPE_COINS.get(ship_type, 0)
            if rarity_id == 3:
                medals += 1
            elif rarity_id == 4:
                medals += 4
            elif rarity_id == 5:
                medals += 10
            elif rarity_id == 6:
                medals += 30
                cores += 500
        if coins > 0:
            session.execute(
                text("INSERT INTO owned_resources (commander_id, resource_id, amount) VALUES (:cid, 1, :amt) "
                     "ON CONFLICT (commander_id, resource_id) DO UPDATE SET amount = owned_resources.amount + :amt2"),
                {"cid": cid, "amt": coins, "amt2": coins},
            )
        if medals > 0:
            session.execute(
                text("INSERT INTO commander_items (commander_id, item_id, count) VALUES (:cid, 15001, :cnt) "
                     "ON CONFLICT (commander_id, item_id) DO UPDATE SET count = commander_items.count + :cnt2"),
                {"cid": cid, "cnt": medals, "cnt2": medals},
            )
        if cores > 0:
            session.execute(
                text("INSERT INTO commander_items (commander_id, item_id, count) VALUES (:cid, 59010, :cnt) "
                     "ON CONFLICT (commander_id, item_id) DO UPDATE SET count = commander_items.count + :cnt2"),
                {"cid": cid, "cnt": cores, "cnt2": cores},
            )
        equip_rows = session.execute(
            text("SELECT equip_id, COUNT(*) as cnt FROM owned_ship_equipments WHERE owner_id = :oid AND ship_id = ANY(:sids) AND equip_id > 0 GROUP BY equip_id"),
            {"oid": cid, "sids": list(ship_ids)},
        ).fetchall()
        for erow in equip_rows:
            eid = erow[0]
            cnt = erow[1]
            session.execute(
                text("INSERT INTO owned_equipments (commander_id, equipment_id, count) VALUES (:cid, :eid, :cnt) "
                     "ON CONFLICT (commander_id, equipment_id) DO UPDATE SET count = owned_equipments.count + :cnt2"),
                {"cid": cid, "eid": eid, "cnt": cnt, "cnt2": cnt},
            )
        session.execute(
            text("DELETE FROM owned_ship_equipments WHERE owner_id = :oid AND ship_id = ANY(:sids)"),
            {"oid": cid, "sids": list(ship_ids)},
        )
        session.commit()
    if cores > 0:
        from src.orm.limit_item import add_limit_item
        add_limit_item(cid, 59010, cores)
    _sync_remove_owned_ships(cid, [{"id": sid} for sid in ship_ids])
    equip_map = {}
    if hasattr(commander, "owned_equipment_map"):
        for erow in equip_rows:
            eid = erow[0]
            cnt = erow[1]
            existing = commander.owned_equipment_map.get(eid, {"equipment_id": eid, "count": 0})
            existing["count"] = existing.get("count", 0) + cnt
            commander.owned_equipment_map[eid] = existing


def _sync_set_ship_favorite(ship, flag) -> None:
    ship_id = ship.get("id", 0) if isinstance(ship, dict) else getattr(ship, "id", 0)
    with get_sync_session() as session:
        obj = session.get(OwnedShip, ship_id)
        if obj is not None:
            obj.is_locked = bool(flag)
            session.commit()

def _sync_update_owned_ship(_commander, owned_id: int, **kwargs) -> None:
    with get_sync_session() as session:
        obj = session.get(OwnedShip, owned_id)
        if obj is not None:
            for key, val in kwargs.items():
                if hasattr(obj, key):
                    setattr(obj, key, val)
            session.commit()

def _sync_update_owned_ship_ship_id_skin_id(_commander_id: int, ship_id: int, new_ship_id: int, new_skin_id: int) -> None:
    with get_sync_session() as session:
        obj = session.get(OwnedShip, ship_id)
        if obj is not None:
            obj.ship_id = new_ship_id
            if new_skin_id != 0:
                obj.skin_id = new_skin_id
            session.commit()

def _sync_consume_mod_material_ships(commander, material_ids: list) -> None:
    """Consume material ships used in modification: return equipped gear to the
    bag, drop the ship-equipment rows and soft-delete the ships."""
    cid = getattr(commander, "commander_id", commander if isinstance(commander, int) else 0)
    from src.orm.equipment import list_owned_ship_equipment as _list_ship_equips
    from src.orm.owned_equipment import _sync_add_owned_equipment, _sync_delete_owned_ship_equipments
    # The in-memory equipment bag is kept in sync by _sync_add_owned_equipment
    # (which bumps owned_equipment_map), so no manual map update is needed here.
    for material_id in material_ids:
        for entry in _list_ship_equips(cid, material_id):
            equip_id = entry.get("equip_id", 0)
            if not equip_id:
                continue
            _sync_add_owned_equipment(cid, equip_id, 1)
        _sync_delete_owned_ship_equipments(cid, material_id)
    _sync_remove_owned_ships(commander, [{"id": mid} for mid in material_ids])

add_ship = _sync_add_ship
list_ships_by_owner = _sync_list_ships_by_owner
list_dock_ships = _sync_list_dock_ships
list_owned_secretaries = _sync_list_owned_secretaries
count_owned_ships = _sync_count_owned_ships
count_married_ships = _sync_count_married_ships
get_owned_ship_transforms = _sync_get_owned_ship_transforms
list_owned_ship_shadow_skins = _sync_list_owned_ship_shadow_skins
list_random_flag_ship_phantoms = _sync_list_random_flag_ship_phantoms
remove_owned_ships = _sync_remove_owned_ships
soft_delete_owned_ship = _sync_soft_delete_owned_ship
retire_ships = _sync_retire_ships
set_ship_favorite = _sync_set_ship_favorite
update_owned_ship = _sync_update_owned_ship
update_owned_ship_ship_id_skin_id = _sync_update_owned_ship_ship_id_skin_id
consume_mod_material_ships = _sync_consume_mod_material_ships

class OwnedShip(Base):
    __tablename__ = 'owned_ships'
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    owner_id: Mapped[int] = mapped_column(BigInteger)
    ship_id: Mapped[int] = mapped_column(BigInteger)
    level: Mapped[int] = mapped_column(BigInteger, default=0)
    exp: Mapped[int] = mapped_column(BigInteger, default=0)
    surplus_exp: Mapped[int] = mapped_column(BigInteger, default=0)
    max_level: Mapped[int] = mapped_column(BigInteger, default=0)
    intimacy: Mapped[int] = mapped_column(BigInteger, default=5000)
    is_locked: Mapped[bool] = mapped_column(Boolean, default=False)
    propose: Mapped[bool] = mapped_column(Boolean, default=False)
    common_flag: Mapped[bool] = mapped_column(Boolean, default=False)
    blueprint_flag: Mapped[bool] = mapped_column(Boolean, default=False)
    proficiency: Mapped[bool] = mapped_column(Boolean, default=False)
    activity_npc: Mapped[int] = mapped_column(BigInteger, default=0)
    custom_name: Mapped[str] = mapped_column(String, default='')
    change_name_timestamp: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    create_time: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    energy: Mapped[int] = mapped_column(BigInteger, default=0)
    state: Mapped[int] = mapped_column(BigInteger, default=0)
    state_info1: Mapped[int] = mapped_column(BigInteger, default=0)
    state_info2: Mapped[int] = mapped_column(BigInteger, default=0)
    state_info3: Mapped[int] = mapped_column(BigInteger, default=0)
    state_info4: Mapped[int] = mapped_column(BigInteger, default=0)
    skin_id: Mapped[int] = mapped_column(BigInteger, default=0)
    is_secretary: Mapped[bool] = mapped_column(Boolean, default=False)
    secretary_position: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    secretary_phantom_id: Mapped[int] = mapped_column(BigInteger, default=0)
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
