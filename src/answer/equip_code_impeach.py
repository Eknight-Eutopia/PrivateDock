import asyncio
from typing import Optional

from src.connection.client import Client
from src.protobuf import protobuf

EQUIP_CODE_IMPEACH_RESULT_OK = 0
EQUIP_CODE_IMPEACH_RESULT_ERR = 1
EQUIP_CODE_IMPEACH_WARNING_RESULT = 0xFFFFFFFF
EQUIP_CODE_IMPEACH_DEFAULT_DAILY_LIMIT = 5


def _equip_code_impeach_daily_limit() -> int:
    import os
    raw = os.environ.get("EQUIP_CODE_IMPEACH_DAILY_LIMIT", "")
    if raw == "":
        return EQUIP_CODE_IMPEACH_DEFAULT_DAILY_LIMIT
    try:
        limit = int(raw)
        if limit <= 0:
            return EQUIP_CODE_IMPEACH_DEFAULT_DAILY_LIMIT
        return limit
    except (ValueError, TypeError):
        return EQUIP_CODE_IMPEACH_DEFAULT_DAILY_LIMIT


def handle_equip_code_impeach(buffer: bytes, client: Client) -> tuple[int, int, Optional[Exception]]:
    packet_id = 17608
    payload = protobuf.CS_17607()
    payload.ParseFromString(buffer)

    ship_group_id = payload.shipgroup
    share_id = payload.shareid
    report_type = payload.report_type

    if ship_group_id == 0 or share_id == 0 or (report_type != 1 and report_type != 2):
        asyncio.create_task(client.send_message(packet_id, protobuf.SC_17608(result=EQUIP_CODE_IMPEACH_RESULT_ERR)))
        return 0, packet_id, None

    import time
    now = int(time.time())
    day = now // 86400
    commander_id = client.commander.commander_id

    from src.orm.equip_code import try_insert_equip_code_report
    try:
        try_insert_equip_code_report(commander_id, ship_group_id, share_id, report_type, day)
    except Exception as e:
        return 0, packet_id, e

    limit = _equip_code_impeach_daily_limit()
    since = now - 86400

    from src.orm.equip_code import count_equip_code_reports_since
    try:
        count = count_equip_code_reports_since(commander_id, since)
    except Exception:
        count = 0

    result = EQUIP_CODE_IMPEACH_WARNING_RESULT if count > limit else EQUIP_CODE_IMPEACH_RESULT_OK
    asyncio.create_task(client.send_message(packet_id, protobuf.SC_17608(result=result)))
    return 0, packet_id, None
