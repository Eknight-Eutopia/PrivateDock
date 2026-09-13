from src.db.store import get_default_store


def update_commander_random_flag_ship_enabled(commander_id: int, enabled: bool) -> None:
    store = get_default_store()
    store.execute(
        "UPDATE commanders SET random_flag_ship_enabled = $1 WHERE commander_id = $2",
        enabled, commander_id
    )


def update_commander_random_ship_mode(commander_id: int, mode: int) -> None:
    store = get_default_store()
    store.execute(
        "UPDATE commanders SET random_ship_mode = $1 WHERE commander_id = $2",
        mode, commander_id
    )


def apply_random_flag_ship_updates(commander_id: int, updates: list[dict]) -> None:
    store = get_default_store()
    for entry in updates:
        store.execute(
            "INSERT INTO random_flag_ships (commander_id, ship_id, phantom_id, enabled) "
            "VALUES ($1, $2, $3, $4) "
            "ON CONFLICT (commander_id, ship_id) DO UPDATE SET phantom_id = EXCLUDED.phantom_id, enabled = EXCLUDED.enabled",
            commander_id, entry["ship_id"], entry["phantom_id"], entry["flag"]
        )
