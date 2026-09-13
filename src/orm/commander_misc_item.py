from __future__ import annotations
from typing import Any, Optional

from sqlalchemy import BigInteger, text
from sqlalchemy.orm import Mapped, mapped_column

from src.db.session import Base, get_session, get_sync_session


# ── Async ORM query functions (for api/handlers) ──


async def list_commander_misc_items(commander_id: int) -> list[dict[str, Any]]:
    async with get_session() as session:
        result = await session.execute(
            text("SELECT item_id, data FROM commander_misc_items WHERE commander_id = :cid"),
            {"cid": commander_id},
        )
        return [dict(r) for r in result.mappings().all()]


def list_commander_misc_items_sync(commander_id: int) -> list[dict[str, Any]]:
    with get_sync_session() as session:
        result = session.execute(
            text("SELECT item_id, data FROM commander_misc_items WHERE commander_id = :cid"),
            {"cid": commander_id},
        )
        return [dict(r) for r in result.mappings().all()]


async def list_commander_misc_items_with_name(commander_id: int) -> list[dict[str, Any]]:
    async with get_session() as session:
        result = await session.execute(
            text("SELECT mi.item_id, mi.data, i.name FROM commander_misc_items mi "
                 "JOIN items i ON i.id = mi.item_id WHERE mi.commander_id = :cid"),
            {"cid": commander_id},
        )
        return [dict(r) for r in result.mappings().all()]


async def get_commander_misc_item(commander_id: int, item_id: int) -> Optional[dict[str, Any]]:
    async with get_session() as session:
        result = await session.execute(
            text("SELECT mi.item_id, mi.data, i.name FROM commander_misc_items mi "
                 "JOIN items i ON i.id = mi.item_id WHERE mi.commander_id = :cid AND mi.item_id = :iid"),
            {"cid": commander_id, "iid": item_id},
        )
        row = result.mappings().first()
        return dict(row) if row else None


async def get_commander_misc_item_data(commander_id: int, item_id: int) -> Optional[int]:
    async with get_session() as session:
        result = await session.execute(
            text("SELECT data FROM commander_misc_items WHERE commander_id = :cid AND item_id = :iid"),
            {"cid": commander_id, "iid": item_id},
        )
        row = result.first()
        return row[0] if row else None


async def upsert_commander_misc_item(commander_id: int, item_id: int, data: int) -> None:
    async with get_session() as session:
        await session.execute(
            text("INSERT INTO commander_misc_items (commander_id, item_id, data) "
                 "VALUES (:cid, :iid, :dat) "
                 "ON CONFLICT (commander_id, item_id) DO UPDATE SET data = :dat"),
            {"cid": commander_id, "iid": item_id, "dat": data},
        )
        await session.commit()


async def delete_commander_misc_item(commander_id: int, item_id: int) -> None:
    async with get_session() as session:
        await session.execute(
            text("DELETE FROM commander_misc_items WHERE commander_id = :cid AND item_id = :iid"),
            {"cid": commander_id, "iid": item_id},
        )
        await session.commit()


# ── SQLAlchemy model ──

class CommanderMiscItem(Base):
    __tablename__ = 'commander_misc_items'
    commander_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    item_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    data: Mapped[int] = mapped_column(BigInteger, default=0)
