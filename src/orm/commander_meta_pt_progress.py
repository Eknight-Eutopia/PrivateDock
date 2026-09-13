from __future__ import annotations

import json
from typing import Optional

from sqlalchemy import BigInteger, JSON, select, text
from sqlalchemy.orm import Mapped, mapped_column

from src.db.session import Base, get_sync_session


def get_commander_meta_pt_progress(commander_id: int, group_id: int) -> Optional[CommanderMetaPtProgress]:
    with get_sync_session() as session:
        result = session.execute(
            select(CommanderMetaPtProgress).where(
                CommanderMetaPtProgress.commander_id == commander_id,
                CommanderMetaPtProgress.group_id == group_id,
            )
        )
        return result.scalar_one_or_none()


def get_or_create_commander_meta_pt_progress(commander_id: int, group_id: int) -> CommanderMetaPtProgress:
    with get_sync_session() as session:
        result = session.execute(
            select(CommanderMetaPtProgress).where(
                CommanderMetaPtProgress.commander_id == commander_id,
                CommanderMetaPtProgress.group_id == group_id,
            )
        )
        state = result.scalar_one_or_none()
        if state is not None:
            return state

        state = CommanderMetaPtProgress(
            commander_id=commander_id,
            group_id=group_id,
            fetch_list=[],
        )
        session.add(state)
        session.commit()
        session.refresh(state)
        return state


def list_commander_meta_pt_progress(commander_id: int) -> list[CommanderMetaPtProgress]:
    with get_sync_session() as session:
        result = session.execute(
            select(CommanderMetaPtProgress)
            .where(CommanderMetaPtProgress.commander_id == commander_id)
            .order_by(CommanderMetaPtProgress.group_id)
        )
        return list(result.scalars().all())


def save_commander_meta_pt_progress(state: CommanderMetaPtProgress) -> None:
    fetch_list_raw = json.dumps(state.fetch_list or [])
    with get_sync_session() as session:
        session.execute(
            text("""
                INSERT INTO commander_meta_pt_progress (commander_id, group_id, pt, fetch_list, created_at, updated_at)
                VALUES (:commander_id, :group_id, :pt, :fetch_list, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                ON CONFLICT (commander_id, group_id)
                DO UPDATE SET
                    pt = EXCLUDED.pt,
                    fetch_list = EXCLUDED.fetch_list,
                    updated_at = CURRENT_TIMESTAMP
            """),
            {
                "commander_id": state.commander_id,
                "group_id": state.group_id,
                "pt": state.pt,
                "fetch_list": fetch_list_raw,
            },
        )
        session.commit()


class CommanderMetaPtProgress(Base):
    __tablename__ = "commander_meta_pt_progress"
    commander_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    group_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    pt: Mapped[int] = mapped_column(BigInteger, default=0)
    fetch_list: Mapped[Optional[list]] = mapped_column(JSON, default=list)
