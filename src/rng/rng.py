import random
import time
import threading


class LockedRand:
    def __init__(self, seed: int = 0):
        self._lock = threading.Lock()
        if seed:
            self._rng = random.Random(seed)
        else:
            self._rng = random.Random(
                (time.time_ns() ^ _counter()) & 0xFFFFFFFFFFFFFFFF
            )

    def uint32(self) -> int:
        with self._lock:
            return self._rng.getrandbits(32)

    def int_n(self, n: int) -> int:
        with self._lock:
            return self._rng.randrange(n)

    def uint32_n(self, n: int) -> int:
        with self._lock:
            return self._rng.randrange(n)

    def shuffle(self, x: list):
        with self._lock:
            self._rng.shuffle(x)


_counter_val = 0


def _counter() -> int:
    global _counter_val
    _counter_val += 1
    return _counter_val
