
from src.connection.client import Client
from src.protobuf import protobuf

friendOperationSuccess = 0
friendOperationFailure = 1
friendOperationMaxed = 6
maxFriendCount = 50

friendBlacklistResultSuccess = 0
friendBlacklistResultInvalidTarget = 1
friendBlacklistResultNotFound = 2

friendRecommendationLimit = 20


def build_display_info(profile: dict) -> protobuf.DISPLAYINFO:
    return protobuf.DISPLAYINFO(
        Icon=profile.get("display_icon_id", 0),
        Skin=profile.get("display_skin_id", 0),
        IconFrame=profile.get("icon_frame_id", 0) or profile.get("selected_icon_frame_id", 0),
        ChatFrame=profile.get("chat_frame_id", 0) or profile.get("selected_chat_frame_id", 0),
        IconTheme=profile.get("icon_theme_id", 0) or profile.get("display_icon_theme_id", 0),
        MarryFlag=0,
        TransformFlag=0,
    )


def online_state(target_commander_id: int, client: Client, profile: dict) -> tuple:
    if client is not None and client.server is not None:
        target = client.server.find_client_by_commander(target_commander_id)
        if target is not None:
            return 1, 0
    return 0, profile.get("last_login_unix", 0) or profile.get("pre_online_time", 0)


def build_friend_info(profile: dict, client: Client) -> protobuf.FRIEND_INFO:
    online, pre_online = online_state(profile.get("commander_id", 0), client, profile)
    return protobuf.FRIEND_INFO(
        Id=profile.get("commander_id", 0),
        Name=profile.get("name", ""),
        Lv=profile.get("level", 0),
        Adv=profile.get("manifesto", "") or profile.get("adv", ""),
        Online=online,
        PreOnlineTime=pre_online,
        Display=build_display_info(profile),
    )


def build_player_info_p50(profile: dict) -> protobuf.PLAYER_INFO_P50:
    return protobuf.PLAYER_INFO_P50(
        Id=profile.get("commander_id", 0),
        Name=profile.get("name", ""),
        Lv=profile.get("level", 0),
        Display=build_display_info(profile),
    )


def build_detail_info(profile: dict, client: Client, medal_ids: list) -> protobuf.DETAIL_INFO:
    online, pre_online = online_state(profile.get("commander_id", 0), client, profile)
    return protobuf.DETAIL_INFO(
        Id=profile.get("commander_id", 0),
        Name=profile.get("name", ""),
        Title=0,
        Lv=profile.get("level", 0),
        ShipCount=profile.get("ship_count", 0),
        CollectionCount=profile.get("collection_count", 0),
        PvpAttackCount=profile.get("pvp_attack_count", 0),
        PvpWinCount=profile.get("pvp_win_count", 0),
        CollectAttackCount=profile.get("collect_attack_count", 0),
        AttackCount=0,
        WinCount=0,
        Adv=profile.get("manifesto", "") or profile.get("adv", ""),
        Online=online,
        PreOnlineTime=pre_online,
        Score=0,
        MedalId=medal_ids or [],
        Display=build_display_info(profile),
    )
