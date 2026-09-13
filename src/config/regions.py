"""Per-region game data loaded from ``configurations/regions.json``.

That file is the single definition of everything that varies by region: the
official gateway/proxy hosts, the UTC offset driving day/week/month rollovers,
the Monday-00:00 anchor timestamp and the per-platform store URLs.

Loading mirrors :mod:`src.config.game_variables` — lazy, thread-safe and
mtime-based, so editing the JSON takes effect without a restart. Consumers use
the :class:`RegionMap` singletons (``REGION_GATEWAYS.get(region, "")``), which
are read-only live ``{region: value}`` views over the file. A missing or
unreadable file degrades to :data:`_FALLBACK_REGIONS` instead of crashing.
"""

from __future__ import annotations

import json
import os
import threading
from collections.abc import Iterator, Mapping
from pathlib import Path
from typing import Any, Optional

from src.logger.logger import LOG_LEVEL_ERROR, LOG_LEVEL_WARN, log_event

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

_CONFIG_FILENAME = "regions.json"

# Applied to every region entry so consumers can rely on the keys existing
# (``GAME_PLATFORM_URL["JP"]`` is ``{}`` rather than missing).
_FIELD_DEFAULTS: dict[str, Any] = {
    "gateway": "",
    "proxy": "",
    "utc_offset_seconds": 0,
    "monday_0oclock_timestamp": 0,
    "platform_urls": {},
}

# Safety net used ONLY when configurations/regions.json is missing or
# unreadable, so a deleted/typo'd file cannot stop the server from booting
# (region validation would otherwise reject every region). This is not a second
# source of truth — change region data in the JSON, never here.
_FALLBACK_REGIONS: dict[str, dict[str, Any]] = {
    "CN": {"utc_offset_seconds": 8 * 3600},
    "EN": {"utc_offset_seconds": -7 * 3600},
    "JP": {"utc_offset_seconds": 9 * 3600},
    "KR": {"utc_offset_seconds": 9 * 3600},
    "TW": {"utc_offset_seconds": 8 * 3600},
}

_LOCK = threading.Lock()
_CACHED_PATH: Optional[str] = None
_CACHED_MTIME: float = -1.0
_CACHE: dict[str, dict[str, Any]] = {}


def resolve_config_path() -> Optional[str]:
    """Absolute path of ``configurations/regions.json``, or None if absent."""
    cand = _PROJECT_ROOT / "configurations" / _CONFIG_FILENAME
    if cand.is_file():
        return str(cand)
    rel = os.path.join("configurations", _CONFIG_FILENAME)
    if os.path.isfile(rel):
        return os.path.abspath(rel)
    return None


def reload_regions() -> None:
    """Drop the cache so the next access re-reads the file."""
    global _CACHE, _CACHED_MTIME, _CACHED_PATH
    with _LOCK:
        _CACHE = {}
        _CACHED_MTIME = -1.0
        _CACHED_PATH = None


def _normalize_regions(raw: Any) -> dict[str, dict[str, Any]]:
    """Keep only well-formed ``{region: {field: value}}`` entries, filled with defaults."""
    if not isinstance(raw, dict):
        return {}
    table: dict[str, dict[str, Any]] = {}
    for region, entry in raw.items():
        if not isinstance(region, str) or not isinstance(entry, dict):
            continue
        merged = dict(_FIELD_DEFAULTS)
        merged.update(entry)
        urls = merged.get("platform_urls")
        merged["platform_urls"] = dict(urls) if isinstance(urls, dict) else {}
        table[region] = merged
    return table


def load_regions() -> dict[str, dict[str, Any]]:
    """Normalized ``{region: fields}`` table from the config file."""
    global _CACHE, _CACHED_MTIME, _CACHED_PATH

    path = resolve_config_path()
    if path is None:
        with _LOCK:
            if not _CACHE:
                log_event(
                    "Config", "regions",
                    f"{_CONFIG_FILENAME} not found; using built-in region fallback",
                    LOG_LEVEL_WARN,
                )
                _CACHE = _normalize_regions(_FALLBACK_REGIONS)
            return _CACHE

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
        except (json.JSONDecodeError, OSError) as e:
            log_event("Config", "regions", f"failed to read {path}: {e}", LOG_LEVEL_ERROR)
            data = None

        table = _normalize_regions(data.get("regions")) if isinstance(data, dict) else {}
        if not table:
            log_event(
                "Config", "regions",
                f"{path} has no usable 'regions' table; using built-in fallback",
                LOG_LEVEL_ERROR,
            )
            table = _normalize_regions(_FALLBACK_REGIONS)

        _CACHE = table
        _CACHED_PATH = path
        _CACHED_MTIME = mtime
        return _CACHE


def all_regions() -> dict[str, dict[str, Any]]:
    """Normalized ``{region: fields}`` table.

    Named ``all_regions`` (not ``regions``) so that re-exporting it from
    ``src.config`` does not shadow this very module.
    """
    return load_regions()


def valid_regions() -> set[str]:
    """Every region code defined in the config."""
    return set(all_regions())


def entry(region: str) -> dict[str, Any]:
    """Normalized field dict for one region (defaults when unknown)."""
    found = all_regions().get(region)
    if found is not None:
        return found
    merged = dict(_FIELD_DEFAULTS)
    merged["platform_urls"] = {}
    return merged


class RegionMap(Mapping):
    """Read-only live ``{region: value}`` view over one field of the config.

    Behaves like the plain dicts it replaced (``.get(region, default)``,
    ``region in map``, ``dict(map)``), but reads through to the config on every
    access, so an edited ``regions.json`` is picked up without a restart.
    Unknown regions raise ``KeyError`` — so ``.get()`` yields the caller's
    default — while known regions missing the field yield the field default.
    """

    __slots__ = ("_field",)

    def __init__(self, field: str) -> None:
        self._field = field

    def __getitem__(self, region: str) -> Any:
        table = all_regions()
        if region not in table:
            raise KeyError(region)
        return table[region][self._field]

    def __iter__(self) -> Iterator[str]:
        return iter(all_regions())

    def __len__(self) -> int:
        return len(all_regions())

    def __eq__(self, other: object) -> bool:
        if isinstance(other, Mapping):
            return dict(self.items()) == dict(other.items())
        return NotImplemented

    __hash__ = None  # type: ignore[assignment]

    def __repr__(self) -> str:
        return f"RegionMap({self._field!r}, {dict(self.items())!r})"


REGION_GATEWAYS = RegionMap("gateway")
REGION_PROXIES = RegionMap("proxy")
MONDAY_0CLOCK_TIMESTAMPS = RegionMap("monday_0oclock_timestamp")
GAME_PLATFORM_URL = RegionMap("platform_urls")
REGION_UTC_OFFSETS = RegionMap("utc_offset_seconds")

__all__ = [
    "RegionMap",
    "REGION_GATEWAYS",
    "REGION_PROXIES",
    "MONDAY_0CLOCK_TIMESTAMPS",
    "GAME_PLATFORM_URL",
    "REGION_UTC_OFFSETS",
    "entry",
    "all_regions",
    "load_regions",
    "reload_regions",
    "resolve_config_path",
    "valid_regions",
]
