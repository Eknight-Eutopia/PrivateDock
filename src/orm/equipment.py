from __future__ import annotations
from typing import Any, Optional

from sqlalchemy import BigInteger, JSON, text
from sqlalchemy.orm import Mapped, mapped_column

from src.db.session import Base, get_session, get_sync_session
from sqlalchemy import select
from src.orm.owned_equipment import OwnedEquipment


# ── Async ORM query functions (for api/handlers) ──


async def list_ship_equipment(owner_id: int, ship_id: int) -> list[dict[str, Any]]:
    async with get_session() as session:
        result = await session.execute(
            text("SELECT pos, equip_id, skin_id FROM owned_ship_equipments WHERE owner_id = :oid AND ship_id = :sid"),
            {"oid": owner_id, "sid": ship_id},
        )
        return [dict(r) for r in result.mappings().all()]


async def replace_ship_equipment(owner_id: int, ship_id: int, equipment: list[dict[str, Any]]) -> None:
    async with get_session() as session:
        await session.execute(
            text("DELETE FROM owned_ship_equipments WHERE owner_id = :oid AND ship_id = :sid"),
            {"oid": owner_id, "sid": ship_id},
        )
        for entry in equipment:
            await session.execute(
                text("INSERT INTO owned_ship_equipments (owner_id, ship_id, pos, equip_id, skin_id) "
                     "VALUES (:oid, :sid, :pos, :eid, :skid)"),
                {"oid": owner_id, "sid": ship_id, "pos": entry["pos"],
                 "eid": entry.get("equip_id", 0), "skid": entry.get("skin_id", 0)},
            )
        await session.commit()


class Equipment(Base):
    __tablename__ = 'equipments'
    __table_args__ = {}
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    base: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    destroy_gold: Mapped[int] = mapped_column(BigInteger, default=0)
    destroy_item: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    equip_limit: Mapped[int] = mapped_column(BigInteger, default=0)
    group: Mapped[int] = mapped_column(BigInteger, default=0)
    important: Mapped[int] = mapped_column(BigInteger, default=0)
    level: Mapped[int] = mapped_column(BigInteger, default=0)
    next: Mapped[int] = mapped_column(BigInteger, default=0)
    prev: Mapped[int] = mapped_column(BigInteger, default=0)
    restore_gold: Mapped[int] = mapped_column(BigInteger, default=0)
    restore_item: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    ship_type_forbidden: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    trans_use_gold: Mapped[int] = mapped_column(BigInteger, default=0)
    trans_use_item: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    type: Mapped[int] = mapped_column(BigInteger, default=0)
    upgrade_formula_id: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)




def add_owned_equipment(commander_id: int, equipment_id: int, count: int = 1) -> None:
    from src.orm.owned_equipment import _sync_add_owned_equipment
    return _sync_add_owned_equipment(commander_id, equipment_id, count)


def remove_owned_equipment(commander_id: int, equipment_id: int, count: int = 1):
    with get_sync_session() as session:
        obj = session.get(OwnedEquipment, (commander_id, equipment_id))
        if obj is not None:
            if obj.count > count:
                obj.count -= count
            else:
                session.delete(obj)
            session.commit()


def get_equipment_by_id(equip_id: int) -> Equipment | None:
    with get_sync_session() as session:
        return session.execute(
            select(Equipment).where(Equipment.id == equip_id)
        ).scalar_one_or_none()


def list_owned_ship_equipment(commander_id: int, ship_id: int) -> list[dict]:
    with get_sync_session() as session:
        result = session.execute(
            text("SELECT owner_id, ship_id, pos, equip_id, skin_id FROM owned_ship_equipments "
                 "WHERE owner_id = :oid AND ship_id = :sid"),
            {"oid": commander_id, "sid": ship_id},
        )
        return [dict(r) for r in result.mappings().all()]


def list_all_owned_ship_equipment(commander_id: int) -> dict[int, list[dict]]:
    """Bulk-load all equipment for a commander, grouped by ship_id.
    Returns dict of ship_id -> list of {pos, equip_id, skin_id}.
    """
    with get_sync_session() as session:
        result = session.execute(
            text("SELECT ship_id, pos, equip_id, skin_id FROM owned_ship_equipments "
                 "WHERE owner_id = :oid ORDER BY ship_id, pos"),
            {"oid": commander_id},
        )
        grouped: dict[int, list[dict]] = {}
        for row in result.mappings().all():
            sid = row["ship_id"]
            grouped.setdefault(sid, []).append({
                "pos": row["pos"],
                "equip_id": row["equip_id"],
                "skin_id": row["skin_id"],
            })
        return grouped


def upsert_owned_ship_equipment(owner_id: int, ship_id: int, pos: int, equip_id: int, skin_id: int = 0):
    with get_sync_session() as session:
        session.execute(
            text("INSERT INTO owned_ship_equipments (owner_id, ship_id, pos, equip_id, skin_id) "
                 "VALUES (:oid, :sid, :pos, :eid, :skid) "
                 "ON CONFLICT (owner_id, ship_id, pos) DO UPDATE SET equip_id = :eid, skin_id = :skid"),
            {"oid": owner_id, "sid": ship_id, "pos": pos, "eid": equip_id, "skid": skin_id},
        )
        session.commit()


def delete_owned_equipments(commander_id: int, equipment_id: int):
    from src.orm.owned_equipment import delete_owned_equipment_sync
    delete_owned_equipment_sync(commander_id, equipment_id)


def get_owned_ship_equipment(ship_id: int, pos: int) -> Optional[dict]:
    with get_sync_session() as session:
        result = session.execute(
            text("SELECT owner_id, ship_id, pos, equip_id, skin_id FROM owned_ship_equipments "
                 "WHERE ship_id = :sid AND pos = :pos"),
            {"sid": ship_id, "pos": pos},
        )
        row = result.mappings().first()
        return dict(row) if row else None


def delete_owned_ship_equipments(commander_id: int, ship_id: int):
    with get_sync_session() as session:
        session.execute(
            text("DELETE FROM owned_ship_equipments WHERE owner_id = :oid AND ship_id = :sid"),
            {"oid": commander_id, "sid": ship_id},
        )
        session.commit()


def delete_owned_ship_equipments_by_ship_pos(ship_id: int, pos: int):
    with get_sync_session() as session:
        session.execute(
            text("DELETE FROM owned_ship_equipments WHERE ship_id = :sid AND pos = :pos"),
            {"sid": ship_id, "pos": pos},
        )
        session.commit()
