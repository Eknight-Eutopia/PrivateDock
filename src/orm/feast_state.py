from __future__ import annotations

from typing import Optional

from sqlalchemy import BigInteger, JSON, select
from sqlalchemy.orm import Mapped, mapped_column

from src.db.session import Base, get_sync_session


def get_or_create_feast_state(commander_id: int, feast_id: int):
    with get_sync_session() as session:
        result = session.execute(
            select(FeastState).where(
                FeastState.commander_id == commander_id,
                FeastState.feast_id == feast_id,
            )
        )
        row = result.scalar_one_or_none()
        if row is None:
            row = FeastState(commander_id=commander_id, feast_id=feast_id)
            session.add(row)
            session.commit()
        return row


def save_feast_state(commander_id: int, feast_id: int, data: dict):
    with get_sync_session() as session:
        result = session.execute(
            select(FeastState).where(
                FeastState.commander_id == commander_id,
                FeastState.feast_id == feast_id,
            )
        )
        row = result.scalar_one_or_none()
        if row is not None:
            row.state = data
            session.commit()


class FeastState(Base):
    __tablename__ = "feast_states"
    commander_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    feast_id: Mapped[int] = mapped_column(BigInteger, default=0)
    state: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
