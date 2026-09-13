from __future__ import annotations

from typing import Optional

from sqlalchemy import select

from src.db.session import get_sync_session
from src.orm.chapter_progress import ChapterProgress
from src.orm.chapter_state import ChapterState

# ── Local models (not in sa_models.py) ──

def get_chapter_state_sync(commander_id: int) -> Optional[ChapterState]:
    with get_sync_session() as session:
        result = session.execute(
            select(ChapterState).where(ChapterState.commander_id == commander_id)
        )
        return result.scalar_one_or_none()

def upsert_chapter_state_sync(commander_id: int, chapter_id: int, state_bytes: bytes):
    with get_sync_session() as session:
        import time
        now = int(time.time())
        obj = session.get(ChapterState, commander_id)
        if obj:
            obj.chapter_id = chapter_id
            obj.state = state_bytes
            obj.updated_at = now
        else:
            session.add(ChapterState(
                commander_id=commander_id,
                chapter_id=chapter_id,
                state=state_bytes,
                updated_at=now,
            ))
        session.commit()

def delete_chapter_state(commander_id: int):
    with get_sync_session() as session:
        obj = session.get(ChapterState, commander_id)
        if obj is not None:
            session.delete(obj)
            session.commit()

delete_chapter_state_sync = delete_chapter_state

def get_chapter_progress_sync(commander_id: int, chapter_id: int) -> Optional[ChapterProgress]:
    with get_sync_session() as session:
        result = session.execute(
            select(ChapterProgress).where(
                ChapterProgress.commander_id == commander_id,
                ChapterProgress.chapter_id == chapter_id,
            )
        )
        return result.scalar_one_or_none()

def upsert_chapter_progress_sync(progress: ChapterProgress):
    with get_sync_session() as session:
        session.merge(progress)
        session.commit()

def list_chapter_progress_sync(commander_id: int) -> list[ChapterProgress]:
    with get_sync_session() as session:
        result = session.execute(
            select(ChapterProgress).where(ChapterProgress.commander_id == commander_id)
        )
        return list(result.scalars().all())

def ensure_chapter_progress(commander_id: int, chapter_id: int):
    with get_sync_session() as session:
        result = session.execute(
            select(ChapterProgress).where(
                ChapterProgress.commander_id == commander_id,
                ChapterProgress.chapter_id == chapter_id,
            )
        )
        if result.scalar_one_or_none() is not None:
            return
        import time
        now = int(time.time())
        session.add(ChapterProgress(
            commander_id=commander_id,
            chapter_id=chapter_id,
            updated_at=now,
        ))
        session.commit()

def get_chapter_drops(commander_id: int, chapter_id: int) -> list[int]:
    # The chapter drop-ship pool is derived from the chapter template's awards
    # (see src.answer.chapter.helpers.get_chapter_drops). Delegated to avoid
    # duplicating the resolution logic here.
    from src.answer.chapter.helpers import get_chapter_drops as _resolve
    return _resolve(commander_id, chapter_id)

get_chapter_state = get_chapter_state_sync
upsert_chapter_state = upsert_chapter_state_sync
get_chapter_progress = get_chapter_progress_sync
upsert_chapter_progress = upsert_chapter_progress_sync
list_chapter_progress = list_chapter_progress_sync

def get_max_chapter_id(commander_id: int) -> int:
    from sqlalchemy import func
    with get_sync_session() as session:
        result = session.execute(
            select(func.coalesce(func.max(ChapterProgress.chapter_id), 0)).where(
                ChapterProgress.commander_id == commander_id
            )
        )
        return result.scalar() or 0


def search_chapter_states(commander_id: int, chapter_id_filter: Optional[int], updated_since_unix: Optional[int], offset: int, limit: int):
    from sqlalchemy import func
    with get_sync_session() as session:
        q = select(ChapterState).where(ChapterState.commander_id == commander_id)
        if chapter_id_filter is not None:
            q = q.where(ChapterState.chapter_id == chapter_id_filter)
        if updated_since_unix is not None:
            q = q.where(ChapterState.updated_at > updated_since_unix)
        total = session.execute(select(func.count()).select_from(q.subquery())).scalar() or 0
        q = q.order_by(ChapterState.chapter_id.asc()).offset(offset).limit(limit)
        rows = list(session.execute(q).scalars().all())
        return {"total": total, "states": rows}


def search_chapter_progress(commander_id: int, chapter_id_filter: Optional[int], updated_since_unix: Optional[int], offset: int, limit: int):
    from sqlalchemy import func
    with get_sync_session() as session:
        q = select(ChapterProgress).where(ChapterProgress.commander_id == commander_id)
        if chapter_id_filter is not None:
            q = q.where(ChapterProgress.chapter_id == chapter_id_filter)
        if updated_since_unix is not None:
            q = q.where(ChapterProgress.updated_at > updated_since_unix)
        total = session.execute(select(func.count()).select_from(q.subquery())).scalar() or 0
        q = q.order_by(ChapterProgress.chapter_id.asc()).offset(offset).limit(limit)
        rows = list(session.execute(q).scalars().all())
        return {"total": total, "progress": rows}


def list_chapter_progress_page(commander_id: int, offset: int, limit: int):
    from sqlalchemy import func
    with get_sync_session() as session:
        q = select(ChapterProgress).where(ChapterProgress.commander_id == commander_id)
        total = session.execute(select(func.count()).select_from(q.subquery())).scalar() or 0
        q = q.order_by(ChapterProgress.chapter_id.asc()).offset(offset).limit(limit)
        rows = list(session.execute(q).scalars().all())
        return {"total": total, "progress": rows}


def delete_chapter_progress(commander_id: int, chapter_id: int):
    with get_sync_session() as session:
        obj = session.execute(
            select(ChapterProgress).where(
                ChapterProgress.commander_id == commander_id,
                ChapterProgress.chapter_id == chapter_id,
            )
        ).scalar_one_or_none()
        if obj is not None:
            session.delete(obj)
            session.commit()
