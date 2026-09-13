"""Coin amount overrides, loaded from ``configurations/coin_override.json``.

Two independent knobs live in that file:

* ``default`` — ``[min, max]`` gold range for research/technology completion
  coin rewards (see :func:`get_coin_range`), used by
  ``src/answer/technology/handlers.py``.
* ``coin_word_amounts`` — ``[min, max]`` gold range per expedition
  ``award_display`` coin word, e.g. ``"Few"``/``"Numerous"`` (see
  :func:`get_coin_word_range`), used by ``src/answer/battle_session.py``.

The file is cached in-process; call :func:`reload_coin_override` (or restart the
server) after editing it.
"""

import json
import os
from pathlib import Path
from typing import Optional, Tuple

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

_CONFIG_FILENAME = "coin_override.json"


def _resolve_path() -> str:
    """Path of ``configurations/coin_override.json`` (repo-root relative)."""
    cand = _PROJECT_ROOT / "configurations" / _CONFIG_FILENAME
    if cand.is_file():
        return str(cand)
    # Fall back to the working directory, mirroring the other src/config loaders.
    return os.path.abspath(os.path.join("configurations", _CONFIG_FILENAME))


_CACHE = None


def load_coin_override() -> dict:
    """Whole config document (cached; see :func:`reload_coin_override`)."""
    global _CACHE
    if _CACHE is None:
        try:
            with open(_resolve_path(), "r", encoding="utf-8") as f:
                _CACHE = json.load(f) or {}
        except (json.JSONDecodeError, OSError):
            _CACHE = {}
    return _CACHE


def reload_coin_override() -> None:
    """Drop the cache so the next access re-reads the file."""
    global _CACHE
    _CACHE = None


def _parse_range(rng) -> Optional[Tuple[int, int]]:
    """Coerce a ``[min, max]`` entry into a tuple of ints, or None if unusable."""
    if not isinstance(rng, (list, tuple)) or len(rng) < 2:
        return None
    try:
        lo, hi = int(rng[0]), int(rng[1])
    except (TypeError, ValueError):
        return None
    if hi < lo:
        hi = lo
    return lo, hi


def get_coin_range() -> Tuple[int, int]:
    """Gold range for research completion coin rewards.

    Returns (lo, hi). A hi <= 0 means "no override" (use the template amount).
    Configure via configurations/coin_override.json:
        {"default": [100, 500]}   or   {"min": 100, "max": 500}
    """
    cfg = load_coin_override()
    rng = None
    if isinstance(cfg.get("default"), (list, tuple)):
        rng = cfg["default"]
    elif "min" in cfg and "max" in cfg:
        rng = [cfg["min"], cfg["max"]]
    parsed = _parse_range(rng)
    return parsed if parsed is not None else (0, 0)


def get_coin_word_amounts() -> dict:
    """Whole ``{word: [min, max]}`` table (empty when not configured)."""
    table = load_coin_override().get("coin_word_amounts")
    return table if isinstance(table, dict) else {}


def get_coin_word_range(word: str) -> Optional[Tuple[int, int]]:
    """Gold range for an ``award_display`` coin word ("Few", "Some", "Many", ...).

    Case-insensitive. Returns (lo, hi), or None when the word is not configured —
    callers then apply their own fallback amount. Configure via
    configurations/coin_override.json:
        {"coin_word_amounts": {"few": [150, 350], ...}}
    """
    rng = get_coin_word_amounts().get(str(word).lower())
    return _parse_range(rng)
