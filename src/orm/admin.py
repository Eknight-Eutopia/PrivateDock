from __future__ import annotations

from sqlalchemy import select, func, and_, text

from src.db.session import get_sync_session
from src.db.gen.pagination import normalize_pagination
from src.orm.item import Item as SAItem
from src.orm.resource import Resource as SAResource
from src.orm.config_entry import ConfigEntry as SAConfigEntry
from src.orm.equipment import Equipment as SAEquipment
from src.orm.ship import Ship as SAShip
from src.orm.weapon import Weapon as SAWeapon
from src.orm.skill import Skill as SASkill
from src.orm.buff import Buff as SABuff
from src.orm.skin import Skin as SASkin
from src.orm.global_skin_restriction import GlobalSkinRestriction as SARestriction
from src.orm.global_skin_restriction_window import GlobalSkinRestrictionWindow as SARestrictionWindow
from src.orm.ship_type import ShipType as SAShipType
from src.orm.rarity import Rarity as SARarity
from src.orm.commander import Commander as SACommander
from src.orm.requisition_ship import RequisitionShip as SARequisitionShip

# ── Ships ──

def list_ships_page(
    offset: int = 0,
    limit: int = 20,
    rarity_id: int | None = None,
    type_id: int | None = None,
    nationality_id: int | None = None,
    name: str = "",
):
    with get_sync_session() as session:
        q = select(SAShip)
        filters = []
        if rarity_id is not None:
            filters.append(SAShip.rarity_id == rarity_id)
        if type_id is not None:
            filters.append(SAShip.type == type_id)
        if nationality_id is not None:
            filters.append(SAShip.nationality == nationality_id)
        if name:
            filters.append(SAShip.name.ilike(f"%{name}%"))
        if filters:
            q = q.where(and_(*filters))
        total = session.scalar(select(func.count()).select_from(SAShip).where(and_(*filters))) if filters else session.scalar(select(func.count()).select_from(SAShip))
        offset, limit, unlimited = normalize_pagination(offset, limit)
        q = q.order_by(SAShip.template_id.asc()).offset(offset)
        if not unlimited:
            q = q.limit(limit)
        rows = session.execute(q).scalars().all()
        pools_by_ship = _pools_by_template_ids(session, [r.template_id for r in rows])
        data = []
        for r in rows:
            data.append({
                "template_id": r.template_id,
                "name": r.name,
                "english_name": r.english_name,
                "rarity_id": r.rarity_id,
                "star": r.star,
                "type": r.type,
                "nationality": r.nationality,
                "build_time": r.build_time,
                "pools": pools_by_ship.get(r.template_id, []),
            })
        return data, total


def get_ship_by_template_id(template_id: int):
    from src.orm.ship import Ship as SAShip
    with get_sync_session() as session:
        r = session.get(SAShip, template_id)
        if r is None:
            return None
        pools = _pools_by_template_ids(session, [template_id]).get(template_id, [])
        return {
            "template_id": r.template_id,
            "name": r.name,
            "english_name": r.english_name,
            "rarity_id": r.rarity_id,
            "star": r.star,
            "type": r.type,
            "nationality": r.nationality,
            "build_time": r.build_time,
            "pools": pools,
        }


def _pools_by_template_ids(session, template_ids: list[int]) -> dict[int, list[int]]:
    """template_id -> sorted pool ids from build_pool_ships (multi-pool)."""
    result: dict[int, list[int]] = {}
    if not template_ids:
        return result
    rows = session.execute(
        text(
            "SELECT template_id, pool_id FROM build_pool_ships "
            "WHERE template_id = ANY(:ids)"
        ),
        {"ids": list(template_ids)},
    ).fetchall()
    for template_id, pool_id in rows:
        result.setdefault(int(template_id), []).append(int(pool_id))
    for pools in result.values():
        pools.sort()
    return result


def _replace_ship_pools(session, template_id: int, pools) -> None:
    """Sync build_pool_ships rows for a ship (admin ship CRUD)."""
    session.execute(
        text("DELETE FROM build_pool_ships WHERE template_id = :tid"), {"tid": template_id}
    )
    for pool_id in pools or []:
        session.execute(
            text(
                "INSERT INTO build_pool_ships (pool_id, template_id) "
                "VALUES (:p, :tid) ON CONFLICT DO NOTHING"
            ),
            {"p": int(pool_id), "tid": template_id},
        )


def insert_ship(data: dict):
    pools = data.pop("pools", None)
    with get_sync_session() as session:
        obj = SAShip(**data)
        session.add(obj)
        session.commit()
        _replace_ship_pools(session, obj.template_id, pools)
        session.commit()
        return obj.template_id


def update_ship_record(template_id: int, data: dict):
    pools = data.pop("pools", None)
    with get_sync_session() as session:
        r = session.get(SAShip, template_id)
        if r is None:
            return False
        for k, v in data.items():
            setattr(r, k, v)
        session.commit()
        if pools is not None:
            _replace_ship_pools(session, template_id, pools)
            session.commit()
        return True


def delete_ship_record(template_id: int) -> bool:
    with get_sync_session() as session:
        r = session.get(SAShip, template_id)
        if r is None:
            return False
        session.delete(r)
        session.execute(
            text("DELETE FROM build_pool_ships WHERE template_id = :tid"), {"tid": template_id}
        )
        session.commit()
        return True


# ── Items ──

def list_items_page(offset: int = 0, limit: int = 20):
    with get_sync_session() as session:
        total = session.scalar(select(func.count()).select_from(SAItem))
        offset, limit, unlimited = normalize_pagination(offset, limit)
        q = select(SAItem).order_by(SAItem.id.asc()).offset(offset)
        if not unlimited:
            q = q.limit(limit)
        rows = session.execute(q).scalars().all()
        data = [{c.name: getattr(r, c.name) for c in SAItem.__table__.columns} for r in rows]
        return data, total


def get_item_by_id(item_id: int):
    with get_sync_session() as session:
        r = session.get(SAItem, item_id)
        if r is None:
            return None
        return {c.name: getattr(r, c.name) for c in SAItem.__table__.columns}


def create_item_record(data: dict):
    with get_sync_session() as session:
        obj = SAItem(**data)
        session.add(obj)
        session.commit()
        return obj.id


def update_item_record(item_id: int, data: dict):
    with get_sync_session() as session:
        r = session.get(SAItem, item_id)
        if r is None:
            return False
        for k, v in data.items():
            setattr(r, k, v)
        session.commit()
        return True


def delete_item_record(item_id: int) -> bool:
    with get_sync_session() as session:
        r = session.get(SAItem, item_id)
        if r is None:
            return False
        session.delete(r)
        session.commit()
        return True


# ── Resources ──

def list_resources_page(offset: int = 0, limit: int = 20):
    with get_sync_session() as session:
        total = session.scalar(select(func.count()).select_from(SAResource))
        offset, limit, unlimited = normalize_pagination(offset, limit)
        q = select(SAResource).order_by(SAResource.id.asc()).offset(offset)
        if not unlimited:
            q = q.limit(limit)
        rows = session.execute(q).scalars().all()
        data = [{c.name: getattr(r, c.name) for c in SAResource.__table__.columns} for r in rows]
        return data, total


def get_resource_by_id(resource_id: int):
    with get_sync_session() as session:
        r = session.get(SAResource, resource_id)
        if r is None:
            return None
        return {c.name: getattr(r, c.name) for c in SAResource.__table__.columns}


def create_resource_record(data: dict):
    with get_sync_session() as session:
        obj = SAResource(**data)
        session.add(obj)
        session.commit()
        return obj.id


def update_resource_record(resource_id: int, data: dict):
    with get_sync_session() as session:
        r = session.get(SAResource, resource_id)
        if r is None:
            return False
        for k, v in data.items():
            setattr(r, k, v)
        session.commit()
        return True


def delete_resource_record(resource_id: int) -> bool:
    with get_sync_session() as session:
        r = session.get(SAResource, resource_id)
        if r is None:
            return False
        session.delete(r)
        session.commit()
        return True


# ── Equipment ──

def list_equipment_page(offset: int = 0, limit: int = 20):
    with get_sync_session() as session:
        total = session.scalar(select(func.count()).select_from(SAEquipment))
        offset, limit, unlimited = normalize_pagination(offset, limit)
        q = select(SAEquipment).order_by(SAEquipment.id.asc()).offset(offset)
        if not unlimited:
            q = q.limit(limit)
        rows = session.execute(q).scalars().all()
        data = [{c.name: getattr(r, c.name) for c in SAEquipment.__table__.columns} for r in rows]
        return data, total


def get_equipment_by_id(equip_id: int):
    with get_sync_session() as session:
        r = session.get(SAEquipment, equip_id)
        if r is None:
            return None
        return {c.name: getattr(r, c.name) for c in SAEquipment.__table__.columns}


def create_equipment_record(data: dict):
    with get_sync_session() as session:
        obj = SAEquipment(**data)
        session.add(obj)
        session.commit()
        return obj.id


def update_equipment_record(equip_id: int, data: dict):
    with get_sync_session() as session:
        r = session.get(SAEquipment, equip_id)
        if r is None:
            return False
        for k, v in data.items():
            setattr(r, k, v)
        session.commit()
        return True


def delete_equipment_record(equip_id: int) -> bool:
    with get_sync_session() as session:
        r = session.get(SAEquipment, equip_id)
        if r is None:
            return False
        session.delete(r)
        session.commit()
        return True


# ── Weapons ──

def list_weapons_page(offset: int = 0, limit: int = 20):
    with get_sync_session() as session:
        total = session.scalar(select(func.count()).select_from(SAWeapon))
        offset, limit, unlimited = normalize_pagination(offset, limit)
        q = select(SAWeapon).order_by(SAWeapon.id.asc()).offset(offset)
        if not unlimited:
            q = q.limit(limit)
        rows = session.execute(q).scalars().all()
        data = [{c.name: getattr(r, c.name) for c in SAWeapon.__table__.columns} for r in rows]
        return data, total


def get_weapon_by_id(weapon_id: int):
    with get_sync_session() as session:
        r = session.get(SAWeapon, weapon_id)
        if r is None:
            return None
        return {c.name: getattr(r, c.name) for c in SAWeapon.__table__.columns}


def create_weapon_record(data: dict):
    with get_sync_session() as session:
        obj = SAWeapon(**data)
        session.add(obj)
        session.commit()
        return obj.id


def update_weapon_record(weapon_id: int, data: dict):
    with get_sync_session() as session:
        r = session.get(SAWeapon, weapon_id)
        if r is None:
            return False
        for k, v in data.items():
            setattr(r, k, v)
        session.commit()
        return True


def delete_weapon_record(weapon_id: int) -> bool:
    with get_sync_session() as session:
        r = session.get(SAWeapon, weapon_id)
        if r is None:
            return False
        session.delete(r)
        session.commit()
        return True


# ── Skills ──

def list_skills_page(offset: int = 0, limit: int = 20):
    with get_sync_session() as session:
        total = session.scalar(select(func.count()).select_from(SASkill))
        offset, limit, unlimited = normalize_pagination(offset, limit)
        q = select(SASkill).order_by(SASkill.id.asc()).offset(offset)
        if not unlimited:
            q = q.limit(limit)
        rows = session.execute(q).scalars().all()
        data = [{c.name: getattr(r, c.name) for c in SASkill.__table__.columns} for r in rows]
        return data, total


def get_skill_by_id(skill_id: int):
    with get_sync_session() as session:
        r = session.get(SASkill, skill_id)
        if r is None:
            return None
        return {c.name: getattr(r, c.name) for c in SASkill.__table__.columns}


def create_skill_record(data: dict):
    with get_sync_session() as session:
        obj = SASkill(**data)
        session.add(obj)
        session.commit()
        return obj.id


def update_skill_record(skill_id: int, data: dict):
    with get_sync_session() as session:
        r = session.get(SASkill, skill_id)
        if r is None:
            return False
        for k, v in data.items():
            setattr(r, k, v)
        session.commit()
        return True


def delete_skill_record(skill_id: int) -> bool:
    with get_sync_session() as session:
        r = session.get(SASkill, skill_id)
        if r is None:
            return False
        session.delete(r)
        session.commit()
        return True


# ── Buffs ──

def list_buffs_page(offset: int = 0, limit: int = 20):
    with get_sync_session() as session:
        total = session.scalar(select(func.count()).select_from(SABuff))
        offset, limit, unlimited = normalize_pagination(offset, limit)
        q = select(SABuff).order_by(SABuff.id.asc()).offset(offset)
        if not unlimited:
            q = q.limit(limit)
        rows = session.execute(q).scalars().all()
        data = [{c.name: getattr(r, c.name) for c in SABuff.__table__.columns} for r in rows]
        return data, total


def get_buff_by_id(buff_id: int):
    with get_sync_session() as session:
        r = session.get(SABuff, buff_id)
        if r is None:
            return None
        return {c.name: getattr(r, c.name) for c in SABuff.__table__.columns}


def create_buff_record(data: dict):
    with get_sync_session() as session:
        obj = SABuff(**data)
        session.add(obj)
        session.commit()
        return obj.id


def update_buff_record(buff_id: int, data: dict):
    with get_sync_session() as session:
        r = session.get(SABuff, buff_id)
        if r is None:
            return False
        for k, v in data.items():
            setattr(r, k, v)
        session.commit()
        return True


def delete_buff_record(buff_id: int) -> bool:
    with get_sync_session() as session:
        r = session.get(SABuff, buff_id)
        if r is None:
            return False
        session.delete(r)
        session.commit()
        return True


# ── Skins ──

def list_skins_page(offset: int = 0, limit: int = 20):
    with get_sync_session() as session:
        total = session.scalar(select(func.count()).select_from(SASkin))
        offset, limit, unlimited = normalize_pagination(offset, limit)
        q = select(SASkin).order_by(SASkin.id.asc()).offset(offset)
        if not unlimited:
            q = q.limit(limit)
        rows = session.execute(q).scalars().all()
        data = [{c.name: getattr(r, c.name) for c in SASkin.__table__.columns} for r in rows]
        return data, total


def list_skins_by_ship_group_page(ship_group: int, offset: int = 0, limit: int = 20):
    with get_sync_session() as session:
        q = select(SASkin).where(SASkin.ship_group == ship_group)
        total = session.scalar(select(func.count()).select_from(SASkin).where(SASkin.ship_group == ship_group))
        offset, limit, unlimited = normalize_pagination(offset, limit)
        q = q.order_by(SASkin.id.asc()).offset(offset)
        if not unlimited:
            q = q.limit(limit)
        rows = session.execute(q).scalars().all()
        data = [{c.name: getattr(r, c.name) for c in SASkin.__table__.columns} for r in rows]
        return data, total


def get_skin_by_id(skin_id: int):
    with get_sync_session() as session:
        r = session.get(SASkin, skin_id)
        if r is None:
            return None
        return {c.name: getattr(r, c.name) for c in SASkin.__table__.columns}


def create_skin_record(data: dict):
    with get_sync_session() as session:
        obj = SASkin(**data)
        session.add(obj)
        session.commit()
        return obj.id


def update_skin_record(skin_id: int, data: dict):
    with get_sync_session() as session:
        r = session.get(SASkin, skin_id)
        if r is None:
            return False
        for k, v in data.items():
            setattr(r, k, v)
        session.commit()
        return True


def delete_skin_record(skin_id: int) -> bool:
    with get_sync_session() as session:
        r = session.get(SASkin, skin_id)
        if r is None:
            return False
        session.delete(r)
        session.commit()
        return True


# ── Global Skin Restrictions ──

def list_global_skin_restrictions_page(offset: int = 0, limit: int = 20):
    with get_sync_session() as session:
        total = session.scalar(select(func.count()).select_from(SARestriction))
        offset, limit, unlimited = normalize_pagination(offset, limit)
        q = select(SARestriction).order_by(SARestriction.skin_id.asc()).offset(offset)
        if not unlimited:
            q = q.limit(limit)
        rows = session.execute(q).scalars().all()
        data = [{c.name: getattr(r, c.name) for c in SARestriction.__table__.columns} for r in rows]
        return data, total


def get_global_skin_restriction_by_skin_id(skin_id: int):
    with get_sync_session() as session:
        r = session.get(SARestriction, skin_id)
        if r is None:
            return None
        return {c.name: getattr(r, c.name) for c in SARestriction.__table__.columns}


def create_global_skin_restriction(data: dict):
    with get_sync_session() as session:
        obj = SARestriction(**data)
        session.add(obj)
        session.commit()
        return obj.skin_id


def update_global_skin_restriction(skin_id: int, data: dict):
    with get_sync_session() as session:
        r = session.get(SARestriction, skin_id)
        if r is None:
            return False
        for k, v in data.items():
            setattr(r, k, v)
        session.commit()
        return True


def delete_global_skin_restriction(skin_id: int) -> bool:
    with get_sync_session() as session:
        r = session.get(SARestriction, skin_id)
        if r is None:
            return False
        session.delete(r)
        session.commit()
        return True


# ── Global Skin Restriction Windows ──

def list_global_skin_restriction_windows_page(offset: int = 0, limit: int = 20):
    with get_sync_session() as session:
        total = session.scalar(select(func.count()).select_from(SARestrictionWindow))
        offset, limit, unlimited = normalize_pagination(offset, limit)
        q = select(SARestrictionWindow).order_by(SARestrictionWindow.id.asc()).offset(offset)
        if not unlimited:
            q = q.limit(limit)
        rows = session.execute(q).scalars().all()
        data = [{c.name: getattr(r, c.name) for c in SARestrictionWindow.__table__.columns} for r in rows]
        return data, total


def get_global_skin_restriction_window_by_id(window_id: int):
    with get_sync_session() as session:
        r = session.get(SARestrictionWindow, window_id)
        if r is None:
            return None
        return {c.name: getattr(r, c.name) for c in SARestrictionWindow.__table__.columns}


def create_global_skin_restriction_window(data: dict):
    with get_sync_session() as session:
        obj = SARestrictionWindow(**data)
        session.add(obj)
        session.commit()
        return obj.id


def update_global_skin_restriction_window(window_id: int, data: dict):
    with get_sync_session() as session:
        r = session.get(SARestrictionWindow, window_id)
        if r is None:
            return False
        for k, v in data.items():
            setattr(r, k, v)
        session.commit()
        return True


def delete_global_skin_restriction_window(window_id: int) -> bool:
    with get_sync_session() as session:
        r = session.get(SARestrictionWindow, window_id)
        if r is None:
            return False
        session.delete(r)
        session.commit()
        return True


# ── Config Entries ──

def list_config_entries_filtered(category: str = "", key: str = ""):
    with get_sync_session() as session:
        q = select(SAConfigEntry)
        if category:
            q = q.where(SAConfigEntry.category == category)
        if key:
            q = q.where(SAConfigEntry.key == key)
        q = q.order_by(SAConfigEntry.id.asc())
        rows = session.execute(q).scalars().all()
        return [{c.name: getattr(r, c.name) for c in SAConfigEntry.__table__.columns} for r in rows]


def get_config_entry_by_id(entry_id: int):
    with get_sync_session() as session:
        r = session.get(SAConfigEntry, entry_id)
        if r is None:
            return None
        return {c.name: getattr(r, c.name) for c in SAConfigEntry.__table__.columns}


def create_config_entry_record(data: dict):
    with get_sync_session() as session:
        obj = SAConfigEntry(**data)
        session.add(obj)
        session.commit()
        return obj.id


def update_config_entry_record(entry_id: int, data: dict):
    with get_sync_session() as session:
        r = session.get(SAConfigEntry, entry_id)
        if r is None:
            return False
        for k, v in data.items():
            setattr(r, k, v)
        session.commit()
        return True


def delete_config_entry_by_id(entry_id: int) -> bool:
    with get_sync_session() as session:
        r = session.get(SAConfigEntry, entry_id)
        if r is None:
            return False
        session.delete(r)
        session.commit()
        return True


# ── Ship Types ──

def list_ship_types(offset: int = 0, limit: int = 20):
    with get_sync_session() as session:
        total = session.scalar(select(func.count()).select_from(SAShipType))
        offset, limit, unlimited = normalize_pagination(offset, limit)
        q = select(SAShipType).order_by(SAShipType.id.asc()).offset(offset)
        if not unlimited:
            q = q.limit(limit)
        rows = session.execute(q).scalars().all()
        return [{c.name: getattr(r, c.name) for c in SAShipType.__table__.columns} for r in rows], total


def get_ship_type_by_id(type_id: int):
    with get_sync_session() as session:
        r = session.get(SAShipType, type_id)
        if r is None:
            return None
        return {c.name: getattr(r, c.name) for c in SAShipType.__table__.columns}


def create_ship_type(data: dict):
    with get_sync_session() as session:
        obj = SAShipType(**data)
        session.add(obj)
        session.commit()
        return obj.id


def update_ship_type(type_id: int, data: dict):
    with get_sync_session() as session:
        r = session.get(SAShipType, type_id)
        if r is None:
            return False
        for k, v in data.items():
            setattr(r, k, v)
        session.commit()
        return True


def delete_ship_type(type_id: int) -> bool:
    with get_sync_session() as session:
        r = session.get(SAShipType, type_id)
        if r is None:
            return False
        session.delete(r)
        session.commit()
        return True


# ── Rarities ──

def list_rarities(offset: int = 0, limit: int = 20):
    with get_sync_session() as session:
        total = session.scalar(select(func.count()).select_from(SARarity))
        offset, limit, unlimited = normalize_pagination(offset, limit)
        q = select(SARarity).order_by(SARarity.id.asc()).offset(offset)
        if not unlimited:
            q = q.limit(limit)
        rows = session.execute(q).scalars().all()
        return [{c.name: getattr(r, c.name) for c in SARarity.__table__.columns} for r in rows], total


def get_rarity_by_id(rarity_id: int):
    with get_sync_session() as session:
        r = session.get(SARarity, rarity_id)
        if r is None:
            return None
        return {c.name: getattr(r, c.name) for c in SARarity.__table__.columns}


def create_rarity(data: dict):
    with get_sync_session() as session:
        obj = SARarity(**data)
        session.add(obj)
        session.commit()
        return obj.id


def update_rarity(rarity_id: int, data: dict):
    with get_sync_session() as session:
        r = session.get(SARarity, rarity_id)
        if r is None:
            return False
        for k, v in data.items():
            setattr(r, k, v)
        session.commit()
        return True


def delete_rarity(rarity_id: int) -> bool:
    with get_sync_session() as session:
        r = session.get(SARarity, rarity_id)
        if r is None:
            return False
        session.delete(r)
        session.commit()
        return True


# ── Requisition Ships ──

def list_requisition_ship_ids():
    with get_sync_session() as session:
        rows = session.execute(select(SARequisitionShip)).scalars().all()
        return [r.ship_id for r in rows]


def create_requisition_ship(ship_id: int):
    with get_sync_session() as session:
        obj = SARequisitionShip(ship_id=ship_id)
        session.add(obj)
        session.commit()
        return ship_id


def delete_requisition_ship(ship_id: int) -> bool:
    with get_sync_session() as session:
        r = session.get(SARequisitionShip, ship_id)
        if r is None:
            return False
        session.delete(r)
        session.commit()
        return True


# ── Player / Commander ──

def commander_exists(commander_id: int) -> bool:
    with get_sync_session() as session:
        r = session.get(SACommander, commander_id)
        return r is not None
