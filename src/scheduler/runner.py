import asyncio
from typing import Callable, Optional

TickJob = Callable[[], None]


class Runner:
    def __init__(self, interval: float, *jobs: TickJob):
        self.interval = interval
        self.jobs = list(jobs)
        self._task: Optional[asyncio.Task] = None

    async def run(self):
        while True:
            await asyncio.sleep(self.interval)
            for job in self.jobs:
                try:
                    job()
                except Exception:
                    pass

    def start(self):
        self._task = asyncio.create_task(self.run())

    def stop(self):
        if self._task:
            self._task.cancel()
