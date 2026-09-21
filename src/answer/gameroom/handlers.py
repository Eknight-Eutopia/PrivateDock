import math
from datetime import datetime, timezone
from typing import Optional

from src.connection.client import Client
from src.connection.server import generate_packet_header
from src.consts.drop_types import DROP_TYPE_RESOURCE
from src.protobuf import protobuf

from .helpers import (
    GAME_ROOM_COIN_RESOURCE_ID,
    GAME_ROOM_TICKET_RESOURCE_ID,
    load_game_room_template,
    load_game_room_settings,
    load_game_room_state,
    save_game_room_state,
    upsert_game_room_score,
    consume_commander_gold,
    consume_commander_resource,
    add_commander_resource,
    game_room_exchange_price_by_count,
    game_room_multiplier_for_score,
)


def _send_response(client: Client, packet_id: int, response) -> tuple[int, int, Optional[Exception]]:
    data = response.SerializeToString()
    header = generate_packet_header(packet_id, data, client.packet_index)
    client.write_to_buffer(header + data)
    return 0, packet_id, None


def handle_game_room_weekly_coin_claim(buffer: bytes, client: Client) -> tuple[int, int, Optional[Exception]]:
    try:
        payload = protobuf.CS_26122()
        payload.ParseFromString(buffer)
    except Exception as e:
        return 0, 26123, e

    response = protobuf.SC_26123()
    response.result = 1

    if client is None or client.commander is None:
        return _send_response(client, 26123, response)

    cid = client.commander.commander_id
    now = datetime.now(timezone.utc)

    state = load_game_room_state(cid, now)
    if state["weekly_claimed"]:
        return _send_response(client, 26123, response)

    try:
        settings = load_game_room_settings()
    except Exception as e:
        return 0, 26123, e

    from src.orm.resource import get_owned_resource_amount, add_resource
    current_coin = get_owned_resource_amount(cid, GAME_ROOM_COIN_RESOURCE_ID)

    remaining = max(0, settings["coin_max"] - current_coin)
    grant = min(settings["coin_initial"], remaining)
    if grant > 0:
        add_resource(cid, GAME_ROOM_COIN_RESOURCE_ID, grant)

    state["weekly_claimed"] = True
    save_game_room_state(state)

    response.result = 0
    return _send_response(client, 26123, response)


def handle_game_room_exchange_coin(buffer: bytes, client: Client) -> tuple[int, int, Optional[Exception]]:
    try:
        payload = protobuf.CS_26124()
        payload.ParseFromString(buffer)
    except Exception as e:
        return 0, 26125, e

    response = protobuf.SC_26125()
    response.result = 1

    if payload.times == 0 or client is None or client.commander is None:
        return _send_response(client, 26125, response)

    try:
        settings = load_game_room_settings()
    except Exception as e:
        return 0, 26125, e

    cid = client.commander.commander_id
    now = datetime.now(timezone.utc)
    state = load_game_room_state(cid, now)

    from src.orm.resource import get_owned_resource_amount, add_resource
    current_coin = get_owned_resource_amount(cid, GAME_ROOM_COIN_RESOURCE_ID)

    remaining = max(0, settings["coin_max"] - current_coin)
    grant_count = min(payload.times, remaining)
    if grant_count == 0:
        return _send_response(client, 26125, response)

    total_gold = sum(
        game_room_exchange_price_by_count(settings["coin_gold_tiers"], state["pay_coin_count"] + i)
        for i in range(1, grant_count + 1)
    )

    ok = consume_commander_gold(cid, total_gold)
    if not ok:
        return _send_response(client, 26125, response)

    add_resource(cid, GAME_ROOM_COIN_RESOURCE_ID, grant_count)
    state["pay_coin_count"] += grant_count
    save_game_room_state(state)

    response.result = 0
    return _send_response(client, 26125, response)


def handle_game_room_success_settlement(buffer: bytes, client: Client) -> tuple[int, int, Optional[Exception]]:
    try:
        payload = protobuf.CS_26126()
        payload.ParseFromString(buffer)
    except Exception as e:
        return 0, 26127, e

    response = protobuf.SC_26127()
    response.result = 1

    if payload.times == 0 or payload.roomid == 0 or client is None or client.commander is None:
        return _send_response(client, 26127, response)

    room, found, err = load_game_room_template(payload.roomid)
    if err is not None:
        return 0, 26127, err
    if not found or payload.times > room["coin_max"]:
        return _send_response(client, 26127, response)

    try:
        settings = load_game_room_settings()
    except Exception as e:
        return 0, 26127, e

    cid = client.commander.commander_id

    ok = consume_commander_resource(cid, GAME_ROOM_COIN_RESOURCE_ID, payload.times)
    if not ok:
        return _send_response(client, 26127, response)

    now = datetime.now(timezone.utc)
    state = load_game_room_state(cid, now)

    reward_per_play = int(math.floor(
        float(room["add_base"]) * game_room_multiplier_for_score(room.get("add_num", []), payload.score)
    ))
    reward = reward_per_play * payload.times

    ticket_resource_id = room.get("add_type", 0)
    if ticket_resource_id == 0:
        ticket_resource_id = GAME_ROOM_TICKET_RESOURCE_ID

    from src.orm.resource import get_owned_resource_amount, add_resource
    current_ticket = get_owned_resource_amount(cid, ticket_resource_id)

    total_remaining = max(0, settings["ticket_total_max"] - current_ticket)
    monthly_remaining = max(0, settings["ticket_monthly_max"] - state["monthly_ticket"])

    grant = min(reward, total_remaining, monthly_remaining)

    if grant > 0:
        add_resource(cid, ticket_resource_id, grant)
        state["monthly_ticket"] += grant
        drop = protobuf.DROPINFO()
        drop.type = DROP_TYPE_RESOURCE
        drop.id = ticket_resource_id
        drop.number = grant
        response.drop_list.append(drop)

    upsert_game_room_score(cid, payload.roomid, payload.score)
    save_game_room_state(state)

    response.result = 0

    # Server-authoritative task progress: a successful minigame play advances
    # "Finish the Shipgirl Game minigame N time(s)" (sub_type 415, target_id
    # = room id, e.g. room 64).
    try:
        from src.answer.task_handlers import schedule_emit
        schedule_emit(client, 415, payload.roomid, 1)
    except Exception:
        pass

    return _send_response(client, 26127, response)


def handle_game_room_first_enter_coin_claim(buffer: bytes, client: Client) -> tuple[int, int, Optional[Exception]]:
    try:
        payload = protobuf.CS_26128()
        payload.ParseFromString(buffer)
    except Exception as e:
        return 0, 26129, e

    response = protobuf.SC_26129()
    response.result = 1

    if client is None or client.commander is None:
        return _send_response(client, 26129, response)

    try:
        settings = load_game_room_settings()
    except Exception as e:
        return 0, 26129, e

    cid = client.commander.commander_id
    now = datetime.now(timezone.utc)
    state = load_game_room_state(cid, now)

    if state["first_enter_claimed"]:
        return _send_response(client, 26129, response)

    from src.orm.resource import get_owned_resource_amount, add_resource
    current_coin = get_owned_resource_amount(cid, GAME_ROOM_COIN_RESOURCE_ID)

    remaining = max(0, settings["coin_max"] - current_coin)
    grant = min(settings["coin_initial"], remaining)
    if grant > 0:
        add_resource(cid, GAME_ROOM_COIN_RESOURCE_ID, grant)

    state["first_enter_claimed"] = True
    save_game_room_state(state)

    response.result = 0
    return _send_response(client, 26129, response)

