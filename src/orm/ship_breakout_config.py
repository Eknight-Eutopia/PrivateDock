from __future__ import annotations

from typing import Optional

from src.orm.config_entry import get_config_entry_sync

BREAKOUT_CATEGORY = "sharecfgdata/ship_data_breakout.json"


class ShipBreakoutConfig:
    id: int
    breakout_id: int
    pre_id: int
    level: int
    use_gold: int
    use_item: list
    use_char: int
    use_char_num: int
    weapon_ids: list
    breakout_view: str

    def __init__(self, data: dict):
        self.id = data.get("id", 0)
        self.breakout_id = data.get("breakout_id", 0)
        self.pre_id = data.get("pre_id", 0)
        self.level = data.get("level", 0)
        self.use_gold = data.get("use_gold", 0)
        use_item = data.get("use_item") or {}
        if isinstance(use_item, dict):
            self.use_item = list(use_item.values())
        elif isinstance(use_item, list):
            self.use_item = use_item
        else:
            self.use_item = []
        self.use_char = data.get("use_char", 0)
        self.use_char_num = data.get("use_char_num", 0)
        self.weapon_ids = data.get("weapon_ids") or []
        self.breakout_view = data.get("breakout_view", "")


def get_ship_breakout_config(ship_id: int) -> Optional[ShipBreakoutConfig]:
    entry = get_config_entry_sync(BREAKOUT_CATEGORY, str(ship_id))
    if entry is None or entry.data is None:
        return None
    return ShipBreakoutConfig(entry.data)
