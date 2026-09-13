import json

from src.db.store import get_default_store
from src.orm.config_entry import fetch_config_entry_data

_COMMANDER_APPRECIATION_TABLE = "commander_appreciation_state"


class CommanderAppreciationState:
    def __init__(
        self,
        commander_id: int = 0,
        music_no: int = 0,
        music_mode: int = 0,
        cartoon_read_mark: str = "[]",
        cartoon_collect_mark: str = "[]",
        gallery_unlocks: str = "[]",
        gallery_favor_ids: str = "[]",
        music_favor_ids: str = "[]",
    ):
        self.commander_id = commander_id
        self.music_no = music_no
        self.music_mode = music_mode
        self.cartoon_read_mark = cartoon_read_mark
        self.cartoon_collect_mark = cartoon_collect_mark
        self.gallery_unlocks = gallery_unlocks
        self.gallery_favor_ids = gallery_favor_ids
        self.music_favor_ids = music_favor_ids

    @staticmethod
    def from_row(row) -> "CommanderAppreciationState":
        return CommanderAppreciationState(
            commander_id=row["commander_id"],
            music_no=row["music_no"],
            music_mode=row["music_mode"],
            cartoon_read_mark=row["cartoon_read_mark"],
            cartoon_collect_mark=row["cartoon_collect_mark"],
            gallery_unlocks=row["gallery_unlocks"],
            gallery_favor_ids=row["gallery_favor_ids"],
            music_favor_ids=row["music_favor_ids"],
        )


def get_or_create_commander_appreciation_state(commander_id: int) -> CommanderAppreciationState:
    store = get_default_store()
    row = store.fetchrow(
        f"SELECT * FROM {_COMMANDER_APPRECIATION_TABLE} WHERE commander_id = $1",
        commander_id,
    )
    if row is not None:
        return CommanderAppreciationState.from_row(row)
    store.execute(
        f"INSERT INTO {_COMMANDER_APPRECIATION_TABLE} "
        f"(commander_id, music_no, music_mode, cartoon_read_mark, cartoon_collect_mark, gallery_unlocks, gallery_favor_ids, music_favor_ids) "
        f"VALUES ($1, 0, 0, '[]', '[]', '[]', '[]', '[]')",
        commander_id,
    )
    return CommanderAppreciationState(commander_id=commander_id)


def save_commander_appreciation_state(state: CommanderAppreciationState) -> None:
    store = get_default_store()
    store.execute(
        f"UPDATE {_COMMANDER_APPRECIATION_TABLE} SET "
        f"music_no = $1, music_mode = $2, cartoon_read_mark = $3, cartoon_collect_mark = $4, "
        f"gallery_unlocks = $5, gallery_favor_ids = $6, music_favor_ids = $7 "
        f"WHERE commander_id = $8",
        state.music_no,
        state.music_mode,
        state.cartoon_read_mark,
        state.cartoon_collect_mark,
        state.gallery_unlocks,
        state.gallery_favor_ids,
        state.music_favor_ids,
        state.commander_id,
    )


def _parse_ids(value: str) -> list[int]:
    if not value:
        return []
    return json.loads(value)


def _format_ids(ids: list[int]) -> str:
    return json.dumps(ids, separators=(",", ":"))


def _update_bitset_mark(marks: list[int], mark_id: int, enabled: bool) -> list[int]:
    if mark_id == 0:
        return marks
    bucket = (mark_id - 1) // 32
    bit = (mark_id - 1) % 32
    if bucket >= 4096:
        return marks
    if not enabled and len(marks) < bucket + 1:
        return marks
    if len(marks) < bucket + 1:
        marks = marks + [0] * (bucket + 1 - len(marks))
    if enabled:
        marks[bucket] |= (1 << bit)
    else:
        marks[bucket] &= ~(1 << bit)
    return marks


def _update_favor_id_list(ids: list[int], item_id: int, enabled: bool) -> list[int]:
    if item_id == 0:
        return ids
    if enabled:
        for existing in ids:
            if existing == item_id:
                return ids
        return ids + [item_id]
    return [x for x in ids if x != item_id]


def _config_id_exists(category: str, config_id: int) -> bool:
    return fetch_config_entry_data(category, config_id) is not None


def set_commander_appreciation_gallery_unlock(commander_id: int, gallery_id: int) -> None:
    state = get_or_create_commander_appreciation_state(commander_id)
    unlocks = _parse_ids(state.gallery_unlocks)
    unlocks = _update_bitset_mark(unlocks, gallery_id, True)
    state.gallery_unlocks = _format_ids(unlocks)
    save_commander_appreciation_state(state)


def set_commander_appreciation_gallery_favor(commander_id: int, gallery_id: int, liked: bool) -> None:
    if gallery_id == 0:
        return
    if not _config_id_exists("ShareCfg/gallery_config.json", gallery_id):
        return
    state = get_or_create_commander_appreciation_state(commander_id)
    ids = _parse_ids(state.gallery_favor_ids)
    ids = _update_favor_id_list(ids, gallery_id, liked)
    state.gallery_favor_ids = _format_ids(ids)
    save_commander_appreciation_state(state)


def set_commander_appreciation_music_favor(commander_id: int, music_id: int, liked: bool) -> None:
    if music_id == 0:
        return
    if not _config_id_exists("ShareCfg/music_collect_config.json", music_id):
        return
    state = get_or_create_commander_appreciation_state(commander_id)
    ids = _parse_ids(state.music_favor_ids)
    ids = _update_favor_id_list(ids, music_id, liked)
    state.music_favor_ids = _format_ids(ids)
    save_commander_appreciation_state(state)
