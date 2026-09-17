import asyncio
from typing import Optional

from src.connection.client import Client
from src.protobuf import protobuf
from src.orm.chapter import get_max_chapter_id
from src.orm.profile import get_player_profile_stats
from src.orm import get_player_registration_date

from .helpers import ensure_commander_home


def handle_get_commander_home(buffer: bytes, client: Client) -> tuple[int, int, Optional[Exception]]:
    try:
        payload = protobuf.CS_25026()
        payload.ParseFromString(buffer)
    except Exception as e:
        return 0, 25027, e

    if client.commander is None:
        response = protobuf.SC_25027(level=1, exp=0, clean=0)
        asyncio.create_task(client.send_message(25027, response))
        return 0, 25027, None
    home, slots = ensure_commander_home(client.commander.commander_id)

    protobuf_slots = []
    for slot in slots:
        proto_slot = protobuf.COMMANDERHOMESLOT()
        proto_slot.id = slot["slot_id"]
        proto_slot.op_flag = slot["op_flag"]
        proto_slot.exp_time = slot["exp_time"]
        proto_slot.commander_id = slot["assigned_commander_id"]
        proto_slot.style = slot["style"]
        proto_slot.cache_exp = slot["cache_exp"]
        if slot["assigned_commander_id"] != 0:
            from src.orm.commander_meow import get_commander_meow
            meow = get_commander_meow(client.commander.commander_id, slot["assigned_commander_id"])
            if meow is not None:
                proto_slot.commander_level = meow.level
                proto_slot.commander_exp = meow.exp
            else:
                owned = getattr(client.commander, "owned_ships_map", {}) or {}
                assigned = owned.get(slot["assigned_commander_id"])
                if assigned is not None:
                    proto_slot.commander_level = assigned.level
                    proto_slot.commander_exp = assigned.exp
        protobuf_slots.append(proto_slot)

    response = protobuf.SC_25027()
    response.level = home["level"]
    response.exp = home["exp"]
    response.slots.extend(protobuf_slots)
    response.clean = home["clean"]

    asyncio.create_task(client.send_message(25027, response))
    return 0, 25027, None


def handle_get_player_summary_info(buffer: bytes, client: Client) -> tuple[int, int, Optional[Exception]]:
    try:
        payload = protobuf.CS_26021()
        payload.ParseFromString(buffer)
    except Exception as e:
        return 0, 26022, e

    commander_id = client.commander.commander_id

    response = protobuf.SC_26022()
    response.result = 0
    response.guild_name = ""
    response.marry_number = 0
    response.medal_number = 0
    response.furniture_number = 0
    response.furniture_worth = 0
    response.character_id = 100001
    response.first_lady_id = 0
    response.first_lady_name = ""
    response.first_lady_time = 0
    response.world_max_task = 0
    response.collect_num = 0
    response.combat = 0
    response.ship_num_total = 0
    response.ship_num_120 = 0
    response.ship_num_125 = 0
    response.love200_num = 0
    response.skin_num = 0
    response.skin_ship_num = 0

    register_date = get_player_registration_date(commander_id)
    if register_date:
        response.register_date = register_date

    chapter_id = get_max_chapter_id(commander_id)
    if chapter_id < 101:
        chapter_id = 101
    response.chapter_id = chapter_id

    stats = get_player_profile_stats(commander_id)
    response.medal_number = stats["medal_number"]
    response.furniture_number = stats["furniture_number"]
    response.ship_num_total = stats["ship_num_total"]
    response.ship_num_120 = stats["ship_num_120"]
    response.ship_num_125 = stats["ship_num_125"]
    response.marry_number = stats["marry_number"]
    response.love200_num = stats["love200_num"]
    response.collect_num = stats["collect_num"]
    response.character_id = stats["character_id"]
    response.first_lady_id = stats["first_lady_id"]
    response.first_lady_name = stats["first_lady_name"]
    response.first_lady_time = stats["first_lady_time"]
    response.skin_num = stats["skin_num"]
    response.skin_ship_num = stats["skin_ship_num"]

    asyncio.create_task(client.send_message(26022, response))
    return 0, 26022, None
