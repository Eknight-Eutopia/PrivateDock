from __future__ import annotations

from src.db.session import Base


from sqlalchemy import select
from sqlalchemy.orm import Mapped, mapped_column

from src.db.session import get_sync_session
from sqlalchemy import BigInteger
from sqlalchemy.orm import Mapped, mapped_column

def list_owned_ship_strengths(commander_id: int, ship_id: int) -> list:
    with get_sync_session() as session:
        result = session.execute(
            select(OwnedShipStrength).where(
                OwnedShipStrength.owner_id == commander_id,
                OwnedShipStrength.ship_id == ship_id,
            )
        )
        return list(result.scalars().all())

def list_all_owned_ship_strengths(commander_id: int, ship_ids: list) -> list:
    if not ship_ids:
        return []
    with get_sync_session() as session:
        result = session.execute(
            select(OwnedShipStrength).where(
                OwnedShipStrength.owner_id == commander_id,
                OwnedShipStrength.ship_id.in_(ship_ids),
            )
        )
        return list(result.scalars().all())

def upsert_owned_ship_strength(*args) -> None:
    with get_sync_session() as session:
        if len(args) == 4:
            commander_id, ship_id, strength_id, exp = args
        elif len(args) == 1 and isinstance(args[0], dict):
            d = args[0]
            commander_id = d.get("owner_id", 0)
            ship_id = d.get("ship_id", 0)
            strength_id = d.get("strength_id", 1)
            exp = d.get("exp", 0)
        else:
            raise TypeError(f"upsert_owned_ship_strength: unexpected args {args}")
        existing = session.execute(
            select(OwnedShipStrength).where(
                OwnedShipStrength.owner_id == commander_id,
                OwnedShipStrength.ship_id == ship_id,
                OwnedShipStrength.strength_id == strength_id,
            )
        ).scalar_one_or_none()
        if existing is not None:
            existing.exp = exp
        else:
            session.add(OwnedShipStrength(
                owner_id=commander_id,
                ship_id=ship_id,
                strength_id=strength_id,
                exp=exp,
            ))
        session.commit()

class OwnedShipStrength(Base):
    __tablename__ = 'owned_ship_strengths'
    owner_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    ship_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    strength_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    exp: Mapped[int] = mapped_column(BigInteger, default=0)
