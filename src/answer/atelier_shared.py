import json

ATELIER_RESULT_SUCCESS = 0
ATELIER_RESULT_MALFORMED_REQUEST = 1
ATELIER_RESULT_INVALID_ACTIVITY = 2
ATELIER_RESULT_INVALID_RECIPE_OR_ITEM = 3
ATELIER_RESULT_INSUFFICIENT_ITEMS = 4
ATELIER_RESULT_RECIPE_LIMIT_REACHED = 5
ATELIER_RESULT_STORAGE_FAILURE = 6

ATELIER_RECIPE_CATEGORY = "ShareCfg/activity_ryza_recipe.json"
ATELIER_CIRCLE_CATEGORY = "ShareCfg/activity_ryza_recipe_circle.json"
ATELIER_ITEM_CATEGORY = "ShareCfg/activity_ryza_item.json"


def parse_atelier_recipe_config(recipe_id: int) -> dict:
    from src.orm.config_entry import get_config_entry
    entry = get_config_entry(ATELIER_RECIPE_CATEGORY, str(recipe_id))
    data = entry.data if isinstance(entry.data, str) else json.dumps(entry.data)
    recipe = json.loads(data)
    if recipe.get("id", 0) == 0:
        recipe["id"] = recipe_id
    return recipe


def parse_atelier_recipe_allowed_items(recipe: dict) -> set:
    allowed = set()
    from src.orm.config_entry import get_config_entry
    for circle_id in recipe.get("recipe_circle", []):
        try:
            entry = get_config_entry(ATELIER_CIRCLE_CATEGORY, str(circle_id))
            data = entry.data if isinstance(entry.data, str) else json.dumps(entry.data)
            circle = json.loads(data)
            if circle.get("recipe_id", 0) != 0 and circle.get("recipe_id", 0) != recipe.get("id", 0):
                continue
            ryza_item_id = circle.get("ryza_item_id", 0)
            if ryza_item_id != 0:
                allowed.add(ryza_item_id)
        except Exception:
            continue
    return allowed


def parse_atelier_item_config(item_id: int) -> dict:
    from src.orm.config_entry import get_config_entry
    entry = get_config_entry(ATELIER_ITEM_CATEGORY, str(item_id))
    data = entry.data if isinstance(entry.data, str) else json.dumps(entry.data)
    item = json.loads(data)
    if item.get("id", 0) == 0:
        item["id"] = item_id
    return item


def atelier_item_buff_tier_count(item_config: dict) -> int:
    benefit_buff = item_config.get("benefit_buff")
    if not benefit_buff:
        return 0
    if isinstance(benefit_buff, str):
        trimmed = benefit_buff.strip()
        if not trimmed or trimmed in ("null", '""'):
            return 0
        try:
            lst = json.loads(trimmed)
            return len(lst) if isinstance(lst, list) else 0
        except (json.JSONDecodeError, TypeError):
            return 0
    elif isinstance(benefit_buff, list):
        return len(benefit_buff)
    return 0


def ensure_atelier_activity(act_id: int) -> None:
    if act_id == 0:
        raise ValueError("missing activity")
    from .activity_templates import load_activity_template
    activity = load_activity_template(act_id)
    if activity is None or activity.type != 88:
        raise ValueError("unexpected activity type")


def sorted_atelier_kvdata(entries: dict) -> list:
    result = []
    if not entries:
        return result
    keys = sorted(k for k, v in entries.items() if k != 0 and v != 0)
    for k in keys:
        result.append({"key": k, "value": entries[k]})
    return result


def sorted_atelier_slots(slots: dict) -> list:
    result = []
    for pos in range(1, 6):
        slot = slots.get(pos, {})
        result.append({
            "pos": pos,
            "itemid": slot.get("item_id", 0) if isinstance(slot, dict) else getattr(slot, "item_id", 0),
            "itemnum": slot.get("item_num", 0) if isinstance(slot, dict) else getattr(slot, "item_num", 0),
        })
    return result
