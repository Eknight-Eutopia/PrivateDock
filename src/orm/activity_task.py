from __future__ import annotations


from sqlalchemy import select

from src.db.session import get_sync_session
from src.orm.commander_activity_task import CommanderActivityTask

ACTIVITY_TASK_PROGRESS_MODE_APPEND = 1
ACTIVITY_TASK_PROGRESS_MODE_SET = 2


def list_commander_activity_tasks(commander_id: int) -> list[CommanderActivityTask]:
    with get_sync_session() as session:
        result = session.execute(
            select(CommanderActivityTask).where(
                CommanderActivityTask.commander_id == commander_id
            )
        )
        return list(result.scalars().all())


def try_submit_ready_commander_activity_task(commander_id: int, task_id: int) -> bool:
    with get_sync_session() as session:
        result = session.execute(
            select(CommanderActivityTask).where(
                CommanderActivityTask.commander_id == commander_id,
                CommanderActivityTask.task_id == task_id,
                CommanderActivityTask.submitted == False,
                CommanderActivityTask.progress >= CommanderActivityTask.max_progress,
            )
        )
        obj = result.scalar_one_or_none()
        if obj is None:
            return False
        obj.submitted = True
        session.commit()
        return True


def try_submit_commander_activity_task(commander_id: int, task_id: int) -> bool:
    return try_submit_ready_commander_activity_task(commander_id, task_id)


def upsert_commander_activity_task_progress(commander_id: int, task_id: int, progress: int, max_progress: int):
    with get_sync_session() as session:
        result = session.execute(
            select(CommanderActivityTask).where(
                CommanderActivityTask.commander_id == commander_id,
                CommanderActivityTask.task_id == task_id,
            )
        )
        obj = result.scalar_one_or_none()
        if obj is None:
            obj = CommanderActivityTask(
                commander_id=commander_id, task_id=task_id,
                progress=progress, max_progress=max_progress, submitted=False,
            )
            session.add(obj)
        else:
            obj.progress = progress
            obj.max_progress = max_progress
        session.commit()
