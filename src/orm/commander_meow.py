from __future__ import annotations
from datetime import datetime

from src.db.session import Base

from typing import Optional

from sqlalchemy import select

from src.db.session import get_sync_session
from sqlalchemy import select
from sqlalchemy import BigInteger, DateTime
from sqlalchemy.orm import Mapped, mapped_column

def ensure_commander_meows(commander_id: int, meow_ids: list[int]):
    with get_sync_session() as session:
        existing = session.execute(
            select(CommanderMeow).where(CommanderMeow.commander_id == commander_id)
        ).scalars().all()
        existing_ids = {m.meow_id for m in existing}
        for mid in meow_ids:
            if mid not in existing_ids:
                session.add(CommanderMeow(commander_id=commander_id, meow_id=mid))
        session.commit()

def get_commander_meow(commander_id: int, meow_id: int) -> CommanderMeow | None:
    with get_sync_session() as session:
        return session.execute(
            select(CommanderMeow).where(
                CommanderMeow.commander_id == commander_id,
                CommanderMeow.meow_id == meow_id,
            )
        ).scalar_one_or_none()

def list_commander_meows(commander_id: int) -> list:
    with get_sync_session() as session:
        result = session.execute(
            select(CommanderMeow).where(CommanderMeow.commander_id == commander_id)
        )
        return list(result.scalars().all())

def create_commander_meow(commander_id: int, meow_id: int) -> CommanderMeow:
    with get_sync_session() as session:
        obj = CommanderMeow(commander_id=commander_id, meow_id=meow_id)
        session.add(obj)
        session.commit()
        session.refresh(obj)
        return obj

def delete_commander_meows(commander_id: int, meow_ids: list[int]):
    with get_sync_session() as session:
        for mid in meow_ids:
            obj = session.execute(
                select(CommanderMeow).where(
                    CommanderMeow.commander_id == commander_id,
                    CommanderMeow.meow_id == mid,
                )
            ).scalar_one_or_none()
            if obj is not None:
                session.delete(obj)
        session.commit()

def update_commander_meow_exp(commander_id: int, meow_id: int, exp: int):
    with get_sync_session() as session:
        obj = session.execute(
            select(CommanderMeow).where(
                CommanderMeow.commander_id == commander_id,
                CommanderMeow.meow_id == meow_id,
            )
        ).scalar_one_or_none()
        if obj is not None:
            obj.exp = exp
            session.commit()

def get_commander_create_material_config() -> dict:
    return {}

def get_commander_data_template_config() -> dict:
    return {}

def get_commander_ability_template() -> dict:
    return {}

def list_commander_ability_groups() -> list:
    return []

def roll_commander_template_for_pool() -> dict:
    return {}

def update_fleet_meowfficer_slot(commander_id: int, fleet_id: int, slot: int, meow_id: int):
    pass

class CommanderCatteryOpBit:
    pass

async def compute_commander_quick_finish_counts():
    return 0, 0


async def apply_commander_quick_finish(commander_id: int, task_id: int, count: int):
    pass


def get_commander_upgrade_rates() -> tuple[int, int, int]:
    from src.answer.remaster_config import load_gameset_value
    val = load_gameset_value("commander_exp_same_rate")
    same_rate = val if val is not None else 12000
    return same_rate, 0, 0


class CommanderMeow(Base):
    __tablename__ = 'commander_meows'
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    commander_id: Mapped[int] = mapped_column(BigInteger)
    template_id: Mapped[int] = mapped_column(BigInteger, default=0)
    level: Mapped[int] = mapped_column(BigInteger, default=0)
    exp: Mapped[int] = mapped_column(BigInteger, default=0)
    is_locked: Mapped[int] = mapped_column(BigInteger, default=0)
    used_pt: Mapped[int] = mapped_column(BigInteger, default=0)
    created_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
