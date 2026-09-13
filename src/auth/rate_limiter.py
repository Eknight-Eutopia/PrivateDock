import time


class RateEntry:
    def __init__(self):
        self.count = 0
        self.reset_at: float = 0.0


class RateLimiter:
    def __init__(self):
        self._entries: dict[str, RateEntry] = {}

    def allow(self, key: str, limit: int, window_seconds: float) -> bool:
        if limit <= 0 or window_seconds <= 0:
            return True
        now = time.monotonic()
        entry = self._entries.get(key)
        if entry is None or now > entry.reset_at:
            entry = RateEntry()
            entry.count = 1
            entry.reset_at = now + window_seconds
            self._entries[key] = entry
            return True
        if entry.count >= limit:
            return False
        entry.count += 1
        return True
