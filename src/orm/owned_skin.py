from __future__ import annotations
from datetime import datetime
from typing import Any, Optional

from sqlalchemy import text
from sqlalchemy import BigInteger, DateTime
from sqlalchemy.orm import Mapped, mapped_column

from src.db.session import Base, get_session


# ── Async ORM query functions (for api/handlers) ──


async def list_owned_skins(commander_id: int) -> list[dict[str, Any]]:
    async with get_session() as session:
        result = await session.execute(
            text("SELECT skin_id, expires_at FROM owned_skins WHERE commander_id = :cid"),
            {"cid": commander_id},
        )
        return [dict(r) for r in result.mappings().all()]


async def get_owned_skin(commander_id: int, skin_id: int) -> Optional[dict[str, Any]]:
    async with get_session() as session:
        result = await session.execute(
            text("SELECT skin_id, expires_at FROM owned_skins WHERE commander_id = :cid AND skin_id = :sid"),
            {"cid": commander_id, "sid": skin_id},
        )
        row = result.mappings().first()
        return dict(row) if row else None


async def upsert_owned_skin(commander_id: int, skin_id: int, expires_at: Optional[str]) -> None:
    async with get_session() as session:
        if expires_at is not None:
            await session.execute(
                text("INSERT INTO owned_skins (commander_id, skin_id, expires_at) "
                     "VALUES (:cid, :sid, :exp) "
                     "ON CONFLICT (commander_id, skin_id) DO UPDATE SET expires_at = :exp"),
                {"cid": commander_id, "sid": skin_id, "exp": expires_at},
            )
        else:
            await session.execute(
                text("INSERT INTO owned_skins (commander_id, skin_id) "
                     "VALUES (:cid, :sid) "
                     "ON CONFLICT (commander_id, skin_id) DO NOTHING"),
                {"cid": commander_id, "sid": skin_id},
            )
        await session.commit()


async def update_owned_skin_expires(commander_id: int, skin_id: int, expires_at: str) -> None:
    async with get_session() as session:
        await session.execute(
            text("UPDATE owned_skins SET expires_at = :exp WHERE commander_id = :cid AND skin_id = :sid"),
            {"exp": expires_at, "cid": commander_id, "sid": skin_id},
        )
        await session.commit()


async def delete_owned_skin(commander_id: int, skin_id: int) -> None:
    async with get_session() as session:
        await session.execute(
            text("DELETE FROM owned_skins WHERE commander_id = :cid AND skin_id = :sid"),
            {"cid": commander_id, "sid": skin_id},
        )
        await session.commit()

def _sync_give_skin(commander_id: int, skin_id: int) -> bool:
    from src.orm.skin import give_skin as _real_give_skin
    return _real_give_skin(commander_id, skin_id)

give_skin = _sync_give_skin

class OwnedSkin(Base):
    __tablename__ = 'owned_skins'
    commander_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    skin_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

class OwnedShipShadowSkin(Base):
    __tablename__ = 'owned_ship_shadow_skins'
    __table_args__ = {}
    commander_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    ship_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    shadow_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    skin_id: Mapped[int] = mapped_column(BigInteger, default=0)
