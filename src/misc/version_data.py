from __future__ import annotations

import json
import os
from typing import Optional

from src.misc import _get_latest_versions


def resolve_region_version(region: str) -> str:
    versions = _get_latest_versions()
    if versions:
        entry = versions.get(region)
        if entry:
            if isinstance(entry, dict):
                v = entry.get("version") or entry.get("Version")
                if v:
                    return v
            return str(entry)
    local = _load_local_versions()
    version = local.get(region)
    if version is None:
        raise ValueError(f"missing version for region {region!r}")
    return version


_local_versions: Optional[dict[str, str]] = None
_local_versions_loaded = False


def _load_local_versions() -> dict[str, str]:
    global _local_versions, _local_versions_loaded
    if _local_versions_loaded:
        return _local_versions or {}
    _local_versions_loaded = True
    candidates = [
        os.path.join(os.path.dirname(__file__), "..", "..", "data", "versions.json"),
        os.path.join("data", "versions.json"),
    ]
    for path in candidates:
        path = os.path.normpath(path)
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            _local_versions = data if isinstance(data, dict) else {}
            return _local_versions
        except (FileNotFoundError, json.JSONDecodeError):
            continue
    _local_versions = {}
    return _local_versions
