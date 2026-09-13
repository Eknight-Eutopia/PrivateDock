from __future__ import annotations


from sqlalchemy import BigInteger, select, text

from src.db.session import Base, get_session, get_sync_session
from sqlalchemy import BigInteger, String, Text
from sqlalchemy.orm import Mapped, mapped_column


async def get_activity_store_state(commander_id: int, activity_id: int):
    async with get_session() as session:
        result = await session.execute(
            select(ActivityStoreState).where(
                ActivityStoreState.commander_id == commander_id,
                ActivityStoreState.activity_id == activity_id,
            )
        )
        return result.scalar_one_or_none()


async def upsert_activity_store_state(commander_id: int, activity_id: int, data: str):
    async with get_session() as session:
        await session.execute(
            text("""
                INSERT INTO activity_store_states (commander_id, activity_id, data)
                VALUES (:cid, :aid, :data)
                ON CONFLICT (commander_id, activity_id)
                DO UPDATE SET data = EXCLUDED.data
            """),
            {"cid": commander_id, "aid": activity_id, "data": data},
        )
        await session.commit()


def get_activity_store_data2_sync(commander_id: int, activity_id: int) -> int:
    with get_sync_session() as session:
        result = session.execute(
            select(ActivityStoreState.data2).where(
                ActivityStoreState.commander_id == commander_id,
                ActivityStoreState.activity_id == activity_id,
            )
        )
        return int(result.scalar() or 0)


async def aget_activity_store_data2(commander_id: int, activity_id: int) -> int:
    async with get_session() as session:
        result = await session.execute(
            select(ActivityStoreState.data2).where(
                ActivityStoreState.commander_id == commander_id,
                ActivityStoreState.activity_id == activity_id,
            )
        )
        return int(result.scalar() or 0)


_SQL_UPSERT_DAY_STATE_WITH_ANCHOR = text(
    "INSERT INTO activity_store_states (commander_id, activity_id, data1, data2, data3, data1_list) "
    "VALUES (:cid, :aid, 0, :data2, :data3, '[]') "
    "ON CONFLICT (commander_id, activity_id) DO UPDATE SET data2 = :data2, data3 = :data3"
)

_SQL_UPSERT_DAY_STATE = text(
    "INSERT INTO activity_store_states (commander_id, activity_id, data1, data2, data3, data1_list) "
    "VALUES (:cid, :aid, 0, :data2, :data3, '[]') "
    "ON CONFLICT (commander_id, activity_id) DO UPDATE SET data3 = :data3"
)


def set_activity_store_day_state_sync(
    commander_id: int, activity_id: int, anchor: int, day: int, update_anchor: bool = True
) -> None:
    stmt = _SQL_UPSERT_DAY_STATE_WITH_ANCHOR if update_anchor else _SQL_UPSERT_DAY_STATE
    with get_sync_session() as session:
        session.execute(stmt, {"cid": commander_id, "aid": activity_id, "data2": anchor, "data3": day})
        session.commit()


async def aset_activity_store_day_state(
    commander_id: int, activity_id: int, anchor: int, day: int, update_anchor: bool = True
) -> None:
    stmt = _SQL_UPSERT_DAY_STATE_WITH_ANCHOR if update_anchor else _SQL_UPSERT_DAY_STATE
    async with get_session() as session:
        await session.execute(stmt, {"cid": commander_id, "aid": activity_id, "data2": anchor, "data3": day})
        await session.commit()


get_activity_store_data2 = get_activity_store_data2_sync
set_activity_store_day_state = set_activity_store_day_state_sync


class ActivityStoreState(Base):
    __tablename__ = 'activity_store_states'
    commander_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    activity_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    data1: Mapped[int] = mapped_column(BigInteger, default=0)
    data2: Mapped[int] = mapped_column(BigInteger, default=0)
    data3: Mapped[int] = mapped_column(BigInteger, default=0)
    data1_list: Mapped[str] = mapped_column(Text, default='[]')
    str_data1: Mapped[str] = mapped_column(String, default='')
