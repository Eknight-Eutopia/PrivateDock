from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from sqlalchemy import BigInteger, Boolean, DateTime, select, text
from sqlalchemy.orm import Mapped, mapped_column

from src.db.session import Base, get_session, get_sync_session


async def list_remaster_progress_rows(commander_id: int) -> list[dict[str, Any]]:
    async with get_session() as session:
        result = await session.execute(
            text("SELECT chapter_id, pos, count, received, updated_at FROM remaster_progresses WHERE commander_id = :cid ORDER BY chapter_id, pos"),
            {"cid": commander_id},
        )
        rows = result.mappings().all()
        return [dict(r) for r in rows]


async def get_remaster_progress_row(commander_id: int, chapter_id: int, pos: int) -> Optional[dict[str, Any]]:
    async with get_session() as session:
        result = await session.execute(
            text("SELECT count, received FROM remaster_progresses WHERE commander_id = :cid AND chapter_id = :ch AND pos = :pos"),
            {"cid": commander_id, "ch": chapter_id, "pos": pos},
        )
        row = result.mappings().first()
        if row is None:
            return None
        return dict(row)


async def upsert_remaster_progress_row(commander_id: int, chapter_id: int, pos: int, count: int, received: bool) -> None:
    async with get_session() as session:
        await session.execute(
            text("""INSERT INTO remaster_progresses (commander_id, chapter_id, pos, count, received)
                    VALUES (:cid, :ch, :pos, :count, :received)
                    ON CONFLICT (commander_id, chapter_id, pos)
                    DO UPDATE SET count = :count, received = :received"""),
            {"cid": commander_id, "ch": chapter_id, "pos": pos, "count": count, "received": received},
        )
        await session.commit()


async def update_remaster_progress_row(commander_id: int, chapter_id: int, pos: int, count: int, received: bool) -> None:
    async with get_session() as session:
        await session.execute(
            text("UPDATE remaster_progresses SET count = :count, received = :received WHERE commander_id = :cid AND chapter_id = :ch AND pos = :pos"),
            {"count": count, "received": received, "cid": commander_id, "ch": chapter_id, "pos": pos},
        )
        await session.commit()


async def delete_remaster_progress_row(commander_id: int, chapter_id: int, pos: int) -> None:
    async with get_session() as session:
        await session.execute(
            text("DELETE FROM remaster_progresses WHERE commander_id = :cid AND chapter_id = :ch AND pos = :pos"),
            {"cid": commander_id, "ch": chapter_id, "pos": pos},
        )
        await session.commit()


def list_remaster_progress(commander_id: int) -> list[RemasterProgress]:
    with get_sync_session() as session:
        result = session.execute(
            select(RemasterProgress)
            .where(RemasterProgress.commander_id == commander_id)
            .order_by(RemasterProgress.chapter_id, RemasterProgress.pos)
        )
        return list(result.scalars().all())


def upsert_remaster_progress(entry: RemasterProgress) -> None:
    now = datetime.utcnow()
    with get_sync_session() as session:
        created_at = entry.created_at if entry.created_at else now
        session.execute(
            text("""
                INSERT INTO remaster_progresses (commander_id, chapter_id, pos, count, received, created_at, updated_at)
                VALUES (:commander_id, :chapter_id, :pos, :count, :received, :created_at, :updated_at)
                ON CONFLICT (commander_id, chapter_id, pos)
                DO UPDATE SET
                    count = EXCLUDED.count,
                    received = EXCLUDED.received,
                    updated_at = EXCLUDED.updated_at
            """),
            {
                "commander_id": entry.commander_id,
                "chapter_id": entry.chapter_id,
                "pos": entry.pos,
                "count": entry.count,
                "received": entry.received,
                "created_at": created_at,
                "updated_at": now,
            },
        )
        session.commit()


def get_remaster_progress(commander_id: int, chapter_id: int, pos: int) -> Optional[RemasterProgress]:
    with get_sync_session() as session:
        result = session.execute(
            select(RemasterProgress).where(
                RemasterProgress.commander_id == commander_id,
                RemasterProgress.chapter_id == chapter_id,
                RemasterProgress.pos == pos,
            )
        )
        return result.scalar_one_or_none()


def delete_remaster_progress(commander_id: int, chapter_id: int, pos: int) -> None:
    with get_sync_session() as session:
        session.execute(
            text("""
                DELETE FROM remaster_progresses
                WHERE commander_id = :commander_id AND chapter_id = :chapter_id AND pos = :pos
            """),
            {"commander_id": commander_id, "chapter_id": chapter_id, "pos": pos},
        )
        session.commit()


class RemasterProgress(Base):
    __tablename__ = "remaster_progresses"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    commander_id: Mapped[int] = mapped_column(BigInteger, default=0)
    chapter_id: Mapped[int] = mapped_column(BigInteger, default=0)
    pos: Mapped[int] = mapped_column(BigInteger, default=0)
    count: Mapped[int] = mapped_column(BigInteger, default=0)
    received: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), default=None)
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), default=None)
