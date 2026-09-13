from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select

from src.db.session import get_sync_session
from src.orm.config_entry import ConfigEntry

SHIP_DATA_STATISTICS_CATEGORY = "sharecfgdata/ship_data_statistics.json"


@dataclass
class ShipDataStatisticsConfig:
    id: int = 0
    skin_id: int = 0


def get_ship_data_statistics_config(template_id: int) -> ShipDataStatisticsConfig | None:
    with get_sync_session() as session:
        result = session.execute(
            select(ConfigEntry).where(
                ConfigEntry.category == SHIP_DATA_STATISTICS_CATEGORY,
                ConfigEntry.key == str(template_id),
            )
        )
        entry = result.scalar_one_or_none()
    if entry is None:
        return None
    return ShipDataStatisticsConfig(**entry.data)


def get_ship_base_skin_id(template_id: int) -> int:
    config = get_ship_data_statistics_config(template_id)
    if config is None:
        return 0
    return config.skin_id
