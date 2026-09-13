from __future__ import annotations

from sqlalchemy import BigInteger
from sqlalchemy import select
from sqlalchemy.orm import Mapped, mapped_column

from src.db.session import Base, get_sync_session


class OwnedShipMetaRepair(Base):
    __tablename__ = "owned_ship_meta_repairs"
    owner_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    ship_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    repair_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)


def list_owned_ship_meta_repair_ids(owner_id: int, ship_id: int) -> list[int]:
    with get_sync_session() as session:
        result = session.execute(
            select(OwnedShipMetaRepair.repair_id)
            .where(
                OwnedShipMetaRepair.owner_id == owner_id,
                OwnedShipMetaRepair.ship_id == ship_id,
            )
            .order_by(OwnedShipMetaRepair.repair_id.asc())
        )
        return [row[0] for row in result.all()]


def add_owned_ship_meta_repair(owner_id: int, ship_id: int, repair_id: int) -> None:
    with get_sync_session() as session:
        obj = OwnedShipMetaRepair(
            owner_id=owner_id,
            ship_id=ship_id,
            repair_id=repair_id,
        )
        session.merge(obj)
        session.commit()


def list_owned_ship_meta_repair_ids_by_ships(owner_id: int, ship_ids: list[int]) -> dict[int, list[int]]:
    if owner_id == 0 or not ship_ids:
        return {}

    unique_ids = sorted(set(sid for sid in ship_ids if sid != 0))
    if not unique_ids:
        return {}

    with get_sync_session() as session:
        result = session.execute(
            select(OwnedShipMetaRepair.ship_id, OwnedShipMetaRepair.repair_id)
            .where(
                OwnedShipMetaRepair.owner_id == owner_id,
                OwnedShipMetaRepair.ship_id.in_(unique_ids),
            )
            .order_by(OwnedShipMetaRepair.ship_id.asc(), OwnedShipMetaRepair.repair_id.asc())
        )
        out: dict[int, list[int]] = {}
        for row in result.all():
            sid = row[0]
            rid = row[1]
            if sid not in out:
                out[sid] = []
            out[sid].append(rid)
        return out
