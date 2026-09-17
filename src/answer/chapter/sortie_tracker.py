from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Optional

from src.logger.logger import log_event, LOG_LEVEL_INFO


@dataclass
class ChapterSortieTracker:
    chapter_id: int
    start_time: int
    total_combat_time: int = 0
    loading_overhead: int = 0
    battles_count: int = 0


_SORTIE_TRACKERS: dict[int, ChapterSortieTracker] = {}


def start_chapter_sortie(commander_id: int, chapter_id: int, start_time: Optional[int] = None) -> ChapterSortieTracker:
    """Initialize or reset the sortie tracker for a commander starting a chapter."""
    if start_time is None:
        start_time = int(time.time())
    tracker = ChapterSortieTracker(
        chapter_id=chapter_id,
        start_time=start_time,
    )
    _SORTIE_TRACKERS[commander_id] = tracker
    log_event(
        "Chapter/SortieTracker",
        "Start",
        f"commander={commander_id} chapter={chapter_id} start_time={start_time}",
        LOG_LEVEL_INFO,
    )
    return tracker


def record_battle_overhead(
    commander_id: int,
    battle_start_ts: int,
    combat_duration: int,
    now_ts: Optional[int] = None,
) -> int:
    """Record loading screen and end-of-combat overhead for a finished battle.

    Calculates:
      wall_clock = max(0, now_ts - battle_start_ts)
      overhead = max(0, wall_clock - combat_duration)

    Adds the overhead to the commander's active sortie tracker if present.
    Returns the overhead in seconds.
    """
    if now_ts is None:
        now_ts = int(time.time())
    wall_clock = max(0, now_ts - battle_start_ts)
    overhead = max(0, wall_clock - max(0, combat_duration))

    tracker = _SORTIE_TRACKERS.get(commander_id)
    if tracker is not None:
        tracker.loading_overhead += overhead
        tracker.total_combat_time += max(0, combat_duration)
        tracker.battles_count += 1
        log_event(
            "Chapter/SortieTracker",
            "BattleOverhead",
            f"commander={commander_id} chapter={tracker.chapter_id} "
            f"wall_clock={wall_clock} combat={combat_duration} overhead={overhead} "
            f"accum_overhead={tracker.loading_overhead} total_combat={tracker.total_combat_time}",
            LOG_LEVEL_INFO,
        )
    return overhead


def get_sortie_loading_overhead(commander_id: int, chapter_id: int) -> int:
    """Return total accumulated loading and transition overhead for the sortie."""
    tracker = _SORTIE_TRACKERS.get(commander_id)
    if tracker is not None and tracker.chapter_id == chapter_id:
        return tracker.loading_overhead
    return 0


def calculate_effective_duration(commander_id: int, chapter_id: int, wall_clock_duration: int) -> int:
    """Calculate clear duration excluding loading and transition screens.

    effective_duration = max(1, wall_clock_duration - loading_overhead)
    """
    overhead = get_sortie_loading_overhead(commander_id, chapter_id)
    return max(1, wall_clock_duration - overhead)


def finish_chapter_sortie(commander_id: int) -> Optional[ChapterSortieTracker]:
    """Clean up and return the sortie tracker when the chapter is finished or aborted."""
    return _SORTIE_TRACKERS.pop(commander_id, None)
