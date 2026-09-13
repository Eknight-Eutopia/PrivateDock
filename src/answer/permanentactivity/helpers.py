from src.db.store import get_default_store
from src.orm.config_entry import fetch_config_entries_data


def list_permanent_activity_ids() -> list[int]:
    rows = fetch_config_entries_data("ShareCfg/activity_task_permanent.json")
    return [d.get("id", 0) for d in rows if isinstance(d, dict) and d.get("id")]


def get_or_create_activity_permanent_state(commander_id: int) -> dict:
    store = get_default_store()
    row = store.fetchrow(
        "SELECT commander_id, current_activity_id FROM activity_permanent_states WHERE commander_id = $1",
        commander_id
    )
    if row is None:
        store.execute(
            "INSERT INTO activity_permanent_states (commander_id, current_activity_id) VALUES ($1, 0)",
            commander_id
        )
        return {"commander_id": commander_id, "current_activity_id": 0}
    return {"commander_id": row[0], "current_activity_id": row[1]}
