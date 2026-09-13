
from src.protobuf import protobuf


def bool_to_uint32(value: bool) -> int:
    return 1 if value else 0


def to_proto_drop_info_list(attachments: list) -> list:
    result = []
    for a in attachments:
        drop = protobuf.DROPINFO()
        drop.type = a["type"]
        drop.id = a["item_id"]
        drop.number = a["quantity"]
        result.append(drop)
    return result


def compensation_to_time_reward_info(row: dict, attachments: list):
    info = protobuf.TIME_REWARD_INFO()
    info.id = row["id"]
    expires_at = row["expires_at"]
    send_time = row["send_time"]
    info.timestamp = int(expires_at.timestamp()) if expires_at else 0
    info.title = row["title"]
    info.text = row["text"]
    info.attachment_list = to_proto_drop_info_list(attachments)
    info.attach_flag = bool_to_uint32(row.get("attach_flag", False))
    info.send_time = int(send_time.timestamp()) if send_time else 0
    return info


def compensation_summary(rows: list, now: float) -> tuple:
    count = 0
    max_timestamp = 0
    now_unix = int(now)
    for row in rows:
        expires_at = row["expires_at"]
        if expires_at and expires_at.timestamp() <= now:
            continue
        expires_at_ts = int(expires_at.timestamp()) if expires_at else 0
        if not row.get("attach_flag", False):
            count += 1
        if expires_at_ts > max_timestamp:
            max_timestamp = expires_at_ts
    if max_timestamp <= now_unix:
        max_timestamp = 0
    return count, max_timestamp
