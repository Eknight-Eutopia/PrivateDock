from __future__ import annotations
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import BigInteger, DateTime, select, text
from sqlalchemy.orm import Mapped, mapped_column

from src.db.session import Base, get_session, get_sync_session


# ── Async ORM query functions (for api/handlers) ──


async def list_commander_buffs_row(commander_id: int) -> list[dict[str, Any]]:
    async with get_session() as session:
        result = await session.execute(
            text("SELECT buff_id, timestamp, instigator FROM commander_buffs WHERE commander_id = :cid"),
            {"cid": commander_id},
        )
        return [dict(r) for r in result.mappings().all()]


async def get_commander_buff(commander_id: int, buff_id: int) -> Optional[dict[str, Any]]:
    async with get_session() as session:
        result = await session.execute(
            text("SELECT buff_id, timestamp, instigator FROM commander_buffs WHERE commander_id = :cid AND buff_id = :bid"),
            {"cid": commander_id, "bid": buff_id},
        )
        row = result.mappings().first()
        return dict(row) if row else None


async def insert_commander_buff(commander_id: int, buff_id: int, timestamp: int, instigator: int) -> None:
    async with get_session() as session:
        await session.execute(
            text("INSERT INTO commander_buffs (commander_id, buff_id, timestamp, instigator) "
                 "VALUES (:cid, :bid, :ts, :inst) ON CONFLICT DO NOTHING"),
            {"cid": commander_id, "bid": buff_id, "ts": timestamp, "inst": instigator},
        )
        await session.commit()


async def update_commander_buff_dynamic(commander_id: int, buff_id: int, **fields) -> None:
    if not fields:
        return
    set_clause = ", ".join(f"{k} = :{k}" for k in fields)
    params = {"cid": commander_id, "bid": buff_id}
    params.update(fields)
    async with get_session() as session:
        await session.execute(
            text(f"UPDATE commander_buffs SET {set_clause} WHERE commander_id = :cid AND buff_id = :bid"),
            params,
        )
        await session.commit()


async def delete_commander_buff(commander_id: int, buff_id: int) -> None:
    async with get_session() as session:
        await session.execute(
            text("DELETE FROM commander_buffs WHERE commander_id = :cid AND buff_id = :bid"),
            {"cid": commander_id, "bid": buff_id},
        )
        await session.commit()


def list_commander_buffs(commander_id: int) -> list:
    with get_sync_session() as session:
        result = session.execute(
            select(CommanderBuff).where(CommanderBuff.commander_id == commander_id)
        )
        return list(result.scalars().all())


def upsert_commander_buff(commander_id: int, buff_id: int, expires_at: Optional[datetime]) -> None:
    """Sync upsert of an active commander buff.

    Merges with the existing row keeping the later expiry when stacking the same buff.
    Uses the real schema columns (commander_id, buff_id, expires_at).
    """
    if expires_at is None or buff_id <= 0:
        return
    with get_sync_session() as session:
        existing = session.execute(
            select(CommanderBuff).where(
                CommanderBuff.commander_id == commander_id,
                CommanderBuff.buff_id == buff_id,
            )
        ).scalar_one_or_none()
        if existing is None:
            session.add(CommanderBuff(commander_id=commander_id, buff_id=buff_id, expires_at=expires_at))
        elif existing.expires_at is None or expires_at > existing.expires_at:
            existing.expires_at = expires_at
        session.commit()


def list_active_commander_buffs(commander_id: int, now: Optional[datetime] = None) -> list[CommanderBuff]:
    if now is None:
        now = datetime.now(timezone.utc)
    with get_sync_session() as session:
        result = session.execute(
            select(CommanderBuff).where(
                CommanderBuff.commander_id == commander_id,
                CommanderBuff.expires_at > now,
            )
        )
        return list(result.scalars().all())


def list_active_commander_buff_ids(commander_id: int, now: Optional[datetime] = None) -> list[int]:
    return [b.buff_id for b in list_active_commander_buffs(commander_id, now)]


async def alist_active_commander_buff_ids(commander_id: int, now: Optional[datetime] = None) -> list[int]:
    if now is None:
        now = datetime.now(timezone.utc)
    async with get_session() as session:
        result = await session.execute(
            select(CommanderBuff.buff_id).where(
                CommanderBuff.commander_id == commander_id,
                CommanderBuff.expires_at > now,
            )
        )
        return list(result.scalars().all())


class CommanderBuff(Base):
    __tablename__ = 'commander_buffs'
    commander_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    buff_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
