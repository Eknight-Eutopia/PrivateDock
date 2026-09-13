from src.answer.friend.helpers import (
    build_display_info as _build_display_info,
    build_friend_info as _build_friend_info,
    build_player_info_p50 as _build_player_info_p50,
    build_detail_info as _build_detail_info,
)
from src.connection.client import Client
from src.protobuf import protobuf


def BuildDisplayInfo(profile: dict) -> protobuf.DISPLAYINFO:
    return _build_display_info(profile)


def BuildFriendInfo(profile: dict, client: Client) -> protobuf.FRIEND_INFO:
    return _build_friend_info(profile, client)


def BuildPlayerInfoP50(profile: dict) -> protobuf.PLAYER_INFO_P50:
    return _build_player_info_p50(profile)


def BuildDetailInfo(profile: dict, client: Client, medal_ids: list) -> protobuf.DETAIL_INFO:
    return _build_detail_info(profile, client, medal_ids)
