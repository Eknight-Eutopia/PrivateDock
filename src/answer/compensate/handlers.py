import asyncio
import time
from typing import Optional

from src.connection.client import Client
from src.connection.server import generate_packet_header
from src.protobuf import protobuf
from src.db.store import get_default_store
from .helpers import (
    compensation_to_time_reward_info,
    compensation_summary,
    to_proto_drop_info_list,
)


def handle_compensate_notification(_buffer: bytes, client: Client) -> tuple[int, int, Optional[Exception]]:
    store = get_default_store()
    commander_id = client.commander.commander_id
    rows = store.fetch(
        "SELECT id, commander_id, title, text, send_time, expires_at, attach_flag, created_at "
        "FROM compensations WHERE commander_id = $1",
        commander_id
    )

    now = time.time()
    count = 0
    max_timestamp = 0
    now_unix = int(now)
    for row in rows:
        expires_at = row["expires_at"]
        if expires_at and expires_at.timestamp() <= now:
            continue
        expires_at_ts = int(expires_at.timestamp()) if expires_at else 0
        if not row.get("attach_flag", False):
            count += 1
        if expires_at_ts > max_timestamp:
            max_timestamp = expires_at_ts
    if max_timestamp <= now_unix:
        max_timestamp = 0

    response = protobuf.SC_30101()
    response.number = count
    response.max_timestamp = max_timestamp
    data = response.SerializeToString()
    header = generate_packet_header(30101, data, client.packet_index)
    client.write_to_buffer(header + data)
    return 0, 30101, None


def handle_get_compensate_list(buffer: bytes, client: Client) -> tuple[int, int, Optional[Exception]]:
    try:
        payload = protobuf.CS_30102()
        payload.ParseFromString(buffer)
    except Exception as e:
        return 0, 30103, e

    store = get_default_store()
    commander_id = client.commander.commander_id
    rows = store.fetch(
        "SELECT id, commander_id, title, text, send_time, expires_at, attach_flag, created_at "
        "FROM compensations WHERE commander_id = $1",
        commander_id
    )

    now = time.time()
    response = protobuf.SC_30103()
    for row in rows:
        expires_at = row["expires_at"]
        if expires_at and expires_at.timestamp() <= now:
            continue
        attachment_rows = store.fetch(
            "SELECT id, compensation_id, type, item_id, quantity "
            "FROM compensation_attachments WHERE compensation_id = $1",
            row["id"]
        )
        info = compensation_to_time_reward_info(row, attachment_rows)
        response.time_reward_list.append(info)

    data = response.SerializeToString()
    header = generate_packet_header(30103, data, client.packet_index)
    client.write_to_buffer(header + data)
    return 0, 30103, None


def handle_get_compensate_reward(buffer: bytes, client: Client) -> tuple[int, int, Optional[Exception]]:
    try:
        payload = protobuf.CS_30104()
        payload.ParseFromString(buffer)
    except Exception as e:
        return 0, 30105, e

    response = protobuf.SC_30105()
    response.result = 1

    store = get_default_store()
    commander_id = client.commander.commander_id
    reward_id = payload.reward_id

    row = store.fetchrow(
        "SELECT id, commander_id, title, text, send_time, expires_at, attach_flag, created_at "
        "FROM compensations WHERE id = $1 AND commander_id = $2",
        reward_id, commander_id
    )
    if row is None:
        asyncio.create_task(client.send_message(30105, response))
        return 0, 30105, None

    now = time.time()
    expires_at = row["expires_at"]
    if (expires_at and expires_at.timestamp() <= now) or row.get("attach_flag", False):
        asyncio.create_task(client.send_message(30105, response))
        return 0, 30105, None

    attachment_rows = store.fetch(
        "SELECT id, compensation_id, type, item_id, quantity "
        "FROM compensation_attachments WHERE compensation_id = $1",
        row["id"]
    )

    drop_list = to_proto_drop_info_list(attachment_rows)
    response.drop_list = drop_list

    all_rows = store.fetch(
        "SELECT id, commander_id, title, text, send_time, expires_at, attach_flag, created_at "
        "FROM compensations WHERE commander_id = $1",
        commander_id
    )
    count, max_timestamp = compensation_summary(all_rows, now)
    response.number = count
    response.max_timestamp = max_timestamp
    response.result = 0

    store.execute(
        "UPDATE compensations SET attach_flag = true WHERE id = $1",
        row["id"]
    )

    asyncio.create_task(client.send_message(30105, response))
    return 0, 30105, None
