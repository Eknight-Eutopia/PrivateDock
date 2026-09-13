import asyncio
from typing import Optional

from src.connection.client import Client
from src.protobuf import protobuf

from .helpers import (
    load_or_create_world_runtime,
    save_world_runtime,
    sync_world_runtime,
    build_world_count_info,
    get_or_create_commander_world_boss_state,
    world_boss_state_to_proto,
)


def handle_world_check_info(_buffer: bytes, client: Client) -> tuple[int, int, Optional[Exception]]:
    runtime = load_or_create_world_runtime(client.commander.commander_id)
    if runtime is None:
        return 0, 33001, Exception("failed to load world runtime")

    changed, _ = sync_world_runtime(runtime)
    if changed:
        save_world_runtime(runtime)

    is_world_open = 1 if runtime.get("map_id", 0) != 0 else 0

    response = protobuf.SC_33001()
    response.is_world_open = is_world_open
    response.camp = runtime.get("camp", 0)
    response.count_info.CopyFrom(build_world_count_info(runtime))

    asyncio.create_task(client.send_message(33001, response))
    return 0, 33001, None


def handle_world_base_info(_buffer: bytes, client: Client) -> tuple[int, int, Optional[Exception]]:
    runtime = load_or_create_world_runtime(client.commander.commander_id)
    if runtime is None:
        return 0, 33114, Exception("failed to load world runtime")

    changed, _ = sync_world_runtime(runtime)
    if changed:
        save_world_runtime(runtime)

    is_world_open = 1 if runtime.get("map_id", 0) != 0 else 0

    response = protobuf.SC_33114()
    response.is_world_open = is_world_open
    response.progress = runtime.get("progress", 0)
    response.ship_id_list.extend(runtime.get("fleet_ship_ids", []))
    response.cmd_id_list.extend(runtime.get("commander_ids", []))

    data = response.SerializeToString()
    from src.connection.server import generate_packet_header
    header = generate_packet_header(33114, data, client.packet_index)
    client.write_to_buffer(header + data)
    return 0, 33114, None


def handle_world_boss_info(_buffer: bytes, client: Client) -> tuple[int, int, Optional[Exception]]:
    if client.commander is None:
        asyncio.create_task(client.send_message(34502, protobuf.SC_34502(
            fight_count=0, fight_count_update_time=0,
            summon_pt=0, summon_pt_old=0,
            summon_pt_daily_acc=0, summon_pt_old_daily_acc=0,
            summon_free=0, auto_fight_finish_time=0,
            default_boss_id=0, auto_fight_max_damage=0,
            guild_support=0, friend_support=0,
            world_support=0, self_boss_lv=0,
        )))
        return 0, 34502, None
    state = get_or_create_commander_world_boss_state(client.commander.commander_id)
    if state is None:
        return 0, 34502, Exception("failed to load world boss state")

    response = protobuf.SC_34502()
    response.fight_count = state.get("fight_count", 0)
    response.fight_count_update_time = state.get("fight_count_update_time", 0)
    boss = state.get("self_boss")
    if boss is not None:
        response.self_boss.CopyFrom(world_boss_state_to_proto(boss))
    response.summon_pt = state.get("summon_pt", 0)
    response.summon_pt_old = state.get("summon_pt_old", 0)
    response.summon_pt_daily_acc = state.get("summon_pt_daily_acc", 0)
    response.summon_pt_old_daily_acc = state.get("summon_pt_old_daily_acc", 0)
    response.summon_free = state.get("summon_free", 0)
    response.auto_fight_finish_time = state.get("auto_fight_finish_time", 0)
    response.default_boss_id = state.get("default_boss_id", 0)
    response.auto_fight_max_damage = state.get("auto_fight_max_damage", 0)
    response.guild_support = state.get("guild_support", 0)
    response.friend_support = state.get("friend_support", 0)
    response.world_support = state.get("world_support", 0)
    response.self_boss_lv = state.get("self_boss_lv", 0)

    asyncio.create_task(client.send_message(34502, response))
    return 0, 34502, None
