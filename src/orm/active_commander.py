"""Tracks the live Commander object bound to each connected client.

Grant helpers (add_item, add_resource, add_owned_equipment, give_skin, ...) write
to the database but must also keep the in-memory commander maps (commander_items_map,
owned_resources_map, owned_equipment_map, owned_skins_map) in sync, otherwise items
granted or returned during gameplay are invisible to handlers that read those maps
(e.g. disassembly) until the next login.

There is no global registry of live commander objects elsewhere, so we maintain one
here. It is keyed by commander_id and updated whenever a commander is loaded (login /
reload) and cleared on disconnect.
"""

from typing import Dict, Optional

_ACTIVE_COMMANDERS: Dict[int, object] = {}


def register_active_commander(commander) -> None:
    cid = getattr(commander, "commander_id", None)
    if cid is None:
        return
    _ACTIVE_COMMANDERS[int(cid)] = commander


def unregister_active_commander(commander) -> None:
    cid = getattr(commander, "commander_id", None)
    if cid is None:
        return
    cid = int(cid)
    if _ACTIVE_COMMANDERS.get(cid) is commander:
        del _ACTIVE_COMMANDERS[cid]


def get_active_commander(commander_id) -> Optional[object]:
    if commander_id is None:
        return None
    return _ACTIVE_COMMANDERS.get(int(commander_id))


# Live Client objects keyed by commander_id. Populated on login so that code
# paths which only have a commander_id (e.g. the central consume_resource)
# can still drive server-authoritative task progress for the connected player.
_ACTIVE_CLIENTS: Dict[int, object] = {}


def register_active_client(commander_id, client) -> None:
    if commander_id is None or client is None:
        return
    _ACTIVE_CLIENTS[int(commander_id)] = client


def unregister_active_client(commander_id) -> None:
    if commander_id is None:
        return
    cid = int(commander_id)
    if cid in _ACTIVE_CLIENTS:
        del _ACTIVE_CLIENTS[cid]


def get_active_client(commander_id):
    if commander_id is None:
        return None
    return _ACTIVE_CLIENTS.get(int(commander_id))


def list_active_clients() -> list:
    """Snapshot of live (commander_id, client) pairs for background loops
    (e.g. the secretary-affinity ticker in src/orm/secretary.py)."""
    return list(_ACTIVE_CLIENTS.items())


def _bump_count_map(commander_id, map_attr: str, key, count, id_key: str) -> None:
    """Increment ``count`` for ``key`` in the live commander's mapping, creating it."""
    commander = get_active_commander(commander_id)
    if commander is None:
        return
    mapping = getattr(commander, map_attr, None)
    if mapping is None:
        return
    entry = mapping.get(key)
    if entry is None:
        if count > 0:
            mapping[key] = {id_key: key, "count": count}
    else:
        new_count = entry.get("count", 0) + count
        if new_count <= 0:
            mapping.pop(key, None)
        else:
            entry["count"] = new_count


def _bump_amount_map(commander_id, map_attr: str, key, amount, id_key: str) -> None:
    """Increment ``amount`` for ``key`` in the live commander's mapping, creating it."""
    commander = get_active_commander(commander_id)
    if commander is None:
        return
    mapping = getattr(commander, map_attr, None)
    if mapping is None:
        return
    entry = mapping.get(key)
    if entry is None:
        mapping[key] = {id_key: key, "amount": amount}
    else:
        entry["amount"] = entry.get("amount", 0) + amount


def _set_value_map(commander_id, map_attr: str, key) -> None:
    """Ensure ``key`` exists in the live commander's mapping (value equals key)."""
    commander = get_active_commander(commander_id)
    if commander is None:
        return
    mapping = getattr(commander, map_attr, None)
    if mapping is None:
        return
    if key not in mapping:
        mapping[key] = key
