from typing import Optional

from src.connection.client import Client
from src.connection.server import generate_packet_header
from src.protobuf import protobuf


def handle_update_loading_pic(
    buffer: bytes,
    client: Client,
) -> tuple[int, int, Optional[Exception]]:
    req = protobuf.cs_11034()
    req.ParseFromString(buffer)

    commander = client.commander
    commander.loading_pic_open_flag = int(req.loading_pic_open_flag)
    commander.loading_pic_id_list_1 = [int(x) for x in req.loading_pic_id_list_1]
    commander.loading_pic_id_list_2 = [int(x) for x in req.loading_pic_id_list_2]
    commander.save_loading_pic()

    response = protobuf.sc_11035(result=0)
    data = response.SerializeToString()
    header = generate_packet_header(11035, data, client.packet_index)
    client.write_to_buffer(header + data)
    return 0, 11035, None
