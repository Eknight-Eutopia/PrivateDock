import json
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select, text

from src.db.session import get_session
from src.orm.challenge_mode_state import ChallengeModeState


def _current_limit_challenge_month_bucket() -> int:
    now = datetime.now(timezone.utc)
    return now.year * 100 + now.month


class ChallengeCommanderSlot:
    def __init__(self, pos: int = 0, commander_id: int = 0):
        self.pos = pos
        self.commander_id = commander_id

    def to_dict(self) -> dict:
        return {"pos": self.pos, "commander_id": self.commander_id}

    @classmethod
    def from_dict(cls, d: dict) -> "ChallengeCommanderSlot":
        return cls(pos=d.get("pos", 0), commander_id=d.get("commander_id", 0))


class LimitChallengeStateData:
    def __init__(self):
        self.commander_id: int = 0
        self.month_bucket: int = 0
        self.best_times: dict[int, int] = []
        self.awarded: dict[int, bool] = []
        self.pass_ids: list[int] = []


def _row_to_challenge_state(row) -> ChallengeModeState:
    s = ChallengeModeState()
    s.commander_id = row.commander_id
    s.activity_id = row.activity_id
    s.mode = row.mode
    s.season_id = row.season_id or 1
    s.level = row.level or 1
    s.current_score = row.current_score or 0
    s.issl = row.issl or 0
    s.regular_group_id = row.regular_group_id or 0
    s.submarine_group_id = row.submarine_group_id or 0
    s.regular_ship_ids = list(row.regular_ship_ids) if row.regular_ship_ids else []
    s.submarine_ship_ids = list(row.submarine_ship_ids) if row.submarine_ship_ids else []
    s.regular_commanders = [ChallengeCommanderSlot.from_dict(c) for c in (row.regular_commanders or [])]
    s.submarine_commanders = [ChallengeCommanderSlot.from_dict(c) for c in (row.submarine_commanders or [])]
    return s


async def list_challenge_mode_states(commander_id: int, activity_id: int) -> list[ChallengeModeState]:
    async with get_session() as session:
        result = await session.execute(
            select(ChallengeModeState).where(
                ChallengeModeState.commander_id == commander_id,
                ChallengeModeState.activity_id == activity_id,
            ).order_by(ChallengeModeState.mode)
        )
        return [_row_to_challenge_state(r) for r in result.scalars().all()]


async def get_challenge_mode_state(commander_id: int, activity_id: int, mode: int) -> Optional[ChallengeModeState]:
    async with get_session() as session:
        result = await session.execute(
            select(ChallengeModeState).where(
                ChallengeModeState.commander_id == commander_id,
                ChallengeModeState.activity_id == activity_id,
                ChallengeModeState.mode == mode,
            )
        )
        row = result.scalar_one_or_none()
        if row is None:
            return None
        return _row_to_challenge_state(row)


async def upsert_challenge_mode_state(state: ChallengeModeState):
    async with get_session() as session:
        await session.execute(
            text("""
                INSERT INTO challenge_mode_states (
                    commander_id, activity_id, mode, season_id, level, current_score, issl,
                    regular_group_id, submarine_group_id,
                    regular_ship_ids, submarine_ship_ids,
                    regular_commanders, submarine_commanders,
                    created_at, updated_at
                ) VALUES (
                    :commander_id, :activity_id, :mode, :season_id, :level, :current_score, :issl,
                    :regular_group_id, :submarine_group_id,
                    :regular_ship_ids, :submarine_ship_ids,
                    :regular_commanders, :submarine_commanders,
                    CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
                )
                ON CONFLICT (commander_id, activity_id, mode)
                DO UPDATE SET
                    season_id = EXCLUDED.season_id,
                    level = EXCLUDED.level,
                    current_score = EXCLUDED.current_score,
                    issl = EXCLUDED.issl,
                    regular_group_id = EXCLUDED.regular_group_id,
                    submarine_group_id = EXCLUDED.submarine_group_id,
                    regular_ship_ids = EXCLUDED.regular_ship_ids,
                    submarine_ship_ids = EXCLUDED.submarine_ship_ids,
                    regular_commanders = EXCLUDED.regular_commanders,
                    submarine_commanders = EXCLUDED.submarine_commanders,
                    updated_at = CURRENT_TIMESTAMP
            """),
            {
                "commander_id": state.commander_id,
                "activity_id": state.activity_id,
                "mode": state.mode,
                "season_id": state.season_id,
                "level": state.level,
                "current_score": state.current_score,
                "issl": state.issl,
                "regular_group_id": state.regular_group_id,
                "submarine_group_id": state.submarine_group_id,
                "regular_ship_ids": json.dumps(state.regular_ship_ids or []),
                "submarine_ship_ids": json.dumps(state.submarine_ship_ids or []),
                "regular_commanders": json.dumps([c.to_dict() for c in (state.regular_commanders or [])]),
                "submarine_commanders": json.dumps([c.to_dict() for c in (state.submarine_commanders or [])]),
            },
        )
        await session.commit()


async def delete_challenge_mode_state(commander_id: int, activity_id: int, mode: int):
    async with get_session() as session:
        await session.execute(
            text("""
                DELETE FROM challenge_mode_states
                WHERE commander_id = :cid AND activity_id = :aid AND mode = :mode
            """),
            {"cid": commander_id, "aid": activity_id, "mode": mode},
        )
        await session.commit()


async def load_limit_challenge_state(commander_id: int) -> LimitChallengeStateData:
    current_month = _current_limit_challenge_month_bucket()
    async with get_session() as session:
        result = await session.execute(
            select(ChallengeModeState).where(
                ChallengeModeState.commander_id == commander_id,
            )
        )
        row = result.scalar_one_or_none()
        if row is None:
            state = LimitChallengeStateData()
            state.commander_id = commander_id
            state.month_bucket = current_month
            state.best_times = {}
            state.awarded = {}
            state.pass_ids = []
            await save_limit_challenge_state(state)
            return state

        state = LimitChallengeStateData()
        state.commander_id = row.commander_id
        state.month_bucket = row.month_bucket or current_month
        state.best_times = dict(row.best_times) if row.best_times else {}
        state.awarded = {int(k): bool(v) for k, v in (row.awarded or {}).items()}
        state.pass_ids = list(row.pass_ids) if row.pass_ids else []

        if state.month_bucket != current_month:
            state.month_bucket = current_month
            state.best_times = {}
            state.awarded = {}
            state.pass_ids = []
            await save_limit_challenge_state(state)

        return state


async def save_limit_challenge_state(state: LimitChallengeStateData):
    if state.best_times is None:
        state.best_times = {}
    if state.awarded is None:
        state.awarded = {}
    if state.pass_ids is None:
        state.pass_ids = []

    pass_ids = sorted(state.pass_ids)
    best_times_encoded = {str(k): v for k, v in state.best_times.items()}
    awarded_encoded = {str(k): v for k, v in state.awarded.items()}

    async with get_session() as session:
        await session.execute(
            text("""
                INSERT INTO limit_challenge_states (
                    commander_id, month_bucket, best_times, awarded, pass_ids, created_at, updated_at
                ) VALUES (
                    :cid, :month, :best_times, :awarded, :pass_ids,
                    CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
                )
                ON CONFLICT (commander_id)
                DO UPDATE SET
                    month_bucket = EXCLUDED.month_bucket,
                    best_times = EXCLUDED.best_times,
                    awarded = EXCLUDED.awarded,
                    pass_ids = EXCLUDED.pass_ids,
                    updated_at = CURRENT_TIMESTAMP
            """),
            {
                "cid": state.commander_id,
                "month": state.month_bucket,
                "best_times": json.dumps(best_times_encoded),
                "awarded": json.dumps(awarded_encoded),
                "pass_ids": json.dumps(pass_ids),
            },
        )
        await session.commit()


def mark_limit_challenge_pass(state: LimitChallengeStateData, challenge_id: int, total_time: int):
    if state.best_times is None:
        state.best_times = {}
    if state.awarded is None:
        state.awarded = {}
    if state.pass_ids is None:
        state.pass_ids = []

    best = state.best_times.get(challenge_id, 0)
    if best == 0 or (total_time > 0 and total_time < best):
        state.best_times[challenge_id] = total_time

    if challenge_id not in state.pass_ids:
        state.pass_ids.append(challenge_id)
        state.pass_ids.sort()
