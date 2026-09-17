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


def guild_store_window(now: Optional[datetime] = None) -> Window:
    now_dt = _normalize_now(now)
    location = _current_region_location()
    local = now_dt.astimezone(location)
    # Azur Lane Guild Shop refreshes twice a week on Monday (1) and Friday (5) at 00:00 server time.
    # Python weekday(): Monday=0, Tuesday=1, Wednesday=2, Thursday=3, Friday=4, Saturday=5, Sunday=6.
    local_midnight = datetime(local.year, local.month, local.day, 0, 0, 0, 0, location)
    if local.weekday() < 4:
        # Monday (0) to Thursday (3): window started on Monday, ends Friday
        start_local = local_midnight - timedelta(days=local.weekday())
        end_local = start_local + timedelta(days=4)
    else:
        # Friday (4) to Sunday (6): window started on Friday, ends next Monday
        start_local = local_midnight - timedelta(days=local.weekday() - 4)
        end_local = start_local + timedelta(days=3)
    start = start_local.astimezone(timezone.utc)
    end = end_local.astimezone(timezone.utc)
    return Window(start=start, end=end, key=int(start.timestamp()))


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
