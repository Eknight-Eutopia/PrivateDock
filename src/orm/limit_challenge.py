from __future__ import annotations

from typing import Any


from src.db.session import get_sync_session
from src.orm.limit_challenge_state import LimitChallengeState


# ── Sync CRUD ──


def load_limit_challenge_state(commander_id: int) -> dict[str, Any]:
    from datetime import datetime
    now = datetime.utcnow()
    current_month = now.year * 100 + now.month
    with get_sync_session() as session:
        obj = session.get(LimitChallengeState, commander_id)
        if obj is None:
            return {
                "commander_id": commander_id,
                "month_bucket": current_month,
                "best_times": {},
                "awarded": {},
                "pass_ids": [],
            }
        if obj.month_bucket != current_month:
            return {
                "commander_id": commander_id,
                "month_bucket": current_month,
                "best_times": {},
                "awarded": {},
                "pass_ids": [],
            }
        return {
            "commander_id": int(obj.commander_id),
            "month_bucket": obj.month_bucket,
            "best_times": obj.best_times or {},
            "awarded": obj.awarded or {},
            "pass_ids": obj.pass_ids or [],
        }


def save_limit_challenge_state(
    commander_id: int,
    month_bucket: int,
    best_times: dict,
    awarded: dict,
    pass_ids: list,
):
    with get_sync_session() as session:
        obj = session.get(LimitChallengeState, commander_id)
        if obj:
            obj.month_bucket = month_bucket
            obj.best_times = best_times
            obj.awarded = awarded
            obj.pass_ids = pass_ids
        else:
            session.add(LimitChallengeState(
                commander_id=commander_id,
                month_bucket=month_bucket,
                best_times=best_times,
                awarded=awarded,
                pass_ids=pass_ids,
            ))
        session.commit()
