import random
from typing import Optional

from src.db.store import get_default_store
from src.orm.config_entry import fetch_config_entry_data
from src.protobuf import protobuf

SUPPORT_REQUISITION_ITEM_ID = 15001

SUPPORT_REQUISITION_RESULT_OK = 0
SUPPORT_REQUISITION_RESULT_FAILED = 1
SUPPORT_REQUISITION_RESULT_NOT_ENOUGH_MEDALS = 2
SUPPORT_REQUISITION_RESULT_LIMIT_REACHED = 30


get_config_entry = fetch_config_entry_data


def load_support_requisition_config() -> Optional[dict]:
    entry = get_config_entry("ShareCfg/gameset.json", "supports_config")
    if entry is None:
        return None
    key_value = entry.get("key_value", 0)
    description = entry.get("description", [])
    if not description or len(description) < 3:
        return None
    cost = description[0]
    weights_raw = description[1]
    monthly_cap = description[2]
    weights = []
    for w in weights_raw:
        if len(w) >= 2:
            weights.append({"rarity": w[0], "weight": w[1]})
    return {"cost": cost, "rarity_weights": weights, "monthly_cap": monthly_cap}


def get_random_requisition_ship_by_rarity(rarity: int) -> Optional[int]:
    store = get_default_store()
    row = store.fetchrow(
        "SELECT template_id FROM ships JOIN requisition_ships ON requisition_ships.ship_id = ships.template_id WHERE ships.rarity_id = $1 ORDER BY RANDOM() LIMIT 1",
        rarity
    )
    if row is None:
        return None
    return int(row[0])


def select_support_requisition_rarity(weights: list) -> int:
    total = sum(w["weight"] for w in weights)
    if total == 0:
        raise ValueError("support requisition weights are empty")
    roll = random.randint(1, total)
    cumulative = 0
    for w in weights:
        cumulative += w["weight"]
        if roll <= cumulative:
            return w["rarity"]
    raise ValueError("support requisition rarity selection failed")


def blank_assist_ship_info():
    info = protobuf.SHIPINFO()
    info.id = 0
    info.template_id = 0
    info.level = 0
    info.exp = 0
    info.energy = 0
    info.state.state = 0
    info.is_locked = 0
    info.intimacy = 0
    info.proficiency = 0
    info.create_time = 0
    info.skin_id = 0
    info.propose = 0
    info.max_level = 0
    info.activity_npc = 0
    return info
