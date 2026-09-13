from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Optional

from sqlalchemy import BigInteger, DateTime
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from src.db.session import Base, get_session, get_sync_session


async def get_battle_session(commander_id: int) -> Optional["BattleSession"]:
    async with get_session() as session:
        return await session.get(BattleSession, commander_id)


async def upsert_battle_session(commander_id: int, session_key: str, data: dict[str, Any]):
    async with get_session() as session:
        from datetime import timezone
        now = datetime.now(timezone.utc)
        obj = await session.get(BattleSession, commander_id)
        if obj:
            obj.system = data.get("system", 0)
            obj.stage_id = data.get("stage_id", 0)
            obj.key = int(session_key)
            obj.ship_ids = data.get("ship_ids", [])
            obj.updated_at = now
        else:
            session.add(BattleSession(
                commander_id=commander_id,
                system=data.get("system", 0),
                stage_id=data.get("stage_id", 0),
                key=int(session_key),
                ship_ids=data.get("ship_ids", []),
                created_at=now,
                updated_at=now,
            ))
        await session.commit()


async def delete_battle_session(commander_id: int):
    async with get_session() as session:
        obj = await session.get(BattleSession, commander_id)
        if obj is not None:
            await session.delete(obj)
            await session.commit()


def get_battle_session_sync(commander_id: int) -> Optional["BattleSession"]:
    with get_sync_session() as session:
        return session.get(BattleSession, commander_id)


def _ensure_ship_ids(value: Any) -> list:
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        return json.loads(value)
    if value is None:
        return []
    return list(value)

def upsert_battle_session_sync(commander_id: int, session_key: str, data: dict[str, Any]):
    with get_sync_session() as session:
        from datetime import timezone
        now = datetime.now(timezone.utc)
        obj = session.get(BattleSession, commander_id)
        ship_ids = _ensure_ship_ids(data.get("ship_ids", []))
        if obj:
            obj.system = data.get("system", 0)
            obj.stage_id = data.get("stage_id", 0)
            obj.key = int(session_key)
            obj.ship_ids = ship_ids
            obj.updated_at = now
        else:
            session.add(BattleSession(
                commander_id=commander_id,
                system=data.get("system", 0),
                stage_id=data.get("stage_id", 0),
                key=int(session_key),
                ship_ids=ship_ids,
                created_at=now,
                updated_at=now,
            ))
        session.commit()


def delete_battle_session_sync(commander_id: int):
    with get_sync_session() as session:
        obj = session.get(BattleSession, commander_id)
        if obj is not None:
            session.delete(obj)
            session.commit()


class BattleSession(Base):
    __tablename__ = 'battle_sessions'
    commander_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    system: Mapped[int] = mapped_column(BigInteger, default=0)
    stage_id: Mapped[int] = mapped_column(BigInteger, default=0)
    key: Mapped[int] = mapped_column(BigInteger, default=0)
    ship_ids: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
