from __future__ import annotations

from datetime import datetime


def ordered_builds(builds: list) -> list:
    if not builds:
        return []
    return sorted(builds, key=lambda b: b["id"] if isinstance(b, dict) else b.id)


def remaining_seconds(finish_time: datetime, now: datetime) -> int:
    remaining = (finish_time - now).total_seconds()
    if remaining <= 0:
        return 0
    return int(remaining)


ordered_builds_sync = ordered_builds
remaining_seconds_sync = remaining_seconds
