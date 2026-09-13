import asyncio
import re
from typing import Optional

from src.config.config import current as get_config
from src.connection.client import Client
from src.protobuf import protobuf

CHANGE_PLAYER_NAME_MIN = 4
CHANGE_PLAYER_NAME_MAX = 14


def handle_change_player_name(
    buffer: bytes, client: Client,
) -> tuple[int, int, Optional[Exception]]:
    import json
    payload = json.loads(buffer.decode("utf-8", errors="replace"))
    name = payload.get("name", "").strip()
    if not name:
        asyncio.create_task(client.send_message(11008, protobuf.SC_11008(result=1)))
        return 0, 11008, None
    if name == client.commander.name:
        asyncio.create_task(client.send_message(11008, protobuf.SC_11008(result=1)))
        return 0, 11008, None
    name_length = len(name)
    if name_length < CHANGE_PLAYER_NAME_MIN or name_length > CHANGE_PLAYER_NAME_MAX:
        asyncio.create_task(client.send_message(11008, protobuf.SC_11008(result=1)))
        return 0, 11008, None

    cfg = get_config()
    create_cfg = cfg.create_player
    if create_cfg.name_blacklist:
        lower_name = name.lower()
        for blocked in create_cfg.name_blacklist:
            blocked = blocked.strip()
            if not blocked:
                continue
            if blocked.lower() in lower_name:
                asyncio.create_task(client.send_message(11008, protobuf.SC_11008(result=1)))
                return 0, 11008, None
    if create_cfg.name_illegal_pattern:
        try:
            matcher = re.compile(create_cfg.name_illegal_pattern)
        except re.error as e:
            return 0, 11008, e
        if matcher.search(name):
            asyncio.create_task(client.send_message(11008, protobuf.SC_11008(result=1)))
            return 0, 11008, None

    from src.orm.commander import check_commander_name_availability
    from src.orm import ERR_COMMANDER_NAME_EXISTS
    try:
        check_commander_name_availability(name)
    except type(ERR_COMMANDER_NAME_EXISTS) if isinstance(ERR_COMMANDER_NAME_EXISTS, type) else Exception as e:
        asyncio.create_task(client.send_message(11008, protobuf.SC_11008(result=2015)))
        return 0, 11008, None
    except Exception as e:
        return 0, 11008, e

    change_type = payload.get("type", 1)

    def _load_game_set_entry(key: str):
        from src.orm.config_entry import get_config_entry
        entry = get_config_entry("ShareCfg/gameset.json", key)
        return json.loads(entry.data) if isinstance(entry.data, str) else entry.data

    if change_type == 1:
        try:
            level_entry = _load_game_set_entry("player_name_change_lv_limit")
        except Exception:
            asyncio.create_task(client.send_message(11008, protobuf.SC_11008(result=1)))
            return 0, 11008, None
        if client.commander.level < int(level_entry.get("key_value", 0)):
            asyncio.create_task(client.send_message(11008, protobuf.SC_11008(result=1)))
            return 0, 11008, None

        from datetime import datetime, timezone
        try:
            cooldown_entry = _load_game_set_entry("player_name_cold_time")
        except Exception:
            asyncio.create_task(client.send_message(11008, protobuf.SC_11008(result=1)))
            return 0, 11008, None
        now = datetime.now(timezone.utc)
        cooldown = getattr(client.commander, "name_change_cooldown", None)
        if cooldown and cooldown > now:
            asyncio.create_task(client.send_message(11008, protobuf.SC_11008(result=1)))
            return 0, 11008, None

        try:
            cost_entry = _load_game_set_entry("player_name_change_cost")
        except Exception:
            asyncio.create_task(client.send_message(11008, protobuf.SC_11008(result=1)))
            return 0, 11008, None
        cost_desc = cost_entry.get("description", [])
        if len(cost_desc) < 3:
            asyncio.create_task(client.send_message(11008, protobuf.SC_11008(result=1)))
            return 0, 11008, None
        cost_type = cost_desc[0]
        cost_id = cost_desc[1]
        cost_count = cost_desc[2]

        if cost_type == 1:
            if not client.commander.has_enough_resource(cost_id, cost_count):
                asyncio.create_task(client.send_message(11008, protobuf.SC_11008(result=1)))
                return 0, 11008, None
            client.commander.consume_resource(cost_id, cost_count)
        elif cost_type == 2:
            if not client.commander.has_enough_item(cost_id, cost_count):
                asyncio.create_task(client.send_message(11008, protobuf.SC_11008(result=1)))
                return 0, 11008, None
            client.commander.consume_item(cost_id, cost_count)
        else:
            asyncio.create_task(client.send_message(11008, protobuf.SC_11008(result=1)))
            return 0, 11008, None

        client.commander.name_change_cooldown = now
        client.commander.name = name
        result = 0
        try:
            client.commander.commit()
        except Exception:
            result = 1
        asyncio.create_task(client.send_message(11008, protobuf.SC_11008(result=result)))
        return 0, 11008, None

    elif change_type == 2:
        client.commander.name = name
        result = 0
        try:
            client.commander.commit()
        except Exception:
            result = 1
        else:
            from src.consts.common_flags import ILLEGALITY_PLAYER_NAME
            from src.orm.players import clear_commander_common_flag
            try:
                clear_commander_common_flag(client.commander.commander_id, ILLEGALITY_PLAYER_NAME)
            except Exception:
                result = 1
        asyncio.create_task(client.send_message(11008, protobuf.SC_11008(result=result)))
        return 0, 11008, None

    asyncio.create_task(client.send_message(11008, protobuf.SC_11008(result=1)))
    return 0, 11008, None
