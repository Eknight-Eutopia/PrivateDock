from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy import select

from src.db.session import get_sync_session
from src.orm.config_entry import ConfigEntry


@dataclass
class SupportRarityWeight:
    rarity: int = 0
    weight: int = 0


@dataclass
class SupportRequisitionConfig:
    cost: int = 0
    rarity_weights: list[SupportRarityWeight] = field(default_factory=list)
    monthly_cap: int = 0


def load_support_requisition_config() -> SupportRequisitionConfig:
    with get_sync_session() as session:
        result = session.execute(
            select(ConfigEntry).where(
                ConfigEntry.category == "ShareCfg/gameset.json",
                ConfigEntry.key == "supports_config",
            )
        )
        entry = result.scalar_one_or_none()
    if entry is None:
        raise ValueError("support_requisition config not found")

    payload = entry.data
    description = payload.get("description")
    if not isinstance(description, list) or len(description) < 3:
        raise ValueError("supports_config description missing fields")

    cost = int(description[0])
    weights_raw = description[1]
    weights = []
    for w in weights_raw:
        if not isinstance(w, list) or len(w) != 2:
            raise ValueError("supports_config rarity entry must have 2 values")
        weights.append(SupportRarityWeight(rarity=int(w[0]), weight=int(w[1])))
    cap = int(description[2])

    return SupportRequisitionConfig(cost=cost, rarity_weights=weights, monthly_cap=cap)
