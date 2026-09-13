from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select, text

from src.db.session import get_session, get_sync_session
from src.orm.remaster_state import RemasterState
from src.region.region import local_now


async def _async_get_or_create_remaster_state(commander_id: int) -> RemasterState:
    async with get_session() as session:
        result = await session.execute(
            select(RemasterState).where(
                RemasterState.commander_id == commander_id,
            )
        )
        state = result.scalar_one_or_none()
        if state is None:
            now = datetime.now(timezone.utc)
            epoch = datetime.fromtimestamp(0, tz=timezone.utc)
            state = RemasterState(
                commander_id=commander_id,
                last_daily_reset_at=epoch,
                created_at=now,
                updated_at=now,
            )
            session.add(state)
            await session.commit()
        return state


# ── Sync CRUD ──


def _sync_get_or_create_remaster_state(commander_id: int) -> RemasterState:
    with get_sync_session() as session:
        result = session.execute(
            select(RemasterState).where(RemasterState.commander_id == commander_id)
        )
        state = result.scalar_one_or_none()
        if state is None:
            now = datetime.now(timezone.utc)
            epoch = datetime.fromtimestamp(0, tz=timezone.utc)
            state = RemasterState(
                commander_id=commander_id,
                last_daily_reset_at=epoch,
                created_at=now,
                updated_at=now,
            )
            session.add(state)
            session.commit()
        return state


_SQL_DAILY_RESET = text("""
    UPDATE remaster_states SET daily_count = 0,
        last_daily_reset_at = :reset_at
    WHERE commander_id = :cid
      AND (last_daily_reset_at IS NULL OR last_daily_reset_at < :today_start)
""")

_SQL_SET_ACTIVE_CHAPTER = text(
    "UPDATE remaster_states SET active_chapter_id = :aid WHERE commander_id = :cid"
)

_SQL_UPDATE_TICKETS = text(
    "UPDATE remaster_states SET ticket_count = :tickets, daily_count = :daily WHERE commander_id = :cid"
)

_SQL_TRY_CONSUME_TICKETS = text(
    "UPDATE remaster_states SET ticket_count = ticket_count - :amount "
    "WHERE commander_id = :cid AND ticket_count >= :amount"
)


def _sync_apply_remaster_daily_reset(commander_id: int) -> Optional[RemasterState]:
    with get_sync_session() as session:
        today_start = local_now().replace(hour=0, minute=0, second=0, microsecond=0)
        session.execute(
            _SQL_DAILY_RESET,
            {"cid": commander_id, "reset_at": today_start, "today_start": today_start},
        )
        session.commit()
        result = session.execute(
            select(RemasterState).where(RemasterState.commander_id == commander_id)
        )
        return result.scalar_one_or_none()


async def save_remaster_state(state: RemasterState):
    async with get_session() as session:
        session.add(state)
        await session.commit()


async def _async_apply_remaster_daily_reset(commander_id: int):
    async with get_session() as session:
        today_start = local_now().replace(hour=0, minute=0, second=0, microsecond=0)
        await session.execute(
            _SQL_DAILY_RESET,
            {"cid": commander_id, "reset_at": today_start, "today_start": today_start},
        )
        await session.commit()


def set_remaster_active_chapter_sync(commander_id: int, active_chapter_id: int) -> None:
    with get_sync_session() as session:
        session.execute(
            _SQL_SET_ACTIVE_CHAPTER,
            {"aid": active_chapter_id, "cid": commander_id},
        )
        session.commit()


async def aset_remaster_active_chapter(commander_id: int, active_chapter_id: int) -> None:
    async with get_session() as session:
        await session.execute(
            _SQL_SET_ACTIVE_CHAPTER,
            {"aid": active_chapter_id, "cid": commander_id},
        )
        await session.commit()


def update_remaster_tickets_sync(commander_id: int, ticket_count: int, daily_count: int) -> None:
    with get_sync_session() as session:
        session.execute(
            _SQL_UPDATE_TICKETS,
            {"tickets": ticket_count, "daily": daily_count, "cid": commander_id},
        )
        session.commit()


async def aupdate_remaster_tickets(commander_id: int, ticket_count: int, daily_count: int) -> None:
    async with get_session() as session:
        await session.execute(
            _SQL_UPDATE_TICKETS,
            {"tickets": ticket_count, "daily": daily_count, "cid": commander_id},
        )
        await session.commit()


def try_consume_remaster_tickets_sync(commander_id: int, amount: int = 5) -> bool:
    with get_sync_session() as session:
        result = session.execute(
            _SQL_TRY_CONSUME_TICKETS,
            {"amount": amount, "cid": commander_id},
        )
        session.commit()
        return (result.rowcount or 0) > 0


async def atry_consume_remaster_tickets(commander_id: int, amount: int = 5) -> bool:
    async with get_session() as session:
        result = await session.execute(
            _SQL_TRY_CONSUME_TICKETS,
            {"amount": amount, "cid": commander_id},
        )
        await session.commit()
        return (result.rowcount or 0) > 0


get_or_create_remaster_state = _sync_get_or_create_remaster_state
aget_or_create_remaster_state = _async_get_or_create_remaster_state
apply_remaster_daily_reset = _sync_apply_remaster_daily_reset
aapply_remaster_daily_reset = _async_apply_remaster_daily_reset
