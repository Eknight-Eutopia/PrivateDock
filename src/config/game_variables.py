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
