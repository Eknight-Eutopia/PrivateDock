from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from typing import Optional

from src.orm.config_entry import get_config_entry_sync, list_config_entries_sync, upsert_config_entry

_WORLD_BOSS_STATE_CATEGORY = "runtime/world_boss_state"


@dataclass
class WorldBossBossState:
    id: int = 0
    template_id: int = 0
    lv: int = 0
    hp: int = 0
    owner: int = 0
    last_time: int = 0
    kill_time: int = 0
    fight_count: int = 0
    rank_count: int = 0


@dataclass
class WorldBossRankEntry:
    commander_id: int = 0
    name: str = ""
    damage: int = 0


@dataclass
class WorldBossState:
    commander_id: int = 0
    fight_count: int = 0
    fight_count_update_time: int = 0
    self_boss: Optional[WorldBossBossState] = None
    summon_pt: int = 0
    summon_pt_old: int = 0
    summon_pt_daily_acc: int = 0
    summon_pt_old_daily_acc: int = 0
    summon_free: int = 0
    auto_fight_finish_time: int = 0
    default_boss_id: int = 0
    auto_fight_max_damage: int = 0
    guild_support: int = 0
    friend_support: int = 0
    world_support: int = 0
    self_boss_lv: int = 0
    next_boss_id: int = 0
    rankings: dict[str, list[WorldBossRankEntry]] = field(default_factory=dict)
    reward_claimed: dict[str, bool] = field(default_factory=dict)
    auto_battle_start_time: int = 0
    auto_battle_boss_id: int = 0


def _ensure_defaults(state: WorldBossState, commander_id: int) -> None:
    if state.commander_id == 0:
        state.commander_id = commander_id
    if state.rankings is None:
        state.rankings = {}
    if state.reward_claimed is None:
        state.reward_claimed = {}
    if state.next_boss_id == 0:
        state.next_boss_id = 1


def _clone_world_boss_state(state: WorldBossState) -> WorldBossState:
    return deepcopy(state)


def _default_world_boss_state(commander_id: int) -> WorldBossState:
    return WorldBossState(
        commander_id=commander_id,
        summon_pt=1,
        summon_pt_old=1,
        rankings={},
        reward_claimed={},
        next_boss_id=1,
    )


def _state_to_dict(state: WorldBossState) -> dict:
    d: dict = {
        "commander_id": state.commander_id,
        "fight_count": state.fight_count,
        "fight_count_update_time": state.fight_count_update_time,
        "summon_pt": state.summon_pt,
        "summon_pt_old": state.summon_pt_old,
        "summon_pt_daily_acc": state.summon_pt_daily_acc,
        "summon_pt_old_daily_acc": state.summon_pt_old_daily_acc,
        "summon_free": state.summon_free,
        "auto_fight_finish_time": state.auto_fight_finish_time,
        "default_boss_id": state.default_boss_id,
        "auto_fight_max_damage": state.auto_fight_max_damage,
        "guild_support": state.guild_support,
        "friend_support": state.friend_support,
        "world_support": state.world_support,
        "self_boss_lv": state.self_boss_lv,
        "next_boss_id": state.next_boss_id,
        "rankings": {
            k: [{"commander_id": e.commander_id, "name": e.name, "damage": e.damage} for e in v]
            for k, v in state.rankings.items()
        },
        "reward_claimed": dict(state.reward_claimed),
        "auto_battle_start_time": state.auto_battle_start_time,
        "auto_battle_boss_id": state.auto_battle_boss_id,
    }
    if state.self_boss is not None:
        d["self_boss"] = {
            "id": state.self_boss.id,
            "template_id": state.self_boss.template_id,
            "lv": state.self_boss.lv,
            "hp": state.self_boss.hp,
            "owner": state.self_boss.owner,
            "last_time": state.self_boss.last_time,
            "kill_time": state.self_boss.kill_time,
            "fight_count": state.self_boss.fight_count,
            "rank_count": state.self_boss.rank_count,
        }
    return d


def _dict_to_state(data: dict, commander_id: int) -> WorldBossState:
    self_boss_data = data.get("self_boss")
    self_boss = None
    if self_boss_data:
        self_boss = WorldBossBossState(
            id=self_boss_data.get("id", 0),
            template_id=self_boss_data.get("template_id", 0),
            lv=self_boss_data.get("lv", 0),
            hp=self_boss_data.get("hp", 0),
            owner=self_boss_data.get("owner", 0),
            last_time=self_boss_data.get("last_time", 0),
            kill_time=self_boss_data.get("kill_time", 0),
            fight_count=self_boss_data.get("fight_count", 0),
            rank_count=self_boss_data.get("rank_count", 0),
        )
    rankings_raw = data.get("rankings", {})
    rankings: dict[str, list[WorldBossRankEntry]] = {}
    for k, entries in rankings_raw.items():
        rankings[k] = [
            WorldBossRankEntry(
                commander_id=int(e.get("commander_id", 0)),
                name=str(e.get("name", "")),
                damage=int(e.get("damage", 0)),
            )
            for e in entries
        ]
    return WorldBossState(
        commander_id=data.get("commander_id", commander_id),
        fight_count=data.get("fight_count", 0),
        fight_count_update_time=data.get("fight_count_update_time", 0),
        self_boss=self_boss,
        summon_pt=data.get("summon_pt", 0),
        summon_pt_old=data.get("summon_pt_old", 0),
        summon_pt_daily_acc=data.get("summon_pt_daily_acc", 0),
        summon_pt_old_daily_acc=data.get("summon_pt_old_daily_acc", 0),
        summon_free=data.get("summon_free", 0),
        auto_fight_finish_time=data.get("auto_fight_finish_time", 0),
        default_boss_id=data.get("default_boss_id", 0),
        auto_fight_max_damage=data.get("auto_fight_max_damage", 0),
        guild_support=data.get("guild_support", 0),
        friend_support=data.get("friend_support", 0),
        world_support=data.get("world_support", 0),
        self_boss_lv=data.get("self_boss_lv", 0),
        next_boss_id=data.get("next_boss_id", 0),
        rankings=rankings,
        reward_claimed={k: bool(v) for k, v in data.get("reward_claimed", {}).items()},
        auto_battle_start_time=data.get("auto_battle_start_time", 0),
        auto_battle_boss_id=data.get("auto_battle_boss_id", 0),
    )


def get_commander_world_boss_state(commander_id: int) -> Optional[WorldBossState]:
    entry = get_config_entry_sync(_WORLD_BOSS_STATE_CATEGORY, str(commander_id))
    if entry is None:
        return None
    state = _dict_to_state(entry.data or {}, commander_id)
    _ensure_defaults(state, commander_id)
    return state


def get_or_create_commander_world_boss_state(commander_id: int) -> WorldBossState:
    state = get_commander_world_boss_state(commander_id)
    if state is not None:
        return state
    state = _default_world_boss_state(commander_id)
    save_commander_world_boss_state(state)
    return state


def save_commander_world_boss_state(state: WorldBossState) -> None:
    _ensure_defaults(state, state.commander_id)
    payload = _state_to_dict(state)
    upsert_config_entry(_WORLD_BOSS_STATE_CATEGORY, str(state.commander_id), payload)


def list_world_boss_states() -> list[WorldBossState]:
    entries = list_config_entries_sync(_WORLD_BOSS_STATE_CATEGORY)
    states: list[WorldBossState] = []
    for entry in entries:
        try:
            cid = int(entry.key)
        except (ValueError, TypeError):
            continue
        state = _dict_to_state(entry.data or {}, cid)
        _ensure_defaults(state, cid)
        states.append(state)
    return states


def get_rankings(state: WorldBossState, boss_id: int) -> list[WorldBossRankEntry]:
    _ensure_defaults(state, state.commander_id)
    values = state.rankings.get(str(boss_id), [])
    if not values:
        return []
    return [WorldBossRankEntry(commander_id=e.commander_id, name=e.name, damage=e.damage) for e in values]


def set_rankings(state: WorldBossState, boss_id: int, values: list[WorldBossRankEntry]) -> None:
    _ensure_defaults(state, state.commander_id)
    key = str(boss_id)
    if not values:
        state.rankings.pop(key, None)
        return
    state.rankings[key] = [WorldBossRankEntry(commander_id=e.commander_id, name=e.name, damage=e.damage) for e in values]


def is_reward_claimed(state: WorldBossState, boss_id: int) -> bool:
    _ensure_defaults(state, state.commander_id)
    return state.reward_claimed.get(str(boss_id), False)


def set_reward_claimed(state: WorldBossState, boss_id: int, claimed: bool) -> None:
    _ensure_defaults(state, state.commander_id)
    key = str(boss_id)
    if claimed:
        state.reward_claimed[key] = True
    else:
        state.reward_claimed.pop(key, None)
