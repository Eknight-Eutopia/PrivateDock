from typing import Optional

from src.connection.client import Client
from src.connection.server import generate_packet_header
from src.protobuf import extra_sc  # noqa: F401  (registers dynamic SC_23431)
from src.protobuf import protobuf


def handle_auction_game_init(_buffer: bytes, client: Client) -> tuple[int, int, Optional[Exception]]:
    response = protobuf.SC_23431()
    response.gold = 0
    response.buy_num = 0
    response.max_profit = 0
    response.acc_profit = 0
    response.acc_buy_price = 0
    response.pre_buy_state = 0
    response.pre_timestamp = 0
    response.match_time = 0
    response.is_forbidden = 0
    response.game_num = 0
    response.inactive_num = 0
    response.inactive_state = 0
    response.back_forbidden = 0
    response.acc_item_price = 0
    response.get_relief_num = 0
    data = response.SerializeToString()
    header = generate_packet_header(23431, data, client.packet_index)
    client.write_to_buffer(header + data)
    return 0, 23431, None
