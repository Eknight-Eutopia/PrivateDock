import asyncio
import json
import threading
import time
from typing import Optional

from src.connection.client import Client


DAILY_REFRESH_SECONDS = 24 * 60 * 60
PORT_GOODS_DEFAULT = 3

_state_lock = threading.Lock()
_state: dict[int, dict] = {}


def _commander_state(commander_id: int) -> dict:
    with _state_lock:
        if commander_id not in _state:
            now_ts = int(time.time())
            _state[commander_id] = {
                "daily_offers": [210200, 210201, 210202],
                "daily_refresh_at": now_ts + DAILY_REFRESH_SECONDS,
                "active_daily_tasks": {},
                "shop_goods_counts": {},
                "fleet_group_ships": {},
                "achievement_claims": set(),
            }
        return _state[commander_id]


def handle_world_port_get_data(buffer: bytes, client: Client) -> tuple[int, int, Optional[Exception]]:
    try:
        payload = json.loads(buffer.decode("utf-8", errors="replace"))
    except Exception as e:
        return 0, 19497, e

    map_id = int(payload.get("map_id", 0))
    now_ts = int(time.time())

    state = _commander_state(client.commander.commander_id)
    with _state_lock:
        if now_ts >= state["daily_refresh_at"]:
            state["daily_refresh_at"] = now_ts + DAILY_REFRESH_SECONDS
        goods_id = map_id * 1000 + 1 if map_id > 0 else 0
        if goods_id > 0 and goods_id not in state["shop_goods_counts"]:
            state["shop_goods_counts"][goods_id] = PORT_GOODS_DEFAULT
        task_list = [0] + state["daily_offers"]
        goods_count = state["shop_goods_counts"].get(goods_id, PORT_GOODS_DEFAULT) if goods_id > 0 else 0
        next_refresh = state["daily_refresh_at"]

    port_obj = {
        "port_id": map_id,
        "task_list": task_list,
        "goods_list": [{"goods_id": goods_id, "count": goods_count}] if goods_id > 0 else [],
        "next_refresh_time": next_refresh,
    }

    response = {
        "result": 0,
        "port_list": [port_obj],
        "daily_task_list": [],
        "left_refresh_count": 0,
        "purchase_list": [],
    }
    asyncio.create_task(client.send_message(19497, response))
    return 0, 19497, None


def handle_world_port_update_daily_task(buffer: bytes, client: Client) -> tuple[int, int, Optional[Exception]]:
    try:
        payload = json.loads(buffer.decode("utf-8", errors="replace"))
    except Exception as e:
        return 0, 19525, e

    task_ids = payload.get("task_list", [])
    if not isinstance(task_ids, list) or len(task_ids) == 0:
        asyncio.create_task(client.send_message(19525, {"result": 1, "daily_task_list": []}))
        return 0, 19525, None

    state = _commander_state(client.commander.commander_id)
    with _state_lock:
        offer_set = set(state["daily_offers"])
        requested = []
        seen = set()
        for tid in task_ids:
            tid = int(tid)
            if tid == 0:
                asyncio.create_task(client.send_message(19525, {"result": 1, "daily_task_list": []}))
                return 0, 19525, None
            if tid in seen:
                continue
            seen.add(tid)
            requested.append(tid)

        for tid in requested:
            if tid not in offer_set:
                asyncio.create_task(client.send_message(19525, {"result": 6, "daily_task_list": []}))
                return 0, 19525, None
            if tid in state["active_daily_tasks"]:
                asyncio.create_task(client.send_message(19525, {"result": 20, "daily_task_list": []}))
                return 0, 19525, None

        now_ts = int(time.time())
        result_tasks = []
        for tid in requested:
            state["active_daily_tasks"][tid] = {"accepted_at": now_ts}
            result_tasks.append({
                "id": tid,
                "progress": 0,
                "accept_time": now_ts,
                "submit_time": 0,
                "event_map_id": 0,
            })

        result_tasks.sort(key=lambda t: t["id"])

    response = {
        "result": 0,
        "daily_task_list": result_tasks,
    }
    asyncio.create_task(client.send_message(19525, response))
    return 0, 19525, None


def handle_world_port_refresh_daily_task(buffer: bytes, client: Client) -> tuple[int, int, Optional[Exception]]:
    try:
        payload = json.loads(buffer.decode("utf-8", errors="replace"))
    except Exception as e:
        return 0, 19527, e

    req_type = int(payload.get("type", 0))
    if req_type != 0:
        asyncio.create_task(client.send_message(19527, {"result": 1}))
        return 0, 19527, None

    now_ts = int(time.time())
    state = _commander_state(client.commander.commander_id)
    with _state_lock:
        if now_ts >= state["daily_refresh_at"]:
            state["daily_refresh_at"] = now_ts + DAILY_REFRESH_SECONDS
        task_list = [0] + state["daily_offers"]
        next_refresh = state["daily_refresh_at"]

    response = {
        "result": 0,
        "task_list": task_list,
        "next_refresh_time": next_refresh,
    }
    asyncio.create_task(client.send_message(19527, response))
    return 0, 19527, None
