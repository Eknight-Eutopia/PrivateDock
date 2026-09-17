from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from src.db.store import decode_json_value, get_default_store
from src.misc.safe_ts import safe_ts


def _row_to_prefab_dict(row: Any) -> dict:
    raw_slots = decode_json_value(row[4])
    if isinstance(raw_slots, str):
        try:
            slots_list = json.loads(raw_slots)
        except Exception:
            slots_list = []
    elif isinstance(raw_slots, list):
        slots_list = raw_slots
    else:
        slots_list = []

    normalized_slots = []
    for s in slots_list:
        if isinstance(s, dict):
            pos = int(s.get("pos", 0))
            cid = int(s.get("id") or s.get("commander_id") or 0)
            normalized_slots.append({"pos": pos, "id": cid})

    return {
        "owner_commander_id": int(row[0]),
        "prefab_id": int(row[1]),
        "name": str(row[2] or ""),
        "rename_cooldown_at": row[3],
        "commander_slots": normalized_slots,
    }


def get_commander_prefab_fleet(owner_commander_id: int, prefab_id: int) -> dict | None:
    store = get_default_store()
    if store is None:
        return None
    row = store.fetchrow(
        "SELECT owner_commander_id, prefab_id, name, rename_cooldown_at, commander_slots, created_at, updated_at "
        "FROM commander_prefab_fleets WHERE owner_commander_id = $1 AND prefab_id = $2",
        owner_commander_id, prefab_id,
    )
    if not row:
        return None
    return _row_to_prefab_dict(row)


def list_commander_prefab_fleets(owner_commander_id: int) -> list[dict]:
    store = get_default_store()
    if store is None:
        return []
    rows = store.fetch(
        "SELECT owner_commander_id, prefab_id, name, rename_cooldown_at, commander_slots, created_at, updated_at "
        "FROM commander_prefab_fleets WHERE owner_commander_id = $1 ORDER BY prefab_id ASC",
        owner_commander_id,
    )
    return [_row_to_prefab_dict(r) for r in (rows or [])]


def save_commander_prefab_fleet(
    owner_commander_id: int,
    prefab_id: int,
    slots: list[dict],
    name: str = "",
) -> None:
    store = get_default_store()
    if store is None:
        return
    slots_json = json.dumps(slots)
    default_cooldown = datetime(1970, 1, 1, tzinfo=timezone.utc)
    store.execute(
        "INSERT INTO commander_prefab_fleets ("
        "  owner_commander_id, prefab_id, name, rename_cooldown_at, commander_slots, created_at, updated_at"
        ") VALUES ($1, $2, $3, $4, $5, NOW(), NOW()) "
        "ON CONFLICT (owner_commander_id, prefab_id) "
        "DO UPDATE SET "
        "  commander_slots = EXCLUDED.commander_slots, "
        "  name = CASE WHEN commander_prefab_fleets.name <> '' THEN commander_prefab_fleets.name ELSE EXCLUDED.name END, "
        "  updated_at = NOW()",
        owner_commander_id, prefab_id, name, default_cooldown, slots_json,
    )


def rename_commander_prefab_fleet(
    owner_commander_id: int,
    prefab_id: int,
    name: str,
    cooldown_seconds: int = 60,
) -> bool:
    store = get_default_store()
    if store is None:
        return False
    current = get_commander_prefab_fleet(owner_commander_id, prefab_id)
    now = datetime.now(timezone.utc)
    if current:
        cooldown_at = current.get("rename_cooldown_at")
        if safe_ts(cooldown_at) > safe_ts(now):
            return False

    new_cooldown = now + timedelta(seconds=cooldown_seconds)
    store.execute(
        "INSERT INTO commander_prefab_fleets ("
        "  owner_commander_id, prefab_id, name, rename_cooldown_at, commander_slots, created_at, updated_at"
        ") VALUES ($1, $2, $3, $4, '[]'::jsonb, NOW(), NOW()) "
        "ON CONFLICT (owner_commander_id, prefab_id) "
        "DO UPDATE SET "
        "  name = EXCLUDED.name, "
        "  rename_cooldown_at = EXCLUDED.rename_cooldown_at, "
        "  updated_at = NOW()",
        owner_commander_id, prefab_id, name, new_cooldown,
    )
    return True
