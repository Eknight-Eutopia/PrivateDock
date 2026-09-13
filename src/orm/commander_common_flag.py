from __future__ import annotations
from datetime import datetime

from src.db.session import Base

from typing import Optional

from sqlalchemy import select

from src.db.session import get_session, get_sync_session
from sqlalchemy import select, text
from sqlalchemy import BigInteger, DateTime
from sqlalchemy.orm import Mapped, mapped_column

def list_commander_common_flags(commander_id: int) -> list:
    with get_sync_session() as session:
        result = session.execute(
            select(CommanderCommonFlag).where(
                CommanderCommonFlag.commander_id == commander_id
            )
        )
        return list(result.scalars().all())

def has_commander_common_flag(commander_id: int, flag_id: int) -> bool:
    with get_sync_session() as session:
        result = session.execute(
            select(CommanderCommonFlag).where(
                CommanderCommonFlag.commander_id == commander_id,
                CommanderCommonFlag.flag_id == flag_id,
            )
        )
        return result.scalar_one_or_none() is not None

def clear_commander_common_flag(commander_id: int, flag_id: int):
    with get_sync_session() as session:
        obj = session.execute(
            select(CommanderCommonFlag).where(
                CommanderCommonFlag.commander_id == commander_id,
                CommanderCommonFlag.flag_id == flag_id,
            )
        ).scalar_one_or_none()
        if obj is not None:
            session.delete(obj)
            session.commit()

_SQL_SET_FLAG = text(
    "INSERT INTO commander_common_flags (commander_id, flag_id) VALUES (:cid, :fid) ON CONFLICT DO NOTHING"
)

def set_commander_common_flag(commander_id: int, flag_id: int) -> None:
    with get_sync_session() as session:
        session.execute(_SQL_SET_FLAG, {"cid": commander_id, "fid": flag_id})
        session.commit()

async def aset_commander_common_flag(commander_id: int, flag_id: int) -> None:
    async with get_session() as session:
        await session.execute(_SQL_SET_FLAG, {"cid": commander_id, "fid": flag_id})
        await session.commit()

def should_auto_lock_new_ship(commander_id: int, ship_id: int) -> bool:
    """True when the LOCK_NEW_SHIP flag is set AND the player has not yet
    ever obtained any ship of this group (ship_id // 10), mirroring the
    client's ``virgin`` check against the collection."""
    from src.consts.common_flags import LOCK_NEW_SHIP
    with get_sync_session() as session:
        has_flag = session.execute(
            select(CommanderCommonFlag).where(
                CommanderCommonFlag.commander_id == commander_id,
                CommanderCommonFlag.flag_id == LOCK_NEW_SHIP,
            )
        ).scalar_one_or_none() is not None
        if not has_flag:
            return False
        group_id = int(ship_id) // 10
        owns_group = session.execute(
            text("SELECT 1 FROM owned_ships WHERE owner_id = :cid AND ship_id / 10 = :gid LIMIT 1"),
            {"cid": commander_id, "gid": group_id},
        ).fetchone() is not None
        return not owns_group

class CommanderCommonFlag(Base):
    __tablename__ = 'commander_common_flags'
    commander_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    flag_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    created_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
