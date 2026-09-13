from dataclasses import dataclass
from typing import Optional

from src.db.store import NotFoundError, get_default_store
from src.orm.config_entry import fetch_config_entry_data
from src.protobuf import protobuf

JUUSTAGRAM_CHAT_GROUP_CONFIG_CATEGORY = "ShareCfg/activity_ins_chat_group.json"
JUUSTAGRAM_RED_PACKET_CONFIG_CATEGORY = "ShareCfg/activity_ins_redpackage.json"


@dataclass
class JuustagramChatGroupConfig:
    id: int = 0
    ship_group: int = 0


@dataclass
class JuustagramRedPacketConfig:
    id: int = 0
    type: int = 0
    content: list = None


def get_config_entry(category: str, key: str):
    """Like the shared helper but raises :class:`NotFoundError` on a miss.

    The juustagram callers wrap every lookup in ``except NotFoundError`` and
    treat "no such config" as "feature disabled", so the exception is part of
    this package's contract.
    """
    data = fetch_config_entry_data(category, key)
    if data is None:
        raise NotFoundError(f"config_entry not found: {category}/{key}")
    return data


def get_juustagram_chat_group_config(chat_group_id: int) -> Optional[JuustagramChatGroupConfig]:
    try:
        data = get_config_entry(JUUSTAGRAM_CHAT_GROUP_CONFIG_CATEGORY, str(chat_group_id))
    except NotFoundError:
        return None
    if not isinstance(data, dict):
        return None
    # Explicit fields: the config rows carry many more keys (name, content,
    # trigger_type, ...) and positional data['id'] silently dropped ship_group.
    return JuustagramChatGroupConfig(
        id=data.get("id", 0),
        ship_group=data.get("ship_group", 0),
    )


def get_juustagram_red_packet_config(red_packet_id: int) -> Optional[JuustagramRedPacketConfig]:
    try:
        data = get_config_entry(JUUSTAGRAM_RED_PACKET_CONFIG_CATEGORY, str(red_packet_id))
    except NotFoundError:
        return None
    if not isinstance(data, dict):
        return None
    return JuustagramRedPacketConfig(
        id=data.get("id", 0),
        type=data.get("type", 0),
        content=list(data.get("content") or []),
    )


def ensure_juustagram_group_exists(commander_id: int, group_id: int, chat_group_id: int) -> dict:
    from src.orm.juustagram_group import ensure_juustagram_group_sync
    return ensure_juustagram_group_sync(commander_id, group_id, chat_group_id)


def get_juustagram_chat_group(commander_id: int, chat_group_id: int) -> dict:
    store = get_default_store()
    row = store.fetchrow(
        "SELECT id, commander_id, group_record_id, chat_group_id, op_time, read_flag "
        "FROM juustagram_chat_groups WHERE commander_id = $1 AND chat_group_id = $2",
        commander_id, chat_group_id,
    )
    if row is None:
        raise NotFoundError("juustagram_chat_group not found")
    return dict(row)


def create_juustagram_chat_group(commander_id: int, group_id: int, chat_group_id: int, op_time: int) -> dict:
    group = ensure_juustagram_group_exists(commander_id, group_id, chat_group_id)
    store = get_default_store()
    row = store.fetchrow(
        "INSERT INTO juustagram_chat_groups (commander_id, group_record_id, chat_group_id, op_time, read_flag) "
        "VALUES ($1, $2, $3, $4, 0) RETURNING id, commander_id, group_record_id, chat_group_id, op_time, read_flag",
        commander_id, group["id"], chat_group_id, op_time,
    )
    result = dict(row)
    result["reply_list"] = []
    return result


def add_juustagram_chat_reply(commander_id: int, chat_group_id: int, chat_id: int, value: int, now: int) -> dict:
    store = get_default_store()
    cg = get_juustagram_chat_group(commander_id, chat_group_id)
    row = store.fetchrow(
        "SELECT COALESCE(MAX(sequence), 0) as max_seq FROM juustagram_replies "
        "WHERE chat_group_record_id = $1",
        cg["id"],
    )
    max_seq = row["max_seq"] if row else 0
    store.execute(
        "INSERT INTO juustagram_replies (chat_group_record_id, sequence, key, value) "
        "VALUES ($1, $2, $3, $4)",
        cg["id"], max_seq + 1, chat_id, value,
    )
    store.execute(
        "UPDATE juustagram_chat_groups SET op_time = $1, read_flag = 0 WHERE id = $2 AND commander_id = $3",
        now, cg["id"], commander_id,
    )
    cg["op_time"] = now
    cg["read_flag"] = 0
    if "reply_list" not in cg:
        cg["reply_list"] = []
    cg["reply_list"].append({"id": 0, "chat_group_record_id": cg["id"], "sequence": max_seq + 1, "key": chat_id, "value": value})
    return cg


def update_juustagram_group(commander_id: int, group_id: int, skin_id=None, favorite=None, cur_chat_group=None):
    if skin_id is None and favorite is None and cur_chat_group is None:
        return
    sets = []
    params = []
    idx = 1
    if skin_id is not None:
        sets.append(f"skin_id = ${idx}")
        params.append(skin_id)
        idx += 1
    if favorite is not None:
        sets.append(f"favorite = ${idx}")
        params.append(favorite)
        idx += 1
    if cur_chat_group is not None:
        sets.append(f"cur_chat_group = ${idx}")
        params.append(cur_chat_group)
        idx += 1
    params.extend([commander_id, group_id])
    store = get_default_store()
    store.execute(
        f"UPDATE juustagram_groups SET {', '.join(sets)} WHERE commander_id = ${idx} AND group_id = ${idx+1}",
        *params,
    )


def set_juustagram_current_chat_group(commander_id: int, chat_group_id: int):
    store = get_default_store()
    row = store.fetchrow(
        "SELECT id, group_record_id FROM juustagram_chat_groups "
        "WHERE commander_id = $1 AND chat_group_id = $2",
        commander_id, chat_group_id,
    )
    if row is None:
        raise NotFoundError("juustagram_chat_group not found")
    store.execute(
        "UPDATE juustagram_groups SET cur_chat_group = $1 WHERE id = $2 AND commander_id = $3",
        chat_group_id, row["group_record_id"], commander_id,
    )


def build_juustagram_red_packet_drops(client, red_packet_id: int) -> list:
    config = get_juustagram_red_packet_config(red_packet_id)
    if config is None:
        return []
    if not config.content or len(config.content) != 3:
        return []
    drop_type = config.content[0]
    drop_id = config.content[1]
    drop_number = config.content[2]
    apply_juustagram_drop(client, drop_type, drop_id, drop_number)
    drop = protobuf.DROPINFO()
    drop.type = drop_type
    drop.id = drop_id
    drop.number = drop_number
    return [drop]


def apply_juustagram_drop(client, drop_type: int, drop_id: int, drop_number: int):
    if drop_type == 1:
        client.commander.add_resource(drop_id, drop_number)
    elif drop_type == 2:
        client.commander.add_item(drop_id, drop_number)
    elif drop_type == 6:
        client.commander.give_skin(drop_id)
