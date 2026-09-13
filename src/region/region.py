import os
from datetime import datetime, timezone, timedelta

from src.config.regions import REGION_UTC_OFFSETS as _REGION_OFFSETS
from src.config.regions import valid_regions as _valid_regions

_current_region: str = ""

# UTC offset (seconds) per region, defined in configurations/regions.json. Used
# as the basis for all day/week/month rollovers (daily shop reset, research
# refresh, weekly/monthly windows, ...). That file is the single definition; do
# not duplicate region offsets elsewhere.


def offset() -> int:
    """UTC offset (seconds) for the current region; 0 if unknown."""
    return _REGION_OFFSETS.get(current(), 0)


def location() -> timezone:
    """tzinfo for the current region (UTC if unknown)."""
    return timezone(timedelta(seconds=offset()), current() or "UTC")


def local_now() -> datetime:
    """Current time expressed in the current region's local timezone."""
    return datetime.now(location())


def current() -> str:
    global _current_region
    if _current_region:
        return _current_region
    value = os.environ.get("AL_REGION", "")
    if not value:
        return "EN"
    return value


def set_current(region: str):
    validate(region)
    global _current_region
    _current_region = region


def validate(region: str):
    if region not in _valid_regions():
        raise ValueError(f"invalid region {region!r}")


def reset_for_test():
    global _current_region
    _current_region = ""
