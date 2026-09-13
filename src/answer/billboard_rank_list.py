import asyncio
from typing import Optional

from src.connection.client import Client
from src.protobuf import protobuf


PACKET_ID_PAGE = 18202
PACKET_ID_MY_RANK = 18204

BILLBOARD_RANK_SUPPORTED_MAX_TYPE = 50
BILLBOARD_RANK_POINT = 1
BILLBOARD_RANK_RANK = 1


def _is_supported_billboard_rank_type(rank_type: int) -> bool:
    return 1 <= rank_type <= BILLBOARD_RANK_SUPPORTED_MAX_TYPE


def _build_display_info(commander) -> protobuf.DISPLAYINFO:
    icon = getattr(commander, "display_icon_id", 0) or 0
    skin = getattr(commander, "display_skin_id", 0) or 0
    secretaries = commander.get_secretaries() if hasattr(commander, "get_secretaries") else []
    if icon == 0 and secretaries:
        icon = secretaries[0].ship_id if hasattr(secretaries[0], "ship_id") else 0
    if skin == 0 and secretaries:
        skin = secretaries[0].skin_id if hasattr(secretaries[0], "skin_id") else 0
    return protobuf.DISPLAYINFO(
        icon=icon,
        skin=skin,
        icon_frame=getattr(commander, "selected_icon_frame_id", 0) or 0,
        chat_frame=getattr(commander, "selected_chat_frame_id", 0) or 0,
        icon_theme=getattr(commander, "display_icon_theme_id", 0) or 0,
        marry_flag=0,
        transform_flag=0,
    )


def _build_rank_row(commander) -> protobuf.RANK_INFO_P18:
    return protobuf.RANK_INFO_P18(
        user_id=getattr(commander, "commander_id", 0),
        point=BILLBOARD_RANK_POINT,
        name=getattr(commander, "name", ""),
        lv=getattr(commander, "level", 0),
        arena_rank=BILLBOARD_RANK_RANK,
        display=_build_display_info(commander),
    )


def handle_billboard_rank_list_page(buffer: bytes, client: Client) -> tuple[int, int, Optional[Exception]]:
    try:
        payload = protobuf.CS_18201()
        payload.ParseFromString(buffer)
    except Exception as e:
        asyncio.create_task(client.send_message(PACKET_ID_PAGE, protobuf.SC_18202()))
        return 0, PACKET_ID_PAGE, e

    page = payload.page
    rank_type = payload.type
    if page != 1 or not _is_supported_billboard_rank_type(rank_type):
        asyncio.create_task(client.send_message(PACKET_ID_PAGE, protobuf.SC_18202()))
        return 0, PACKET_ID_PAGE, None

    commander = client.commander
    if commander is None:
        asyncio.create_task(client.send_message(PACKET_ID_PAGE, protobuf.SC_18202()))
        return 0, PACKET_ID_PAGE, None

    response = protobuf.SC_18202()
    response.list.append(_build_rank_row(commander))
    asyncio.create_task(client.send_message(PACKET_ID_PAGE, response))
    return 0, PACKET_ID_PAGE, None


def handle_billboard_my_rank(buffer: bytes, client: Client) -> tuple[int, int, Optional[Exception]]:
    try:
        payload = protobuf.CS_18203()
        payload.ParseFromString(buffer)
    except Exception as e:
        asyncio.create_task(client.send_message(PACKET_ID_MY_RANK, protobuf.SC_18204(point=0, rank=0)))
        return 0, PACKET_ID_MY_RANK, e

    rank_type = payload.type
    if not _is_supported_billboard_rank_type(rank_type):
        asyncio.create_task(client.send_message(PACKET_ID_MY_RANK, protobuf.SC_18204(point=0, rank=0)))
        return 0, PACKET_ID_MY_RANK, None

    commander = client.commander
    if commander is None:
        asyncio.create_task(client.send_message(PACKET_ID_MY_RANK, protobuf.SC_18204(point=0, rank=0)))
        return 0, PACKET_ID_MY_RANK, None

    asyncio.create_task(client.send_message(PACKET_ID_MY_RANK, protobuf.SC_18204(point=BILLBOARD_RANK_POINT, rank=BILLBOARD_RANK_RANK)))
    return 0, PACKET_ID_MY_RANK, None
