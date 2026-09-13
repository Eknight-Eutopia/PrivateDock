from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select

from src.db.session import get_sync_session
from src.orm.config_entry import ConfigEntry

TECHNOLOGY_SHADOW_UNLOCK_CATEGORY = "ShareCfg/technology_shadow_unlock.json"


@dataclass
class TechnologyShadowUnlockConfig:
    id: int = 0
    type: int = 0
    target_num: int = 0


def get_technology_shadow_unlock_config(id: int) -> TechnologyShadowUnlockConfig | None:
    with get_sync_session() as session:
        result = session.execute(
            select(ConfigEntry).where(
                ConfigEntry.category == TECHNOLOGY_SHADOW_UNLOCK_CATEGORY,
                ConfigEntry.key == str(id),
            )
        )
        entry = result.scalar_one_or_none()
    if entry is None:
        return None
    return TechnologyShadowUnlockConfig(**entry.data)
