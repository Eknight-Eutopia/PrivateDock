import datetime

ACTIVITY_TYPE_BOSS_BATTLE_MARK_2 = 52
ACTIVITY_TYPE_CHALLENGE = 37
ACTIVITY_TYPE_NPC_COLLECTION = 15
ACTIVITY_TYPE_TASKS = 13
ACTIVITY_TYPE_ATELIER_LINK = 88
ACTIVITY_TYPE_COLORING_ALPHA = 43
ACTIVITY_TYPE_PUZZLE = 21
ACTIVITY_TYPE_NEW_SERVER_TASK = 82
ACTIVITY_TYPE_SURVEY = 101
ACTIVITY_TYPE_PUZZLE_CONNECT = 1001
ACTIVITY_TYPE_TOWN = 116
ACTIVITY_TYPE_EVENT_SINGLE = 112
ACTIVITY_TYPE_TASK_LIST = 18
ACTIVITY_TYPE_TASK_RES = 40
ACTIVITY_TYPE_STORY_AWARD = 59
# Type 17 (activity 21): "Akashi's Commission" chain — the hidden shop-tap
# easter egg. config_id = head task, config_data[0] = the touch-flag task.
ACTIVITY_TYPE_MINGSHI = 17
ACTIVITY_TYPE_NEW_SERVER_SHOP = 83
ACTIVITY_TYPE_BLACK_FRIDAY_SHOP = 38
ACTIVITY_TYPE_FRESH_TEC_CATCHUP = 71
ACTIVITY_CMD_SINGLE_EVENT_REFRESH = 2

# Build-pool activity types. The client's BuildShipProxy.GetPools() turns any
# active activity of these types into an EVENT build pool (Wishing Well / Pray
# for BUILDSHIP_1, new-server build for NEWSERVER_BUILD). The server has no
# Wishing Well / event-build logic, so including them in SC_11200 makes the
# client show a broken EVENT/Limited build tab (only the shop purchase works)
# and breaks the normal Light/Heavy/Special construction. Exclude them from the
# activity list we send.
ACTIVITY_TYPE_BUILDSHIP_1 = 1
ACTIVITY_TYPE_NEWSERVER_BUILD = 85
ACTIVITY_TYPES_THAT_CREATE_BUILD_POOLS = frozenset(
    (ACTIVITY_TYPE_BUILDSHIP_1, ACTIVITY_TYPE_NEWSERVER_BUILD)
)

NEW_SERVER_SHOP_RESULT_OK = 0
NEW_SERVER_SHOP_RESULT_FAILED = 1
NEW_SERVER_SHOP_RESULT_INSUFFICIENT = 2
NEW_SERVER_SHOP_RESULT_LIMIT = 3
NEW_SERVER_SHOP_RESULT_UNSUPPORTED = 4

NEW_SERVER_SHOP_GOODS_TYPE_FIXED = 1
NEW_SERVER_SHOP_GOODS_TYPE_SELECTABLE = 4


def _parse_timer_point(raw) -> tuple:
    if not isinstance(raw, list) or len(raw) != 2:
        return None, False
    date = raw[0]
    clock = raw[1]
    if not isinstance(date, list) or len(date) != 3:
        return None, False
    if not isinstance(clock, list) or len(clock) != 3:
        return None, False
    try:
        dt = datetime.datetime(
            int(date[0]), int(date[1]), int(date[2]),
            int(clock[0]), int(clock[1]), int(clock[2]),
            tzinfo=datetime.timezone.utc,
        )
        return dt, True
    except (ValueError, TypeError):
        return None, False


def parse_activity_time_window(time_config, now_dt) -> tuple:
    if time_config is None:
        return 0, 0, True, None
    if isinstance(time_config, str):
        if time_config == "always":
            unix = int(now_dt.timestamp())
            return unix, unix + 31536000, True, None
        return 0, 0, False, None
    if isinstance(time_config, list) and len(time_config) >= 1:
        tag = time_config[0]
        if tag == "timer" and len(time_config) >= 3:
            start, start_ok = _parse_timer_point(time_config[1])
            stop, stop_ok = _parse_timer_point(time_config[2])
            if not start_ok or not stop_ok:
                return 0, 0, False, None
            active = not (now_dt < start) and not (now_dt > stop)
            return int(start.timestamp()), int(stop.timestamp()), active, None
        if isinstance(tag, (int, float)):
            start = int(tag)
            end = int(time_config[1]) if len(time_config) > 1 and isinstance(time_config[1], (int, float)) else 0
            active = not (now_dt.timestamp() < start) and not (now_dt.timestamp() >= end) if end else True
            return start, end, active, None
    return 0, 0, True, None
