import asyncio
import json
import time
from typing import Optional

from src.connection.client import Client
from src.orm.world_boss_state import (
    get_or_create_commander_world_boss_state,
    save_commander_world_boss_state,
)
from src.orm.config_entry import get_config_entry_sync


def _world_boss_gameset_seconds(key: str, fallback: int) -> int:
    for cat in ("ShareCfg/gameset.json", "sharecfgdata/gameset.json"):
        entry = get_config_entry_sync(cat, key)
        if entry is not None and entry.data:
            val = entry.data.get("key_value", 0)
            if val:
                if isinstance(val, (int, float)) and val > 0:
                    return int(val)
                if isinstance(val, list) and len(val) > 0:
                    head = val[0]
                    if isinstance(head, (int, float)) and head > 0:
                        return int(head)
    return fallback


def _boss_to_dict(boss) -> Optional[dict]:
    if boss is None:
        return None
    return {
        "id": boss.id,
        "template_id": boss.template_id,
        "lv": boss.lv,
        "hp": boss.hp,
        "owner": boss.owner,
        "last_time": boss.last_time,
        "kill_time": boss.kill_time,
        "fight_count": boss.fight_count,
        "rank_count": boss.rank_count,
    }


def handle_world_boss_get_info(buffer: bytes, client: Client) -> tuple[int, int, Optional[Exception]]:
    try:
        payload = json.loads(buffer.decode("utf-8", errors="replace"))
    except Exception as e:
        return 0, 19493, e

    user_ids = payload.get("user_id_list", [])
    if not isinstance(user_ids, list):
        user_ids = [int(payload.get("user_id", client.commander.commander_id))]

    seen = set()
    info_list = []
    for uid in user_ids:
        uid = int(uid)
        if uid in seen:
            continue
        seen.add(uid)
        state = get_or_create_commander_world_boss_state(uid)
        if state.self_boss is None:
            continue
        info_list.append(_boss_to_dict(state.self_boss))

    info_list.sort(key=lambda b: (-b["last_time"], b["id"]))

    response = {
        "info": info_list,
        "group_list": [],
        "rank_list": [],
        "military_reward_info": [],
    }
    asyncio.create_task(client.send_message(19493, response))
    return 0, 19493, None


def handle_world_boss_get_support_info(buffer: bytes, client: Client) -> tuple[int, int, Optional[Exception]]:
    try:
        payload = json.loads(buffer.decode("utf-8", errors="replace"))
    except Exception as e:
        return 0, 19495, e

    support_type = int(payload.get("type", 1))
    if support_type < 1 or support_type > 3:
        asyncio.create_task(client.send_message(19495, {"support_info": []}))
        return 0, 19495, None

    state = get_or_create_commander_world_boss_state(client.commander.commander_id)
    if state.self_boss is None:
        asyncio.create_task(client.send_message(19495, {"support_info": []}))
        return 0, 19495, None

    until = int(time.time()) + _world_boss_gameset_seconds("joint_boss_world_time", 1800)
    if support_type == 1:
        state.friend_support = until
    elif support_type == 2:
        state.guild_support = until
    elif support_type == 3:
        state.world_support = until
    save_commander_world_boss_state(state)

    asyncio.create_task(client.send_message(19495, {"support_info": []}))
    return 0, 19495, None
