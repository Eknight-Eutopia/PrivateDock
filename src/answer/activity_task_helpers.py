

ACTIVITY_TASK_RESULT_SUCCESS = 0
ACTIVITY_TASK_RESULT_FAILURE = 1
QUICK_TASK_TICKET_ITEM_ID = 15013


def load_activity_task_template(task_id: int) -> dict:
    from src.orm.config_entry import get_config_entry
    from src.db.store import NotFoundError
    import json

    key = str(task_id)
    try:
        entry = get_config_entry("ShareCfg/task_data_template.json", key)
    except NotFoundError:
        entry = get_config_entry("sharecfgdata/task_data_template.json", key)
    data = entry.data if isinstance(entry.data, str) else json.dumps(entry.data)
    return json.loads(data)


def load_activity_task_id_set(act_id: int) -> set:
    from .activity_templates import load_activity_template
    from .activity_builders import _parse_activity_task_ids

    template = load_activity_template(act_id)
    ids = _parse_activity_task_ids(template.get("config_data", []))
    return set(ids)


def build_award_drop_map(award_display: list) -> dict:
    drops = {}
    for entry in award_display:
        if len(entry) < 3:
            continue
        drop_type = entry[0]
        drop_id = entry[1]
        count = entry[2]
        if count == 0:
            continue
        key = f"{drop_type}_{drop_id}"
        if key in drops:
            drops[key]["number"] = drops[key].get("number", 0) + count
        else:
            drops[key] = {"type": drop_type, "id": drop_id, "number": count}
    return drops


def activity_drop_map_to_sorted_list(drops: dict) -> list:
    keys = sorted(drops.keys())
    return [drops[k] for k in keys]


def apply_activity_task_drops(commander, drops: dict):
    from src.consts.drop_types import (DROP_TYPE_RESOURCE, DROP_TYPE_ITEM, DROP_TYPE_VITEM,
                                       DROP_TYPE_ICON_FRAME, DROP_TYPE_CHAT_FRAME, DROP_TYPE_COMBAT_UI_STYLE)
    from src.db.store import get_default_store
    store = get_default_store()
    for key, drop in drops.items():
        drop_type = drop.get("type") or drop.get("Type") or 0
        drop_id = drop.get("id") or drop.get("Id") or 0
        count = drop.get("number") or drop.get("Number") or 0
        if drop_type == DROP_TYPE_RESOURCE:
            commander.add_resource(drop_id, count)
        elif drop_type == DROP_TYPE_ITEM:
            commander.add_item(drop_id, count)
        elif drop_type == DROP_TYPE_VITEM:
            continue
        elif drop_type in (DROP_TYPE_ICON_FRAME, DROP_TYPE_CHAT_FRAME, DROP_TYPE_COMBAT_UI_STYLE):
            from src.orm.commander_attire import grant_commander_attire_drop_sync
            grant_commander_attire_drop_sync(commander.commander_id, drop_type, drop_id, count)
        else:
            raise ValueError(f"unsupported drop type {drop_type}")
