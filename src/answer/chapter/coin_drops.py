import json
import os
from typing import Dict, Tuple


def _resolve_path() -> str:
    here = os.path.dirname(os.path.abspath(__file__))
    cur = here
    for _ in range(6):
        cand = os.path.join(cur, "configurations", "chapter_coin_drops.json")
        if os.path.exists(cand):
            return cand
        parent = os.path.dirname(cur)
        if parent == cur:
            break
        cur = parent
    return os.path.join("configurations", "chapter_coin_drops.json")


_CACHE: Dict = None


def load() -> dict:
    global _CACHE
    if _CACHE is None:
        try:
            with open(_resolve_path(), "r", encoding="utf-8") as f:
                _CACHE = json.load(f) or {}
        except (json.JSONDecodeError, OSError):
            _CACHE = {}
    return _CACHE


def reload() -> None:
    global _CACHE
    _CACHE = None


def get_coin_range(chapter_id: int, is_boss: bool) -> Tuple[int, int]:
    """Returns (lo, hi) coin drop range for the given chapter and boss flag.
    Delegates to drop_rates.get_fleet_coin_range using fleet size profile.
    """
    cfg = load()
    if cfg:
        entry = cfg.get(str(chapter_id)) or cfg.get("default") or {}
        key = "boss" if is_boss else "normal"
        rng = entry.get(key) or [0, 0]
        try:
            lo, hi = int(rng[0]), int(rng[1])
            if hi >= lo > 0:
                return lo, hi
        except (TypeError, ValueError, IndexError):
            pass
    from src.answer.chapter import drop_rates
    fleet_size = "boss" if is_boss else "medium"
    return drop_rates.get_fleet_coin_range(fleet_size, is_boss)
