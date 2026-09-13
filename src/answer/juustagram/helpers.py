import json
import re
import time
from dataclasses import dataclass
from typing import Optional

from src.db.store import NotFoundError
from src.logger.logger import (
    LOG_LEVEL_DEBUG,
    LOG_LEVEL_ERROR,
    log_event,
)
from src.orm.commander_appreciation_state import (
    get_appreciation_row_sync,
    insert_default_appreciation_sync,
    update_cartoon_collect_mark_sync,
    update_cartoon_read_mark_sync,
)
from src.orm.config_entry import fetch_config_entry_data
from src.orm.juustagram_chat_group import mark_chat_groups_read_sync
from src.orm.juustagram_group import (
    create_group_with_chat_group_sync,
    get_commander_group_tree_sync,
)
from src.orm.juustagram_language import (
    get_language_value_sync,
    get_language_values_by_keys_sync,
    list_language_rows_by_prefix_sync,
)
from src.orm.juustagram_message_state import (
    get_message_states_sync,
    insert_message_states_sync,
    update_message_state_sync,
)
from src.orm.juustagram_npc_template import (
    get_npc_template_row_sync,
    get_npc_template_rows_by_ids_sync,
    list_npc_templates_by_message_persist_prefix_sync,
)
from src.orm.juustagram_player_discuss import (
    get_player_discuss_sync,
    list_player_discusses_for_ids_sync,
    list_player_discusses_sync,
    upsert_player_discuss_sync,
)
from src.orm.juustagram_template import (
    get_template_row_sync,
    get_template_rows_by_ids_sync,
)
from src.consts.juustagram import (
    JUUSTAGRAM_OP_ACTIVE,
    JUUSTAGRAM_OP_LIKE,
    JUUSTAGRAM_OP_MARK_READ,
    JUUSTAGRAM_OP_SHARE,
    JUUSTAGRAM_OP_UPDATE,
)
from src.protobuf import protobuf

JUUSTAGRAM_PLACEHOLDER_SHIP_GROUP = 960007
JUUSTAGRAM_PLACEHOLDER_CHAT_GROUP = 1

JUUSTAGRAM_CHAT_GROUP_CONFIG_CATEGORY = "ShareCfg/activity_ins_chat_group.json"
JUUSTAGRAM_RED_PACKET_CONFIG_CATEGORY = "ShareCfg/activity_ins_redpackage.json"


@dataclass
class JuustagramDiscussOption:
    discuss_id: int = 0
    index: int = 0
    text: str = ""
    npc_reply_id: int = 0


@dataclass
class JuustagramChatGroupConfig:
    id: int = 0
    ship_group: int = 0


@dataclass
class JuustagramRedPacketConfig:
    id: int = 0
    type: int = 0
    content: list = None


def get_juustagram_chat_group_config(chat_group_id: int):
    data = fetch_config_entry_data(JUUSTAGRAM_CHAT_GROUP_CONFIG_CATEGORY, chat_group_id)
    if not isinstance(data, dict):
        return None
    # Explicit fields: the config rows carry many more keys (name, content,
    # trigger_type, ...) and **data would reject them.
    return JuustagramChatGroupConfig(
        id=data.get("id", 0),
        ship_group=data.get("ship_group", 0),
    )


def get_juustagram_red_packet_config(red_packet_id: int):
    data = fetch_config_entry_data(JUUSTAGRAM_RED_PACKET_CONFIG_CATEGORY, red_packet_id)
    if not isinstance(data, dict):
        return None
    return JuustagramRedPacketConfig(
        id=data.get("id", 0),
        type=data.get("type", 0),
        content=list(data.get("content") or []),
    )


_TEMPLATE_CACHE: dict = {}
_NPC_TEMPLATE_CACHE: dict = {}
_LANG_PREFIX_CACHE: dict = {}
_OP_REPLIES_CACHE: dict = {}


def get_juustagram_template(template_id: int):
    if template_id in _TEMPLATE_CACHE:
        cached = _TEMPLATE_CACHE[template_id]
        if cached is None:
            raise NotFoundError("juustagram_template not found")
        return dict(cached)
    row = get_template_row_sync(template_id)
    if row is None:
        # Negative cache: the client asks for ids that have no template row
        # every login; do not re-query them per request.
        _TEMPLATE_CACHE[template_id] = None
        raise NotFoundError("juustagram_template not found")
    _TEMPLATE_CACHE[template_id] = row
    return dict(row)


def preload_juustagram_templates(template_ids: list) -> None:
    """One ANY() query warms the template cache for the whole requested id
    set (the client asks for the full active-id list in a single CS_11705)."""
    uncached = [t for t in dict.fromkeys(int(i) for i in template_ids) if t not in _TEMPLATE_CACHE]
    if not uncached:
        return
    found = get_template_rows_by_ids_sync(uncached)
    for t in uncached:
        _TEMPLATE_CACHE[t] = found.get(t)


def get_juustagram_npc_template(npc_id: int):
    if npc_id in _NPC_TEMPLATE_CACHE:
        cached = _NPC_TEMPLATE_CACHE[npc_id]
        if cached is None:
            raise NotFoundError("juustagram_npc_template not found")
        return dict(cached)
    row = get_npc_template_row_sync(npc_id)
    if row is None:
        _NPC_TEMPLATE_CACHE[npc_id] = None
        raise NotFoundError("juustagram_npc_template not found")
    _NPC_TEMPLATE_CACHE[npc_id] = row
    return dict(row)


def preload_juustagram_npc_templates(npc_ids: list) -> None:
    """Warm the npc-template cache with ANY() queries. npc_reply_persist chains
    may reference further npc ids, so iterate until no new uncached ids appear
    (normally a single roundtrip)."""
    discovered = [int(n) for n in dict.fromkeys(npc_ids) if int(n) != 0]
    for _ in range(8):
        uncached = [n for n in dict.fromkeys(discovered) if n not in _NPC_TEMPLATE_CACHE]
        if not uncached:
            return
        found = get_npc_template_rows_by_ids_sync(uncached)
        for t in uncached:
            _NPC_TEMPLATE_CACHE[t] = found.get(t)
        discovered = []
        for tpl in found.values():
            for entry in _ensure_list(json.loads(tpl.get("npc_reply_persist") or "[]")):
                rid = _resolve_npc_id(entry)
                if rid and rid not in _NPC_TEMPLATE_CACHE:
                    discovered.append(rid)
        if not discovered:
            return


_LANG_CACHE: dict[str, Optional[str]] = {}


def get_juustagram_language(key: str) -> str:
    # Static table (imported config) -- negative caching keeps the feed build
    # from re-querying keys that do not exist (the ins_<n> fallback path).
    if key in _LANG_CACHE:
        val = _LANG_CACHE[key]
        if val is None:
            raise NotFoundError("juustagram_language not found")
        return val
    value = get_language_value_sync(key)
    if value is None:
        _LANG_CACHE[key] = None
        raise NotFoundError("juustagram_language not found")
    _LANG_CACHE[key] = value
    return value


def preload_juustagram_languages(keys: list) -> None:
    uncached = [k for k in dict.fromkeys(k for k in keys if k) if k not in _LANG_CACHE]
    if not uncached:
        return
    found = get_language_values_by_keys_sync(uncached)
    for k in uncached:
        _LANG_CACHE[k] = found.get(k)


def list_juustagram_language_by_prefix(prefix: str) -> list:
    cached = _LANG_PREFIX_CACHE.get(prefix)
    if cached is not None:
        return list(cached)
    data = list_language_rows_by_prefix_sync(prefix)
    _LANG_PREFIX_CACHE[prefix] = data
    return list(data)


def list_juustagram_op_replies(message_id: int) -> list:
    cached = _OP_REPLIES_CACHE.get(message_id)
    if cached is not None:
        return list(cached)
    prefix = f"op_reply_{message_id}_"
    data = list_npc_templates_by_message_persist_prefix_sync(prefix)
    _OP_REPLIES_CACHE[message_id] = data
    return list(data)


def get_or_create_juustagram_message_states(commander_id: int, message_ids: list, now: int) -> dict:
    """Batch variant: one SELECT for the whole id list, minimal per-row inserts
    (no re-SELECT - the row contents are known). Cuts ~2-3 sync roundtrips
    per message from the feed-range handler."""
    ids = [int(m) for m in message_ids]
    if not ids:
        return {}
    states = get_message_states_sync(commander_id, ids)
    missing = [mid for mid in ids if mid not in states]
    if missing:
        insert_message_states_sync([(commander_id, mid, now) for mid in missing])
        for mid in missing:
            states[mid] = {
                "commander_id": commander_id,
                "message_id": mid,
                "is_read": 0,
                "is_good": 0,
                "good_count": 0,
                "updated_at": now,
            }
    return states


def get_or_create_juustagram_message_state(commander_id: int, message_id: int, now: int) -> dict:
    return get_or_create_juustagram_message_states(commander_id, [message_id], now)[message_id]


def save_juustagram_message_state(state: dict):
    update_message_state_sync(state)


def get_juustagram_player_discuss(commander_id: int, message_id: int, discuss_id: int):
    row = get_player_discuss_sync(commander_id, message_id, discuss_id)
    if row is None:
        raise NotFoundError("juustagram_player_discuss not found")
    return row


def list_juustagram_player_discuss(commander_id: int, message_id: int) -> list:
    return list_player_discusses_sync(commander_id, message_id)


def list_juustagram_player_discusses_for_ids(commander_id: int, message_ids: list) -> dict:
    """Batch variant keyed by message_id (one roundtrip for the whole range)."""
    return list_player_discusses_for_ids_sync(commander_id, message_ids)


def upsert_juustagram_player_discuss(entry: dict):
    upsert_player_discuss_sync(entry)


def get_juustagram_groups(commander_id: int) -> list:
    return get_commander_group_tree_sync(commander_id)


def create_juustagram_group(commander_id: int, group_id: int, chat_group_id: int) -> dict:
    return create_group_with_chat_group_sync(commander_id, group_id, chat_group_id)


def mark_juustagram_chat_groups_read(commander_id: int, chat_group_ids: list):
    mark_chat_groups_read_sync(commander_id, chat_group_ids)


def set_commander_cartoon_read_mark(commander_id: int, cartoon_id: int):
    row = get_appreciation_row_sync(commander_id)
    if row is None:
        insert_default_appreciation_sync(commander_id, json.dumps([cartoon_id]), json.dumps([]))
        return
    marks = json.loads(row["cartoon_read_mark"]) if row["cartoon_read_mark"] else []
    if cartoon_id not in marks:
        marks.append(cartoon_id)
    update_cartoon_read_mark_sync(commander_id, json.dumps(marks))


def set_commander_cartoon_collect_mark(commander_id: int, cartoon_id: int, liked: bool):
    row = get_appreciation_row_sync(commander_id)
    if row is None:
        marks = [cartoon_id] if liked else []
        insert_default_appreciation_sync(commander_id, json.dumps([]), json.dumps(marks))
        return
    marks = json.loads(row["cartoon_collect_mark"]) if row["cartoon_collect_mark"] else []
    if liked:
        if cartoon_id not in marks:
            marks.append(cartoon_id)
    else:
        marks = [m for m in marks if m != cartoon_id]
    update_cartoon_collect_mark_sync(commander_id, json.dumps(marks))


def resolve_juustagram_text(key: str) -> str:
    if not key:
        return ""
    try:
        return get_juustagram_language(key)
    except NotFoundError:
        m = re.match(r"^ins_(\d+)$", key)
        if m:
            try:
                return get_juustagram_language(m.group(1))
            except NotFoundError:
                return ""
        return ""


def parse_juustagram_time(config: list, fallback: int) -> int:
    if len(config) < 2 or len(config[0]) < 3 or len(config[1]) < 3:
        return fallback
    date = config[0]
    time_parts = config[1]
    if date[0] == 0 or date[1] == 0 or date[2] == 0:
        return fallback
    import datetime
    dt = datetime.datetime(date[0], date[1], date[2], time_parts[0], time_parts[1], time_parts[2], tzinfo=datetime.timezone.utc)
    return int(dt.timestamp())


def parse_juustagram_op_key(key: str, prefix: str):
    if not key.startswith(prefix):
        return None, None, False
    parts = key[len(prefix):].split("_")
    if len(parts) < 2:
        return None, None, False
    try:
        discuss_id = int(parts[0])
        index = int(parts[1])
        return discuss_id, index, True
    except (ValueError, IndexError):
        return None, None, False


def _selection_time(value: int, fallback: int) -> int:
    return value if value != 0 else fallback


def _selection_option_text(options: list, index: int) -> str:
    for opt in options:
        if opt.index == index:
            return opt.text
    return ""


def _uint32_slice_or_empty(value: int) -> list:
    return [value] if value != 0 else []


def _ensure_list(val):
    if val is None:
        return []
    return val if isinstance(val, list) else [val]


def _unique_uint32(values: list) -> list:
    seen = set()
    result = []
    for v in values:
        if v == 0 or v in seen:
            continue
        seen.add(v)
        result.append(v)
    result.sort()
    return result


def load_juustagram_discuss_options(message_id: int):
    """Static per-message content (config + language rows) - identical for every
    commander, so cache it in-process. Returns fresh containers; the cached
    option objects are shared but only ever mutated idempotently."""
    cached = _DISCUSS_OPTIONS_CACHE.get(message_id)
    if cached is not None:
        options, option_map = cached
        return list(options), option_map

    prefix = f"ins_op_{message_id}_"
    entries = list_juustagram_language_by_prefix(prefix)
    replies = list_juustagram_op_replies(message_id)

    reply_map = {}
    for reply in replies:
        msg_persist = reply.get("message_persist", "")
        rprefix = f"op_reply_{message_id}_"
        discuss_id, index, ok = parse_juustagram_op_key(msg_persist, rprefix)
        if not ok:
            continue
        if discuss_id not in reply_map:
            reply_map[discuss_id] = {}
        reply_map[discuss_id][index] = reply["id"]

    options = []
    for entry in entries:
        key = entry["key"]
        discuss_id, index, ok = parse_juustagram_op_key(key, prefix)
        if not ok:
            continue
        option = JuustagramDiscussOption(
            discuss_id=discuss_id,
            index=index,
            text=entry["value"],
        )
        if discuss_id in reply_map and index in reply_map[discuss_id]:
            option.npc_reply_id = reply_map[discuss_id][index]
        options.append(option)

    options.sort(key=lambda o: (o.discuss_id, o.index))
    option_map = {}
    for opt in options:
        if opt.discuss_id not in option_map:
            option_map[opt.discuss_id] = {}
        option_map[opt.discuss_id][opt.index] = opt
    _DISCUSS_OPTIONS_CACHE[message_id] = (options, option_map)
    return list(options), option_map


def list_juustagram_discuss_options(message_id: int) -> list:
    options, _ = load_juustagram_discuss_options(message_id)
    return options


def build_juustagram_npc_entry(template: dict, now: int):
    text = resolve_juustagram_text(template.get("message_persist", ""))
    npc_reply_persist = _ensure_list(json.loads(template.get("npc_reply_persist", "[]")))
    time_persist = _ensure_list(json.loads(template.get("time_persist", "[]")))
    entry_time = parse_juustagram_time(time_persist, now)
    entry = protobuf.INS_NPC()
    entry.id = template["id"]
    entry.time = entry_time
    entry.text = text
    entry.npc_reply.extend(_resolve_npc_id(r) for r in npc_reply_persist)
    return entry


def _resolve_npc_id(entry) -> int:
    if isinstance(entry, dict):
        val = entry.get("id", 0)
    else:
        val = entry
    if val is None or val == "":
        return 0
    return int(val)


def build_juustagram_npc_discuss(ids: list, now: int):
    if not ids:
        return [], []
    entries = []
    reply_ids = []
    for entry in ids:
        npc_id = _resolve_npc_id(entry)
        if npc_id == 0:
            continue
        template = get_juustagram_npc_template(npc_id)
        entry = build_juustagram_npc_entry(template, now)
        entries.append(entry)
        npc_reply_persist = _ensure_list(json.loads(template.get("npc_reply_persist", "[]")))
        for r in npc_reply_persist:
            reply_ids.append(_resolve_npc_id(r))
    return entries, reply_ids


def build_juustagram_npc_reply(reply_ids: list, now: int):
    if not reply_ids:
        return []
    queue = _unique_uint32(reply_ids)
    seen = set()
    entries = []
    while queue:
        npc_id = queue.pop(0)
        if npc_id in seen:
            continue
        seen.add(npc_id)
        template = get_juustagram_npc_template(npc_id)
        entry = build_juustagram_npc_entry(template, now)
        entries.append(entry)
        npc_reply_persist = _ensure_list(json.loads(template.get("npc_reply_persist", "[]")))
        queue = _unique_uint32(queue + [_resolve_npc_id(r) for r in npc_reply_persist])
    entries.sort(key=lambda e: e.id)
    return entries


def build_juustagram_player_discuss(commander_id: int, message_id: int, options: list, option_map: dict, now: int,
                                    selections: Optional[list] = None):
    if selections is None:
        selections = list_juustagram_player_discuss(commander_id, message_id)
    selection_map = {}
    for sel in selections:
        selection_map[sel["discuss_id"]] = sel

    grouped = {}
    for opt in options:
        if opt.discuss_id not in grouped:
            grouped[opt.discuss_id] = []
        grouped[opt.discuss_id].append(opt)

    discuss_ids = sorted(grouped.keys())
    player_discuss = []
    op_reply_ids = []

    for discuss_id in discuss_ids:
        options_for_discuss = grouped[discuss_id]
        selection = selection_map.get(discuss_id)
        if selection is not None:
            if discuss_id not in option_map:
                return None, None, Exception("missing discuss options")
            discuss_options = option_map[discuss_id]
            option_index = selection["option_index"]
            if option_index not in discuss_options:
                return None, None, Exception("invalid discuss option")
            opt = discuss_options[option_index]
            text = opt.text
            if not text:
                text = _selection_option_text(options_for_discuss, option_index)
            npc_reply_id = selection.get("npc_reply_id", 0) or opt.npc_reply_id
            player = protobuf.INS_PLAYER()
            player.id = discuss_id
            player.time = _selection_time(selection.get("comment_time", 0), now)
            player.text_list.extend([])
            player.text = text
            player.npc_reply.extend(_uint32_slice_or_empty(npc_reply_id))
            player_discuss.append(player)
            if npc_reply_id != 0:
                op_reply_ids.append(npc_reply_id)
            continue

        text_list = []
        for opt in options_for_discuss:
            text_list.append(opt.text)
            if opt.npc_reply_id != 0:
                op_reply_ids.append(opt.npc_reply_id)
        replies = _unique_uint32(op_reply_ids)
        player = protobuf.INS_PLAYER()
        player.id = discuss_id
        player.time = now
        player.text_list.extend(text_list)
        player.text = ""
        player.npc_reply.extend(replies)
        player_discuss.append(player)

    return player_discuss, _unique_uint32(op_reply_ids)


def build_juustagram_message_payload(template: dict, state: dict, message_text: str, message_time: int,
                                     player_discuss: list, op_reply_ids: list, now: int):
    npc_discuss_persist = _ensure_list(json.loads(template.get("npc_discuss_persist", "[]")))
    npc_discuss, reply_ids = build_juustagram_npc_discuss(npc_discuss_persist, now)
    reply_ids.extend(op_reply_ids)
    npc_reply = build_juustagram_npc_reply(reply_ids, now)

    msg = protobuf.INS_MESSAGE()
    msg.id = template["id"]
    msg.time = message_time
    msg.text = message_text
    msg.picture = template.get("picture_persist", "")
    msg.oalist_pic = template.get("oalist_pic_persist", "")
    msg.player_discuss.extend(player_discuss)
    msg.npc_discuss.extend(npc_discuss)
    msg.npc_reply.extend(npc_reply)
    msg.good = state.get("good_count", 0)
    msg.is_good = state.get("is_good", 0)
    msg.is_read = state.get("is_read", 0)
    return msg


_DISCUSS_OPTIONS_CACHE: dict = {}


def build_juustagram_message(commander_id: int, message_id: int, now: int,
                             state: Optional[dict] = None, selections: Optional[list] = None):
    if state is None:
        state = get_or_create_juustagram_message_state(commander_id, message_id, now)
    template = get_juustagram_template(message_id)
    text = resolve_juustagram_text(template.get("message_persist", "")) or (template.get("title") or "")
    time_persist = _ensure_list(json.loads(template.get("time_persist", "[]")))
    message_time = parse_juustagram_time(time_persist, now)

    options, option_map = load_juustagram_discuss_options(message_id)
    player_discuss, op_reply_ids = build_juustagram_player_discuss(
        commander_id, message_id, options, option_map, now, selections=selections)
    return build_juustagram_message_payload(template, state, text, message_time, player_discuss, op_reply_ids, now)


def ensure_juustagram_option(message_id: int, discuss_id: int, index: int):
    options, option_map = load_juustagram_discuss_options(message_id)
    if discuss_id not in option_map:
        raise Exception("missing discuss options")
    discuss_options = option_map[discuss_id]
    if index not in discuss_options:
        raise Exception("invalid discuss option")
    opt = discuss_options[index]
    if not opt.text:
        for candidate in options:
            if candidate.discuss_id == discuss_id and candidate.index == index:
                opt.text = candidate.text
                break
    return opt


def is_publishable_juustagram_template(template: dict) -> bool:
    if (template.get("message_persist") or "").strip():
        return True
    return bool((template.get("title") or "").strip())


def juus_group_from_model(group: dict) -> object:
    chat_groups_sorted = sorted(group.get("chat_groups", []), key=lambda cg: cg.get("chat_group_id", 0))
    chat_group_protos = []
    for cg in chat_groups_sorted:
        replies_sorted = sorted(cg.get("reply_list", []), key=lambda r: r.get("sequence", 0))
        kv_pairs = []
        for reply in replies_sorted:
            kv = protobuf.KEYVALUE_P11()
            kv.key = reply.get("key", 0)
            kv.value = reply.get("value", 0)
            kv_pairs.append(kv)
        chat_group = protobuf.JUUS_CHAT_GROUP()
        chat_group.id = cg.get("chat_group_id", 0)
        chat_group.op_time = cg.get("op_time", 0)
        chat_group.read_flag = cg.get("read_flag", 0)
        chat_group.reply_list.extend(kv_pairs)
        chat_group_protos.append(chat_group)

    juus = protobuf.JUUS_GROUP()
    juus.id = group.get("group_id", 0)
    juus.skin_id = group.get("skin_id", 0)
    juus.favorite = group.get("favorite", 0)
    juus.cur_chat_group = group.get("cur_chat_group", 0)
    juus.chat_group_list.extend(chat_group_protos)
    return juus


def build_juustagram_messages_for_ids(commander_id: int, ids: list) -> list:
    now = int(time.time())
    messages = []
    contentless = []
    ids = [int(m) for m in ids]

    # Batched preload: templates, npc templates and language rows are static
    # content fetched once per process; states + player discusses are one
    # query each per request. After the warm-up the whole feed build is
    # O(1) queries, not O(messages).
    preload_juustagram_templates(ids)
    states = get_or_create_juustagram_message_states(commander_id, ids, now)
    discusses = list_juustagram_player_discusses_for_ids(commander_id, ids)

    npc_ids: list = []
    lang_keys: list = []
    for mid in ids:
        template = _TEMPLATE_CACHE.get(mid)
        if template is None:
            # preload negative-cached it: no template row in the DB
            log_event("answer", "Juustagram",
                      f"uid={commander_id} mid={mid} no template row", LOG_LEVEL_ERROR)
            continue
        if not is_publishable_juustagram_template(template):
            # Placeholder shells ship in the official EN config itself
            # (ins_658..667: is_active=1 with past dates but no message/title/
            # picture/npc content and empty language rows). The client asks for
            # every is_active id on each login; skipping them here is expected,
            # not an error.
            contentless.append(mid)
            continue
        message_persist = template.get("message_persist") or ""
        if message_persist:
            lang_keys.append(message_persist)
            m = re.match(r"^ins_(\d+)$", message_persist)
            if m:
                lang_keys.append(m.group(1))
        for entry in _ensure_list(json.loads(template.get("npc_discuss_persist") or "[]")):
            npc_id = _resolve_npc_id(entry)
            if npc_id:
                npc_ids.append(npc_id)
        options, _ = load_juustagram_discuss_options(mid)
        for opt in options:
            if opt.npc_reply_id:
                npc_ids.append(opt.npc_reply_id)

    preload_juustagram_npc_templates(npc_ids)
    for npc_id in dict.fromkeys(npc_ids):
        tpl = _NPC_TEMPLATE_CACHE.get(npc_id)
        if tpl:
            lang_keys.append(tpl.get("message_persist") or "")
    preload_juustagram_languages(lang_keys)

    for mid in ids:
        template = _TEMPLATE_CACHE.get(mid)
        if template is None:
            stub = protobuf.INS_MESSAGE()
            stub.id = mid
            stub.time = now
            stub.text = ""
            stub.picture = ""
            stub.oalist_pic = ""
            stub.good = 0
            stub.is_good = 0
            stub.is_read = 0
            messages.append(stub)
            continue
        if not is_publishable_juustagram_template(template):
            continue
        try:
            msg = build_juustagram_message(
                commander_id, mid, now,
                state=states.get(mid),
                # [] (not None): None makes build_juustagram_player_discuss
                # fall back to a per-message SELECT for quiet messages.
                selections=discusses.get(mid) or [],
            )
            messages.append(msg)
        except Exception as e:
            log_event("answer", "Juustagram", f"uid={commander_id} mid={mid} failed 2: {e}", LOG_LEVEL_ERROR)
    if contentless:
        log_event("answer", "Juustagram",
                  f"uid={commander_id} skipped {len(contentless)} contentless ins templates: {contentless}",
                  LOG_LEVEL_DEBUG)
    return messages
