import time
from typing import Optional

from src.connection.client import Client
from src.connection.server import generate_packet_header
from src.orm.owned_ship import list_dock_ships
from src.answer.shipinfo.builder import build_ship_infos
from src.protobuf import protobuf


def handle_player_dock(
    _buffer: bytes, client: Client,
) -> tuple[int, int, Optional[Exception]]:
    # Passive morale (energy) recovery for ships not in dorm. The client
    # recovers energy locally on a 360s timer, but it is server-authoritative:
    # without this the stored (low) energy is re-sent on every dock sync and
    # overwrites the client's local recovery. apply_commander_morale_recovery
    # advances each ship's energy based on elapsed time since its anchor.
    try:
        from src.orm.morale import apply_commander_morale_recovery
        apply_commander_morale_recovery(client.commander.commander_id, int(time.time()))
    except Exception:
        pass

    try:
        rows = list_dock_ships(client.commander.commander_id)
    except Exception as e:
        return 0, 12001, e

    max_slice = min(101, len(rows))
    ship_slice = list(rows[:max_slice])

    from src.orm.game_data import preload_ship_template_configs
    preload_ship_template_configs([r.ship_id for r in rows])

    response = protobuf.SC_12001()
    # SHIPINFO snapshot building lives in ONE place
    # (src/answer/shipinfo/builder.py): skills, equip slots, strengths,
    # transforms, shadows and flag phantoms all come from there.
    for s in build_ship_infos(ship_slice, client.commander.commander_id):
        response.shiplist.append(s)

    data = response.SerializeToString()
    header = generate_packet_header(12001, data, client.packet_index)
    client.write_to_buffer(header + data)
    return 0, 12001, None
