from __future__ import annotations
import json
from typing import Any, Optional

from sqlalchemy import select, text
from sqlalchemy import BigInteger, String, JSON
from sqlalchemy.orm import Mapped, mapped_column

from src.consts.fleet import SUBMARINE_FLEET_ID
from src.db.session import Base, get_session, get_sync_session


def ensure_submarine_fleet(commander_id: int) -> None:
    with get_sync_session() as session:
        session.execute(
            text(
                "INSERT INTO fleets (commander_id, game_id, name, ship_list, meowfficer_list) "
                "VALUES (:cid, :gid, '', '[]'::jsonb, '[]'::jsonb) "
                "ON CONFLICT (commander_id, game_id) DO NOTHING"
            ),
            {"cid": commander_id, "gid": SUBMARINE_FLEET_ID},
        )
        session.commit()


# ── Async ORM query functions (for api/handlers) ──


async def list_fleets(commander_id: int) -> list[dict[str, Any]]:
    async with get_session() as session:
        result = await session.execute(
            text("SELECT id, name FROM fleets WHERE commander_id = :cid"),
            {"cid": commander_id},
        )
        return [dict(r) for r in result.mappings().all()]


async def list_fleet_ships(fleet_id: int) -> list[int]:
    async with get_session() as session:
        result = await session.execute(
            text("SELECT ship_list FROM fleets WHERE id = :fid"),
            {"fid": fleet_id},
        )
        row = result.first()
        if not row or not row[0]:
            return []
        raw = row[0]
        if isinstance(raw, str):
            try:
                raw = json.loads(raw)
            except Exception:
                return []
        if isinstance(raw, list):
            return [int(x) for x in raw if isinstance(x, (int, float, str)) and str(x).isdigit()]
        return []


async def get_fleet(commander_id: int, fleet_id: int) -> Optional[dict[str, Any]]:
    async with get_session() as session:
        result = await session.execute(
            text("SELECT id, name FROM fleets WHERE commander_id = :cid AND id = :fid"),
            {"cid": commander_id, "fid": fleet_id},
        )
        row = result.mappings().first()
        return dict(row) if row else None


async def create_fleet_row(fleet_id: int, commander_id: int, name: str) -> None:
    async with get_session() as session:
        await session.execute(
            text(
                "INSERT INTO fleets (id, commander_id, game_id, name) "
                "VALUES (:fid, :cid, :gid, :nm) "
                "ON CONFLICT (commander_id, game_id) DO NOTHING"
            ),
            {"fid": fleet_id, "cid": commander_id, "gid": fleet_id, "nm": name},
        )
        await session.commit()


async def add_fleet_ship(fleet_id: int, ship_id: int) -> None:
    ships = await list_fleet_ships(fleet_id)
    if ship_id not in ships:
        ships.append(ship_id)
    async with get_session() as session:
        await session.execute(
            text("UPDATE fleets SET ship_list = :ships WHERE id = :fid"),
            {"ships": json.dumps(ships), "fid": fleet_id},
        )
        await session.commit()


async def update_fleet_name(fleet_id: int, name: str) -> None:
    async with get_session() as session:
        await session.execute(
            text("UPDATE fleets SET name = :nm WHERE id = :fid"),
            {"nm": name, "fid": fleet_id},
        )
        await session.commit()


async def clear_fleet_ships(fleet_id: int) -> None:
    async with get_session() as session:
        await session.execute(
            text("UPDATE fleets SET ship_list = '[]' WHERE id = :fid"),
            {"fid": fleet_id},
        )
        await session.commit()


async def delete_fleet(commander_id: int, fleet_id: int) -> None:
    async with get_session() as session:
        await session.execute(
            text("DELETE FROM fleets WHERE commander_id = :cid AND id = :fid"),
            {"cid": commander_id, "fid": fleet_id},
        )
        await session.commit()

def get_fleet_by_game_id(commander_id: int, game_id: int) -> Optional[Fleet]:
    with get_sync_session() as session:
        return session.execute(
            select(Fleet).where(
                Fleet.commander_id == commander_id,
                Fleet.game_id == game_id,
            )
        ).scalar_one_or_none()


def create_fleet(commander_id: int, fleet_name: str = "", game_id: int = 1) -> Fleet:
    with get_sync_session() as session:
        fleet = Fleet(
            commander_id=commander_id,
            game_id=game_id,
            name=fleet_name,
        )
        session.add(fleet)
        session.commit()
        session.refresh(fleet)
        return fleet


def update_fleet_ships( fleet_id: int, ship_ids: list) -> Fleet:
    with get_sync_session() as session:
        fleet = session.get(Fleet, fleet_id)
        if fleet is None:
            raise ValueError(f"fleet {fleet_id} not found")
        fleet.ship_list = ship_ids
        session.commit()
        session.refresh(fleet)
        return fleet

def rename_fleet(fleet_id: int, new_name: str):
    with get_sync_session() as session:
        fleet = session.get(Fleet, fleet_id)
        if fleet is not None:
            fleet.name = new_name
            session.commit()

class Fleet(Base):
    __tablename__ = 'fleets'
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    game_id: Mapped[int] = mapped_column(BigInteger)
    commander_id: Mapped[int] = mapped_column(BigInteger)
    name: Mapped[str] = mapped_column(String, default='')
    ship_list: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    meowfficer_list: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
