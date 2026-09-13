import json
import os
import random
from typing import Dict, Optional


def _resolve_path() -> str:
    here = os.path.dirname(os.path.abspath(__file__))
    cur = here
    for _ in range(6):
        cand = os.path.join(cur, "configurations", "chapter_core_data_drops.json")
        if os.path.exists(cand):
            return cand
        parent = os.path.dirname(cur)
        if parent == cur:
            break
        cur = parent
    return os.path.join("configurations", "chapter_core_data_drops.json")


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


def get_core_data_amount(stage_id: int) -> Optional[int]:
    # Per-stage Core Data (virtual item 59900) drop amount for hard-mode chapters.
    # Keyed by the hard-mode stage id (e.g. 10101 = chapter 1 hard stage 1).
    # A value may be a fixed integer, or a [min, max] range (rolled per battle).
    # Falls back to "default" if the stage id is not present. Returns None when
    # no amount is configured (the caller keeps the base count of 1).
    cfg = load()
    entry = cfg.get(str(stage_id))
    if entry is None:
        entry = cfg.get("default")
    if entry is None:
        return None
    if isinstance(entry, list) and len(entry) >= 2:
        try:
            lo, hi = int(entry[0]), int(entry[1])
        except (TypeError, ValueError):
            return None
        if hi < lo:
            hi = lo
        return random.randint(lo, hi) if hi > lo else lo
    if isinstance(entry, int):
        return entry
    return None
