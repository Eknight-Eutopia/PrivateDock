from __future__ import annotations

from sqlalchemy import BigInteger, Float, select
from sqlalchemy.orm import Mapped, mapped_column

from src.db.session import Base, get_sync_session


def get_or_create_commander_dorm_state(commander_id: int):
    with get_sync_session() as session:
        result = session.execute(
            select(CommanderDormState).where(CommanderDormState.commander_id == commander_id)
        )
        state = result.scalar_one_or_none()
        if state is None:
            from src.orm.config_entry import get_config_entry_sync
            entry = get_config_entry_sync("ShareCfg/dorm_data_template.json", "1")
            capacity = 0
            if entry is not None and hasattr(entry, "data"):
                import json
                raw = entry.data
                if isinstance(raw, str):
                    try:
                        raw = json.loads(raw)
                    except Exception:
                        raw = {}
                if isinstance(raw, dict):
                    capacity = int(raw.get("capacity", 0))
            state = CommanderDormState(
                commander_id=commander_id,
                level=1,
                food=capacity,
                food_max_increase=0,
                floor_num=1,
                exp_pos=2,
            )
            session.add(state)
            session.commit()
            session.refresh(state)
        else:
            if state.food == 0 and state.food_max_increase == 0 and state.level == 0:
                from src.orm.config_entry import get_config_entry_sync
                entry = get_config_entry_sync("ShareCfg/dorm_data_template.json", "1")
                if entry is not None and hasattr(entry, "data"):
                    raw = entry.data
                    if isinstance(raw, str):
                        import json
                        raw = json.loads(raw)
                    if isinstance(raw, dict):
                        capacity = int(raw.get("capacity", 0))
                        if capacity > 0:
                            state.level = 1
                            state.food = capacity
                            state.floor_num = 1
                            state.exp_pos = 2
                            session.commit()
                            session.refresh(state)
        return state


def save_commander_dorm_state(state):
    with get_sync_session() as session:
        is_orm = hasattr(state, 'commander_id') and not isinstance(state, dict)
        cid = state.commander_id if is_orm else state.get("commander_id", 0)
        result = session.execute(
            select(CommanderDormState).where(CommanderDormState.commander_id == cid)
        )
        obj = result.scalar_one_or_none()
        if obj is None:
            return
        fields = (
            "level", "food", "food_max_increase_count", "food_max_increase",
            "floor_num", "exp_pos", "next_timestamp", "load_exp", "load_food",
            "load_time", "updated_at_unix_timestamp", "pop_time_accum",
            "exp_fraction",
        )
        for field in fields:
            val = getattr(state, field) if is_orm else state.get(field, 0)
            setattr(obj, field, val)
        session.commit()


class CommanderDormState(Base):
    __tablename__ = 'commander_dorm_states'
    commander_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    level: Mapped[int] = mapped_column(BigInteger, default=0)
    food: Mapped[int] = mapped_column(BigInteger, default=0)
    food_max_increase_count: Mapped[int] = mapped_column(BigInteger, default=0)
    food_max_increase: Mapped[int] = mapped_column(BigInteger, default=0)
    floor_num: Mapped[int] = mapped_column(BigInteger, default=0)
    exp_pos: Mapped[int] = mapped_column(BigInteger, default=0)
    next_timestamp: Mapped[int] = mapped_column(BigInteger, default=0)
    load_exp: Mapped[int] = mapped_column(BigInteger, default=0)
    load_food: Mapped[int] = mapped_column(BigInteger, default=0)
    load_time: Mapped[int] = mapped_column(BigInteger, default=0)
    updated_at_unix_timestamp: Mapped[int] = mapped_column(BigInteger, default=0)
    pop_time_accum: Mapped[int] = mapped_column(BigInteger, default=0)
    exp_fraction: Mapped[float] = mapped_column(Float, default=0.0)
