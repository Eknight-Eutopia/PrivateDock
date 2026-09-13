from __future__ import annotations

from typing import Optional

from sqlalchemy import select

from src.db.session import get_sync_session
from src.orm.challenge_mode_state import ChallengeModeState


# ── Sync CRUD ──


def list_challenge_mode_states(commander_id: int, activity_id: int) -> list[ChallengeModeState]:
    with get_sync_session() as session:
        result = session.execute(
            select(ChallengeModeState).where(
                ChallengeModeState.commander_id == commander_id,
                ChallengeModeState.activity_id == activity_id,
            ).order_by(ChallengeModeState.mode)
        )
        return list(result.scalars().all())


def get_challenge_mode_state(commander_id: int, activity_id: int, mode: int) -> Optional[ChallengeModeState]:
    with get_sync_session() as session:
        return session.get(ChallengeModeState, (commander_id, activity_id, mode))


def upsert_challenge_mode_state(
    commander_id: int,
    activity_id: int,
    mode: int,
    season_id: int = 1,
    level: int = 1,
    current_score: int = 0,
    issl: int = 0,
    regular_group_id: int = 0,
    submarine_group_id: int = 0,
    regular_ship_ids: Optional[list] = None,
    submarine_ship_ids: Optional[list] = None,
    regular_commanders: Optional[list] = None,
    submarine_commanders: Optional[list] = None,
):
    with get_sync_session() as session:
        obj = session.get(ChallengeModeState, (commander_id, activity_id, mode))
        if obj:
            obj.season_id = season_id
            obj.level = level
            obj.current_score = current_score
            obj.issl = issl
            obj.regular_group_id = regular_group_id
            obj.submarine_group_id = submarine_group_id
            obj.regular_ship_ids = regular_ship_ids or []
            obj.submarine_ship_ids = submarine_ship_ids or []
            obj.regular_commanders = regular_commanders or []
            obj.submarine_commanders = submarine_commanders or []
        else:
            from datetime import datetime, timezone
            now = datetime.now(timezone.utc)
            session.add(ChallengeModeState(
                commander_id=commander_id,
                activity_id=activity_id,
                mode=mode,
                season_id=season_id,
                level=level,
                current_score=current_score,
                issl=issl,
                regular_group_id=regular_group_id,
                submarine_group_id=submarine_group_id,
                regular_ship_ids=regular_ship_ids or [],
                submarine_ship_ids=submarine_ship_ids or [],
                regular_commanders=regular_commanders or [],
                submarine_commanders=submarine_commanders or [],
                created_at=now,
                updated_at=now,
            ))
        session.commit()


def delete_challenge_mode_state(commander_id: int, activity_id: int, mode: int):
    with get_sync_session() as session:
        obj = session.get(ChallengeModeState, (commander_id, activity_id, mode))
        if obj is not None:
            session.delete(obj)
            session.commit()
