from __future__ import annotations
from typing import Any

from sqlalchemy import text
from sqlalchemy import BigInteger, Boolean
from sqlalchemy.orm import Mapped, mapped_column

from src.db.session import Base, get_session


# ── Async ORM query functions (for api/handlers) ──


async def list_random_flag_ship_rows(commander_id: int) -> list[dict[str, Any]]:
    async with get_session() as session:
        result = await session.execute(
            text("SELECT ship_id, phantom_id, enabled FROM random_flag_ships WHERE commander_id = :cid ORDER BY ship_id"),
            {"cid": commander_id},
        )
        return [dict(r) for r in result.mappings().all()]


async def upsert_random_flag_ship(commander_id: int, ship_id: int, phantom_id: int, enabled: bool) -> None:
    async with get_session() as session:
        await session.execute(
            text("INSERT INTO random_flag_ships (commander_id, ship_id, phantom_id, enabled) "
                 "VALUES (:cid, :sid, :pid, :en) ON CONFLICT (commander_id, ship_id) "
                 "DO UPDATE SET phantom_id = EXCLUDED.phantom_id, enabled = EXCLUDED.enabled"),
            {"cid": commander_id, "sid": ship_id, "pid": phantom_id, "en": enabled},
        )
        await session.commit()


async def delete_random_flag_ship(commander_id: int, ship_id: int) -> str:
    async with get_session() as session:
        result = await session.execute(
            text("DELETE FROM random_flag_ships WHERE commander_id = :cid AND ship_id = :sid"),
            {"cid": commander_id, "sid": ship_id},
        )
        await session.commit()
        return f"DELETE {result.rowcount}"

class RandomFlagShip(Base):
    __tablename__ = 'random_flag_ships'
    commander_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    ship_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    phantom_id: Mapped[int] = mapped_column(BigInteger, default=0)
    enabled: Mapped[bool] = mapped_column(Boolean, default=False)
