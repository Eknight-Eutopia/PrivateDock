import json
import os
import threading
from pathlib import Path
from typing import Any, Optional

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

_CONFIG_CANDIDATES = (
    "game_variables.json",
    "gameplay_variables.json",
    "variables.json",
)

_ALIASES: dict[str, list[str]] = {
    "build_dock_slots": [
        "build_dock_slots",
        "max_simultaneous_builds",
        "simultaneous_builds",
        "build_slots",
    ],
    "max_gear_skin_boxes": [
        "max_gear_skin_boxes",
        "gear_skin_boxes",
        "max_equipment_skin_boxes",
        "equipment_skin_boxes",
    ],
    "tutorial_first_build_ship": [
        "tutorial_first_build_ship",
        "first_build_ship",
        "tutorial_build_ship",
    ],
    "exercise_bot_level_min_percent": [
        "exercise_bot_level_min_percent",
        "exercise_bot_level_min",
        "exercise_rival_level_min_percent",
        "exercise_rival_level_min",
        "exercise_npc_level_min_percent",
        "bot_level_min_percent",
        "bot_level_min",
    ],
    "exercise_bot_level_max_percent": [
        "exercise_bot_level_max_percent",
        "exercise_bot_level_max",
        "exercise_rival_level_max_percent",
        "exercise_rival_level_max",
        "exercise_npc_level_max_percent",
        "bot_level_max_percent",
        "bot_level_max",
    ],
    "exercise_recover_amount": [
        "exercise_recover_amount",
        "exercise_attempts_recover",
        "exercise_attempt_recovery",
    ],
    "exercise_refreshes_per_day": [
        "exercise_refreshes_per_day",
        "exercise_refreshes_daily",
        "exercise_daily_refreshes",
    ],
    "exercise_rival_fallback_level": [
        "exercise_rival_fallback_level",
        "exercise_rival_level",
        "exercise_bot_fallback_level",
    ],
    "commission_crit_chance_percent": [
        "commission_crit_chance_percent",
        "commission_great_success_chance",
        "commission_crit_chance",
        "event_finish_crit_chance_percent",
    ],
    "urgent_commission_spawn_chance_percent": [
        "urgent_commission_spawn_chance_percent",
        "urgent_commission_chance",
        "urgent_spawn_chance_percent",
    ],
    "sub_strike_min_damage_cap_percent": [
        "sub_strike_min_damage_cap_percent",
        "sub_strike_min_damage_cap",
        "submarine_min_damage_cap",
    ],
    "sub_strike_max_damage_cap_percent": [
        "sub_strike_max_damage_cap_percent",
        "sub_strike_max_damage_cap",
        "submarine_max_damage_cap",
    ],
    "build_time_multiplier": [
        "build_time_multiplier",
        "ship_build_time_multiplier",
        "build_duration_multiplier",
    ],
    "default_build_time_seconds": [
        "default_build_time_seconds",
        "default_build_time",
        "build_time_fallback",
    ],
    "shopstreet_goods_count": [
        "shopstreet_goods_count",
        "shiranui_goods_count",
        "shop_street_goods_count",
    ],
}

_LOCK = threading.Lock()
_CACHED_PATH: Optional[str] = None
_CACHED_MTIME: float = -1.0
_CACHE: dict[str, Any] = {}


def resolve_config_path() -> Optional[str]:
    """Find the game variables config path."""
    for filename in _CONFIG_CANDIDATES:
        cand = _PROJECT_ROOT / "configurations" / filename
        if cand.is_file():
            return str(cand)
    # Also check working directory relative path
    for filename in _CONFIG_CANDIDATES:
        rel = os.path.join("configurations", filename)
        if os.path.isfile(rel):
            return os.path.abspath(rel)
    return None


def reload_game_variables() -> None:
    """Clear the cached config to force a reload on the next call."""
    global _CACHE, _CACHED_MTIME, _CACHED_PATH
    with _LOCK:
        _CACHE = {}
        _CACHED_MTIME = -1.0
        _CACHED_PATH = None


def load_game_variables() -> dict[str, Any]:
    """Load game variables from config file with mtime-based auto-reload."""
    global _CACHE, _CACHED_MTIME, _CACHED_PATH
    path = resolve_config_path()
    if path is None:
        return {}

    with _LOCK:
        try:
            mtime = os.path.getmtime(path)
        except OSError:
            mtime = -1.0

        if path == _CACHED_PATH and mtime == _CACHED_MTIME and _CACHE:
            return _CACHE

        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                _CACHE = data
                _CACHED_PATH = path
                _CACHED_MTIME = mtime
            else:
                _CACHE = {}
        except (json.JSONDecodeError, OSError):
            # If reading/parsing fails, retain old cache or empty
            pass

        return _CACHE


def get_game_variable(key: str, default: Any = None) -> Any:
    """Retrieve a game variable by key or alias, falling back to default."""
    cfg = load_game_variables()
    aliases = _ALIASES.get(key, [key])
    for alias in aliases:
        if alias in cfg:
            return cfg[alias]
    if key in cfg:
        return cfg[key]
    return default


def get_build_dock_slots() -> int:
    """Number of simultaneous ship build slots (default 4)."""
    raw = get_game_variable("build_dock_slots", 4)
    try:
        val = int(raw)
        return max(1, val)
    except (TypeError, ValueError):
        return 4


def get_tutorial_first_build_ship() -> Optional[int]:
    """Fixed ship granted as every commander's FIRST build (0/absent = random roll).

    The tutorial makes each new player construct one ship; this pins its result
    so everyone starts with the same ship. Ship template id (e.g. 101171 Laffey).
    """
    raw = get_game_variable("tutorial_first_build_ship")
    if raw is None:
        return None
    try:
        val = int(raw)
    except (TypeError, ValueError):
        return None
    return val if val > 0 else None


def get_max_gear_skin_boxes() -> int:
    """Maximum number of gear skin box offers in a street shop draw (default 2)."""
    raw = get_game_variable("max_gear_skin_boxes", 2)
    try:
        val = int(raw)
        return max(0, val)
    except (TypeError, ValueError):
        return 2


def _normalize_percent_or_multiplier(val: float) -> float:
    """Convert configured percent offset or multiplier into a multiplier factor.

    If given a float in [0.1, 2.5] that is not an integer (e.g. 0.9, 1.1),
    it is treated directly as a multiplier. Otherwise, it is treated as a percentage
    offset from base level (e.g. -10 -> 0.9, 10 -> 1.1, 50 -> 1.5).
    """
    if 0.1 <= val <= 2.5 and not isinstance(val, int) and val not in (1.0, 2.0):
        return val
    return 1.0 + (val / 100.0)


def get_exercise_bot_level_min_percent() -> float:
    """Return configured exercise bot level min percent offset (default -10.0)."""
    raw = get_game_variable("exercise_bot_level_min_percent", -10)
    try:
        return float(raw)
    except (TypeError, ValueError):
        return -10.0


def get_exercise_bot_level_max_percent() -> float:
    """Return configured exercise bot level max percent offset (default 10.0)."""
    raw = get_game_variable("exercise_bot_level_max_percent", 10)
    try:
        return float(raw)
    except (TypeError, ValueError):
        return 10.0


def get_exercise_bot_level_range() -> tuple[float, float]:
    """Return (min_multiplier, max_multiplier) for exercise NPC ship levels.

    Defaults to (0.9, 1.1) which corresponds to player top-6 average +/- 10%.
    Configurable via exercise_bot_level_min_percent and exercise_bot_level_max_percent
    (supports percent offsets like -10 and 10, absolute percents like 90 and 110,
    or direct multipliers like 0.9 and 1.1).
    """
    raw_min = get_game_variable("exercise_bot_level_min_percent", -10)
    raw_max = get_game_variable("exercise_bot_level_max_percent", 10)
    try:
        min_val = float(raw_min)
    except (TypeError, ValueError):
        min_val = -10.0
    try:
        max_val = float(raw_max)
    except (TypeError, ValueError):
        max_val = 10.0

    mult1 = _normalize_percent_or_multiplier(min_val)
    mult2 = _normalize_percent_or_multiplier(max_val)
    low = max(0.01, min(mult1, mult2))
    high = max(low, max(mult1, mult2))
    return low, high


def get_exercise_recover_amount() -> int:
    """Number of exercise attempts recovered each recovery period (default 5)."""
    raw = get_game_variable("exercise_recover_amount", 5)
    try:
        return max(1, int(raw))
    except (TypeError, ValueError):
        return 5


def get_exercise_refreshes_per_day() -> int:
    """Number of free rival list refreshes allowed per day (default 5)."""
    raw = get_game_variable("exercise_refreshes_per_day", 5)
    try:
        return max(0, int(raw))
    except (TypeError, ValueError):
        return 5


def get_exercise_rival_fallback_level() -> int:
    """Fallback ship level for NPC rivals when player owns no ships (default 30)."""
    raw = get_game_variable("exercise_rival_fallback_level", 30)
    try:
        return max(1, min(125, int(raw)))
    except (TypeError, ValueError):
        return 30


def get_commission_crit_chance_percent() -> int:
    """Chance (0-100%) of Great Success ('May Find' drop) on finishing a commission (default 100)."""
    raw = get_game_variable("commission_crit_chance_percent", 100)
    try:
        return max(0, min(100, int(raw)))
    except (TypeError, ValueError):
        return 100


def get_urgent_commission_spawn_chance_percent() -> int:
    """Chance (0-100%) of spawning an urgent commission after chapter victory (default 3)."""
    raw = get_game_variable("urgent_commission_spawn_chance_percent", 3)
    try:
        return max(0, min(100, int(raw)))
    except (TypeError, ValueError):
        return 3


def get_sub_strike_damage_caps() -> tuple[float, float]:
    """Return (min_damage_cap, max_damage_cap) percentage for submarine strikes (default 3.0, 20.0)."""
    raw_min = get_game_variable("sub_strike_min_damage_cap_percent", 3.0)
    raw_max = get_game_variable("sub_strike_max_damage_cap_percent", 20.0)
    try:
        min_val = float(raw_min)
    except (TypeError, ValueError):
        min_val = 3.0
    try:
        max_val = float(raw_max)
    except (TypeError, ValueError):
        max_val = 20.0
    low = max(0.0, min_val)
    high = max(low, max_val)
    return low, high


def get_build_time_multiplier() -> float:
    """Multiplier applied to ship construction time (default 1.0; 0.0 = instant)."""
    raw = get_game_variable("build_time_multiplier", 1.0)
    try:
        return max(0.0, float(raw))
    except (TypeError, ValueError):
        return 1.0


def get_default_build_time_seconds() -> int:
    """Fallback build time in seconds if not found in build_times.json (default 600)."""
    raw = get_game_variable("default_build_time_seconds", 600)
    try:
        return max(0, int(raw))
    except (TypeError, ValueError):
        return 600


def get_shopstreet_goods_count() -> int:
    """Number of goods items offered on Shiranui's shopping street (default 10)."""
    raw = get_game_variable("shopstreet_goods_count", 10)
    try:
        return max(1, int(raw))
    except (TypeError, ValueError):
        return 10

