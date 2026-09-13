from typing import Optional

from src.connection.client import Client
from src.connection.server import generate_packet_header
from src.protobuf import protobuf


def handle_commander_friend_list(_buffer: bytes, client: Client) -> tuple[int, int, Optional[Exception]]:
    from src.orm.friend_social import list_commander_friend_ids
    from src.orm.profile import get_commander_social_profiles_by_ids

    response = protobuf.SC_50000()

    friend_ids = []
    try:
        friend_ids = list_commander_friend_ids(client.commander.commander_id)
    except Exception:
        pass

    if friend_ids:
        try:
            profiles_by_id = get_commander_social_profiles_by_ids(friend_ids)
            for fid in friend_ids:
                profile = profiles_by_id.get(fid)
                if profile is None:
                    continue
                response.friend_list.append(_build_friend_info(profile))
        except Exception:
            pass

    if len(response.friend_list) == 0:
        from src.orm.profile import list_friend_profiles
        try:
            legacy = list_friend_profiles(client.commander.commander_id)
            if legacy:
                for profile in legacy:
                    response.friend_list.append(_build_friend_info(profile))
        except Exception:
            pass

    from src.orm.friend_social import list_incoming_friend_requests
    try:
        requests = list_incoming_friend_requests(client.commander.commander_id)
        for req in requests:
            if isinstance(req, dict):
                created_at = req.get("created_at", 0)
                if hasattr(created_at, "timestamp"):
                    created_at = int(created_at.timestamp())
                requester = req.get("requester", {})
                content = req.get("content", "")
            else:
                created_at = getattr(req, "created_at", 0)
                if hasattr(created_at, "timestamp"):
                    created_at = int(created_at.timestamp())
                requester = getattr(req, "requester", {})
                content = getattr(req, "content", "")
            msg = protobuf.MSG_INFO_P50(
                timestamp=created_at,
                content=content,
                player=_build_player_info_p50(requester),
            )
            response.request_list.append(msg)
    except Exception:
        pass

    data = response.SerializeToString()
    header = generate_packet_header(50000, data, client.packet_index)
    client.write_to_buffer(header + data)
    return 0, 50000, None


def _build_display(profile) -> protobuf.DISPLAYINFO:
    if isinstance(profile, dict):
        return protobuf.DISPLAYINFO(
            icon=profile.get("display_icon_id", 0),
            skin=profile.get("display_skin_id", 0),
            icon_frame=profile.get("icon_frame_id", 0),
            chat_frame=profile.get("chat_frame_id", 0),
            icon_theme=profile.get("icon_theme_id", 0),
        )
    return protobuf.DISPLAYINFO(
        icon=getattr(profile, "display_icon_id", 0),
        skin=getattr(profile, "display_skin_id", 0),
        icon_frame=getattr(profile, "icon_frame_id", 0),
        chat_frame=getattr(profile, "chat_frame_id", 0),
        icon_theme=getattr(profile, "icon_theme_id", 0),
    )


def _build_friend_info(profile) -> protobuf.FRIEND_INFO:
    if isinstance(profile, dict):
        return protobuf.FRIEND_INFO(
            id=profile.get("commander_id", 0),
            name=profile.get("name", ""),
            level=profile.get("level", 0),
            adv=profile.get("manifesto", ""),
            online=0,
            pre_online_time=profile.get("pre_online_time", 0),
            display=_build_display(profile),
        )
    return protobuf.FRIEND_INFO(
        id=getattr(profile, "commander_id", 0),
        name=getattr(profile, "name", ""),
        level=getattr(profile, "level", 0),
        adv=getattr(profile, "manifesto", ""),
        online=0,
        pre_online_time=getattr(profile, "pre_online_time", 0),
        display=_build_display(profile),
    )


def _build_player_info_p50(player) -> protobuf.DISPLAYINFO:
    return _build_display(player)
