from __future__ import annotations


from sqlalchemy import BigInteger, select
from sqlalchemy.orm import Mapped, mapped_column

from src.db.session import Base, get_sync_session


def add_commander_furniture(commander_id: int, furniture_id: int, count: int = 1, get_time: int = 0):
    with get_sync_session() as session:
        result = session.execute(
            select(CommanderFurniture).where(
                CommanderFurniture.commander_id == commander_id,
                CommanderFurniture.furniture_id == furniture_id,
            )
        )
        obj = result.scalar_one_or_none()
        if obj is None:
            obj = CommanderFurniture(
                commander_id=commander_id,
                furniture_id=furniture_id,
                count=count,
                get_time=get_time,
            )
            session.add(obj)
        else:
            obj.count += count
            if get_time:
                obj.get_time = get_time
        session.commit()


def list_commander_furniture(commander_id: int) -> list:
    with get_sync_session() as session:
        result = session.execute(
            select(CommanderFurniture).where(CommanderFurniture.commander_id == commander_id)
        )
        return list(result.scalars().all())


class CommanderFurniture(Base):
    __tablename__ = 'commander_furnitures'
    commander_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    furniture_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    count: Mapped[int] = mapped_column(BigInteger, default=0)
    get_time: Mapped[int] = mapped_column(BigInteger, default=0)
