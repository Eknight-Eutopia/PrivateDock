from typing import Optional

from src.connection.client import Client
from src.connection.server import generate_packet_header
from src.protobuf import protobuf


def handle_shipyard_data(
    _buffer: bytes, client: Client,
) -> tuple[int, int, Optional[Exception]]:
    from src.answer.shipyard_blueprint_helpers import get_shipyard_state_or_default
    from src.orm.shipyard import list_commander_shipyard_blueprints

    try:
        state = get_shipyard_state_or_default(client.commander.commander_id)
        rows = list_commander_shipyard_blueprints(client.commander.commander_id)
    except Exception as e:
        return 0, 63100, e

    response = protobuf.SC_63100()
    response.cold_time = int(state.get("cold_time", 0) or 0)
    response.daily_catchup_strengthen = int(state.get("daily_catchup_strengthen", 0) or 0)
    response.daily_catchup_strengthen_ur = int(state.get("daily_catchup_strengthen_ur", 0) or 0)

    # Restore per-blueprint dev state (started/finished developments) so the
    # client's ShipBluePrint VOs survive a re-login. Rows the player never
    # touched are simply omitted and stay in the client's default LOCK state.
    for row in rows:
        bp = response.blueprint_list.add()
        bp.id = int(getattr(row, "blueprint_id", 0) or 0)
        bp.ship_id = int(getattr(row, "ship_id", 0) or 0)
        bp.start_time = int(getattr(row, "start_time", 0) or 0)
        bp.blue_print_level = int(getattr(row, "blue_print_level", 0) or 0)
        bp.exp = int(getattr(row, "exp", 0) or 0)
        bp.start_duration = int(getattr(row, "start_duration", 0) or 0)

    data = response.SerializeToString()
    header = generate_packet_header(63100, data, client.packet_index)
    client.write_to_buffer(header + data)
    return 0, 63100, None
