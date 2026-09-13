from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from sqlalchemy import select, text

from src.db.session import get_sync_session
from src.orm.config_entry import ConfigEntry, get_config_entry_sync

_MINI_GAME_HUB_CATEGORY = "ShareCfg/mini_game_hub.json"
_MINI_GAME_CATEGORY = "ShareCfg/mini_game.json"
_MINI_GAME_HUB_STATE_CATEGORY = "Runtime/minigame_hub_state"
_MINI_GAME_DATA_STATE_CATEGORY = "Runtime/minigame_data_state"
_MINI_GAME_TELEMETRY_STATE_CATEGORY = "Runtime/minigame_telemetry_state"
_ISLAND_NODE_STATE_CATEGORY = "Runtime/island_node_state"
_MINI_GAME_FRIEND_RANK_LIMIT = 100


@dataclass
class MiniGameHubConfig:
    id: int = 0
    act_id: int = 0
    reborn_times: int = 0
    reward_need: int = 0
    reward_target: int = 0
    reward_display: list[int] = field(default_factory=list)


@dataclass
class MiniGameConfig:
    id: int = 0
    hub_id: int = 0


@dataclass
class MiniGameScoreEntry:
    score: int = 0
    extra: int = 0


@dataclass
class MiniGameHubState:
    commander_id: int = 0
    hub_id: int = 0
    available_cnt: int = 0
    used_cnt: int = 0
    ultimate: int = 0
    max_scores: dict[int, MiniGameScoreEntry] = field(default_factory=dict)


@dataclass
class MiniGameKVState:
    key: int = 0
    value: int = 0
    value2: int = 0


@dataclass
class MiniGameKVListState:
    key: int = 0
    values: list[MiniGameKVState] = field(default_factory=list)


@dataclass
class MiniGameDataState:
    commander_id: int = 0
    game_id: int = 0
    datas: list[int] = field(default_factory=list)
    kv_lists: list[MiniGameKVListState] = field(default_factory=list)


@dataclass
class MiniGameTelemetryState:
    commander_id: int = 0
    game_times: dict[int, int] = field(default_factory=dict)


@dataclass
class IslandNodeState:
    id: int = 0
    event_id: int = 0
    is_new: int = 0


from src.orm.config_entry import upsert_config_entry as _upsert_config_entry


def _mini_game_hub_state_key(commander_id: int, hub_id: int) -> str:
    return f"{commander_id}:{hub_id}"


def _mini_game_data_state_key(commander_id: int, game_id: int) -> str:
    return f"{commander_id}:{game_id}"


def _island_node_state_key(commander_id: int, act_id: int) -> str:
    return f"{commander_id}:{act_id}"


def _normalize_mini_game_hub_state(state: MiniGameHubState, commander_id: int, config: MiniGameHubConfig) -> None:
    state.commander_id = commander_id
    state.hub_id = config.id
    if state.max_scores is None:
        state.max_scores = {}


def _normalize_mini_game_data_state(state: MiniGameDataState, commander_id: int, game_id: int) -> None:
    state.commander_id = commander_id
    state.game_id = game_id
    if state.datas is None:
        state.datas = []
    if state.kv_lists is None:
        state.kv_lists = []


# ── Config (read-only ShareCfg) ──


def get_mini_game_hub_config(hub_id: int) -> Optional[MiniGameHubConfig]:
    entry = get_config_entry_sync(_MINI_GAME_HUB_CATEGORY, str(hub_id))
    if entry is None:
        return None
    data = entry.data
    config = MiniGameHubConfig(
        id=data.get("id", hub_id),
        act_id=data.get("act_id", 0),
        reborn_times=data.get("reborn_times", 0),
        reward_need=data.get("reward_need", 0),
        reward_target=data.get("reward_target", 0),
        reward_display=[int(r) for r in data.get("reward_display", [])],
    )
    if config.reward_display is None:
        config.reward_display = []
    return config


def get_mini_game_config(game_id: int) -> Optional[MiniGameConfig]:
    entry = get_config_entry_sync(_MINI_GAME_CATEGORY, str(game_id))
    if entry is None:
        return None
    data = entry.data
    return MiniGameConfig(
        id=data.get("id", game_id),
        hub_id=data.get("hub_id", 0),
    )


# ── Hub State ──


def get_or_create_mini_game_hub_state(commander_id: int, config: MiniGameHubConfig) -> MiniGameHubState:
    key = _mini_game_hub_state_key(commander_id, config.id)
    entry = get_config_entry_sync(_MINI_GAME_HUB_STATE_CATEGORY, key)
    if entry is None:
        state = MiniGameHubState(
            commander_id=commander_id,
            hub_id=config.id,
            available_cnt=config.reborn_times,
            max_scores={},
        )
        save_mini_game_hub_state(state)
        return state
    data = entry.data
    state = MiniGameHubState(
        commander_id=data.get("commander_id", commander_id),
        hub_id=data.get("hub_id", config.id),
        available_cnt=data.get("available_cnt", 0),
        used_cnt=data.get("used_cnt", 0),
        ultimate=data.get("ultimate", 0),
        max_scores={
            int(k): MiniGameScoreEntry(score=int(v.get("score", 0)), extra=int(v.get("extra", 0)))
            for k, v in data.get("max_scores", {}).items()
        },
    )
    _normalize_mini_game_hub_state(state, commander_id, config)
    return state


def save_mini_game_hub_state(state: MiniGameHubState) -> None:
    payload = {
        "commander_id": state.commander_id,
        "hub_id": state.hub_id,
        "available_cnt": state.available_cnt,
        "used_cnt": state.used_cnt,
        "ultimate": state.ultimate,
        "max_scores": {
            str(k): {"score": v.score, "extra": v.extra}
            for k, v in state.max_scores.items()
        },
    }
    _upsert_config_entry(_MINI_GAME_HUB_STATE_CATEGORY, _mini_game_hub_state_key(state.commander_id, state.hub_id), payload)


# ── Data State ──


def get_or_create_mini_game_data_state(commander_id: int, game_id: int) -> MiniGameDataState:
    key = _mini_game_data_state_key(commander_id, game_id)
    entry = get_config_entry_sync(_MINI_GAME_DATA_STATE_CATEGORY, key)
    if entry is None:
        state = MiniGameDataState(commander_id=commander_id, game_id=game_id, datas=[], kv_lists=[])
        save_mini_game_data_state(state)
        return state
    data = entry.data
    state = MiniGameDataState(
        commander_id=data.get("commander_id", commander_id),
        game_id=data.get("game_id", game_id),
        datas=[int(d) for d in data.get("datas", [])],
        kv_lists=[
            MiniGameKVListState(
                key=int(kv.get("key", 0)),
                values=[
                    MiniGameKVState(key=int(v.get("key", 0)), value=int(v.get("value", 0)), value2=int(v.get("value2", 0)))
                    for v in kv.get("values", [])
                ],
            )
            for kv in data.get("kv_lists", [])
        ],
    )
    _normalize_mini_game_data_state(state, commander_id, game_id)
    return state


def save_mini_game_data_state(state: MiniGameDataState) -> None:
    payload = {
        "commander_id": state.commander_id,
        "game_id": state.game_id,
        "datas": list(state.datas),
        "kv_lists": [
            {
                "key": kv.key,
                "values": [
                    {"key": v.key, "value": v.value, "value2": v.value2}
                    for v in kv.values
                ],
            }
            for kv in state.kv_lists
        ],
    }
    _upsert_config_entry(_MINI_GAME_DATA_STATE_CATEGORY, _mini_game_data_state_key(state.commander_id, state.game_id), payload)


# ── Telemetry State ──


def get_or_create_mini_game_telemetry_state(commander_id: int) -> MiniGameTelemetryState:
    entry = get_config_entry_sync(_MINI_GAME_TELEMETRY_STATE_CATEGORY, str(commander_id))
    if entry is None:
        state = MiniGameTelemetryState(commander_id=commander_id, game_times={})
        save_mini_game_telemetry_state(state)
        return state
    data = entry.data
    state = MiniGameTelemetryState(
        commander_id=commander_id,
        game_times={int(k): int(v) for k, v in data.get("game_times", {}).items()},
    )
    if state.game_times is None:
        state.game_times = {}
    return state


def save_mini_game_telemetry_state(state: MiniGameTelemetryState) -> None:
    payload = {
        "commander_id": state.commander_id,
        "game_times": {str(k): v for k, v in state.game_times.items()},
    }
    _upsert_config_entry(_MINI_GAME_TELEMETRY_STATE_CATEGORY, str(state.commander_id), payload)


# ── Island Node State ──


def get_or_create_island_node_state(commander_id: int, act_id: int) -> list[IslandNodeState]:
    key = _island_node_state_key(commander_id, act_id)
    entry = get_config_entry_sync(_ISLAND_NODE_STATE_CATEGORY, key)
    if entry is None:
        save_island_node_state(commander_id, act_id, [])
        return []
    nodes_data = entry.data
    if not isinstance(nodes_data, list):
        nodes_data = []
    nodes = [
        IslandNodeState(id=int(n.get("id", 0)), event_id=int(n.get("event_id", 0)), is_new=int(n.get("is_new", 0)))
        for n in nodes_data
    ]
    nodes.sort(key=lambda n: n.id)
    return nodes


def save_island_node_state(commander_id: int, act_id: int, nodes: list[IslandNodeState]) -> None:
    if nodes is None:
        nodes = []
    nodes.sort(key=lambda n: n.id)
    payload = [{"id": n.id, "event_id": n.event_id, "is_new": n.is_new} for n in nodes]
    _upsert_config_entry(_ISLAND_NODE_STATE_CATEGORY, _island_node_state_key(commander_id, act_id), payload)


# ── Commander Item Balances ──


def list_commander_item_balances(commander_id: int, item_ids: list[int]) -> dict[int, int]:
    balances: dict[int, int] = {}
    if not item_ids:
        return balances
    seen: set[int] = set()
    int_ids: list[int] = []
    for item_id in item_ids:
        if item_id == 0 or item_id in seen:
            continue
        seen.add(item_id)
        int_ids.append(item_id)
    if not int_ids:
        return balances
    with get_sync_session() as session:
        rows = session.execute(
            text("SELECT item_id, count FROM commander_items WHERE commander_id = :cid AND item_id = ANY(:ids)"),
            {"cid": commander_id, "ids": int_ids},
        ).fetchall()
        for item_id_raw, count_raw in rows:
            if count_raw is not None and count_raw > 0:
                balances[int(item_id_raw)] = balances.get(int(item_id_raw), 0) + int(count_raw)
        rows = session.execute(
            text("SELECT item_id, data FROM commander_misc_items WHERE commander_id = :cid AND item_id = ANY(:ids)"),
            {"cid": commander_id, "ids": int_ids},
        ).fetchall()
        for item_id_raw, count_raw in rows:
            if count_raw is not None and count_raw > 0:
                balances[int(item_id_raw)] = balances.get(int(item_id_raw), 0) + int(count_raw)
    return balances


@dataclass
class CommanderMiniGameScore:
    commander_id: int = 0
    name: str = ""
    score: int = 0
    time_data: int = 0
    display_icon: int = 0
    display_skin: int = 0
    icon_frame: int = 0
    chat_frame: int = 0
    icon_theme: int = 0


def list_commander_mini_game_scores(game_id: int) -> list[CommanderMiniGameScore]:
    entries = []
    with get_sync_session() as session:
        config_rows = session.execute(
            select(ConfigEntry).where(ConfigEntry.category == _MINI_GAME_HUB_STATE_CATEGORY)
        ).scalars().all()
    best_by_commander: dict[int, MiniGameScoreEntry] = {}
    for config_entry in config_rows:
        data = config_entry.data
        if not data:
            continue
        state = MiniGameHubState(
            commander_id=data.get("commander_id", 0),
            hub_id=data.get("hub_id", 0),
            max_scores={},
        )
        score_data = data.get("max_scores", {}).get(str(game_id))
        if score_data is None:
            continue
        score = MiniGameScoreEntry(score=int(score_data.get("score", 0)), extra=int(score_data.get("extra", 0)))
        if score.score == 0:
            continue
        current = best_by_commander.get(state.commander_id)
        if current is None or (int(score.score) > int(current.score)) or (score.score == current.score and score.extra < current.extra):
            best_by_commander[state.commander_id] = score
    if not best_by_commander:
        return []
    commander_ids = list(best_by_commander.keys())
    with get_sync_session() as session:
        rows = session.execute(
            text("""
                SELECT commander_id, name, display_icon_id, display_skin_id,
                       selected_icon_frame_id, selected_chat_frame_id, display_icon_theme_id
                FROM commanders
                WHERE commander_id = ANY(:ids)
            """),
            {"ids": commander_ids},
        ).fetchall()
    results: list[CommanderMiniGameScore] = []
    for row in rows:
        cid = int(row[0])
        score = best_by_commander.get(cid)
        if score is None or score.score == 0:
            continue
        results.append(CommanderMiniGameScore(
            commander_id=cid,
            name=str(row[1] or ""),
            score=score.score,
            time_data=score.extra,
            display_icon=int(row[2] or 0),
            display_skin=int(row[3] or 0),
            icon_frame=int(row[4] or 0),
            chat_frame=int(row[5] or 0),
            icon_theme=int(row[6] or 0),
        ))
    results.sort(key=lambda r: (-r.score, r.time_data, r.commander_id))
    return results[:_MINI_GAME_FRIEND_RANK_LIMIT]
