from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import BigInteger, JSON, select, text
from sqlalchemy.orm import Mapped, mapped_column

from src.db.session import Base, get_sync_session
from src.orm.config_entry import get_config_entry_sync, list_config_entries_sync
from src.region.region import location

TECHNOLOGY_DATA_TEMPLATE_CATEGORY = "ShareCfg/technology_data_template.json"


class TechnologyRefreshPoolState:
    def __init__(self, id: int = 0, target: int = 0, technologies: list | None = None):
        self.id = id
        self.target = target
        self.technologies = technologies or []

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "target": self.target,
            "technologies": [t.to_dict() if hasattr(t, "to_dict") else t for t in self.technologies],
        }

    @classmethod
    def from_dict(cls, d: dict) -> "TechnologyRefreshPoolState":
        return cls(
            id=d.get("id", 0),
            target=d.get("target", 0),
            technologies=[TechnologyProjectState.from_dict(t) for t in d.get("technologies", [])],
        )


class TechnologyProjectState:
    def __init__(self, tech_id: int = 0, finish_time: int = 0):
        self.tech_id = tech_id
        self.finish_time = finish_time

    def to_dict(self) -> dict:
        return {"tech_id": self.tech_id, "finish_time": self.finish_time}

    @classmethod
    def from_dict(cls, d: dict) -> "TechnologyProjectState":
        return cls(tech_id=d.get("tech_id", 0), finish_time=d.get("finish_time", 0))


class TechnologyQueueState:
    def __init__(self, tech_id: int = 0, refresh_id: int = 0, finish_time: int = 0):
        self.tech_id = tech_id
        self.refresh_id = refresh_id
        self.finish_time = finish_time

    def to_dict(self) -> dict:
        return {"tech_id": self.tech_id, "refresh_id": self.refresh_id, "finish_time": self.finish_time}

    @classmethod
    def from_dict(cls, d: dict) -> "TechnologyQueueState":
        return cls(tech_id=d.get("tech_id", 0), refresh_id=d.get("refresh_id", 0), finish_time=d.get("finish_time", 0))


class TechnologyDataTemplate:
    def __init__(self, id: int = 0, type: int = 0, time: int = 0, condition: int = 0,
                 blueprint_version: int = 0, consume: list | None = None, drop_client: list | None = None):
        self.id = id
        self.type = type
        self.time = time
        self.condition = condition
        self.blueprint_version = blueprint_version
        self.consume = consume or []
        self.drop_client = drop_client or []


def current_technology_day(now: datetime) -> int:
    local = now.astimezone(location())
    return local.year * 10000 + local.month * 100 + local.day


def build_technology_refresh_pools(seed: int = 0) -> list[TechnologyRefreshPoolState]:
    entries = list_config_entries_sync(TECHNOLOGY_DATA_TEMPLATE_CATEGORY)
    if not entries:
        return [TechnologyRefreshPoolState(id=1, target=0, technologies=[TechnologyProjectState(tech_id=1, finish_time=0)])]

    templates = []
    for entry in entries:
        if isinstance(entry.data, str):
            data = json.loads(entry.data)
        else:
            data = entry.data
        templates.append(TechnologyDataTemplate(
            id=data.get("id", 0),
            type=data.get("type", 0),
            time=data.get("time", 0),
            condition=data.get("condition", 0),
            blueprint_version=data.get("blueprint_version", 0),
            consume=data.get("consume", []),
            drop_client=data.get("drop_client", []),
        ))

    by_pool: dict[int, list[TechnologyProjectState]] = {}
    for t in templates:
        if t.id == 0 or t.type == 0:
            continue
        by_pool.setdefault(t.type, []).append(TechnologyProjectState(tech_id=t.id, finish_time=0))

    pool_ids = sorted(by_pool.keys())
    pools = []
    for pool_id in pool_ids:
        techs = by_pool[pool_id]
        techs.sort(key=lambda x: x.tech_id)
        max_pool_candidates = 5
        if len(techs) > max_pool_candidates:
            offset = seed % len(techs)
            rotated = techs[offset:] + techs[:offset]
            techs = rotated[:max_pool_candidates]
        pools.append(TechnologyRefreshPoolState(id=pool_id, target=0, technologies=techs))

    if not pools:
        return [TechnologyRefreshPoolState(id=1, target=0, technologies=[TechnologyProjectState(tech_id=1, finish_time=0)])]

    return pools


def get_technology_template(tech_id: int) -> TechnologyDataTemplate:
    entry = get_config_entry_sync(TECHNOLOGY_DATA_TEMPLATE_CATEGORY, str(tech_id))
    if entry is None or entry.data is None:
        return TechnologyDataTemplate(
            id=tech_id, type=1, time=60, condition=0,
            consume=[], drop_client=[[2, 59001, 1]],
        )

    if isinstance(entry.data, str):
        data = json.loads(entry.data)
    else:
        data = entry.data

    return TechnologyDataTemplate(
        id=data.get("id", tech_id),
        type=data.get("type", 1),
        time=data.get("time", 60),
        condition=data.get("condition", 0),
        blueprint_version=data.get("blueprint_version", 0),
        consume=data.get("consume", []),
        drop_client=data.get("drop_client", []),
    )


def max_technology_blueprint_version() -> int:
    entries = list_config_entries_sync(TECHNOLOGY_DATA_TEMPLATE_CATEGORY)
    if not entries:
        return 1

    max_version = 0
    for entry in entries:
        if isinstance(entry.data, str):
            data = json.loads(entry.data)
        else:
            data = entry.data
        bp_ver = data.get("blueprint_version", 0)
        if bp_ver > max_version:
            max_version = bp_ver

    return max_version if max_version > 0 else 1


def get_technology_research_state(commander_id: int) -> Optional[TechnologyResearchState]:
    with get_sync_session() as session:
        result = session.execute(
            select(TechnologyResearchState).where(TechnologyResearchState.commander_id == commander_id)
        )
        return result.scalar_one_or_none()


def save_technology_research_state(state: TechnologyResearchState) -> None:
    if state.refresh_pools is None:
        state.refresh_pools = []
    if state.queue is None:
        state.queue = []

    pools_raw = json.dumps([p.to_dict() for p in state.refresh_pools])
    queue_raw = json.dumps([q.to_dict() for q in state.queue])

    with get_sync_session() as session:
        session.execute(
            text("""
                INSERT INTO technology_research_states (
                    commander_id, refresh_flag, refresh_day, catchup_version, catchup_target,
                    refresh_pools, queue, created_at, updated_at
                )
                VALUES (
                    :commander_id, :refresh_flag, :refresh_day, :catchup_version, :catchup_target,
                    :refresh_pools, :queue, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
                )
                ON CONFLICT (commander_id)
                DO UPDATE SET
                    refresh_flag = EXCLUDED.refresh_flag,
                    refresh_day = EXCLUDED.refresh_day,
                    catchup_version = EXCLUDED.catchup_version,
                    catchup_target = EXCLUDED.catchup_target,
                    refresh_pools = EXCLUDED.refresh_pools,
                    queue = EXCLUDED.queue,
                    updated_at = CURRENT_TIMESTAMP
            """),
            {
                "commander_id": state.commander_id,
                "refresh_flag": state.refresh_flag,
                "refresh_day": state.refresh_day,
                "catchup_version": state.catchup_version,
                "catchup_target": state.catchup_target,
                "refresh_pools": pools_raw,
                "queue": queue_raw,
            },
        )
        session.commit()


def get_or_create_technology_research_state(commander_id: int) -> TechnologyResearchState:
    state = get_technology_research_state(commander_id)
    if state is not None:
        return state

    pools = build_technology_refresh_pools(0)
    state = TechnologyResearchState(
        commander_id=commander_id,
        refresh_day=current_technology_day(datetime.now(timezone.utc)),
        refresh_pools=pools,
        queue=[],
    )
    save_technology_research_state(state)
    loaded = get_technology_research_state(commander_id)
    if loaded is None:
        raise RuntimeError("failed to load technology research state after creation")
    return loaded


def load_all_technology_data_templates() -> list[TechnologyDataTemplate]:
    entries = list_config_entries_sync(TECHNOLOGY_DATA_TEMPLATE_CATEGORY)
    templates = []
    for entry in entries:
        if isinstance(entry.data, str):
            data = json.loads(entry.data)
        else:
            data = entry.data
        templates.append(TechnologyDataTemplate(
            id=data.get("id", 0),
            type=data.get("type", 0),
            time=data.get("time", 0),
            condition=data.get("condition", 0),
            blueprint_version=data.get("blueprint_version", 0),
            consume=data.get("consume", []),
            drop_client=data.get("drop_client", []),
        ))
    return templates


class TechnologyResearchState(Base):
    __tablename__ = "technology_research_states"
    commander_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    refresh_flag: Mapped[int] = mapped_column(BigInteger, default=0)
    refresh_day: Mapped[int] = mapped_column(BigInteger, default=0)
    catchup_version: Mapped[int] = mapped_column(BigInteger, default=0)
    catchup_target: Mapped[int] = mapped_column(BigInteger, default=0)
    refresh_pools: Mapped[Optional[list]] = mapped_column(JSON, default=list)
    queue: Mapped[Optional[list]] = mapped_column(JSON, default=list)
