from __future__ import annotations

from sqlalchemy import BigInteger, select
from sqlalchemy.orm import Mapped, mapped_column

from src.db.session import Base, get_sync_session


def list_collection_ship_stats(commander_id: int):
    with get_sync_session() as session:
        result = session.execute(
            select(CollectionShipStat).where(CollectionShipStat.commander_id == commander_id)
        )
        return list(result.scalars().all())


def upsert_collection_ship_stats(commander_id: int, stats: list):
    with get_sync_session() as session:
        for stat in stats:
            existing = session.execute(
                select(CollectionShipStat).where(
                    CollectionShipStat.commander_id == commander_id,
                    CollectionShipStat.group_id == stat.get("group_id", 0),
                )
            ).scalar_one_or_none()
            if existing is None:
                session.add(CollectionShipStat(
                    commander_id=commander_id,
                    group_id=stat.get("group_id", 0),
                    max_star=stat.get("max_star", 0),
                ))
            else:
                existing.max_star = max(existing.max_star, stat.get("max_star", 0))
        session.commit()


class CollectionShipStat(Base):
    __tablename__ = "collection_ship_stats"
    commander_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    group_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    max_star: Mapped[int] = mapped_column(BigInteger, default=0)
