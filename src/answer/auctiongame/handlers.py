from typing import Optional

from google.protobuf import descriptor_pb2, descriptor_pool, message_factory

from src.connection.client import Client
from src.connection.server import generate_packet_header
from src.protobuf import protobuf


def _get_or_create_sc_23431():
    pool = descriptor_pool.Default()
    try:
        desc = pool.FindMessageTypeByName("src.SC_23431")
        return message_factory.GetMessageClass(desc)
    except KeyError:
        pass

    fdp = descriptor_pb2.FileDescriptorProto()
    fdp.name = "SC_23431.proto"
    fdp.package = "src"
    msg = fdp.message_type.add()
    msg.name = "SC_23431"

    # Fields corresponding to p23_pb.lua SC_23431
    fields = [
        ("gold", 13, 2),            # uint32, required
        ("buy_num", 13, 2),         # uint32, required
        ("max_profit", 13, 2),      # uint32, required
        ("acc_profit", 5, 2),       # int32, required
        ("item_list", 13, 3),       # uint32, repeated
        ("acc_buy_price", 13, 2),   # uint32, required
        ("pre_buy_state", 13, 2),   # uint32, required
        ("pre_timestamp", 13, 2),   # uint32, required
        ("match_time", 13, 2),      # uint32, required
        ("is_forbidden", 13, 2),    # uint32, required
        ("game_num", 13, 2),        # uint32, required
        ("inactive_num", 13, 2),    # uint32, required
        ("inactive_state", 13, 2),  # uint32, required
        ("back_forbidden", 13, 2),  # uint32, required
        ("acc_item_price", 13, 2),  # uint32, required
        ("get_relief_num", 13, 2),  # uint32, required
    ]
    for i, (name, ftype, flabel) in enumerate(fields, start=1):
        f = msg.field.add()
        f.name = name
        f.number = i
        f.type = ftype
        f.label = flabel

    pool.AddSerializedFile(fdp.SerializeToString())
    desc = pool.FindMessageTypeByName("src.SC_23431")
    cls = message_factory.GetMessageClass(desc)
    setattr(protobuf, "SC_23431", cls)
    return cls


SC_23431 = _get_or_create_sc_23431()


def handle_auction_game_init(_buffer: bytes, client: Client) -> tuple[int, int, Optional[Exception]]:
    response = SC_23431()
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

