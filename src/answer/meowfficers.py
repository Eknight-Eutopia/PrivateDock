from typing import Optional

from src.connection.client import Client
from src.connection.server import generate_packet_header


def handle_meowfficers(
    _buffer: bytes, client: Client,
) -> tuple[int, int, Optional[Exception]]:
    from src.protobuf import protobuf
    response = protobuf.SC_25001(usage_count=0)
    data = response.SerializeToString()
    header = generate_packet_header(25001, data, client.packet_index)
    client.write_to_buffer(header + data)
    return 0, 25001, None
