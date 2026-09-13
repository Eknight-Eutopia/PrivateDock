from __future__ import annotations

from typing import Optional

from sqlalchemy import BigInteger, select
from sqlalchemy.orm import Mapped, mapped_column

from src.db.session import Base, get_sync_session


def ensure_commander_boxes(commander_id: int):
    with get_sync_session() as session:
        result = session.execute(
            select(CommanderBox).where(CommanderBox.commander_id == commander_id)
        ).scalars().all()
        existing_ids = {b.box_id for b in result}
        for box_id in range(1, 101):
            if box_id not in existing_ids:
                session.add(CommanderBox(commander_id=commander_id, box_id=box_id))
        session.commit()


def get_commander_box(commander_id: int, box_id: int) -> Optional[CommanderBox]:
    with get_sync_session() as session:
        return session.execute(
            select(CommanderBox).where(
                CommanderBox.commander_id == commander_id,
                CommanderBox.box_id == box_id,
            )
        ).scalar_one_or_none()


def upsert_commander_box(box: CommanderBox):
    with get_sync_session() as session:
        session.merge(box)
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
