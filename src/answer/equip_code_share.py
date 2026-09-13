import asyncio
import json
from typing import Optional

from src.connection.client import Client
from src.protobuf import protobuf

EQUIP_CODE_SHARE_RESULT_OK = 0
EQUIP_CODE_SHARE_RESULT_ERR = 1
EQUIP_CODE_SHARE_RESULT_ALREADY_SHARED = 7
EQUIP_CODE_SHARE_RESULT_DAILY_LIMIT = 44
EQUIP_CODE_SHARE_DEFAULT_DAILY_LIMIT = 5


def _equip_code_share_daily_limit() -> int:
    import os
    raw = os.environ.get("EQUIP_CODE_SHARE_DAILY_LIMIT", "")
    if raw == "":
        return EQUIP_CODE_SHARE_DEFAULT_DAILY_LIMIT
    try:
        limit = int(raw)
        if limit <= 0:
            return EQUIP_CODE_SHARE_DEFAULT_DAILY_LIMIT
        return limit
    except (ValueError, TypeError):
        return EQUIP_CODE_SHARE_DEFAULT_DAILY_LIMIT


def _decode_conversion_base32(s: str) -> tuple:
    if not s:
        return 0, False
    out = 0
    for c in s:
        digit = 0
        if "0" <= c <= "9":
            digit = ord(c) - ord("0")
        elif "a" <= c <= "z":
            c = chr(ord(c) - (ord("a") - ord("A")))
            digit = ord(c) - ord("A") + 10
        elif "A" <= c <= "Z":
            digit = ord(c) - ord("A") + 10
        else:
            return 0, False
        if digit >= 32:
            return 0, False
        out = out * 32 + digit
    return out, True


def _validate_equip_share_payload(ship_group_id: int, eqcode: str) -> bool:
    if ship_group_id == 0 or not eqcode:
        return False
    parts = eqcode.split("&")
    if len(parts) != 4:
        return False
    encoded_group = parts[1]
    decoded, ok = _decode_conversion_base32(encoded_group)
    if not ok:
        return False
    return decoded == ship_group_id


def handle_equip_code_share(buffer: bytes, client: Client) -> tuple[int, int, Optional[Exception]]:
    packet_id = 17604
    payload = json.loads(buffer.decode("utf-8", errors="replace"))

    ship_group_id = payload.get("shipgroup", 0)
    eqcode = payload.get("eqcode", "")

    if not _validate_equip_share_payload(ship_group_id, eqcode):
        asyncio.create_task(client.send_message(packet_id, protobuf.SC_17604(result=EQUIP_CODE_SHARE_RESULT_ERR)))
        return 0, packet_id, None

    import time
    now = int(time.time())
    day = now // 86400
    commander_id = client.commander.commander_id
    limit = _equip_code_share_daily_limit()

    from src.orm.equip_code import try_insert_equip_code_share
    try:
        inserted = try_insert_equip_code_share(commander_id, ship_group_id, day, limit)
    except Exception as e:
        return 0, packet_id, e

    if not inserted:
        from src.orm.equip_code import check_equip_code_share_exists
        try:
            exists = check_equip_code_share_exists(commander_id, ship_group_id, day)
        except Exception:
            exists = False
        result = EQUIP_CODE_SHARE_RESULT_ALREADY_SHARED if exists else EQUIP_CODE_SHARE_RESULT_DAILY_LIMIT
    else:
        result = EQUIP_CODE_SHARE_RESULT_OK

    asyncio.create_task(client.send_message(packet_id, protobuf.SC_17604(result=result)))
    return 0, packet_id, None
