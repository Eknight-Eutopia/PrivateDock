from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import BigInteger, JSON, select, text
from sqlalchemy.orm import Mapped, mapped_column

from src.db.session import Base, get_sync_session
from src.db.store import get_default_store


def _decode_weekly_row(row) -> Optional[dict]:
    if row is None:
        return None
    raw = row["tasks"]
    if isinstance(raw, str):
        try:
            parsed = json.loads(raw)
        except Exception:
            parsed = {}
    else:
        parsed = raw
    tasks = (
        parsed.get("tasks", [])
        if isinstance(parsed, dict)
        else (parsed if isinstance(parsed, list) else [])
    )
    raw_counts = parsed.get("counts", {}) if isinstance(parsed, dict) else {}
    counts = (
        {str(k): v for k, v in raw_counts.items()}
        if isinstance(raw_counts, dict)
        else {}
    )
    return {
        "tasks": tasks if isinstance(tasks, list) else [],
        "counts": counts,
        "pt": row["pt"] or 0,
        "reward_lv": row["reward_lv"] or 0,
        "week_start_unix": row["week_start_unix"],
    }


def _encode_weekly_state(state: dict) -> tuple[str, int, int]:
    payload = json.dumps({
        "tasks": state.get("tasks", []),
        "counts": state.get("counts", {}),
        "pt": state.get("pt", 0),
        "reward_lv": state.get("reward_lv", 0),
    })
    return payload, int(state.get("pt", 0) or 0), int(state.get("reward_lv", 0) or 0)


def load_weekly_state(commander_id: int) -> Optional[dict]:
    store = get_default_store()
    if store is None:
        return None
    try:
        row = store.fetchrow(
            "SELECT tasks, pt, reward_lv, week_start_unix FROM weekly_task_progress WHERE commander_id = $1",
            commander_id,
        )
    except Exception:
        return None
    return _decode_weekly_row(row)


async def aload_weekly_state(commander_id: int) -> Optional[dict]:
    store = get_default_store()
    if store is None:
        return None
    try:
        row = await store.afetchrow(
            "SELECT tasks, pt, reward_lv, week_start_unix FROM weekly_task_progress WHERE commander_id = $1",
            commander_id,
        )
    except Exception:
        return None
    return _decode_weekly_row(row)


def save_weekly_state(commander_id: int, state: dict, week_bucket: int) -> None:
    store = get_default_store()
    if store is None:
        return
    payload, pt, reward_lv = _encode_weekly_state(state)
    try:
        store.execute(
            "INSERT INTO weekly_task_progress (commander_id, tasks, pt, reward_lv, week_start_unix) "
            "VALUES ($1, $2::jsonb, $3, $4, $5) "
            "ON CONFLICT (commander_id) DO UPDATE SET tasks = $2::jsonb, pt = $3, reward_lv = $4, week_start_unix = $5",
            commander_id, payload, pt, reward_lv, week_bucket,
        )
    except Exception:
        pass


async def asave_weekly_state(commander_id: int, state: dict, week_bucket: int) -> None:
    store = get_default_store()
    if store is None:
        return
    payload, pt, reward_lv = _encode_weekly_state(state)
    try:
        await store.aexecute(
            "INSERT INTO weekly_task_progress (commander_id, tasks, pt, reward_lv, week_start_unix) "
            "VALUES ($1, $2::jsonb, $3, $4, $5) "
            "ON CONFLICT (commander_id) DO UPDATE SET tasks = $2::jsonb, pt = $3, reward_lv = $4, week_start_unix = $5",
            commander_id, payload, pt, reward_lv, week_bucket,
        )
    except Exception:
        pass



class WeeklyTaskEntry:
    def __init__(self, id: int = 0, progress: int = 0):
        self.id = id
        self.progress = progress

    def to_dict(self) -> dict:
        return {"id": self.id, "progress": self.progress}

    @classmethod
    def from_dict(cls, d: dict) -> "WeeklyTaskEntry":
        return cls(id=d.get("id", 0), progress=d.get("progress", 0))


from src.shopreset.framework import current_weekly_reset_unix


def load_weekly_task_progress(commander_id: int, now: datetime) -> WeeklyTaskProgress:
    week_start = current_weekly_reset_unix(now)
    with get_sync_session() as session:
        result = session.execute(
            select(WeeklyTaskProgress).where(WeeklyTaskProgress.commander_id == commander_id)
        )
        row = result.scalar_one_or_none()

        if row is None:
            state = WeeklyTaskProgress(
                commander_id=commander_id,
                week_start_unix=week_start,
            )
            session.add(state)
            session.commit()
            session.refresh(state)
            return state

        state = row
        tasks = []
        if state.tasks:
            tasks = [WeeklyTaskEntry.from_dict(t) for t in state.tasks]

        if state.week_start_unix != week_start:
            state.week_start_unix = week_start
            state.pt = 0
            state.reward_lv = 0
            state.tasks = []
            session.commit()

        return state


def save_weekly_task_progress(state: WeeklyTaskProgress) -> None:
    with get_sync_session() as session:
        session.execute(
            text("""
                UPDATE weekly_task_progress
                SET week_start_unix = :week_start_unix,
                    pt = :pt,
                    reward_lv = :reward_lv,
                    tasks = :tasks,
                    updated_at = CURRENT_TIMESTAMP
                WHERE commander_id = :commander_id
            """),
            {
                "commander_id": state.commander_id,
                "week_start_unix": state.week_start_unix,
                "pt": state.pt,
                "reward_lv": state.reward_lv,
                "tasks": json.dumps([t.to_dict() for t in (state.tasks or [])]),
            },
        )
        session.commit()


class WeeklyTaskProgress(Base):
    __tablename__ = "weekly_task_progress"
    commander_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    week_start_unix: Mapped[int] = mapped_column(BigInteger, default=0)
    pt: Mapped[int] = mapped_column(BigInteger, default=0)
    reward_lv: Mapped[int] = mapped_column(BigInteger, default=0)
    tasks: Mapped[Optional[list]] = mapped_column(JSON, default=list)
