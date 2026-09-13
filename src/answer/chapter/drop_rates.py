import json
import os
import random
from typing import Dict, List, Tuple


_CAMPAIGN_FILE = "drop_rates_campaign.json"

# S-rank battle rating in BattleScore (S = 4).
S_RANK_SCORE = 4

PLATE_BASES = {
    "general": 17000,
    "main_gun": 17010,
    "torpedo": 17020,
    "antiair": 17030,
    "aircraft": 17040,
}


def _resolve_path(filename: str) -> str:
    here = os.path.dirname(os.path.abspath(__file__))
    cur = here
    for _ in range(6):
        cand = os.path.join(cur, "configurations", filename)
        if os.path.exists(cand):
            return cand
        parent = os.path.dirname(cur)
        if parent == cur:
            break
        cur = parent
    return os.path.join("configurations", filename)


_CACHE: Dict[str, dict] = {}


def _read_file(filename: str) -> dict:
    path = _resolve_path(filename)
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}
    return data or {}


def load_campaign_rates() -> dict:
    cached = _CACHE.get(_CAMPAIGN_FILE)
    if cached is None:
        cached = _read_file(_CAMPAIGN_FILE)
        _CACHE[_CAMPAIGN_FILE] = cached
    return cached


def load_rates(is_boss: bool = False, fleet_size: str = None) -> dict:
    campaign = load_campaign_rates()
    if campaign:
        fs = fleet_size or ("boss" if is_boss else "medium")
        if fs in campaign:
            return campaign[fs]
    return {}


def reload_rates() -> None:
    _CACHE.clear()


def resolve_fleet_profile(expedition_id: int, is_boss: bool = False) -> Tuple[str, str]:
    """Resolves (fleet_size, fleet_role) from expedition_data_template.
    fleet_size: 'small', 'medium', 'large', 'elite', 'boss'
    fleet_role: 'recon', 'main', 'aviation', 'cargo', 'elite', 'boss'
    """
    if is_boss:
        return "boss", "boss"
    if not expedition_id:
        return "medium", "recon"

    ftype = None
    try:
        from src.orm.config_entry import get_config_entry
        cfg = get_config_entry("sharecfgdata/expedition_data_template.json", str(expedition_id))
        data = cfg.data if hasattr(cfg, "data") else (cfg if isinstance(cfg, dict) else None)
        if data:
            ftype = data.get("type")
    except Exception:
        ftype = None

    if ftype == 99:
        return "boss", "boss"

    mapping = {
        1: ("small", "recon"),
        2: ("medium", "recon"),
        3: ("large", "recon"),
        4: ("small", "main"),
        5: ("medium", "main"),
        6: ("large", "main"),
        7: ("small", "aviation"),
        8: ("medium", "aviation"),
        9: ("large", "aviation"),
        10: ("small", "cargo"),
        11: ("medium", "cargo"),
        12: ("large", "cargo"),
        14: ("elite", "elite"),
        99: ("boss", "boss"),
    }
    return mapping.get(ftype, ("medium", "recon"))


def chapter_number(chapter_id: int) -> int:
    if not chapter_id:
        return 1
    cid = int(chapter_id)
    if 10000 < cid <= 11599:
        cid -= 10000
    return max(1, cid // 100)


def max_plate_tier_for_chapter(chapter_id: int) -> int:
    ch = chapter_number(chapter_id)
    if ch <= 2:
        return 1
    if ch <= 5:
        return 2
    return 3


def pick_plate_category(fleet_role: str, ratios_config: dict = None) -> str:
    if ratios_config is None:
        campaign = load_campaign_rates()
        ratios_config = campaign.get("plate_ratios", {})
    role_ratios = ratios_config.get(fleet_role) or ratios_config.get("boss") or {
        "general": 0.20, "main_gun": 0.20, "torpedo": 0.20, "antiair": 0.20, "aircraft": 0.20
    }
    keys = list(role_ratios.keys())
    weights = [float(role_ratios[k]) for k in keys]
    return random.choices(keys, weights=weights)[0]


def is_plate_item(item_id: int) -> bool:
    # 17xxx are concrete gear parts; 54010..54019 are Mystery Gear Part virtual items
    return (17000 <= item_id <= 17999) or (54010 <= item_id <= 54019)


def roll_gear_plates(
    fleet_size: str, fleet_role: str, chapter_id: int, is_boss: bool = False
) -> List[dict]:
    """Authentic tiered gear plates roller matching official server data.
    - Normal mobs: 3 independent rolls for T1, T2, T3 (capped by chapter tier).
    - Boss: 2..4 T3 plates on Ch 6+ (avg 2.71), T2 on Ch 3-5, T1 on Ch 1-2.
    - Elite: 1..2 plates (avg 1.40).
    - Role determines plate categories (Recon: Torp/Air/AA, Main: Gun/Gen/AA, etc.)
    """
    campaign = load_campaign_rates()
    ratios = campaign.get("plate_ratios", {})
    max_tier = max_plate_tier_for_chapter(chapter_id)
    drops_map: Dict[int, int] = {}

    if is_boss or fleet_size == "boss":
        # Boss drops 2..4 plates of the maximum chapter tier
        # Distribution: 2 (40%), 3 (45%), 4 (15%) -> expected ~2.75
        num_plates = random.choices([2, 3, 4], weights=[0.40, 0.45, 0.15])[0]
        for _ in range(num_plates):
            cat = pick_plate_category("boss", ratios)
            item_id = PLATE_BASES.get(cat, 17000) + max_tier
            drops_map[item_id] = drops_map.get(item_id, 0) + 1
    elif fleet_size == "elite":
        # Elite (Sirens) drops 1..2 plates of max tier -> expected ~1.40
        num_plates = random.choices([1, 2], weights=[0.60, 0.40])[0]
        for _ in range(num_plates):
            cat = pick_plate_category(fleet_role, ratios)
            item_id = PLATE_BASES.get(cat, 17000) + max_tier
            drops_map[item_id] = drops_map.get(item_id, 0) + 1
    else:
        # Normal mobs (small, medium, large): independent roll per tier
        fleet_cfg = campaign.get(fleet_size) or campaign.get("medium") or {}
        plate_rates = fleet_cfg.get("plate_rates", {})
        for tier in range(1, max_tier + 1):
            rate = float(plate_rates.get(f"t{tier}", 0.0))
            if rate > 0 and random.random() <= rate:
                cat = pick_plate_category(fleet_role, ratios)
                item_id = PLATE_BASES.get(cat, 17000) + tier
                drops_map[item_id] = drops_map.get(item_id, 0) + 1

    return [{"type": 2, "id": iid, "number": cnt} for iid, cnt in sorted(drops_map.items())]


def get_modifiers(is_boss: bool = False) -> dict:
    campaign = load_campaign_rates()
    if campaign and "modifiers" in campaign:
        return campaign["modifiers"]
    return load_rates(is_boss).get("modifiers", {}) or {}


def get_category_drop_chance(category: str, is_boss: bool = False, fleet_size: str = None) -> float:
    campaign = load_campaign_rates()
    if campaign:
        fs = fleet_size or ("boss" if is_boss else "medium")
        f_cfg = campaign.get(fs) or {}
        cat_chances = f_cfg.get("category_drop_chance", {})
        if category in cat_chances:
            return float(cat_chances[category])
    return float(load_rates(is_boss, fleet_size).get("category_drop_chance", {}).get(category, 1.0))


def get_tier_weights(is_boss: bool = False) -> Dict[str, int]:
    campaign = load_campaign_rates()
    if campaign and "tier_weights" in campaign:
        return {str(k): int(v) for k, v in campaign["tier_weights"].items()}
    return {str(k): int(v) for k, v in load_rates(is_boss).get("tier_weights", {}).items()}


def get_attempts(category: str, is_boss: bool = False, fleet_size: str = None) -> int:
    campaign = load_campaign_rates()
    if campaign:
        fs = fleet_size or ("boss" if is_boss else "medium")
        f_cfg = campaign.get(fs) or {}
        attempts = f_cfg.get("attempts", {})
        if category in attempts:
            return max(1, int(attempts[category]))
    return max(1, int(load_rates(is_boss, fleet_size).get("attempts", {}).get(category, 1)))


def effective_category_chance(
    category: str, score: int, is_boss: bool = False,

    fleet_size: str = None, fleet_role: str = None,
) -> float:
    # Tech boxes (5402x) only drop from Cargo fleets, Elite, or Boss
    if category == "tech":
        if fleet_role == "cargo" or is_boss or fleet_size in ("boss", "elite"):
            return 1.0
        return 0.0

    try:
        base = get_category_drop_chance(category, is_boss, fleet_size)
    except TypeError:
        base = get_category_drop_chance(category, is_boss)
    mods = get_modifiers(is_boss)
    # Ship drop scaling: S-rank score requirement
    if category == "ship":
        s_rank_req = int(mods.get("s_rank_score", S_RANK_SCORE))
        if score < s_rank_req:
            base = base * max(0.0, score / float(s_rank_req))
    return min(1.0, max(0.0, base))


def effective_tier_weights(chapter_id: int, is_boss: bool = False) -> Dict[str, int]:
    base = get_tier_weights(is_boss)
    mods = get_modifiers(is_boss)
    ramp = float(mods.get("chapter_tier_ramp", 0.0))
    ch = chapter_number(chapter_id)
    eff = {}
    for r, w in base.items():
        rr = int(r)
        factor = 1.0 + ramp * (ch - 1) * (rr - 1)
        eff[r] = 0 if w == 0 else max(1, int(round(w * factor)))
    return eff


def get_fleet_coin_range(fleet_size: str, is_boss: bool = False) -> Tuple[int, int]:
    campaign = load_campaign_rates()
    fs = fleet_size or ("boss" if is_boss else "medium")
    rng = campaign.get(fs, {}).get("coin_range")
    if rng and len(rng) >= 2:
        return int(rng[0]), int(rng[1])
    return (40, 90) if is_boss else (10, 25)


def classify_category(virtual_id: int) -> str:
    if 56000 <= virtual_id <= 56999:
        return "ship"
    if 55000 <= virtual_id <= 55999 or 52000 <= virtual_id <= 52099:
        return "blueprint"
    if 54030 <= virtual_id <= 54059 or 21000 <= virtual_id <= 21999:
        return "retrofit"
    if 54010 <= virtual_id <= 54019 or 17000 <= virtual_id <= 17999:
        return "gear"
    if 54020 <= virtual_id <= 54029 or 30000 <= virtual_id <= 39999:
        return "tech"
    if virtual_id == 59001:
        return "coin"
    return "other"

