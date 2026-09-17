from __future__ import annotations

from typing import Optional

from sqlalchemy import BigInteger, select
from sqlalchemy.orm import Mapped, mapped_column

from src.db.session import Base, get_sync_session


def ensure_commander_boxes(commander_id: int) -> list[CommanderBox]:
    with get_sync_session() as session:
        result = session.execute(
            select(CommanderBox).where(CommanderBox.commander_id == commander_id)
        ).scalars().all()
        existing_ids = {b.box_id for b in result}
        for box_id in range(1, 11):
            if box_id not in existing_ids:
                session.add(CommanderBox(commander_id=commander_id, box_id=box_id))
        session.commit()
        refreshed = session.execute(
            select(CommanderBox).where(CommanderBox.commander_id == commander_id)
            .order_by(CommanderBox.box_id)
        ).scalars().all()
        return list(refreshed)


def get_commander_box(commander_id: int, box_id: int) -> Optional[CommanderBox]:
    with get_sync_session() as session:
        return session.execute(
            select(CommanderBox).where(
                CommanderBox.commander_id == commander_id,
                CommanderBox.box_id == box_id,
            )
        ).scalar_one_or_none()


def upsert_commander_box(box_or_data):
    if isinstance(box_or_data, dict):
        commander_id = box_or_data.get("commander_id")
        box_id = box_or_data.get("box_id", box_or_data.get("id"))
        pool_id = box_or_data.get("pool_id", 0)
        begin_time = box_or_data.get("begin_time", 0)
        finish_time = box_or_data.get("finish_time", 0)
    else:
        commander_id = getattr(box_or_data, "commander_id", None)
        box_id = getattr(box_or_data, "box_id", getattr(box_or_data, "id", None))
        pool_id = getattr(box_or_data, "pool_id", 0)
        begin_time = getattr(box_or_data, "begin_time", 0)
        finish_time = getattr(box_or_data, "finish_time", 0)

    if not commander_id or not box_id:
        return

    with get_sync_session() as session:
        obj = session.execute(
            select(CommanderBox).where(
                CommanderBox.commander_id == commander_id,
                CommanderBox.box_id == box_id,
            )
        ).scalar_one_or_none()
        if obj is None:
            obj = CommanderBox(
                commander_id=commander_id,
                box_id=box_id,
                pool_id=pool_id,
                begin_time=begin_time,
                finish_time=finish_time,
            )
            session.add(obj)
        else:
            obj.pool_id = pool_id
            obj.begin_time = begin_time
            obj.finish_time = finish_time
        session.commit()


def to_proto_commander_box(commander_id: int) -> list:
    with get_sync_session() as session:
        result = session.execute(
            select(CommanderBox).where(CommanderBox.commander_id == commander_id)
        )
        return list(result.scalars().all())


class CommanderBox(Base):
    __tablename__ = 'commander_boxes'
    commander_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    box_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    pool_id: Mapped[int] = mapped_column(BigInteger, default=0)
    begin_time: Mapped[int] = mapped_column(BigInteger, default=0)
    finish_time: Mapped[int] = mapped_column(BigInteger, default=0)
