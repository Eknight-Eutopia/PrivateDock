import asyncio
import time

from src.connection.client import Client
from src.protobuf import protobuf
from .helpers import (
    is_secondary_password_valid,
    hash_secondary_password,
    verify_secondary_password,
    sanitize_secondary_system_list,
    secondary_password_locked,
    apply_secondary_password_failure,
    get_or_create_secondary_password_state,
    save_secondary_password_state,
)


def handle_fetch_secondary_password(_buffer: bytes, client: Client) -> tuple:
    async def _handle():
        state = await get_or_create_secondary_password_state(client.commander.commander_id)
        response = protobuf.SC_11604()
        response.state = state["state"]
        response.fail_cd = state["fail_cd"]
        response.fail_count = state["fail_count"]
        response.notice = state["notice"]
        for v in state["system_list"]:
            response.system_list.append(v)
        return await client.send_message(11604, response)

    try:
        result = asyncio.create_task(_handle())
        return 0, 11604, None
    except Exception as e:
        return 0, 11604, e


def handle_set_secondary_password(buffer: bytes, client: Client) -> tuple:
    async def _handle():
        payload = protobuf.CS_11605()
        payload.ParseFromString(buffer)
        response = protobuf.SC_11606()
        response.result = 0

        if not is_secondary_password_valid(payload.password):
            response.result = 1
            return await client.send_message(11606, response)

        state = await get_or_create_secondary_password_state(client.commander.commander_id)
        if state["state"] > 0 or state["password_hash"]:
            response.result = 1
            return await client.send_message(11606, response)

        hashed = hash_secondary_password(payload.password)
        system_list = sanitize_secondary_system_list(list(payload.system_list))

        state["password_hash"] = hashed
        state["notice"] = payload.notice
        state["system_list"] = system_list
        state["state"] = 1
        state["fail_count"] = 0
        state["fail_cd"] = 0
        await save_secondary_password_state(state)

        return await client.send_message(11606, response)

    try:
        asyncio.create_task(_handle())
        return 0, 11606, None
    except Exception as e:
        return 0, 11606, e


def handle_set_secondary_password_settings(buffer: bytes, client: Client) -> tuple:
    async def _handle():
        payload = protobuf.CS_11607()
        payload.ParseFromString(buffer)
        response = protobuf.SC_11608()
        response.result = 0

        state = await get_or_create_secondary_password_state(client.commander.commander_id)
        if state["state"] == 0 or not state["password_hash"]:
            response.result = 1
            return await client.send_message(11608, response)

        now = int(time.time())
        if secondary_password_locked(state, now):
            response.result = 1
            return await client.send_message(11608, response)

        valid = verify_secondary_password(payload.password, state["password_hash"])
        if not valid:
            apply_secondary_password_failure(state, now)
            await save_secondary_password_state(state)
            response.result = 9
            return await client.send_message(11608, response)

        system_list = sanitize_secondary_system_list(list(payload.system_list))
        state["system_list"] = system_list
        if not system_list:
            state["state"] = 0
            state["password_hash"] = ""
            state["notice"] = ""
        else:
            state["state"] = 2
        state["fail_count"] = 0
        state["fail_cd"] = 0
        await save_secondary_password_state(state)

        return await client.send_message(11608, response)

    try:
        asyncio.create_task(_handle())
        return 0, 11608, None
    except Exception as e:
        return 0, 11608, e


def handle_confirm_secondary_password(buffer: bytes, client: Client) -> tuple:
    async def _handle():
        payload = protobuf.CS_11609()
        payload.ParseFromString(buffer)
        response = protobuf.SC_11610()
        response.result = 0

        state = await get_or_create_secondary_password_state(client.commander.commander_id)
        if state["state"] == 0 or not state["password_hash"]:
            response.result = 1
            return await client.send_message(11610, response)

        now = int(time.time())
        if secondary_password_locked(state, now):
            response.result = 1
            return await client.send_message(11610, response)

        valid = verify_secondary_password(payload.password, state["password_hash"])
        if not valid:
            apply_secondary_password_failure(state, now)
            await save_secondary_password_state(state)
            response.result = 9
            return await client.send_message(11610, response)

        state["state"] = 2
        state["fail_count"] = 0
        state["fail_cd"] = 0
        await save_secondary_password_state(state)

        return await client.send_message(11610, response)

    try:
        asyncio.create_task(_handle())
        return 0, 11610, None
    except Exception as e:
        return 0, 11610, e
