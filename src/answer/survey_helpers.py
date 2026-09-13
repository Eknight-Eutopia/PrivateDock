import json
from typing import Optional

from src.db.store import get_default_store
from src.orm.config_entry import afetch_config_entries_data

SURVEY_ACTIVITY_TYPE = 101


async def active_survey_activity(commander_level: int, survey_id: int) -> Optional[dict]:
    rows = await afetch_config_entries_data("ShareCfg/activity_template.json")
    allowlist_rows = await afetch_config_entries_data("ShareCfg/activity_allowlist.json")
    if not rows or not allowlist_rows:
        return None

    allowlist = []
    for parsed in allowlist_rows:
        if isinstance(parsed, list):
            for item in parsed:
                if isinstance(item, dict):
                    allowlist.append(item.get("id", 0))
                elif isinstance(item, (int, float)):
                    allowlist.append(int(item))
        elif isinstance(parsed, dict):
            allowlist.append(parsed.get("id", 0))

    templates_map = {}
    for template in rows:
        if isinstance(template, dict):
            tid = template.get("id", 0)
            if tid:
                templates_map[tid] = template

    for activity_id in allowlist:
        template = templates_map.get(activity_id)
        if template is None:
            continue
        if template.get("type") != SURVEY_ACTIVITY_TYPE:
            continue
        config_data = template.get("config_data", [])
        if not config_data:
            continue
        config = config_data
        if isinstance(config, str):
            config = json.loads(config)
        if not isinstance(config, list) or len(config) < 2:
            continue
        open_flag = config[0]
        level_req = config[1]
        if open_flag != 1:
            continue
        if commander_level < level_req:
            continue
        if template.get("config_id") != survey_id:
            continue
        return {
            "activity_id": template["id"],
            "survey_id": template["config_id"],
            "required_level": level_req,
        }
    return None


async def upsert_survey_state(commander_id: int, survey_id: int) -> None:
    store = get_default_store()
    if store is None:
        return

    try:
        import datetime
        now = datetime.datetime.now(datetime.timezone.utc)
        await store.aexecute(
            "INSERT INTO survey_states (commander_id, survey_id, completed_at) "
            "VALUES ($1, $2, $3) "
            "ON CONFLICT (commander_id) DO UPDATE SET survey_id = $2, completed_at = $3",
            commander_id, survey_id, now,
        )
    except Exception:
        pass
