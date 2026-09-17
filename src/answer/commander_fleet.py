import json
from typing import Optional

from src.connection.client import Client
from src.connection.server import generate_packet_header
from src.db.store import get_default_store
from src.orm.fleet import ensure_submarine_fleet
from src.protobuf import protobuf


def handle_commander_fleet(
    _buffer: bytes, client: Client,
) -> tuple[int, int, Optional[Exception]]:
    store = get_default_store()
    ensure_submarine_fleet(client.commander.commander_id)
    rows = store.fetch(
        "SELECT id, game_id, name, ship_list, meowfficer_list FROM fleets WHERE commander_id = $1 ORDER BY id",
        client.commander.commander_id,
    )
    response = protobuf.SC_12101()
    for row in rows:
        ship_ids = row[3]
        if isinstance(ship_ids, str):
            try:
                ship_ids = json.loads(ship_ids)
            except Exception:
                ship_ids = []
        group = protobuf.GROUPINFO_P12(
            id=row[1] or row[0],
            name=row[2] or "",
            ship_list=[int(s) for s in (ship_ids or []) if str(s).isdigit()],
        )
        meow_ids = row[4]
        if isinstance(meow_ids, str):
            try:
                meow_ids = json.loads(meow_ids)
            except Exception:
                meow_ids = []
        if isinstance(meow_ids, list):
            for pos, mid in enumerate(meow_ids, start=1):
                if pos in (1, 2) and mid and int(mid) > 0:
                    c = protobuf.COMMANDERSINFO(pos=pos, id=int(mid))
                    group.commanders.append(c)

        response.group_list.append(group)

    data = response.SerializeToString()
    header = generate_packet_header(12101, data, client.packet_index)
    client.write_to_buffer(header + data)
    return 0, 12101, None
