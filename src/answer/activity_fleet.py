import asyncio
from typing import Optional

from src.connection.client import Client
from src.protobuf import protobuf


def handle_edit_activity_fleet(buffer: bytes, client: Client) -> tuple[int, int, Optional[Exception]]:
    packet_id = 11205
    payload = protobuf.CS_11204()
    payload.ParseFromString(buffer)

    activity_id = payload.activity_id
    response = protobuf.SC_11205(activity_id=activity_id, result=1)

    try:
        from .activity_templates import load_activity_template
        load_activity_template(activity_id)
    except Exception:
        asyncio.create_task(client.send_message(packet_id, response))
        return 0, packet_id, None

    ships_map = getattr(client.commander, "ships_map", {}) or {}
    for group in payload.group_list:
        for ship_id in group.ship_list:
            if ship_id not in ships_map:
                asyncio.create_task(client.send_message(packet_id, response))
                return 0, packet_id, None

    groups = []
    for group in payload.group_list:
        g = protobuf.GROUPINFO_P11()
        g.id = group.id
        g.ship_list.extend(list(group.ship_list))
        for commander in group.commanders:
            c = protobuf.COMMANDERSINFO()
            c.pos = commander.pos
            c.id = commander.id
            g.commanders.append(c)
        groups.append(g)

    from src.orm.activity_fleet import save_activity_fleet_groups
    try:
        save_activity_fleet_groups(client.commander.commander_id, activity_id, groups)
    except Exception:
        asyncio.create_task(client.send_message(packet_id, response))
        return 0, packet_id, None

    response.result = 0
    asyncio.create_task(client.send_message(packet_id, response))
    return 0, packet_id, None
