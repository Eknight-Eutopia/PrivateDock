from __future__ import annotations

from typing import Optional

from sqlalchemy import select

from src.db.session import get_session, get_sync_session
from src.orm.activity_store_state import (
    ActivityStoreState,
    get_activity_store_state,
    upsert_activity_store_state,
)

# ── Sync CRUD ──

def get_activity_store_state_sync(commander_id: int, activity_id: int) -> Optional[ActivityStoreState]:
    with get_sync_session() as session:
        return session.get(ActivityStoreState, (commander_id, activity_id))

def upsert_activity_store_state_sync(commander_id: int, activity_id: int, data: str):
    with get_sync_session() as session:
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc)
        obj = session.get(ActivityStoreState, (commander_id, activity_id))
        if obj:
            obj.data = data
            obj.updated_at = now
        else:
            session.add(ActivityStoreState(
                commander_id=commander_id,
                activity_id=activity_id,
                data=data,
                created_at=now,
                updated_at=now,
            ))
        session.commit()
