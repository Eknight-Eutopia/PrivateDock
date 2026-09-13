from typing import Optional, NamedTuple

from src.orm.config_entry import list_config_entries, get_config_entry

REMASTER_CONFIG_CATEGORY = "ShareCfg/re_map_template.json"
GAME_SET_CATEGORY = "ShareCfg/gameset.json"


class RemasterDropGain(NamedTuple):
    chapter_id: int
    pos: int
    drop_type: int
    drop_id: int
    max_count: int


from src.orm.config_entry import entry_data


def _entry_data(entry):
    return entry_data(entry) or {}


def list_remaster_drop_gains() -> list:
    entries = list_config_entries(REMASTER_CONFIG_CATEGORY)
    drops = []
    for entry in entries:
        data = _entry_data(entry)
        drop_gain = data.get("drop_gain", [])
        for index, gain in enumerate(drop_gain):
            if not isinstance(gain, (list, tuple)) or len(gain) == 0:
                continue
            if len(gain) < 4:
                raise Exception(f"invalid remaster drop_gain entry for {data.get('id', 0)}")
            drops.append(RemasterDropGain(
                chapter_id=int(gain[0]),
                pos=index + 1,
                drop_type=int(gain[1]),
                drop_id=int(gain[2]),
                max_count=int(gain[3]),
            ))
    return drops


def build_remaster_drop_gain_map(entries: list) -> dict:
    lookup = {}
    for entry in entries:
        lookup[(entry.chapter_id, entry.pos)] = entry
    return lookup


_remaster_chapter_ids_cache = None


def _build_remaster_chapter_ids() -> set:
    entries = list_config_entries(REMASTER_CONFIG_CATEGORY)
    ids = set()
    for entry in entries:
        data = _entry_data(entry)
        config_data = data.get("config_data", [])
        if isinstance(config_data, list):
            for cid in config_data:
                if cid is not None:
                    ids.add(int(cid))
    return ids


def is_remaster_chapter(chapter_id: int) -> bool:
    global _remaster_chapter_ids_cache
    if _remaster_chapter_ids_cache is None:
        _remaster_chapter_ids_cache = _build_remaster_chapter_ids()
    return chapter_id in _remaster_chapter_ids_cache


def load_gameset_value(key: str) -> Optional[int]:
    entry = get_config_entry(GAME_SET_CATEGORY, key)
    if entry is None:
        return None
    data = _entry_data(entry)
    return int(data.get("key_value", 0))


PACKET_ID = 24602


def handle_remaster_request_config(_buffer: bytes, client) -> tuple:
    import asyncio
    data = {"result": 0, "config": []}
    asyncio.create_task(client.send_message(PACKET_ID, data))
    return 0, PACKET_ID, None
