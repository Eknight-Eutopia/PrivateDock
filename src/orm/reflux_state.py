from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import BigInteger, DateTime, select, text
from sqlalchemy.orm import Mapped, mapped_column

from src.db.session import Base, get_sync_session


def get_or_create_reflux_state(commander_id: int) -> RefluxState:
    with get_sync_session() as session:
        result = session.execute(
            select(RefluxState).where(RefluxState.commander_id == commander_id)
        )
        state = result.scalar_one_or_none()
        if state is not None:
            return state

        state = RefluxState(commander_id=commander_id)
        save_reflux_state(state)
        return state


def save_reflux_state(state: RefluxState) -> None:
    with get_sync_session() as session:
        session.execute(
            text("""
                INSERT INTO reflux_states (commander_id, active, return_lv, return_time, ship_number, last_offline_time, pt, sign_cnt, sign_last_time, pt_stage, created_at, updated_at)
                VALUES (:commander_id, :active, :return_lv, :return_time, :ship_number, :last_offline_time, :pt, :sign_cnt, :sign_last_time, :pt_stage, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                ON CONFLICT (commander_id)
                DO UPDATE SET
                    active = EXCLUDED.active,
                    return_lv = EXCLUDED.return_lv,
                    return_time = EXCLUDED.return_time,
                    ship_number = EXCLUDED.ship_number,
                    last_offline_time = EXCLUDED.last_offline_time,
                    pt = EXCLUDED.pt,
                    sign_cnt = EXCLUDED.sign_cnt,
                    sign_last_time = EXCLUDED.sign_last_time,
                    pt_stage = EXCLUDED.pt_stage,
                    updated_at = CURRENT_TIMESTAMP
            """),
            {
                "commander_id": state.commander_id,
                "active": state.active,
                "return_lv": state.return_lv,
                "return_time": state.return_time,
                "ship_number": state.ship_number,
                "last_offline_time": state.last_offline_time,
                "pt": state.pt,
                "sign_cnt": state.sign_cnt,
                "sign_last_time": state.sign_last_time,
                "pt_stage": state.pt_stage,
            },
        )
        session.commit()


class RefluxState(Base):
    __tablename__ = "reflux_states"
    commander_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    active: Mapped[int] = mapped_column(BigInteger, default=0)
    return_lv: Mapped[int] = mapped_column(BigInteger, default=0)
    return_time: Mapped[int] = mapped_column(BigInteger, default=0)
    ship_number: Mapped[int] = mapped_column(BigInteger, default=0)
    last_offline_time: Mapped[int] = mapped_column(BigInteger, default=0)
    pt: Mapped[int] = mapped_column(BigInteger, default=0)
    sign_cnt: Mapped[int] = mapped_column(BigInteger, default=0)
    sign_last_time: Mapped[int] = mapped_column(BigInteger, default=0)
    pt_stage: Mapped[int] = mapped_column(BigInteger, default=0)
    created_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), default=None)
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), default=None)
