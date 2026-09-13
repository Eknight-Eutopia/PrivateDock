from typing import Optional

CLASS_FIELD_RESOURCE_ID = 10
CLASS_UPGRADE_TEMPLATE_CONFIG = "ShareCfg/class_upgrade_template.json"
GAME_SET_CONFIG = "ShareCfg/gameset.json"
SHIP_EXP_BOOKS_GAME_SET_KEY = "ship_exp_books"
ITEM_CONFIG_CATEGORY_PRIMARY = "sharecfgdata/item_data_statistics.json"
ITEM_CONFIG_CATEGORY_FALLBACK = "ShareCfg/item_data_statistics.json"


def load_class_resource_item_id() -> int:
    from src.orm.config_entry import list_config_entries, entry_data
    entries = list_config_entries(CLASS_UPGRADE_TEMPLATE_CONFIG)
    best_level = 0
    item_id = 0
    for entry in entries:
        data = entry_data(entry)
        if not isinstance(data, dict):
            continue
        config_item_id = data.get("item_id", 0)
        level = data.get("level", 0)
        if config_item_id == 0:
            continue
        if item_id == 0 or level < best_level:
            best_level = level
            item_id = config_item_id
    return item_id


def load_item_statistics_config(item_id: int) -> Optional[dict]:
    from src.orm.config_entry import get_config_entry, entry_data
    from src.db.store import NotFoundError
    for category in (ITEM_CONFIG_CATEGORY_PRIMARY, ITEM_CONFIG_CATEGORY_FALLBACK):
        try:
            entry = get_config_entry(category, str(item_id))
            data = entry_data(entry)
            if isinstance(data, dict):
                return data
        except NotFoundError:
            continue
        except Exception:
            continue
    return None


def parse_usage_arg_exp_value(usage_arg) -> int:
    import json
    if usage_arg is None:
        return 0
    if isinstance(usage_arg, (int, float)):
        val = int(usage_arg)
        return val if val > 0 else 0
    if isinstance(usage_arg, str):
        try:
            val = int(usage_arg)
            return val if val > 0 else 0
        except (ValueError, TypeError):
            return 0
    try:
        data = json.loads(usage_arg) if isinstance(usage_arg, str) else usage_arg
    except (json.JSONDecodeError, TypeError):
        return 0
    if isinstance(data, list) and len(data) > 0:
        val = int(data[0]) if data[0] else 0
        return val if val > 0 else 0
    if isinstance(data, (int, float)):
        val = int(data)
        return val if val > 0 else 0
    if isinstance(data, str):
        try:
            val = int(data)
            return val if val > 0 else 0
        except (ValueError, TypeError):
            return 0
    return 0


def load_ship_exp_book_set() -> Optional[set]:
    from src.orm.config_entry import get_config_entry, entry_data
    from src.db.store import NotFoundError
    try:
        entry = get_config_entry(GAME_SET_CONFIG, SHIP_EXP_BOOKS_GAME_SET_KEY)
        data = entry_data(entry)
    except NotFoundError:
        return None
    except Exception:
        return None
    if not isinstance(data, dict):
        return None
    desc = data.get("description", [])
    book_ids = _collect_uint32_values(desc)
    if not book_ids:
        return None
    return set(book_ids)


def _collect_uint32_values(data) -> list:
    values = []
    if isinstance(data, (int, float)):
        if data > 0:
            values.append(int(data))
    elif isinstance(data, str):
        try:
            v = int(data)
            if v > 0:
                values.append(v)
        except (ValueError, TypeError):
            pass
    elif isinstance(data, (list, tuple)):
        for item in data:
            values.extend(_collect_uint32_values(item))
    elif isinstance(data, dict):
        for v in data.values():
            values.extend(_collect_uint32_values(v))
    return values
