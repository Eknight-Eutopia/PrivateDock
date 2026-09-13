from __future__ import annotations

from typing import Optional

from sqlalchemy import BigInteger, JSON
from sqlalchemy.orm import Mapped, mapped_column

from src.db.session import Base, get_session, get_sync_session


async def load_activity_fleet_groups(commander_id: int, activity_id: int):
    async with get_session() as session:
        row = await session.execute(
            "SELECT group_list FROM activity_fleets WHERE commander_id = :cid AND activity_id = :aid",
            {"cid": commander_id, "aid": activity_id},
        )
        record = row.fetchone()
    if record is None:
        return None, False
    return record[0] or [], True


async def save_activity_fleet_groups(commander_id: int, activity_id: int, fleet_data: list):
    from sqlalchemy import text
    async with get_session() as session:
        await session.execute(
            text("INSERT INTO activity_fleets (commander_id, activity_id, group_list) VALUES (:cid, :aid, :gl) "
                 "ON CONFLICT (commander_id, activity_id) DO UPDATE SET group_list = EXCLUDED.group_list"),
            {"cid": commander_id, "aid": activity_id, "gl": fleet_data},
        )
        await session.commit()


def load_activity_fleet_groups_sync(commander_id: int, activity_id: int):
    with get_sync_session() as session:
        row = session.execute(
            "SELECT group_list FROM activity_fleets WHERE commander_id = :cid AND activity_id = :aid",
            {"cid": commander_id, "aid": activity_id},
        ).fetchone()
    if row is None:
        return None, False
    return row[0] or [], True


class ActivityFleet(Base):
    __tablename__ = 'activity_fleets'
    commander_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    activity_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    group_list: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
