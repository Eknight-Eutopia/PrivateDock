from src.db.store import get_default_store
from src.protobuf import protobuf

DEFAULT_RESULT_SUCCESS = 0
DEFAULT_RESULT_OFFLINE = 28
DEFAULT_RESULT_FAILED = 1


def is_friend(commander_id: int, target_id: int) -> bool:
    store = get_default_store()
    row = store.fetchrow(
        "SELECT 1 FROM friend_relationships WHERE (commander_id = $1 AND friend_id = $2) OR (commander_id = $2 AND friend_id = $1)",
        commander_id, target_id
    )
    return row is not None


def create_friend_direct_message(sender_id: int, receiver_id: int, content: str, timestamp: int) -> None:
    store = get_default_store()
    store.execute(
        "INSERT INTO friend_direct_messages (sender_id, receiver_id, content, created_at) VALUES ($1, $2, $3, $4)",
        sender_id, receiver_id, content, timestamp
    )


def create_player_inform(reporter_id: int, target_id: int, info: str, content: str, timestamp: int) -> None:
    store = get_default_store()
    store.execute(
        "INSERT INTO player_informs (reporter_id, target_id, info, content, created_at) VALUES ($1, $2, $3, $4, $5)",
        reporter_id, target_id, info, content, timestamp
    )


def load_commander_social_display(commander_id: int):
    store = get_default_store()
    row = store.fetchrow(
        "SELECT commander_id, name, level, display_icon_id, display_skin_id, "
        "selected_icon_frame_id, selected_chat_frame_id, display_icon_theme_id "
        "FROM commanders WHERE commander_id = $1",
        commander_id
    )
    if row is None:
        return None
    return {
        "commander_id": row[0],
        "name": row[1],
        "level": row[2],
        "display_icon_id": row[3] or 0,
        "display_skin_id": row[4] or 0,
        "selected_icon_frame_id": row[5] or 0,
        "selected_chat_frame_id": row[6] or 0,
        "display_icon_theme_id": row[7] or 0,
    }


def build_social_player_info(commander: dict):
    info = protobuf.PLAYER_INFO_P50()
    info.id = commander.get("commander_id", 0)
    info.name = commander.get("name", "")
    info.lv = commander.get("level", 0)

    display = protobuf.DISPLAYINFO()
    display.icon = commander.get("display_icon_id", 0)
    display.skin = commander.get("display_skin_id", 0)
    display.icon_frame = commander.get("selected_icon_frame_id", 0)
    display.chat_frame = commander.get("selected_chat_frame_id", 0)
    display.icon_theme = commander.get("display_icon_theme_id", 0)
    display.marry_flag = 0
    display.transform_flag = 0
    info.display.CopyFrom(display)
    return info


def empty_social_player_info():
    info = protobuf.PLAYER_INFO_P50()
    info.id = 0
    info.name = ""
    info.lv = 0
    return info
