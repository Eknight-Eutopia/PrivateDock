import json
from datetime import datetime, timezone
from typing import Optional

FEAST_FAILURE_RESULT = 1


def is_feast_activity_active(act_id: int, now: Optional[datetime] = None) -> tuple[bool, Optional[dict]]:
    from src.answer.activity_templates import load_activity_template

    template = load_activity_template(act_id)
    if template is None:
        return False, None

    if now is None:
        now = datetime.now(timezone.utc)

    start_time, stop_time, ok = parse_activity_timer_window(template.time)
    if not ok:
        return False, None

    now_unix = int(now.timestamp())
    if now_unix < start_time or now_unix > stop_time:
        return False, None

    return True, template.__dict__ if hasattr(template, "__dict__") else {"id": template.id, "type": template.type, "config_data": template.config_data, "time": template.time}


def parse_activity_timer_window(raw) -> tuple[int, int, bool]:
    if raw is None:
        return 0, 0, False
    if isinstance(raw, str):
        try:
            value = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return 0, 0, False
    else:
        value = raw

    if not isinstance(value, list) or len(value) < 3:
        return 0, 0, False

    type_tag = value[0]
    if not isinstance(type_tag, str) or type_tag != "timer":
        return 0, 0, False

    start, ok = parse_activity_timer_point(value[1])
    if not ok:
        return 0, 0, False

    stop, ok = parse_activity_timer_point(value[2])
    if not ok:
        return 0, 0, False

    if stop < start:
        return 0, 0, False

    return start, stop, True


def parse_activity_timer_point(raw) -> tuple[int, bool]:
    if not isinstance(raw, list) or len(raw) != 2:
        return 0, False

    date = raw[0]
    clock = raw[1]
    if not isinstance(date, list) or len(date) != 3:
        return 0, False
    if not isinstance(clock, list) or len(clock) != 3:
        return 0, False

    year = _parse_json_int(date[0])
    if year is None:
        return 0, False
    month = _parse_json_int(date[1])
    if month is None:
        return 0, False
    day = _parse_json_int(date[2])
    if day is None:
        return 0, False
    hour = _parse_json_int(clock[0])
    if hour is None:
        return 0, False
    minute = _parse_json_int(clock[1])
    if minute is None:
        return 0, False
    second = _parse_json_int(clock[2])
    if second is None:
        return 0, False

    from datetime import timezone
    dt = datetime(year, month, day, hour, minute, second, tzinfo=timezone.utc)
    return int(dt.timestamp()), True


def _parse_json_int(raw) -> Optional[int]:
    if isinstance(raw, (int, float)):
        return int(raw)
    if isinstance(raw, str):
        try:
            return int(raw)
        except (ValueError, TypeError):
            return None
    return None


def flatten_uint_set_from_json(raw) -> set:
    if raw is None:
        return set()
    if isinstance(raw, str):
        try:
            value = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return set()
    else:
        value = raw

    out = set()
    _flatten_uint_set(out, value)
    return out


def _flatten_uint_set(out: set, value):
    if isinstance(value, (int, float)):
        num = int(value)
        if num > 0:
            out.add(num)
        return
    if isinstance(value, str):
        try:
            num = int(value)
            if num > 0:
                out.add(num)
        except (ValueError, TypeError):
            pass
        return
    if isinstance(value, (list, tuple)):
        for entry in value:
            _flatten_uint_set(out, entry)


def feast_party_roles_to_proto(roles: list) -> list:
    from src.protobuf import protobuf
    result = []
    for r in roles:
        obj = protobuf.P_PARTY_ROLE(tid=r["tid"], bubble=r.get("bubble", 0), speech_bubble=r.get("speech_bubble", 0))
        result.append(obj)
    return result


def feast_special_roles_to_proto(roles: list) -> list:
    from src.protobuf import protobuf
    result = []
    for r in roles:
        obj = protobuf.P_SPECIAL_ROLE(tid=r["tid"], state=r.get("state", 0), gift=r.get("gift", 0))
        result.append(obj)
    return result
