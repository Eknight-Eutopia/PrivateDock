from datetime import datetime, timezone
from typing import Optional

PERMANENT_ACTIVITY_TABLE_KEY = "permanent_activity_data"
PERMANENT_ACTIVITY_TABLE_CONFIG_PREFIX = "permanent_activity_config_"


def is_permanent_activity_open(activity_id: int, now: Optional[datetime] = None) -> bool:
    if now is None:
        now = datetime.now(timezone.utc)
    config = load_permanent_activity_config(activity_id)
    if config is None:
        return False
    start_time = config.get("start_time", 0.0)
    stop_time = config.get("stop_time", 0.0)
    now_ts = now.timestamp()
    return start_time <= now_ts < stop_time if stop_time > 0 else now_ts >= start_time


def load_permanent_activity_config(activity_id: int) -> Optional[dict]:
    from src.db.store import NotFoundError
    from src.orm.config_entry import get_config_entry
    key = f"{PERMANENT_ACTIVITY_TABLE_CONFIG_PREFIX}{activity_id}"
    try:
        entry = get_config_entry(PERMANENT_ACTIVITY_TABLE_KEY, key)
        if isinstance(entry, dict):
            return entry
    except NotFoundError:
        pass
    except Exception:
        pass
    return None
