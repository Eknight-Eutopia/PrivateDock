from datetime import datetime, timezone


def next_reset(server_reset_hour: int = 0) -> float:
    now = datetime.now(timezone.utc)
    next_reset = now.replace(hour=server_reset_hour, minute=0, second=0, microsecond=0)
    if next_reset <= now:
        next_reset = next_reset.replace(day=next_reset.day + 1)
    return (next_reset - now).total_seconds()
