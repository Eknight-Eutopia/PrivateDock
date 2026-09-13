from __future__ import annotations

from typing import NamedTuple, Optional, Sequence
from sqlalchemy import BigInteger, select
from sqlalchemy.orm import Mapped, mapped_column

from src.db.session import Base, get_sync_session
from src.db.store import get_default_store


class TaskRow(NamedTuple):
    task_id: int
    progress: int
    accept_time: int
    submit_time: int


class CommanderTask(Base):
    __tablename__ = "commander_tasks"
    commander_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    task_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    progress: Mapped[int] = mapped_column(BigInteger, default=0)
    accept_time: Mapped[int] = mapped_column(BigInteger, default=0)
    submit_time: Mapped[int] = mapped_column(BigInteger, default=0)


def get_commander_task(commander_id: int, task_id: int) -> CommanderTask | None:
    with get_sync_session() as session:
        return session.execute(
            select(CommanderTask).where(
                CommanderTask.commander_id == commander_id,
                CommanderTask.task_id == task_id,
            )
        ).scalar_one_or_none()


def upsert_commander_task_progress(
    commander_id: int, task_id: int, progress: int, submit_time: int = 0
):
    with get_sync_session() as session:
        obj = session.execute(
            select(CommanderTask).where(
                CommanderTask.commander_id == commander_id,
                CommanderTask.task_id == task_id,
            )
        ).scalar_one_or_none()
        if obj is None:
            obj = CommanderTask(
                commander_id=commander_id,
                task_id=task_id,
                progress=progress,
                submit_time=submit_time,
            )
            session.add(obj)
        else:
            obj.progress = progress
            if submit_time:
                obj.submit_time = submit_time
        session.commit()


def create_or_accept_task(commander_id: int, task_id: int, accept_time: int) -> None:
    store = get_default_store()
    if store is None:
        return
    store.execute(
        "INSERT INTO commander_tasks (commander_id, task_id, progress, accept_time, submit_time) "
        "VALUES ($1, $2, 0, $3, 0) ON CONFLICT (commander_id, task_id) DO NOTHING",
        commander_id, task_id, accept_time,
    )


def seed_commander_tasks(commander_id: int, task_ids: Sequence[int], accept_time: int) -> int:
    store = get_default_store()
    if store is None or not task_ids:
        return 0
    rows = [(commander_id, int(tid), accept_time) for tid in task_ids]
    store.executemany(
        "INSERT INTO commander_tasks (commander_id, task_id, progress, accept_time, submit_time) "
        "VALUES ($1, $2, 0, $3, 0) ON CONFLICT (commander_id, task_id) DO NOTHING",
        rows,
    )
    return len(rows)


def fetch_commander_tasks(commander_id: int, task_ids: Sequence[int]) -> list[TaskRow]:
    store = get_default_store()
    if store is None or not task_ids:
        return []
    rows = store.fetch(
        "SELECT task_id, progress, accept_time, submit_time FROM commander_tasks "
        "WHERE commander_id = $1 AND task_id = ANY($2)",
        commander_id, list(task_ids),
    )
    return [
        TaskRow(
            task_id=int(r[0]),
            progress=int(r[1] or 0),
            accept_time=int(r[2] or 0),
            submit_time=int(r[3] or 0),
        )
        for r in (rows or [])
    ]


def fetch_all_commander_tasks(commander_id: int) -> list[TaskRow]:
    store = get_default_store()
    if store is None:
        return []
    rows = store.fetch(
        "SELECT task_id, progress, accept_time, submit_time "
        "FROM commander_tasks WHERE commander_id = $1 ORDER BY task_id",
        commander_id,
    )
    return [
        TaskRow(
            task_id=int(r[0]),
            progress=int(r[1] or 0),
            accept_time=int(r[2] or 0),
            submit_time=int(r[3] or 0),
        )
        for r in (rows or [])
    ]


def fetch_commander_task_progress_map(
    commander_id: int, task_ids: Optional[Sequence[int]] = None
) -> dict[int, int]:
    store = get_default_store()
    if store is None:
        return {}
    if task_ids is not None:
        if not task_ids:
            return {}
        rows = store.fetch(
            "SELECT task_id, progress FROM commander_tasks "
            "WHERE commander_id = $1 AND task_id = ANY($2)",
            commander_id, list(task_ids),
        )
    else:
        rows = store.fetch(
            "SELECT task_id, progress FROM commander_tasks WHERE commander_id = $1",
            commander_id,
        )
    return {int(r[0]): int(r[1] or 0) for r in (rows or [])}


async def afetch_commander_task_progress_map(
    commander_id: int, task_ids: Optional[Sequence[int]] = None
) -> dict[int, int]:
    store = get_default_store()
    if store is None:
        return {}
    if task_ids is not None:
        if not task_ids:
            return {}
        rows = await store.afetch(
            "SELECT task_id, progress FROM commander_tasks "
            "WHERE commander_id = $1 AND task_id = ANY($2)",
            commander_id, list(task_ids),
        )
    else:
        rows = await store.afetch(
            "SELECT task_id, progress FROM commander_tasks WHERE commander_id = $1",
            commander_id,
        )
    return {int(r[0]): int(r[1] or 0) for r in (rows or [])}


def fetch_existing_task_ids(commander_id: int, task_ids: Sequence[int]) -> set[int]:
    store = get_default_store()
    if store is None or not task_ids:
        return set()
    rows = store.fetch(
        "SELECT task_id FROM commander_tasks WHERE commander_id = $1 AND task_id = ANY($2)",
        commander_id, list(task_ids),
    )
    return {int(r[0]) for r in (rows or [])}


def fetch_submitted_task_ids(
    commander_id: int, task_ids: Optional[Sequence[int]] = None
) -> set[int]:
    store = get_default_store()
    if store is None:
        return set()
    if task_ids is not None:
        if not task_ids:
            return set()
        rows = store.fetch(
            "SELECT task_id FROM commander_tasks WHERE commander_id = $1 AND submit_time <> 0 AND task_id = ANY($2)",
            commander_id, list(task_ids),
        )
    else:
        rows = store.fetch(
            "SELECT task_id FROM commander_tasks WHERE commander_id = $1 AND submit_time <> 0",
            commander_id,
        )
    return {int(r[0]) for r in (rows or [])}


def get_commander_task_submit_time(commander_id: int, task_id: int) -> Optional[int]:
    store = get_default_store()
    if store is None:
        return None
    row = store.fetchrow(
        "SELECT submit_time FROM commander_tasks WHERE commander_id = $1 AND task_id = $2",
        commander_id, task_id,
    )
    return int(row[0] or 0) if row is not None else None


def upsert_task_progress_least(
    commander_id: int, task_id: int, delta: int, target_num: int, accept_time: int
) -> None:
    store = get_default_store()
    if store is None or target_num <= 0:
        return
    store.execute(
        "INSERT INTO commander_tasks (commander_id, task_id, progress, accept_time, submit_time) "
        "VALUES ($1, $2, LEAST($3, $4), $5, 0) "
        "ON CONFLICT (commander_id, task_id) DO UPDATE "
        "SET progress = LEAST(commander_tasks.progress + $3, $4) "
        "WHERE commander_tasks.submit_time = 0",
        commander_id, task_id, delta, target_num, accept_time,
    )


def delete_commander_tasks(commander_id: int, task_ids: Sequence[int]) -> None:
    store = get_default_store()
    if store is None or not task_ids:
        return
    store.execute(
        "DELETE FROM commander_tasks WHERE commander_id = $1 AND task_id = ANY($2)",
        commander_id, list(task_ids),
    )

