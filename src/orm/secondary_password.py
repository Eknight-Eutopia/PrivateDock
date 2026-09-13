from __future__ import annotations

import json
from typing import Optional

from sqlalchemy import BigInteger, JSON, Text, select, text
from sqlalchemy.orm import Mapped, mapped_column

from src.db.session import Base, get_sync_session


def get_or_create_secondary_password_state(commander_id: int) -> SecondaryPasswordState:
    with get_sync_session() as session:
        result = session.execute(
            select(SecondaryPasswordState).where(SecondaryPasswordState.commander_id == commander_id)
        )
        state = result.scalar_one_or_none()
        if state is not None:
            return state

        session.execute(
            text("""
                INSERT INTO secondary_password_states (
                    commander_id, password_hash, notice, system_list, state, fail_count, fail_cd
                ) VALUES (
                    :commander_id, '', '', :system_list, 0, 0, 0
                )
                ON CONFLICT (commander_id) DO NOTHING
            """),
            {"commander_id": commander_id, "system_list": "[]"},
        )
        session.commit()

        result = session.execute(
            select(SecondaryPasswordState).where(SecondaryPasswordState.commander_id == commander_id)
        )
        return result.scalar_one()


def save_secondary_password_state(state: SecondaryPasswordState) -> None:
    system_list_raw = json.dumps(state.system_list or [])
    with get_sync_session() as session:
        session.execute(
            text("""
                INSERT INTO secondary_password_states (
                    commander_id, password_hash, notice, system_list, state, fail_count, fail_cd
                ) VALUES (
                    :commander_id, :password_hash, :notice, :system_list, :state, :fail_count, :fail_cd
                )
                ON CONFLICT (commander_id)
                DO UPDATE SET
                    password_hash = EXCLUDED.password_hash,
                    notice = EXCLUDED.notice,
                    system_list = EXCLUDED.system_list,
                    state = EXCLUDED.state,
                    fail_count = EXCLUDED.fail_count,
                    fail_cd = EXCLUDED.fail_cd
            """),
            {
                "commander_id": state.commander_id,
                "password_hash": state.password_hash,
                "notice": state.notice,
                "system_list": system_list_raw,
                "state": state.state,
                "fail_count": state.fail_count,
                "fail_cd": state.fail_cd,
            },
        )
        session.commit()


class SecondaryPasswordState(Base):
    __tablename__ = "secondary_password_states"
    commander_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    password_hash: Mapped[str] = mapped_column(Text, default="")
    notice: Mapped[str] = mapped_column(Text, default="")
    system_list: Mapped[Optional[list]] = mapped_column(JSON, default=list)
    state: Mapped[int] = mapped_column(BigInteger, default=0)
    fail_count: Mapped[int] = mapped_column(BigInteger, default=0)
    fail_cd: Mapped[int] = mapped_column(BigInteger, default=0)
