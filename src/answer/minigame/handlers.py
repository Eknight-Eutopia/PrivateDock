import asyncio
import time as time_module
from typing import Optional

from src.connection.client import Client
from src.protobuf import protobuf
from src.answer.minigame.helpers import (
    run_mini_game_operation,
    MINI_GAME_OP_RESULT_FAILURE,
    get_or_create_mini_game_telemetry_state,
    save_mini_game_telemetry_state,
    get_mini_game_config,
    MAX_MINI_GAME_TELEMETRY_TIME,
    list_commander_mini_game_scores,
    load_mini_game_shop_config,
    refresh_if_needed,
    build_mini_game_shop_goods_proto,
    force_refresh,
    purchase,
)


def handle_mini_game_hub_data(_buffer: bytes, client: Client) -> tuple[int, int, Optional[Exception]]:
    response = protobuf.SC_26102()
    asyncio.create_task(client.send_message(26102, response))
    return 0, 26102, None


def handle_mini_game_operation(buffer: bytes, client: Client) -> tuple[int, int, Optional[Exception]]:
    try:
        req = protobuf.CS_26103()
        req.ParseFromString(buffer)
    except Exception as e:
        return 0, 26104, e

    commander_id = client.commander.commander_id if client.commander else 0
    result, hub_proto, data_proto, award_list = run_mini_game_operation(
        commander_id, req.hubid, req.cmd, list(req.args1),
    )

    response = protobuf.SC_26104()
    response.result = result
    if hub_proto is not None:
        response.hub.CopyFrom(hub_proto)
    if data_proto is not None:
        response.data.CopyFrom(data_proto)
    for award in award_list:
        drop = protobuf.DROPINFO()
        drop.type = award.get("type", 0)
        drop.id = award.get("id", 0)
        drop.number = award.get("number", 0)
        response.award_list.append(drop)

    asyncio.create_task(client.send_message(26104, response))
    return 0, 26104, None


def handle_mini_game_operation_batch(buffer: bytes, client: Client) -> tuple[int, int, Optional[Exception]]:
    try:
        req = protobuf.CS_26105()
        req.ParseFromString(buffer)
    except Exception as e:
        return 0, 26104, e

    if len(req.combine) == 0:
        response = protobuf.SC_26104()
        response.result = MINI_GAME_OP_RESULT_FAILURE
        asyncio.create_task(client.send_message(26104, response))
        return 0, 26104, None

    commander_id = client.commander.commander_id if client.commander else 0
    for operation in req.combine:
        result, hub_proto, data_proto, award_list = run_mini_game_operation(
            commander_id, operation.hubid, operation.cmd, list(operation.args1),
        )
        response = protobuf.SC_26104()
        response.result = result
        if hub_proto is not None:
            response.hub.CopyFrom(hub_proto)
        if data_proto is not None:
            response.data.CopyFrom(data_proto)
        for award in award_list:
            drop = protobuf.DROPINFO()
            drop.type = award.get("type", 0)
            drop.id = award.get("id", 0)
            drop.number = award.get("number", 0)
            response.award_list.append(drop)
        asyncio.create_task(client.send_message(26104, response))

    return 0, 26104, None


def handle_mini_game_time_submit(buffer: bytes, client: Client) -> tuple[int, int, Optional[Exception]]:
    try:
        req = protobuf.CS_26110()
        req.ParseFromString(buffer)
    except Exception:
        return 0, 0, None

    if req.gameid == 0 or req.time == 0 or req.time > MAX_MINI_GAME_TELEMETRY_TIME:
        return 0, 0, None

    game_config = get_mini_game_config(req.gameid)
    if game_config is None:
        return 0, 0, None

    commander_id = client.commander.commander_id if client.commander else 0
    if commander_id == 0:
        return 0, 0, None

    telemetry = get_or_create_mini_game_telemetry_state(commander_id)
    telemetry["game_times"][str(req.gameid)] = req.time
    save_mini_game_telemetry_state(telemetry)

    return 0, 0, None


def handle_mini_game_friend_rank(buffer: bytes, client: Client) -> tuple[int, int, Optional[Exception]]:
    try:
        req = protobuf.CS_26111()
        req.ParseFromString(buffer)
    except Exception as e:
        return 0, 26112, e

    response = protobuf.SC_26112()

    if req.gameid == 0:
        asyncio.create_task(client.send_message(26112, response))
        return 0, 26112, None

    game_config = get_mini_game_config(req.gameid)
    if game_config is None:
        asyncio.create_task(client.send_message(26112, response))
        return 0, 26112, None

    ranks = list_commander_mini_game_scores(req.gameid)
    for rank in ranks:
        fr = protobuf.FRIENDSCORE()
        fr.id = rank["commander_id"]
        fr.name = rank["name"]
        fr.score = rank["score"]
        display = protobuf.DISPLAYINFO()
        display.icon = rank.get("display_icon", 0)
        display.skin = rank.get("display_skin", 0)
        display.icon_frame = rank.get("icon_frame", 0)
        display.chat_frame = rank.get("chat_frame", 0)
        display.icon_theme = rank.get("icon_theme", 0)
        display.marry_flag = 0
        display.transform_flag = 0
        fr.display.CopyFrom(display)
        fr.time_data = rank.get("time_data", 0)
        response.ranks.append(fr)

    asyncio.create_task(client.send_message(26112, response))
    return 0, 26112, None


def handle_mini_game_shop(buffer: bytes, client: Client) -> tuple[int, int, Optional[Exception]]:
    try:
        protobuf.CS_26150().ParseFromString(buffer)
    except Exception as e:
        return 0, 26151, e

    commander_id = client.commander.commander_id if client.commander else 0
    now_ts = int(time_module.time())

    shop_config = load_mini_game_shop_config(now_ts)
    if shop_config is None:
        return 0, 26151, None

    state, goods = refresh_if_needed(commander_id, now_ts, shop_config)

    response = protobuf.SC_26151()
    response.goods.extend(build_mini_game_shop_goods_proto(goods))
    response.next_flash_time = state.get("next_refresh_time", 0)

    asyncio.create_task(client.send_message(26151, response))
    return 0, 26151, None


def handle_mini_game_shop_buy(buffer: bytes, client: Client) -> tuple[int, int, Optional[Exception]]:
    try:
        payload = protobuf.CS_26152()
        payload.ParseFromString(buffer)
    except Exception as e:
        return 0, 26153, e

    response = protobuf.SC_26153()
    response.result = 1

    if payload.goodsid == 0:
        asyncio.create_task(client.send_message(26153, response))
        return 0, 26153, None

    commander_id = client.commander.commander_id if client.commander else 0
    now_ts = int(time_module.time())

    shop_config = load_mini_game_shop_config(now_ts)
    if shop_config is None:
        asyncio.create_task(client.send_message(26153, response))
        return 0, 26153, None

    selected = []
    for pick in payload.selected:
        selected.append({"id": pick.id, "num": pick.num})

    drops, err = purchase(commander_id, payload.goodsid, selected, now_ts, shop_config)
    if err is not None:
        asyncio.create_task(client.send_message(26153, response))
        return 0, 26153, None

    response.result = 0
    for drop in drops:
        d = protobuf.DROPINFO()
        d.type = drop.get("type", 0)
        d.id = drop.get("id", 0)
        d.number = drop.get("number", 0)
        response.drop_list.append(d)

    asyncio.create_task(client.send_message(26153, response))
    return 0, 26153, None


def handle_mini_game_shop_refresh(buffer: bytes, client: Client) -> tuple[int, int, Optional[Exception]]:
    try:
        payload = protobuf.CS_26154()
        payload.ParseFromString(buffer)
    except Exception as e:
        return 0, 26155, e

    response = protobuf.SC_26155()
    response.result = 1

    if payload.type != 0:
        asyncio.create_task(client.send_message(26155, response))
        return 0, 26155, None

    commander_id = client.commander.commander_id if client.commander else 0
    now_ts = int(time_module.time())

    shop_config = load_mini_game_shop_config(now_ts)
    if shop_config is None:
        asyncio.create_task(client.send_message(26155, response))
        return 0, 26155, None

    state, _goods = force_refresh(commander_id, now_ts, shop_config)

    response.result = 0
    response.next_flash_time.append(state.get("next_refresh_time", 0))

    asyncio.create_task(client.send_message(26155, response))
    return 0, 26155, None
