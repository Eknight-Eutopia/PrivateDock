"""Derive Charge-shop offer limits (gift packages + gem shop) from the
converted client data `data/<region>/sharecfgdata/shop_template.json`.

Writes `configurations/gift_offer_limits.json` and `configurations/gem_shop_limits.json`
— the runtime source consumed by `src/answer/shopping_command_answer.py`
(SC_16105 normal_list membership + the server-side purchase gate).

Called automatically by the `ShopOffers` importer on every reseed / fresh seed;
`scripts/generate_gift_offer_limits.py` is the manual CLI wrapper.
"""
import json
import os

from src.logger.logger import log_event, LOG_LEVEL_INFO, LOG_LEVEL_ERROR
from src.misc.update_data_helpers import CONFIGURATIONS_DIR, DATA_DIR

# genre -> output json file
GENRE_FILES = {
    "gift_package": "gift_offer_limits.json",
    "gem_shop": "gem_shop_limits.json",
}

# limit_args entries [{"level", N}, {"time", N}] -> the fields we keep
_ARG_FIELDS = ("time", "level")


def extract_offer_limits(template_data) -> dict[str, dict[int, dict]]:
    """Parse the client shop_template entries into per-genre limit dicts."""
    limits: dict[str, dict[int, dict]] = {genre: {} for genre in GENRE_FILES}
    entries = template_data.values() if isinstance(template_data, dict) else template_data
    for entry in entries:
        genre = str(entry.get("genre") or "")
        if genre not in GENRE_FILES:
            continue
        offer_id = int(entry.get("id") or 0)
        if offer_id <= 0:
            continue
        caps = {"time": 0, "group": 0, "group_limit": 0, "group_type": 0, "level": 0}
        for arg in entry.get("limit_args") or []:
            if isinstance(arg, (list, tuple)) and len(arg) >= 2 and arg[0] in _ARG_FIELDS:
                caps[arg[0]] = int(arg[1])
        caps["group"] = int(entry.get("group") or 0)
        caps["group_limit"] = int(entry.get("group_limit") or 0)
        caps["group_type"] = int(entry.get("group_type") or 0)
        limits[genre][offer_id] = caps
    return limits


def write_offer_limits(region: str, template_data=None) -> None:
    """Regenerate both limits JSON files and refresh the live in-memory dicts.

    `template_data` may be passed by the caller (the ShopOffers importer
    already has it loaded); otherwise it is read from the region data dir.
    In-memory reload happens only when the module is importable (server
    process); from standalone scripts the files alone are the deliverable.
    """
    if template_data is None:
        path = os.path.join(DATA_DIR, region, "sharecfgdata", "shop_template.json")
        try:
            with open(path, "r", encoding="utf-8") as f:
                template_data = json.load(f)
        except Exception as e:
            log_event("OfferLimits", "Read", f"failed to read {path}: {e}", LOG_LEVEL_ERROR)
            return

    limits = extract_offer_limits(template_data)
    for genre, filename in GENRE_FILES.items():
        out = {str(k): limits[genre][k] for k in sorted(limits[genre])}
        path = os.path.join(CONFIGURATIONS_DIR, filename)
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(out, f, indent=2)
                f.write("\n")
        except Exception as e:
            log_event("OfferLimits", "Write", f"failed to write {path}: {e}", LOG_LEVEL_ERROR)
            continue
        log_event("OfferLimits", "Regenerated", f"{filename}: {len(out)} {genre} entries (region={region})", LOG_LEVEL_INFO)

    try:
        from src.answer.shopping_command_answer import reload_offer_limits
    except ImportError:
        return
    reload_offer_limits(limits["gift_package"], limits["gem_shop"])
