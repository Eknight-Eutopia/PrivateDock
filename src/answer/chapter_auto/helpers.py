from __future__ import annotations

import json
import os
from typing import Optional, Any

from src.orm.config_entry import fetch_config_entry_data
from src.region.region import current

_STATS_CACHE: dict[int, dict] = {}


def load_chapter_auto_statistics(chapter_id: int) -> Optional[dict[str, Any]]:
    """Loads chapter auto statistics entry for a given chapter id.

    First looks up in-memory cache, then DB config_entries, then falls back
    to the repo-local data/ directory.
    """
    if chapter_id in _STATS_CACHE:
        return _STATS_CACHE[chapter_id]

    # Try DB config_entries
    try:
        data = fetch_config_entry_data("ShareCfg/chapter_auto_statistics.json", str(chapter_id))
        if isinstance(data, dict):
            _STATS_CACHE[chapter_id] = data
            return data
    except Exception:
        pass

    # Fallback to repo-local data/
    try:
        region = current() or "EN"
        data_dir = os.path.normpath(
            os.path.join(os.path.dirname(__file__), "..", "..", "..", "data")
        )
        file_path = os.path.join(data_dir, region, "ShareCfg", "chapter_auto_statistics.json")
        if os.path.exists(file_path):
            with open(file_path, "r", encoding="utf-8") as f:
                raw_list = json.load(f)
            for item in raw_list:
                if isinstance(item, dict) and "id" in item:
                    _STATS_CACHE[item["id"]] = item
            if chapter_id in _STATS_CACHE:
                return _STATS_CACHE[chapter_id]
    except Exception:
        pass

    return None


def load_chapter_auto_time_limits() -> tuple[int, int, int]:
    """Returns (daily_time_limit, ticket_to_sec_type1, ticket_to_sec_type3)."""
    base_limit = 28800
    sec_type1 = 3600
    sec_type3 = 3600
    try:
        from src.orm.config_entry import fetch_config_entry_data
        lim = fetch_config_entry_data("ShareCfg/gameset.json", "auto_battle_time_limit")
        if lim and isinstance(lim, dict) and "key_value" in lim:
            base_limit = int(lim["key_value"])
        t1 = fetch_config_entry_data("ShareCfg/gameset.json", "auto_battle_tickect_to_second_type1")
        if t1 and isinstance(t1, dict) and "key_value" in t1:
            sec_type1 = int(t1["key_value"])
        t3 = fetch_config_entry_data("ShareCfg/gameset.json", "auto_battle_tickect_to_second_type3")
        if t3 and isinstance(t3, dict) and "key_value" in t3:
            sec_type3 = int(t3["key_value"])
    except Exception:
        pass
    return base_limit, sec_type1, sec_type3
