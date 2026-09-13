from __future__ import annotations

from src.db.session import Base

from sqlalchemy import select

from src.db.session import get_sync_session
from sqlalchemy import BigInteger
from sqlalchemy.orm import Mapped, mapped_column

def upsert_owned_ship_transform(commander_id: int, ship_id: int, transform_id: int, level: int) -> None:
    with get_sync_session() as session:
        existing = session.execute(
            select(OwnedShipTransform).where(
                OwnedShipTransform.owner_id == commander_id,
                OwnedShipTransform.ship_id == ship_id,
                OwnedShipTransform.transform_id == transform_id,
            )
        ).scalar_one_or_none()
        if existing is not None:
            existing.level = level
        else:
            session.add(OwnedShipTransform(
                owner_id=commander_id,
                ship_id=ship_id,
                transform_id=transform_id,
                level=level,
            ))
        session.commit()

def delete_owned_ship_transforms(commander_id: int, ship_id: int, edit_trans: list) -> None:
    with get_sync_session() as session:
        for tid in edit_trans:
            existing = session.execute(
                select(OwnedShipTransform).where(
                    OwnedShipTransform.owner_id == commander_id,
                    OwnedShipTransform.ship_id == ship_id,
                    OwnedShipTransform.transform_id == tid,
                )
            ).scalar_one_or_none()
            if existing is not None:
                session.delete(existing)
        session.commit()

def list_owned_ship_transforms_grouped(commander_id: int) -> dict[int, list]:
    """All owned_ship_transforms for a commander, grouped by ship_id."""
    with get_sync_session() as session:
        result = session.execute(
            select(OwnedShipTransform).where(
                OwnedShipTransform.owner_id == commander_id
            ).order_by(OwnedShipTransform.transform_id)
        )
        grouped: dict[int, list] = {}
        for row in result.scalars().all():
            grouped.setdefault(row.ship_id, []).append(row)
        return grouped

class OwnedShipTransform(Base):
    __tablename__ = 'owned_ship_transforms'
    owner_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    ship_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    transform_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    level: Mapped[int] = mapped_column(BigInteger, default=0)
