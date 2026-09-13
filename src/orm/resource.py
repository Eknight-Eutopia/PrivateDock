from __future__ import annotations
from typing import Any, Optional

from sqlalchemy import select, text
from sqlalchemy import BigInteger, String
from sqlalchemy.orm import Mapped, mapped_column

from src.db.session import Base, get_session, get_sync_session

RESOURCE_ALIASES = {14: 4}


# ── Async ORM query functions (for api/handlers) ──


async def list_all_resource_types() -> list[dict[str, Any]]:
    async with get_session() as session:
        result = await session.execute(text("SELECT id, name FROM resources ORDER BY id"))
        return [dict(r) for r in result.mappings().all()]


async def list_owned_resources_by_commander(commander_id: int) -> list[dict[str, Any]]:
    async with get_session() as session:
        result = await session.execute(
            text("SELECT resource_id, amount FROM owned_resources WHERE commander_id = :cid"),
            {"cid": commander_id},
        )
        return [dict(r) for r in result.mappings().all()]


def list_owned_resources_sync(commander_id: int) -> list[dict[str, Any]]:
    with get_sync_session() as session:
        result = session.execute(
            text("SELECT resource_id, amount FROM owned_resources WHERE commander_id = :cid"),
            {"cid": commander_id},
        )
        return [dict(r) for r in result.mappings().all()]


async def get_owned_resource(commander_id: int, resource_id: int) -> Optional[dict[str, Any]]:
    async with get_session() as session:
        result = await session.execute(
            text("SELECT resource_id, amount FROM owned_resources WHERE commander_id = :cid AND resource_id = :rid"),
            {"cid": commander_id, "rid": resource_id},
        )
        row = result.mappings().first()
        return dict(row) if row else None


async def get_resource_name(resource_id: int) -> Optional[str]:
    async with get_session() as session:
        result = await session.execute(
            text("SELECT name FROM resources WHERE id = :rid"),
            {"rid": resource_id},
        )
        row = result.first()
        return row[0] if row else None


async def delete_owned_resource(commander_id: int, resource_id: int) -> str:
    async with get_session() as session:
        result = await session.execute(
            text("DELETE FROM owned_resources WHERE commander_id = :cid AND resource_id = :rid"),
            {"cid": commander_id, "rid": resource_id},
        )
        await session.commit()
        return f"DELETE {result.rowcount}"


async def upsert_owned_resource(commander_id: int, resource_id: int, amount: int) -> None:
    async with get_session() as session:
        await session.execute(
            text("INSERT INTO owned_resources (commander_id, resource_id, amount) "
                 "VALUES (:cid, :rid, :amt) "
                 "ON CONFLICT (commander_id, resource_id) DO UPDATE SET amount = :amt"),
            {"cid": commander_id, "rid": resource_id, "amt": amount},
        )
        await session.commit()


async def has_enough_resource_async(commander_id: int, resource_id: int, amount: int) -> bool:
    resource_id = dealias_resource(resource_id)
    async with get_session() as session:
        result = await session.execute(
            text("SELECT 1 FROM owned_resources WHERE commander_id = :cid AND resource_id = :rid AND amount >= :amt LIMIT 1"),
            {"cid": commander_id, "rid": resource_id, "amt": amount},
        )
        return result.first() is not None


async def consume_resource_async(commander_id: int, resource_id: int, amount: int) -> None:
    resource_id = dealias_resource(resource_id)
    async with get_session() as session:
        result = await session.execute(
            text("UPDATE owned_resources SET amount = amount - :amt WHERE commander_id = :cid AND resource_id = :rid AND amount >= :amt"),
            {"cid": commander_id, "rid": resource_id, "amt": amount},
        )
        await session.commit()
        if result.rowcount:
            # rowcount 0 = insufficient balance, nothing was consumed.
            _audit_if_tracked(resource_id, "consume", commander_id, -amount)
            try:
                from src.orm.active_commander import _bump_amount_map
                _bump_amount_map(commander_id, "owned_resources_map", resource_id, -amount, "resource_id")
            except Exception:
                pass


def dealias_resource(resource_id: int) -> int:
    return RESOURCE_ALIASES.get(resource_id, resource_id)


class Resource(Base):
    __tablename__ = 'resources'
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    item_id: Mapped[int] = mapped_column(BigInteger, default=0)
    name: Mapped[str] = mapped_column(String(128), default="")


class OwnedResource(Base):
    __tablename__ = 'owned_resources'
    commander_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    resource_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    amount: Mapped[int] = mapped_column(BigInteger, default=0)


def list_all_resources() -> list:
    with get_sync_session() as session:
        rows = session.execute(
            select(Resource).order_by(Resource.id.asc())
        ).scalars().all()
        return list(rows)


def get_owned_resource_amount(commander_id: int, resource_id: int) -> int:
    resource_id = dealias_resource(resource_id)
    with get_sync_session() as session:
        result = session.execute(
            select(OwnedResource.amount).where(
                OwnedResource.commander_id == commander_id,
                OwnedResource.resource_id == resource_id,
            )
        )
        return result.scalar_one_or_none() or 0


def has_enough_resource(commander_id: int, resource_id: int, amount: int) -> bool:
    resource_id = dealias_resource(resource_id)
    with get_sync_session() as session:
        result = session.execute(
            select(OwnedResource).where(
                OwnedResource.commander_id == commander_id,
                OwnedResource.resource_id == resource_id,
            )
        )
        obj = result.scalar_one_or_none()
        return obj is not None and obj.amount >= amount


_AUDIT_RES_IDS = {2: "Oil", 8: "GuildCoin"}
_AUDIT_PASS_THROUGH = ("src.orm.resource", "src.orm.commander")


def _resource_audit(res_name: str, action: str, commander_id: int, amount: int):
    """Traceability for the audited balances (oil, guild coins): every real
    delta is logged with the calling site, so an unexplained jump can be
    attributed from the server log alone."""
    try:
        import sys
        from src.logger.logger import log_event, LOG_LEVEL_INFO
        caller = "?"
        frame = sys._getframe(2)  # skip _resource_audit and its add/consume wrapper
        while frame is not None:
            name = frame.f_globals.get("__name__", "")
            if not name.startswith(_AUDIT_PASS_THROUGH):
                caller = f"{name}.{frame.f_code.co_name}"
                break
            frame = frame.f_back
        log_event(f"{res_name}Audit", action,
                  f"commander={commander_id} delta={amount} caller={caller}",
                  LOG_LEVEL_INFO)
    except Exception:
        pass


def _audit_if_tracked(resource_id: int, action: str, commander_id: int, amount: int):
    res_name = _AUDIT_RES_IDS.get(resource_id)
    if res_name is not None:
        _resource_audit(res_name, action, commander_id, amount)


def add_resource(commander_id: int, resource_id: int, amount: int):
    resource_id = dealias_resource(resource_id)
    with get_sync_session() as session:
        result = session.execute(
            select(OwnedResource).where(
                OwnedResource.commander_id == commander_id,
                OwnedResource.resource_id == resource_id,
            )
        )
        obj = result.scalar_one_or_none()
        if obj is None:
            obj = OwnedResource(commander_id=commander_id, resource_id=resource_id, amount=amount)
            session.add(obj)
        else:
            obj.amount += amount
        session.commit()
        _audit_if_tracked(resource_id, "add", commander_id, amount)
        # Keep the in-memory owned_resources_map in sync.
        try:
            from src.orm.active_commander import _bump_amount_map
            _bump_amount_map(commander_id, "owned_resources_map", resource_id, amount, "resource_id")
        except Exception:
            pass


def consume_resource(commander_id: int, resource_id: int, amount: int):
    resource_id = dealias_resource(resource_id)
    with get_sync_session() as session:
        result = session.execute(
            select(OwnedResource).where(
                OwnedResource.commander_id == commander_id,
                OwnedResource.resource_id == resource_id,
            )
        )
        obj = result.scalar_one_or_none()
        if obj is not None:
            obj.amount -= amount
            if obj.amount < 0:
                obj.amount = 0
            session.commit()
            _audit_if_tracked(resource_id, "consume", commander_id, -amount)
            try:
                from src.orm.active_commander import _bump_amount_map
                _bump_amount_map(commander_id, "owned_resources_map", resource_id, -amount, "resource_id")
            except Exception:
                pass
    # Server-authoritative task progress: spending Oil (resource_id 2) advances
    # "Spend a total of X Oil" tasks (sub_type 121). The connected client is
    # resolved from the active-client registry; if none (offline/background),
    # the emit is skipped. Imports are lazy to avoid a circular import with
    # task_handlers.
    if resource_id == 2 and amount > 0:
        try:
            from src.orm.active_commander import get_active_client
            client = get_active_client(commander_id)
            if client is not None:
                from src.answer.task_handlers import schedule_emit
                schedule_emit(client, 121, 0, amount)
        except Exception:
            pass


def upsert_resource_amount(commander_id: int, resource_id: int, amount: int):
    resource_id = dealias_resource(resource_id)
    if resource_id in _AUDIT_RES_IDS:
        # An absolute write REPLACES the balance — audit the effective delta.
        _audit_if_tracked(resource_id, "set", commander_id,
                          amount - get_resource_amount(commander_id, resource_id))
    with get_sync_session() as session:
        result = session.execute(
            select(OwnedResource).where(
                OwnedResource.commander_id == commander_id,
                OwnedResource.resource_id == resource_id,
            )
        )
        obj = result.scalar_one_or_none()
        if obj is None:
            obj = OwnedResource(commander_id=commander_id, resource_id=resource_id, amount=amount)
            session.add(obj)
        else:
            obj.amount = amount
        session.commit()


def list_owned_resources(commander_id: int) -> list:
    with get_sync_session() as session:
        result = session.execute(
            select(OwnedResource).where(OwnedResource.commander_id == commander_id)
        )
        return list(result.scalars().all())


def get_resource_amount(commander_id: int, resource_id: int) -> int:
    """Current amount of one owned resource (0 when the row does not exist)."""
    resource_id = dealias_resource(resource_id)
    with get_sync_session() as session:
        result = session.execute(
            select(OwnedResource.amount).where(
                OwnedResource.commander_id == commander_id,
                OwnedResource.resource_id == resource_id,
            )
        )
        row = result.first()
        return int(row[0] or 0) if row else 0
