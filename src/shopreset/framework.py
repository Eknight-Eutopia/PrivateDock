from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from typing import Optional

from src.region.region import location as _current_region_location

FNV_OFFSET_BASIS = 1469598103934665603
FNV_PRIME = 1099511628211


@dataclass
class Window:
    start: datetime
    end: datetime
    key: int


def _normalize_now(now: Optional[datetime]) -> datetime:
    if now is None:
        return datetime.now(timezone.utc)
    if now.tzinfo is None:
        return now.replace(tzinfo=timezone.utc)
    return now


def daily_window(now: Optional[datetime] = None) -> Window:
    now_dt = _normalize_now(now)
    location = _current_region_location()
    local = now_dt.astimezone(location)
    start = datetime(local.year, local.month, local.day, 0, 0, 0, 0, location).astimezone(timezone.utc)
    end = start + timedelta(days=1)
    return Window(start=start, end=end, key=int(start.timestamp()))


def weekly_window(now: Optional[datetime] = None) -> Window:
    now_dt = _normalize_now(now)
    location = _current_region_location()
    local = now_dt.astimezone(location)
    start_local = datetime(local.year, local.month, local.day, 0, 0, 0, 0, location) - timedelta(days=local.weekday())
    start = start_local.astimezone(timezone.utc)
    end = start + timedelta(days=7)
    return Window(start=start, end=end, key=int(start.timestamp()))


def monthly_window(now: Optional[datetime] = None) -> Window:
    now_dt = _normalize_now(now)
    location = _current_region_location()
    local = now_dt.astimezone(location)
    start = datetime(local.year, local.month, 1, 0, 0, 0, 0, location).astimezone(timezone.utc)
    end = (start.astimezone(location).replace(day=28) + timedelta(days=4)).replace(day=1).astimezone(timezone.utc)
    key = local.year * 100 + local.month
    return Window(start=start, end=end, key=key)


def current_weekly_reset_unix(now: Optional[datetime] = None) -> int:
    return weekly_window(now).key


def current_daily_reset_unix(now: Optional[datetime] = None) -> int:
    return daily_window(now).key


def deterministic_seed(commander_id: int, *parts: int) -> int:
    seed = FNV_OFFSET_BASIS
    seed ^= commander_id
    seed = (seed * FNV_PRIME) & 0xFFFFFFFFFFFFFFFF
    for part in parts:
        seed ^= part
        seed = (seed * FNV_PRIME) & 0xFFFFFFFFFFFFFFFF
    return seed
