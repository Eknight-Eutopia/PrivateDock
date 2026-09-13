from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Optional

from src.db.store import get_default_store
from src.orm.config_entry import list_config_entries_sync
from src.protobuf import protobuf

ESCORT_TEMPLATE_CATEGORY = "ShareCfg/escort_template.json"
ESCORT_MAP_TEMPLATE_CATEGORY = "ShareCfg/escort_map_template.json"


@dataclass
class EscortTemplate:
    id: int
    gardroad_reward: Optional[list] = None


@dataclass
class EscortMapTemplate:
    id: int
    refresh_time: int = 0
    drop_by_warn: Optional[list[int]] = None
    escort_id_list: Optional[list] = None


@dataclass
class EscortConfig:
    templates: dict[int, EscortTemplate] = field(default_factory=dict)
    maps: list[EscortMapTemplate] = field(default_factory=list)


def get_escort_config() -> EscortConfig:
    templates_raw = list_config_entries_sync(ESCORT_TEMPLATE_CATEGORY)
    maps_raw = list_config_entries_sync(ESCORT_MAP_TEMPLATE_CATEGORY)

    templates = {}
    for entry in templates_raw:
        data = json.loads(entry.data) if isinstance(entry.data, str) else entry.data
        template = EscortTemplate(**data)
        templates[template.id] = template

    maps = []
    for entry in maps_raw:
        data = json.loads(entry.data) if isinstance(entry.data, str) else entry.data
        maps.append(EscortMapTemplate(**data))

    return EscortConfig(templates=templates, maps=maps)


def load_escort_state(account_id: int) -> list:
    store = get_default_store()
    rows = store.fetch(
        "SELECT line_id, award_timestamp, flash_timestamp, map_positions FROM escort_states WHERE account_id = $1",
        account_id,
    )
    infos = []
    for row in rows:
        positions = []
        map_positions = row[3]
        if map_positions:
            raw = json.loads(map_positions) if isinstance(map_positions, str) else map_positions
            for pos in raw:
                positions.append(protobuf.ESCORT_POS(
                    map_id=pos.get("map_id", 0),
                    chapter_id=pos.get("chapter_id", 0),
                ))
        infos.append(protobuf.ESCORT_INFO(
            line_id=row[0],
            award_timestamp=row[1],
            flash_timestamp=row[2],
            map=positions,
        ))
    return infos


def update_escort_timestamps(account_id: int, line_id: int, award_ts: int, flash_ts: int) -> None:
    store = get_default_store()
    store.execute(
        "INSERT INTO escort_states (account_id, line_id, award_timestamp, flash_timestamp, map_positions) "
        "VALUES ($1, $2, $3, $4, '[]'::jsonb) "
        "ON CONFLICT (account_id, line_id) "
        "DO UPDATE SET award_timestamp = EXCLUDED.award_timestamp, "
        "flash_timestamp = EXCLUDED.flash_timestamp, "
        "map_positions = EXCLUDED.map_positions",
        account_id, line_id, award_ts, flash_ts,
    )
