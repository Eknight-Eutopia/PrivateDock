from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import BigInteger, Integer, DateTime, select, text, delete
from sqlalchemy.orm import Mapped, mapped_column

from src.db.session import Base, get_sync_session
from src.misc.safe_ts import safe_ts
from src.region.region import local_now

FOREVER_TIME = 4294967295


class ChapterAutoRecord(Base):
    __tablename__ = "chapter_auto_records"
    commander_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    type: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    chapter_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    seconds: Mapped[int] = mapped_column(Integer, default=0)


class ChapterAutoBattle(Base):
    __tablename__ = "chapter_auto_battles"
    commander_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    battle_index: Mapped[int] = mapped_column(Integer, primary_key=True)
    type: Mapped[int] = mapped_column(Integer, default=1)
    chapter_id: Mapped[int] = mapped_column(Integer, default=0)
    finish_time: Mapped[int] = mapped_column(BigInteger, default=0)
    ticket_time: Mapped[int] = mapped_column(BigInteger, default=0)
    seconds: Mapped[int] = mapped_column(Integer, default=0)


class ChapterAutoTicket(Base):
    __tablename__ = "chapter_auto_tickets"
    commander_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    ticket_type: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    expire_time: Mapped[int] = mapped_column(BigInteger, primary_key=True, default=0)
    count: Mapped[int] = mapped_column(Integer, default=0)


class ChapterAutoDaily(Base):
    __tablename__ = "chapter_auto_daily"
    commander_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    time_acc: Mapped[int] = mapped_column(Integer, default=0)
    extra_time_max: Mapped[int] = mapped_column(Integer, default=0)
    oil_bank: Mapped[int] = mapped_column(Integer, default=0)
    last_daily_reset_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


# ── Chapter Auto Records ──


def get_chapter_auto_records(commander_id: int) -> list[ChapterAutoRecord]:
    with get_sync_session() as session:
        result = session.execute(
            select(ChapterAutoRecord).where(
                ChapterAutoRecord.commander_id == commander_id
            )
        )
        return list(result.scalars().all())


def get_chapter_auto_record(commander_id: int, type_: int, chapter_id: int) -> Optional[ChapterAutoRecord]:
    with get_sync_session() as session:
        result = session.execute(
            select(ChapterAutoRecord).where(
                ChapterAutoRecord.commander_id == commander_id,
                ChapterAutoRecord.type == type_,
                ChapterAutoRecord.chapter_id == chapter_id,
            )
        )
        return result.scalar_one_or_none()


def upsert_chapter_auto_record(commander_id: int, type_: int, chapter_id: int, seconds: int) -> int:
    """Updates fastest clear record if new seconds < existing seconds (or if existing is 0).

    Returns the resulting fastest clear seconds.
    """
    if seconds <= 0:
        return 0

    with get_sync_session() as session:
        rec = session.execute(
            select(ChapterAutoRecord).where(
                ChapterAutoRecord.commander_id == commander_id,
                ChapterAutoRecord.type == type_,
                ChapterAutoRecord.chapter_id == chapter_id,
            )
        ).scalar_one_or_none()

        if rec is None:
            rec = ChapterAutoRecord(
                commander_id=commander_id,
                type=type_,
                chapter_id=chapter_id,
                seconds=seconds,
            )
            session.add(rec)
            session.commit()
            return seconds

        if rec.seconds <= 1 or seconds < rec.seconds:
            rec.seconds = seconds
            session.commit()
            return seconds

        return rec.seconds


# ── Active Battle Queue ──


def get_active_chapter_auto_battles(commander_id: int) -> list[ChapterAutoBattle]:
    with get_sync_session() as session:
        result = session.execute(
            select(ChapterAutoBattle)
            .where(ChapterAutoBattle.commander_id == commander_id)
            .order_by(ChapterAutoBattle.battle_index.asc())
        )
        return list(result.scalars().all())


def set_chapter_auto_battles(commander_id: int, battles: list[dict]) -> None:
    with get_sync_session() as session:
        session.execute(
            delete(ChapterAutoBattle).where(ChapterAutoBattle.commander_id == commander_id)
        )
        for i, b in enumerate(battles):
            obj = ChapterAutoBattle(
                commander_id=commander_id,
                battle_index=i + 1,
                type=b.get("type", 1),
                chapter_id=b.get("chapter_id", 0),
                finish_time=b.get("finish_time", 0),
                ticket_time=b.get("ticket_time", 0),
                seconds=b.get("seconds", 0),
            )
            session.add(obj)
        session.commit()


def clear_chapter_auto_battles(commander_id: int) -> None:
    with get_sync_session() as session:
        session.execute(
            delete(ChapterAutoBattle).where(ChapterAutoBattle.commander_id == commander_id)
        )
        session.commit()


# ── Chapter Auto Tickets ──


def _migrate_legacy_handover_items(commander_id: int) -> None:
    """Migrate any Handover Permit items previously stored in commander_items."""
    with get_sync_session() as session:
        rows = session.execute(
            text("SELECT item_id, count FROM commander_items WHERE commander_id = :cid AND item_id IN (68700, 68701, 68702)"),
            {"cid": commander_id},
        ).fetchall()
        if not rows:
            return
        session.execute(
            text("DELETE FROM commander_items WHERE commander_id = :cid AND item_id IN (68700, 68701, 68702)"),
            {"cid": commander_id},
        )
        session.commit()
    from src.orm.item import add_item
    for item_id, count in rows:
        if count > 0:
            add_item(commander_id, item_id, count)


def get_chapter_auto_tickets(commander_id: int, ticket_type: int = 1) -> list[ChapterAutoTicket]:
    """Returns unexpired tickets for commander, sorted by expire_time ascending."""
    _migrate_legacy_handover_items(commander_id)
    now_ts = int(local_now().timestamp())
    with get_sync_session() as session:
        result = session.execute(
            select(ChapterAutoTicket)
            .where(
                ChapterAutoTicket.commander_id == commander_id,
                ChapterAutoTicket.ticket_type == ticket_type,
                ChapterAutoTicket.count > 0,
                (ChapterAutoTicket.expire_time > now_ts) | (ChapterAutoTicket.expire_time == FOREVER_TIME),
            )
            .order_by(ChapterAutoTicket.expire_time.asc())
        )
        return list(result.scalars().all())


def add_chapter_auto_tickets(commander_id: int, ticket_type: int, count: int, expire_time: int) -> None:
    if count <= 0:
        return
    with get_sync_session() as session:
        result = session.execute(
            select(ChapterAutoTicket).where(
                ChapterAutoTicket.commander_id == commander_id,
                ChapterAutoTicket.ticket_type == ticket_type,
                ChapterAutoTicket.expire_time == expire_time,
            )
        )
        obj = result.scalar_one_or_none()
        if obj is None:
            obj = ChapterAutoTicket(
                commander_id=commander_id,
                ticket_type=ticket_type,
                expire_time=expire_time,
                count=count,
            )
            session.add(obj)
        else:
            obj.count += count
        session.commit()


def consume_chapter_auto_tickets(commander_id: int, ticket_type: int, count: int) -> list[tuple[int, int]]:
    """Consumes count tickets FIFO by expire_time.

    Returns list of (expire_time, count_consumed) or empty list if not enough tickets.
    """
    if count <= 0:
        return []

    now_ts = int(local_now().timestamp())
    consumed = []
    needed = count

    with get_sync_session() as session:
        rows = list(
            session.execute(
                select(ChapterAutoTicket)
                .where(
                    ChapterAutoTicket.commander_id == commander_id,
                    ChapterAutoTicket.ticket_type == ticket_type,
                    ChapterAutoTicket.count > 0,
                    (ChapterAutoTicket.expire_time > now_ts) | (ChapterAutoTicket.expire_time == FOREVER_TIME),
                )
                .order_by(ChapterAutoTicket.expire_time.asc())
            ).scalars().all()
        )

        total_avail = sum(r.count for r in rows)
        if total_avail < count:
            return []

        for row in rows:
            if needed <= 0:
                break
            take = min(row.count, needed)
            row.count -= take
            needed -= take
            consumed.append((row.expire_time, take))
            if row.count == 0:
                session.delete(row)

        session.commit()

    return consumed


def refund_chapter_auto_tickets(commander_id: int, ticket_type: int, tickets: list[tuple[int, int]]) -> None:
    for expire_time, count in tickets:
        if count > 0:
            add_chapter_auto_tickets(commander_id, ticket_type, count, expire_time)


# ── Chapter Auto Daily Limits & Bank ──


def get_or_create_chapter_auto_daily(commander_id: int) -> ChapterAutoDaily:
    with get_sync_session() as session:
        result = session.execute(
            select(ChapterAutoDaily).where(ChapterAutoDaily.commander_id == commander_id)
        )
        daily = result.scalar_one_or_none()
        if daily is None:
            today_start = local_now().replace(hour=0, minute=0, second=0, microsecond=0).astimezone(timezone.utc)
            daily = ChapterAutoDaily(
                commander_id=commander_id,
                time_acc=0,
                extra_time_max=0,
                oil_bank=0,
                last_daily_reset_at=today_start,
            )
            session.add(daily)
            session.commit()
            return daily
        return daily


def apply_chapter_auto_daily_reset(commander_id: int) -> ChapterAutoDaily:
    today_start = local_now().replace(hour=0, minute=0, second=0, microsecond=0).astimezone(timezone.utc)
    today_start_ts = safe_ts(today_start)
    with get_sync_session() as session:
        result = session.execute(
            select(ChapterAutoDaily).where(ChapterAutoDaily.commander_id == commander_id)
        )
        daily = result.scalar_one_or_none()
        if daily is None:
            daily = ChapterAutoDaily(
                commander_id=commander_id,
                time_acc=0,
                extra_time_max=0,
                oil_bank=0,
                last_daily_reset_at=today_start,
            )
            session.add(daily)
            session.commit()
            return daily

        last_ts = safe_ts(daily.last_daily_reset_at)
        if last_ts < today_start_ts:
            daily.time_acc = 0
            daily.extra_time_max = 0
            daily.last_daily_reset_at = today_start
            session.commit()
        return daily


def add_chapter_auto_daily_cost_time(commander_id: int, seconds: int) -> None:
    if seconds <= 0:
        return
    get_or_create_chapter_auto_daily(commander_id)
    with get_sync_session() as session:
        session.execute(
            text(
                "UPDATE chapter_auto_daily SET time_acc = time_acc + :sec WHERE commander_id = :cid"
            ),
            {"sec": seconds, "cid": commander_id},
        )
        session.commit()


def reduce_chapter_auto_daily_cost_time(commander_id: int, seconds: int) -> None:
    if seconds <= 0:
        return
    get_or_create_chapter_auto_daily(commander_id)
    with get_sync_session() as session:
        session.execute(
            text(
                "UPDATE chapter_auto_daily SET time_acc = CASE WHEN time_acc >= :sec THEN time_acc - :sec ELSE 0 END WHERE commander_id = :cid"
            ),
            {"sec": seconds, "cid": commander_id},
        )
        session.commit()


def add_chapter_auto_daily_extra_time(commander_id: int, seconds: int) -> None:
    if seconds <= 0:
        return
    get_or_create_chapter_auto_daily(commander_id)
    with get_sync_session() as session:
        session.execute(
            text(
                "UPDATE chapter_auto_daily SET extra_time_max = extra_time_max + :sec WHERE commander_id = :cid"
            ),
            {"sec": seconds, "cid": commander_id},
        )
        session.commit()


def add_chapter_auto_oil_bank(commander_id: int, oil: int) -> None:
    if oil <= 0:
        return
    get_or_create_chapter_auto_daily(commander_id)
    with get_sync_session() as session:
        session.execute(
            text(
                "UPDATE chapter_auto_daily SET oil_bank = oil_bank + :oil WHERE commander_id = :cid"
            ),
            {"oil": oil, "cid": commander_id},
        )
        session.commit()


def consume_chapter_auto_oil_bank(commander_id: int, max_oil: int) -> int:
    """Consumes up to max_oil from oil_bank. Returns actual amount consumed."""
    if max_oil <= 0:
        return 0
    with get_sync_session() as session:
        result = session.execute(
            select(ChapterAutoDaily).where(ChapterAutoDaily.commander_id == commander_id)
        )
        daily = result.scalar_one_or_none()
        if daily is None or daily.oil_bank <= 0:
            return 0
        consumed = min(daily.oil_bank, max_oil)
        daily.oil_bank -= consumed
        session.commit()
        return consumed
