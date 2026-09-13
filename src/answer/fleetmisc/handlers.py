import time
from typing import Optional

from src.connection.client import Client
from src.connection.server import generate_packet_header
from src.protobuf import protobuf

from .helpers import apply_commander_morale_recovery


def handle_fleet_energy_recover_time(_buffer: bytes, client: Client) -> tuple[int, int, Optional[Exception]]:
    now_unix = int(time.time())
    response = protobuf.SC_12031()

    next_tick = apply_commander_morale_recovery(client.commander.commander_id, now_unix)
    if next_tick == 0:
        next_tick = now_unix + 6 * 60

    response.energy_auto_increase_time = next_tick
    data = response.SerializeToString()
    header = generate_packet_header(12031, data, client.packet_index)
    client.write_to_buffer(header + data)
    return 0, 12031, None
