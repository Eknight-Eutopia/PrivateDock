from __future__ import annotations

from typing import Optional

from sqlalchemy import BigInteger, String, select
from sqlalchemy.orm import Mapped, mapped_column

from src.db.session import Base, get_sync_session


def get_or_create_appreciation_state(commander_id: int):
    return _sync_get_or_create_appreciation_state(commander_id)


def get_or_create_commander_appreciation_state(commander_id: int):
    return _sync_get_or_create_appreciation_state(commander_id)


def _sync_get_or_create_appreciation_state(commander_id: int):
    with get_sync_session() as session:
        result = session.execute(
            select(CommanderAppreciationState).where(CommanderAppreciationState.commander_id == commander_id)
        )
        state = result.scalar_one_or_none()
        if state is not None:
            return state
        state = CommanderAppreciationState(commander_id=commander_id)
        session.add(state)
        session.commit()
        return state


class CommanderAppreciationState(Base):
    __tablename__ = 'commander_appreciation_states'
    commander_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    music_no: Mapped[int] = mapped_column(BigInteger, default=0)
    music_mode: Mapped[int] = mapped_column(BigInteger, default=0)
    cartoon_read_mark: Mapped[str] = mapped_column(String, default='')
    cartoon_collect_mark: Mapped[str] = mapped_column(String, default='')
    gallery_unlocks: Mapped[str] = mapped_column(String, default='')
    gallery_favor_ids: Mapped[str] = mapped_column(String, default='')
    music_favor_ids: Mapped[str] = mapped_column(String, default='')


# ── sync (store-based) access for game-packet handlers ────────────────────

from src.db.store import get_default_store


def get_appreciation_row_sync(commander_id: int) -> Optional[dict]:
    store = get_default_store()
    row = store.fetchrow(
        "SELECT commander_id, cartoon_read_mark, cartoon_collect_mark "
        "FROM commander_appreciation_states WHERE commander_id = $1",
        commander_id,
    )
    return dict(row) if row is not None else None


def insert_default_appreciation_sync(commander_id: int, read_mark_json: str, collect_mark_json: str) -> None:
    store = get_default_store()
    store.execute(
        "INSERT INTO commander_appreciation_states (commander_id, cartoon_read_mark, cartoon_collect_mark) "
        "VALUES ($1, $2, $3)",
        commander_id, read_mark_json, collect_mark_json,
    )


def update_cartoon_read_mark_sync(commander_id: int, marks_json: str) -> None:
    store = get_default_store()
    store.execute(
        "UPDATE commander_appreciation_states SET cartoon_read_mark = $1 WHERE commander_id = $2",
        marks_json, commander_id,
    )


def update_cartoon_collect_mark_sync(commander_id: int, marks_json: str) -> None:
    store = get_default_store()
    store.execute(
        "UPDATE commander_appreciation_states SET cartoon_collect_mark = $1 WHERE commander_id = $2",
        marks_json, commander_id,
    )
