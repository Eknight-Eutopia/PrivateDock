from typing import Optional

from src.connection.client import Client
from src.protobuf import protobuf
from .helpers import list_notices


def handle_game_notices(_buffer: bytes, client: Client) -> tuple[int, int, Optional[Exception]]:
    notices = list_notices(10)
    response = protobuf.SC_11300()
    from src.protobuf import protobuf as pb
    for n in notices:
        item = pb.NOTICEINFO_P11()
        item.id = n["id"]
        item.version = str(n["version"]) if n["version"] is not None else ""
        item.btn_title = n["btn_title"] or ""
        item.title = n["title"] or ""
        item.title_image = n["title_image"] or ""
        item.time_desc = n["time_desc"] or ""
        item.content = n["content"] or ""
        item.tag_type = n["tag_type"]
        item.icon = n["icon"]
        item.track = n["track"] or ""
        item.priority = 0
        item.need_level = 0
        response.notice_list.append(item)
    from src.connection.server import generate_packet_header
    data = response.SerializeToString()
    header = generate_packet_header(11300, data, client.packet_index)
    client.write_to_buffer(header + data)
    return 0, 11300, None


def handle_game_tracking(buffer: bytes, _client: Client) -> tuple[int, int, Optional[Exception]]:
    try:
        payload = protobuf.CS_10991()
        payload.ParseFromString(buffer)
    except Exception:
        return 0, 10991, None
    return 0, 0, None
