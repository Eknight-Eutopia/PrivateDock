from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from sqlalchemy import BigInteger, DateTime, text
from sqlalchemy.orm import Mapped, mapped_column

from src.db.session import Base, get_session, get_sync_session

ErrorNotEnoughQuickFinishers = ValueError("not enough quick finishers")


def _parse_finishes_at(value):
    """Raw ``text()`` reads bypass SA column types: on SQLite the driver hands
    ``finishes_at`` back as TEXT while asyncpg returns an aware datetime for
    timestamptz. Restore that parity so consumers doing arithmetic on the
    value (build timers, ``.tzinfo`` checks) never see a str."""
    if isinstance(value, str):
        from src.db import sqlite_types
        parsed = sqlite_types._convert_timestamp(value)
        if parsed is not None:
            return parsed
    return value


# ── Async ORM query functions (for api/handlers) ──


async def list_builds_for_builder(builder_id: int) -> list[dict[str, Any]]:
    async with get_session() as session:
        result = await session.execute(
            text("SELECT id, builder_id, ship_id, pool_id, finishes_at FROM builds WHERE builder_id = :bid ORDER BY id"),
            {"bid": builder_id},
        )
        rows = [dict(r) for r in result.mappings().all()]
        for r in rows:
            r["finishes_at"] = _parse_finishes_at(r["finishes_at"])
        return rows


async def list_build_queue(builder_id: int) -> list[dict[str, Any]]:
    async with get_session() as session:
        result = await session.execute(
            text("SELECT id, pool_id, finishes_at FROM builds WHERE builder_id = :bid ORDER BY id"),
            {"bid": builder_id},
        )
        rows = [dict(r) for r in result.mappings().all()]
        for r in rows:
            r["finishes_at"] = _parse_finishes_at(r["finishes_at"])
        return rows


async def create_build(builder_id: int, ship_id: int, pool_id: int, finishes_at: datetime) -> int:
    async with get_session() as session:
        result = await session.execute(
            text("INSERT INTO builds (builder_id, ship_id, pool_id, finishes_at) VALUES (:bid, :sid, :pid, :fa) RETURNING id"),
            {"bid": builder_id, "sid": ship_id, "pid": pool_id, "fa": finishes_at},
        )
        await session.commit()
        return result.scalar_one()


async def update_build_dynamic(build_id: int, **fields) -> None:
    if not fields:
        return
    set_clause = ", ".join(f"{k} = :{k}" for k in fields)
    params = {"bid": build_id}
    params.update(fields)
    async with get_session() as session:
        await session.execute(
            text(f"UPDATE builds SET {set_clause} WHERE id = :bid"),
            params,
        )
        await session.commit()


async def delete_build_by_id(build_id: int) -> None:
    async with get_session() as session:
        await session.execute(
            text("DELETE FROM builds WHERE id = :bid"),
            {"bid": build_id},
        )
        await session.commit()


class Build(Base):
    __tablename__ = 'builds'
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    builder_id: Mapped[int] = mapped_column(BigInteger)
    ship_id: Mapped[int] = mapped_column(BigInteger, default=0)
    pool_id: Mapped[int] = mapped_column(BigInteger, default=0)
    finishes_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    # 1 = started (running or finished); 0 = queued (waiting for a dock slot).
    state: Mapped[int] = mapped_column(BigInteger, default=1)


def build_create(builder_id: int, ship_id: int, pool_id: int, finishes_at: datetime) -> Optional[dict]:
    with get_sync_session() as session:
        row = session.execute(
            text("""
                INSERT INTO builds (builder_id, ship_id, pool_id, finishes_at)
                VALUES (:bid, :sid, :pid, :fa)
                RETURNING id
            """),
            {"bid": builder_id, "sid": ship_id, "pid": pool_id, "fa": finishes_at},
        ).fetchone()
        session.commit()
        if row is None:
            return None
        return {
            "id": row[0],
            "builder_id": builder_id,
            "ship_id": ship_id,
            "pool_id": pool_id,
            "finishes_at": finishes_at,
        }


def build_update(build_id: int, builder_id: int, ship_id: int, pool_id: int, finishes_at: datetime) -> None:
    with get_sync_session() as session:
        session.execute(
            text("""
                UPDATE builds
                SET builder_id = :bid, ship_id = :sid, pool_id = :pid, finishes_at = :fa
                WHERE id = :id
            """),
            {"id": build_id, "bid": builder_id, "sid": ship_id, "pid": pool_id, "fa": finishes_at},
        )
        session.commit()


def build_retrieve(build_id: int, greedy: bool = False) -> Optional[dict]:
    with get_sync_session() as session:
        row = session.execute(
            text("SELECT id, builder_id, ship_id, pool_id, finishes_at FROM builds WHERE id = :id"),
            {"id": build_id},
        ).fetchone()
        if row is None:
            return None
        result = {
            "id": row[0],
            "builder_id": row[1],
            "ship_id": row[2],
            "pool_id": row[3],
            "finishes_at": _parse_finishes_at(row[4]),
        }
        if greedy:
            ship = session.execute(
                text("SELECT * FROM ships WHERE template_id = :sid"),
                {"sid": result["ship_id"]},
            ).fetchone()
            if ship:
                result["ship"] = dict(ship._mapping)
            commander = session.execute(
                text("SELECT * FROM commanders WHERE commander_id = :cid AND deleted_at IS NULL"),
                {"cid": result["builder_id"]},
            ).fetchone()
            if commander:
                result["commander"] = dict(commander._mapping)
        return result


def build_delete(build_id: int) -> bool:
    with get_sync_session() as session:
        result = session.execute(
            text("DELETE FROM builds WHERE id = :id"),
            {"id": build_id},
        )
        session.commit()
        return result.rowcount > 0

'''
async def get_build_by_id(build_id: int) -> Optional[dict[str, Any]]:
    async with get_session() as session:
        result = await session.execute(
            text("SELECT * FROM builds WHERE id = :bid"),
            {"bid": build_id},
        )
        row = result.mappings().first()
        return dict(row) if row else None
'''

async def get_build_by_id(build_id: int) -> Optional[dict]:
    async with get_session() as session:
        row = (await session.execute(
            text("SELECT id, builder_id, ship_id, pool_id, finishes_at FROM builds WHERE id = :id"),
            {"id": build_id},
        )).fetchone()
        if row is None:
            return None
        return {
            "id": row[0],
            "builder_id": row[1],
            "ship_id": row[2],
            "pool_id": row[3],
            "finishes_at": _parse_finishes_at(row[4]),
        }


def list_builds_by_builder(builder_id: int) -> list[dict]:
    with get_sync_session() as session:
        rows = session.execute(
            text("SELECT id, builder_id, ship_id, pool_id, finishes_at FROM builds WHERE builder_id = :bid ORDER BY id ASC"),
            {"bid": builder_id},
        ).fetchall()
        return [
            {
                "id": r[0],
                "builder_id": r[1],
                "ship_id": r[2],
                "pool_id": r[3],
                "finishes_at": _parse_finishes_at(r[4]),
            }
            for r in rows
        ]


def list_builds_by_builder_and_pool(builder_id: int, pool_id: int) -> list[dict]:
    with get_sync_session() as session:
        rows = session.execute(
            text("""
                SELECT id, builder_id, ship_id, pool_id, finishes_at
                FROM builds
                WHERE builder_id = :bid AND pool_id = :pid
            """),
            {"bid": builder_id, "pid": pool_id},
        ).fetchall()
        return [
            {
                "id": r[0],
                "builder_id": r[1],
                "ship_id": r[2],
                "pool_id": r[3],
                "finishes_at": _parse_finishes_at(r[4]),
            }
            for r in rows
        ]


def build_consume(build_id: int, ship_id: int, commander_id: int) -> Optional[dict]:
    with get_sync_session() as session:
        build = session.execute(
            text("SELECT id, builder_id, ship_id, pool_id, finishes_at FROM builds WHERE id = :id"),
            {"id": build_id},
        ).fetchone()
        if build is None:
            raise ValueError("build not found")
        session.execute(text("DELETE FROM builds WHERE id = :id"), {"id": build_id})
        session.commit()

    # Ship creation goes through the single path (owned_ship.add_ship):
    # GLOBAL id allocation, auto-lock, proper starter stats (level=1,
    # max_level=70, intimacy=5000, energy=100, create_time) and default
    # equipment slots. The previous inline INSERT set only
    # id/owner/ship_id/is_locked, leaving level/max_level/intimacy/energy at
    # the model defaults (0) until the next login re-sync.
    from src.orm.owned_ship import add_ship
    owned_ship_id = add_ship(commander_id, ship_id).id
    return {
        "build_id": build_id,
        "ship_id": ship_id,
        "owned_ship_id": owned_ship_id,
    }


def build_quick_finish(build_id: int, commander_id: int) -> Optional[dict]:
    with get_sync_session() as session:
        has_item = session.execute(
            text("SELECT COUNT(*) FROM commander_items WHERE commander_id = :cid AND item_id = 15003 AND count > 0"),
            {"cid": commander_id},
        ).scalar() or 0
        if not has_item:
            raise ErrorNotEnoughQuickFinishers
        # ``CURRENT_TIMESTAMP - INTERVAL '1 second'`` is PostgreSQL-only. The
        # instant is computed here instead, which binds identically on both
        # engines and keeps the column's timezone semantics in one place.
        finishes_at = datetime.now(timezone.utc) - timedelta(seconds=1)
        session.execute(
            text("UPDATE builds SET finishes_at = :ts WHERE id = :id"),
            {"id": build_id, "ts": finishes_at},
        )
        session.execute(
            text("""
                UPDATE commander_items
                SET count = count - 1
                WHERE commander_id = :cid AND item_id = 15003 AND count > 0
            """),
            {"cid": commander_id},
        )
        session.commit()
        return build_retrieve(build_id)

