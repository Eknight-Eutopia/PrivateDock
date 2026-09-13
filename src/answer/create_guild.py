import asyncio
from typing import Optional

from src.connection.client import Client
from src.protobuf import protobuf
from .guild_core_helpers_compat import is_valid_guild_name,is_valid_guild_faction,is_valid_guild_policy,load_game_set_uint,GUILD_RESULT_SUCCESS,GUILD_RESULT_FAILURE,GUILD_RESULT_NAME_INVALID

def handle_create_guild(
    buffer: bytes, client: Client,
) -> tuple[int, int, Optional[Exception]]:
    import json
    payload = json.loads(buffer.decode("utf-8", errors="replace"))

    faction = payload.get("faction", 0)
    policy = payload.get("policy", 0)
    name = payload.get("name", "").strip()
    manifesto = payload.get("manifesto", "").strip()

    if not is_valid_guild_name(name):
        asyncio.create_task(client.send_message(60002, protobuf.SC_60002(result=GUILD_RESULT_NAME_INVALID, id=0)))
        return 0, 60002, None
    if not is_valid_guild_faction(faction) or not is_valid_guild_policy(policy) or not manifesto:
        asyncio.create_task(client.send_message(60002, protobuf.SC_60002(result=GUILD_RESULT_FAILURE, id=0)))
        return 0, 60002, None

    try:
        create_cost = load_game_set_uint("create_guild_cost")
    except Exception:
        asyncio.create_task(client.send_message(60002, protobuf.SC_60002(result=GUILD_RESULT_FAILURE, id=0)))
        return 0, 60002, None

    if not client.commander.has_enough_resource(4, create_cost):
        asyncio.create_task(client.send_message(60002, protobuf.SC_60002(result=GUILD_RESULT_FAILURE, id=0)))
        return 0, 60002, None

    from src.orm.guild_core import get_guild_set_uint, create_guild
    from src.orm import ERR_GUILD_NAME_EXISTS
    try:
        base_capital = get_guild_set_uint("base_capital")
    except Exception:
        asyncio.create_task(client.send_message(60002, protobuf.SC_60002(result=GUILD_RESULT_FAILURE, id=0)))
        return 0, 60002, None
    try:
        default_tech_id = get_guild_set_uint("guild_tech_default")
    except Exception:
        asyncio.create_task(client.send_message(60002, protobuf.SC_60002(result=GUILD_RESULT_FAILURE, id=0)))
        return 0, 60002, None

    try:
        guild_id = create_guild(
            client.commander, faction, policy, name, manifesto,
            create_cost, base_capital, default_tech_id,
        )
    except type(ERR_GUILD_NAME_EXISTS) if isinstance(ERR_GUILD_NAME_EXISTS, type) else Exception:
        asyncio.create_task(client.send_message(60002, protobuf.SC_60002(result=GUILD_RESULT_NAME_INVALID, id=0)))
        return 0, 60002, None
    except Exception:
        asyncio.create_task(client.send_message(60002, protobuf.SC_60002(result=GUILD_RESULT_FAILURE, id=0)))
        return 0, 60002, None

    asyncio.create_task(client.send_message(60002, protobuf.SC_60002(result=GUILD_RESULT_SUCCESS, id=guild_id)))
    # Server-authoritative task progress: joining/creating a guild satisfies
    # "Join any guild" (sub_type 403). The possession sync records it.
    try:
        from src.answer.task_handlers import schedule_possession_sync
        schedule_possession_sync(client)
    except Exception:
        pass
    return 0, 60002, None
