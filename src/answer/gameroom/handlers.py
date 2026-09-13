import asyncio
import math
from datetime import datetime, timezone
from typing import Optional

from src.connection.client import Client
from src.protobuf import protobuf
from src.consts.drop_types import DROP_TYPE_RESOURCE
from src.db.store import get_default_store

from .helpers import (
    GAME_ROOM_COIN_RESOURCE_ID,
    GAME_ROOM_TICKET_RESOURCE_ID,
    load_game_room_template,
    load_game_room_settings,
    load_game_room_state,
    load_game_room_state_for_update,
    load_game_room_resource_amount_for_update,
    save_game_room_state,
    upsert_game_room_score,
    consume_commander_gold,
    consume_commander_resource,
    add_commander_resource,
    game_room_exchange_price_by_count,
    game_room_multiplier_for_score,
)


def handle_game_room_weekly_coin_claim(buffer: bytes, client: Client) -> tuple[int, int, Optional[Exception]]:
    try:
        payload = protobuf.CS_26122()
        payload.ParseFromString(buffer)
    except Exception as e:
        return 0, 26123, e

    response = protobuf.SC_26123()
    response.result = 1

    if client is None or client.commander is None:
        asyncio.create_task(client.send_message(26123, response))
        return 0, 26123, None

    cid = client.commander.commander_id
    now = datetime.now(timezone.utc)

    state = load_game_room_state(cid, now)
    if state["weekly_claimed"]:
        asyncio.create_task(client.send_message(26123, response))
        return 0, 26123, None

    try:
        settings = load_game_room_settings()
    except Exception as e:
        return 0, 26123, e

    from src.orm.resource import get_owned_resource_amount, add_resource
    current_coin = get_owned_resource_amount(cid, GAME_ROOM_COIN_RESOURCE_ID)

    remaining = 0
    if current_coin < settings["coin_max"]:
        remaining = settings["coin_max"] - current_coin
    grant = settings["coin_initial"]
    if grant > remaining:
        grant = remaining
    if grant > 0:
        add_resource(cid, GAME_ROOM_COIN_RESOURCE_ID, grant)

    store = get_default_store()

    store.execute(
        "UPDATE game_room_states SET weekly_claimed = TRUE, updated_at = CURRENT_TIMESTAMP WHERE commander_id = $1",
        cid,
    )

    response.result = 0
    asyncio.create_task(client.send_message(26123, response))
    return 0, 26123, None


def handle_game_room_exchange_coin(buffer: bytes, client: Client) -> tuple[int, int, Optional[Exception]]:
    try:
        payload = protobuf.CS_26124()
        payload.ParseFromString(buffer)
    except Exception as e:
        return 0, 26125, e

    response = protobuf.SC_26125()
    response.result = 1

    if payload.times == 0 or client is None or client.commander is None:
        asyncio.create_task(client.send_message(26125, response))
        return 0, 26125, None

    try:
        client.commander.load()
    except Exception:
        asyncio.create_task(client.send_message(26125, response))
        return 0, 26125, None

    try:
        settings = load_game_room_settings()
    except Exception as e:
        return 0, 26125, e

    insufficient_gold = False
    no_capacity = False
    tx_error = None

    async def _run_tx():
        nonlocal insufficient_gold, no_capacity
        state = await load_game_room_state_for_update(client.commander.commander_id)

        current_coin = await load_game_room_resource_amount_for_update(
            client.commander.commander_id, GAME_ROOM_COIN_RESOURCE_ID
        )
        remaining = 0
        if current_coin < settings["coin_max"]:
            remaining = settings["coin_max"] - current_coin
        grant_count = payload.times
        if grant_count > remaining:
            grant_count = remaining
        if grant_count == 0:
            no_capacity = True
            return

        total_gold = 0
        for i in range(1, grant_count + 1):
            total_gold += game_room_exchange_price_by_count(settings["coin_gold_tiers"], state["pay_coin_count"] + i)

        ok = await consume_commander_gold(client.commander.commander_id, total_gold)
        if not ok:
            insufficient_gold = True
            return

        await add_commander_resource(client.commander.commander_id, GAME_ROOM_COIN_RESOURCE_ID, grant_count)
        state["pay_coin_count"] += grant_count
        await save_game_room_state(state)

    try:
        asyncio.create_task(_run_tx())
    except Exception as e:
        return 0, 26125, e

    if insufficient_gold or no_capacity:
        asyncio.create_task(client.send_message(26125, response))
        return 0, 26125, None

    response.result = 0
    asyncio.create_task(client.send_message(26125, response))
    return 0, 26125, None


def handle_game_room_success_settlement(buffer: bytes, client: Client) -> tuple[int, int, Optional[Exception]]:
    try:
        payload = protobuf.CS_26126()
        payload.ParseFromString(buffer)
    except Exception as e:
        return 0, 26127, e

    response = protobuf.SC_26127()
    response.result = 1

    if payload.times == 0 or payload.roomid == 0 or client is None or client.commander is None:
        asyncio.create_task(client.send_message(26127, response))
        return 0, 26127, None

    try:
        client.commander.load()
    except Exception:
        asyncio.create_task(client.send_message(26127, response))
        return 0, 26127, None

    room, found, err = load_game_room_template(payload.roomid)
    if err is not None:
        return 0, 26127, err
    if not found or payload.times > room["coin_max"]:
        asyncio.create_task(client.send_message(26127, response))
        return 0, 26127, None

    try:
        settings = load_game_room_settings()
    except Exception as e:
        return 0, 26127, e

    insufficient_coin = False
    tx_error = None

    async def _run_tx():
        nonlocal insufficient_coin
        state = await load_game_room_state_for_update(client.commander.commander_id)

        ok = await consume_commander_resource(client.commander.commander_id, GAME_ROOM_COIN_RESOURCE_ID, payload.times)
        if not ok:
            insufficient_coin = True
            return

        reward_per_play = int(math.floor(
            float(room["add_base"]) * game_room_multiplier_for_score(room.get("add_num", []), payload.score)
        ))
        reward = reward_per_play * payload.times

        ticket_resource_id = room.get("add_type", 0)
        if ticket_resource_id == 0:
            ticket_resource_id = GAME_ROOM_TICKET_RESOURCE_ID

        current_ticket = await load_game_room_resource_amount_for_update(
            client.commander.commander_id, ticket_resource_id
        )
        total_remaining = 0
        if current_ticket < settings["ticket_total_max"]:
            total_remaining = settings["ticket_total_max"] - current_ticket
        monthly_remaining = 0
        if state["monthly_ticket"] < settings["ticket_monthly_max"]:
            monthly_remaining = settings["ticket_monthly_max"] - state["monthly_ticket"]
        grant = reward
        if grant > total_remaining:
            grant = total_remaining
        if grant > monthly_remaining:
            grant = monthly_remaining

        if grant > 0:
            await add_commander_resource(client.commander.commander_id, ticket_resource_id, grant)
            state["monthly_ticket"] += grant
            drop = protobuf.DROPINFO()
            drop.type = DROP_TYPE_RESOURCE
            drop.id = ticket_resource_id
            drop.number = grant
            response.drop_list.append(drop)

        await upsert_game_room_score(client.commander.commander_id, payload.roomid, payload.score)
        await save_game_room_state(state)

    try:
        asyncio.create_task(_run_tx())
    except Exception as e:
        return 0, 26127, e

    if insufficient_coin:
        asyncio.create_task(client.send_message(26127, response))
        return 0, 26127, None

    response.result = 0
    # Server-authoritative task progress: a successful minigame play advances
    # "Finish the Shipgirl Game minigame N time(s)" (sub_type 415, target_id
    # = room id, e.g. room 64).
    try:
        from src.answer.task_handlers import schedule_emit
        schedule_emit(client, 415, payload.roomid, 1)
    except Exception:
        pass
    asyncio.create_task(client.send_message(26127, response))
    return 0, 26127, None


def handle_game_room_first_enter_coin_claim(buffer: bytes, client: Client) -> tuple[int, int, Optional[Exception]]:
    try:
        payload = protobuf.CS_26128()
        payload.ParseFromString(buffer)
    except Exception as e:
        return 0, 26129, e

    response = protobuf.SC_26129()
    response.result = 1

    if client is None or client.commander is None:
        asyncio.create_task(client.send_message(26129, response))
        return 0, 26129, None

    try:
        client.commander.load()
    except Exception:
        asyncio.create_task(client.send_message(26129, response))
        return 0, 26129, None

    try:
        settings = load_game_room_settings()
    except Exception as e:
        return 0, 26129, e

    already_claimed = False

    async def _run_tx():
        nonlocal already_claimed
        state = await load_game_room_state_for_update(client.commander.commander_id)
        if state["first_enter_claimed"]:
            already_claimed = True
            return

        current_coin = await load_game_room_resource_amount_for_update(
            client.commander.commander_id, GAME_ROOM_COIN_RESOURCE_ID
        )
        remaining = 0
        if current_coin < settings["coin_max"]:
            remaining = settings["coin_max"] - current_coin
        grant = settings["coin_initial"]
        if grant > remaining:
            grant = remaining
        if grant > 0:
            await add_commander_resource(client.commander.commander_id, GAME_ROOM_COIN_RESOURCE_ID, grant)

        state["first_enter_claimed"] = True
        await save_game_room_state(state)

    try:
        asyncio.create_task(_run_tx())
    except Exception as e:
        return 0, 26129, e

    if already_claimed:
        asyncio.create_task(client.send_message(26129, response))
        return 0, 26129, None

    response.result = 0
    asyncio.create_task(client.send_message(26129, response))
    return 0, 26129, None
