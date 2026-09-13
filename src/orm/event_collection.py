from __future__ import annotations

from typing import Optional

from sqlalchemy import BigInteger, JSON, SmallInteger, select
from sqlalchemy.orm import Mapped, mapped_column

from src.db.session import Base, get_session, get_sync_session


# Commission instance state machine.
STATE_AVAILABLE = 0   # offered to the player, not yet started (has an expires_at)
STATE_STARTED = 1     # ships dispatched, counting down to finish_time
STATE_READY = 2       # finish_time reached, awaiting collection

# Commission "spawn class" — not the collection_template `type`, but the
# lifecycle class used by the spawner (daily pool vs. urgent).
TYPE_DAILY = 1
TYPE_URGENT = 2


async def list_commissions(commander_id: int) -> list:
    async with get_session() as session:
        result = await session.execute(
            select(EventCollection).where(EventCollection.commander_id == commander_id)
        )
        return list(result.scalars().all())


def list_commissions_sync(commander_id: int) -> list:
    with get_sync_session() as session:
        result = session.execute(
            select(EventCollection).where(EventCollection.commander_id == commander_id)
        )
        return list(result.scalars().all())


# Backwards-compatible alias used by existing call sites.
list_active_event_collections_sync = list_commissions_sync


def get_commission_sync(row_id: int) -> Optional["EventCollection"]:
    with get_sync_session() as session:
        return session.get(EventCollection, row_id)


def get_commission_by_template_sync(
    commander_id: int, commission_id: int, state: Optional[int] = None
) -> Optional["EventCollection"]:
    """Resolve a player's commission row by template id. Because of the
    no-duplicate rule, at most one active row exists per (commander, template),
    so this is unambiguous. When `state` is given, only that state is matched."""
    with get_sync_session() as session:
        stmt = select(EventCollection).where(
            EventCollection.commander_id == commander_id,
            EventCollection.commission_id == commission_id,
        )
        if state is not None:
            stmt = stmt.where(EventCollection.state == state)
        rows = session.execute(stmt).scalars().all()
        if not rows:
            return None
        if state is not None:
            return rows[0]
        # Prefer an available row (not yet started) for dispatch resolution.
        for r in rows:
            if r.state == STATE_AVAILABLE:
                return r
        return rows[0]


def count_started_sync(commander_id: int) -> int:
    with get_sync_session() as session:
        result = session.execute(
            select(EventCollection).where(
                EventCollection.commander_id == commander_id,
                EventCollection.state == STATE_STARTED,
            )
        )
        return len(result.scalars().all())


def count_spawned_since_sync(commander_id: int, commission_ids, since_ts: int) -> int:
    """How many rows with the given template ids were SPAWNED for this commander
    since `since_ts` (any state — includes already-collected offers? no: collected
    rows are deleted; this counts the offers still on the board). Used for the
    wiki's "first 10 daily commissions generated in a day are Resource Extraction"
    rule, which is derived from the persisted spawn_time instead of a separate
    per-day counter."""
    ids = list(commission_ids)
    if not ids:
        return 0
    with get_sync_session() as session:
        result = session.execute(
            select(EventCollection).where(
                EventCollection.commander_id == commander_id,
                EventCollection.commission_id.in_(ids),
                EventCollection.spawn_time >= since_ts,
            )
        )
        return len(result.scalars().all())


def count_available_type_sync(commander_id: int, ctype: int) -> int:
    with get_sync_session() as session:
        result = session.execute(
            select(EventCollection).where(
                EventCollection.commander_id == commander_id,
                EventCollection.type == ctype,
                EventCollection.state == STATE_AVAILABLE,
            )
        )
        return len(result.scalars().all())


def delete_expired_available_sync(commander_id: int, now: int) -> int:
    with get_sync_session() as session:
        rows = session.execute(
            select(EventCollection).where(
                EventCollection.commander_id == commander_id,
                EventCollection.state == STATE_AVAILABLE,
                EventCollection.expires_at > 0,
                EventCollection.expires_at < now,
            )
        ).scalars().all()
        n = len(rows)
        for r in rows:
            session.delete(r)
        session.commit()
        return n


def delete_available_night_sync(commander_id: int, night_ids) -> int:
    """Remove unstarted (available) night commissions whose template id is in
    `night_ids`. Started night commissions are left untouched: the client shows
    executing/executed missions at any time, so the player can still collect
    them and free their ships. Used to clear night commissions outside the
    client's night window (gameset night_collection_begin/end) so an available
    night commission whose over_time lapses can never sit hidden as StateExpire."""
    ids = list(night_ids)
    if not ids:
        return 0
    with get_sync_session() as session:
        rows = session.execute(
            select(EventCollection).where(
                EventCollection.commander_id == commander_id,
                EventCollection.commission_id.in_(ids),
                EventCollection.state == STATE_AVAILABLE,
            )
        ).scalars().all()
        n = len(rows)
        for r in rows:
            session.delete(r)
        session.commit()
        return n


def delete_commission_sync(row_id: int):
    with get_sync_session() as session:
        obj = session.get(EventCollection, row_id)
        if obj is not None:
            session.delete(obj)
            session.commit()


def save_commission_sync(obj: "EventCollection"):
    with get_sync_session() as session:
        session.add(obj)
        session.commit()


def insert_commission_sync(
    commander_id: int,
    commission_id: int,
    ctype: int,
    state: int,
    ship_ids: Optional[list],
    start_time: int = 0,
    finish_time: int = 0,
    spawn_time: int = 0,
    expires_at: int = 0,
    created_at: int = 0,
) -> int:
    with get_sync_session() as session:
        obj = EventCollection(
            commander_id=commander_id,
            commission_id=commission_id,
            type=ctype,
            state=state,
            ship_ids=ship_ids if ship_ids is not None else [],
            start_time=start_time,
            finish_time=finish_time,
            spawn_time=spawn_time,
            expires_at=expires_at,
            created_at=created_at,
        )
        session.add(obj)
        session.commit()
        return obj.id


def update_commission_sync(
    row_id: int,
    state: Optional[int] = None,
    ship_ids: Optional[list] = None,
    start_time: Optional[int] = None,
    finish_time: Optional[int] = None,
    expires_at: Optional[int] = None,
    spawn_time: Optional[int] = None,
):
    with get_sync_session() as session:
        obj = session.get(EventCollection, row_id)
        if obj is None:
            return
        if state is not None:
            obj.state = state
        if ship_ids is not None:
            obj.ship_ids = ship_ids
        if start_time is not None:
            obj.start_time = start_time
        if finish_time is not None:
            obj.finish_time = finish_time
        if expires_at is not None:
            obj.expires_at = expires_at
        if spawn_time is not None:
            obj.spawn_time = spawn_time
        session.commit()


class EventCollection(Base):
    __tablename__ = 'event_collections'
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    commander_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    commission_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    type: Mapped[int] = mapped_column(SmallInteger, default=TYPE_DAILY)
    state: Mapped[int] = mapped_column(SmallInteger, default=STATE_AVAILABLE)
    ship_ids: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    start_time: Mapped[int] = mapped_column(BigInteger, default=0)
    finish_time: Mapped[int] = mapped_column(BigInteger, default=0)
    spawn_time: Mapped[int] = mapped_column(BigInteger, default=0)
    expires_at: Mapped[int] = mapped_column(BigInteger, default=0)
    created_at: Mapped[int] = mapped_column(BigInteger, default=0)
