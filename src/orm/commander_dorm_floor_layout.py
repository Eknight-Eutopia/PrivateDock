from __future__ import annotations

from typing import Optional

from sqlalchemy import BigInteger, JSON, select
from sqlalchemy.orm import Mapped, mapped_column

from src.db.session import Base, get_sync_session


def list_commander_dorm_floor_layouts(commander_id: int):
    with get_sync_session() as session:
        result = session.execute(
            select(CommanderDormFloorLayout)
            .where(CommanderDormFloorLayout.commander_id == commander_id)
            .order_by(CommanderDormFloorLayout.floor)
        )
        return list(result.scalars().all())


def upsert_commander_dorm_floor_layout(commander_id: int, floor: int, data):
    with get_sync_session() as session:
        result = session.execute(
            select(CommanderDormFloorLayout).where(
                CommanderDormFloorLayout.commander_id == commander_id,
                CommanderDormFloorLayout.floor == floor,
            )
        )
        obj = result.scalar_one_or_none()
        if obj is None:
            obj = CommanderDormFloorLayout(
                commander_id=commander_id, floor=floor, furniture_put_list=data,
            )
            session.add(obj)
        else:
            obj.furniture_put_list = data
        session.commit()


class CommanderDormFloorLayout(Base):
    __tablename__ = 'commander_dorm_floor_layouts'
    commander_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    floor: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    furniture_put_list: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
