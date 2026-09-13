import json
from datetime import datetime, timezone

from src.db.store import get_default_store
from src.orm.config_entry import (
    fetch_config_entries_data,
    fetch_config_entry_data,
    upsert_config_entry_data,
)
from src.orm.mini_game_shop import (
    create_mini_game_shop_state,
    get_mini_game_shop_good_count,
    get_mini_game_shop_state,
    increment_mini_game_shop_good_buy_count,
    list_mini_game_shop_goods,
    refresh_mini_game_shop_goods,
)
from src.protobuf import protobuf
from src.consts.drop_types import DROP_TYPE_RESOURCE, DROP_TYPE_ITEM, DROP_TYPE_VITEM

MINI_GAME_HUB_CATEGORY = "ShareCfg/mini_game_hub.json"
MINI_GAME_CATEGORY = "ShareCfg/mini_game.json"
MINI_GAME_HUB_STATE_CATEGORY = "Runtime/minigame_hub_state"
MINI_GAME_DATA_STATE_CATEGORY = "Runtime/minigame_data_state"
MINI_GAME_TELEMETRY_STATE_CATEGORY = "Runtime/minigame_telemetry_state"
GAME_ROOM_SHOP_CATEGORY = "ShareCfg/gameroom_shop_template.json"

MINI_GAME_SHOP_TICKET_RESOURCE_ID = 12
MINI_GAME_FRIEND_RANK_LIMIT = 100

MINI_GAME_OP_RESULT_SUCCESS = 0
MINI_GAME_OP_RESULT_FAILURE = 1

MINI_GAME_CMD_COMPLETE = 1
MINI_GAME_CMD_ULTIMATE = 2
MINI_GAME_CMD_SPECIAL_GAME = 3
MINI_GAME_CMD_HIGH_SCORE = 4
MINI_GAME_CMD_PLAY = 5
MINI_GAME_CMD_SUCCESS_DATA = 101

MAX_MINI_GAME_TELEMETRY_TIME = 86400


get_config_entry = fetch_config_entry_data
list_config_entries = fetch_config_entries_data
upsert_config_entry = upsert_config_entry_data


def get_mini_game_hub_config(hub_id: int):
    entry = get_config_entry(MINI_GAME_HUB_CATEGORY, str(hub_id))
    if entry is None:
        return None
    if entry.get("id", 0) == 0:
        entry["id"] = hub_id
    if entry.get("reward_display") is None:
        entry["reward_display"] = []
    return entry


def get_mini_game_config(game_id: int):
    entry = get_config_entry(MINI_GAME_CATEGORY, str(game_id))
    if entry is None:
        return None
    if entry.get("id", 0) == 0:
        entry["id"] = game_id
    return entry


def _hub_state_key(commander_id: int, hub_id: int) -> str:
    return f"{commander_id}:{hub_id}"


def _data_state_key(commander_id: int, game_id: int) -> str:
    return f"{commander_id}:{game_id}"


def get_or_create_mini_game_hub_state(commander_id: int, hub_config: dict) -> dict:
    hub_id = hub_config.get("id", 0)
    key = _hub_state_key(commander_id, hub_id)
    entry = get_config_entry(MINI_GAME_HUB_STATE_CATEGORY, key)
    if entry is None:
        state = {
            "commander_id": commander_id,
            "hub_id": hub_id,
            "available_cnt": hub_config.get("reborn_times", 0),
            "used_cnt": 0,
            "ultimate": 0,
            "max_scores": {},
        }
        save_mini_game_hub_state(state)
        return state
    if entry.get("max_scores") is None:
        entry["max_scores"] = {}
    entry["commander_id"] = commander_id
    entry["hub_id"] = hub_id
    return entry


def save_mini_game_hub_state(state: dict):
    payload = json.dumps(state, ensure_ascii=False)
    key = _hub_state_key(state["commander_id"], state["hub_id"])
    upsert_config_entry(MINI_GAME_HUB_STATE_CATEGORY, key, payload)


def get_or_create_mini_game_data_state(commander_id: int, game_id: int) -> dict:
    key = _data_state_key(commander_id, game_id)
    entry = get_config_entry(MINI_GAME_DATA_STATE_CATEGORY, key)
    if entry is None:
        state = {
            "commander_id": commander_id,
            "game_id": game_id,
            "datas": [],
            "kv_lists": [],
        }
        save_mini_game_data_state(state)
        return state
    if entry.get("datas") is None:
        entry["datas"] = []
    if entry.get("kv_lists") is None:
        entry["kv_lists"] = []
    entry["commander_id"] = commander_id
    entry["game_id"] = game_id
    return entry


def save_mini_game_data_state(state: dict):
    payload = json.dumps(state, ensure_ascii=False)
    key = _data_state_key(state["commander_id"], state["game_id"])
    upsert_config_entry(MINI_GAME_DATA_STATE_CATEGORY, key, payload)


def get_or_create_mini_game_telemetry_state(commander_id: int) -> dict:
    key = str(commander_id)
    entry = get_config_entry(MINI_GAME_TELEMETRY_STATE_CATEGORY, key)
    if entry is None:
        state = {"commander_id": commander_id, "game_times": {}}
        save_mini_game_telemetry_state(state)
        return state
    if entry.get("game_times") is None:
        entry["game_times"] = {}
    entry["commander_id"] = commander_id
    return entry


def save_mini_game_telemetry_state(state: dict):
    payload = json.dumps(state, ensure_ascii=False)
    key = str(state["commander_id"])
    upsert_config_entry(MINI_GAME_TELEMETRY_STATE_CATEGORY, key, payload)


def list_commander_mini_game_scores(game_id: int) -> list:
    states = list_config_entries(MINI_GAME_HUB_STATE_CATEGORY)
    best_by_commander = {}
    for state in states:
        if not isinstance(state, dict):
            continue
        max_scores = state.get("max_scores") or {}
        score_entry = max_scores.get(str(game_id)) or max_scores.get(game_id)
        if score_entry is None:
            continue
        score = score_entry.get("score", 0)
        if score == 0:
            continue
        cid = state.get("commander_id", 0)
        current = best_by_commander.get(cid)
        extra = score_entry.get("extra", 0)
        if current is None or score > current["score"] or (score == current["score"] and extra < current.get("extra", 0)):
            best_by_commander[cid] = {"score": score, "extra": extra}

    if not best_by_commander:
        return []

    commander_ids = list(best_by_commander.keys())
    store = get_default_store()
    rows = store.fetch(
        "SELECT commander_id, name, display_icon_id, display_skin_id, "
        "selected_icon_frame_id, selected_chat_frame_id, display_icon_theme_id "
        "FROM commanders "
        "WHERE commander_id = ANY($1::bigint[])",
        commander_ids,
    )
    results = []
    for row in rows:
        cid = row[0]
        se = best_by_commander.get(cid)
        if se is None or se["score"] == 0:
            continue
        results.append({
            "commander_id": cid,
            "name": row[1],
            "score": se["score"],
            "time_data": se["extra"],
            "display_icon": row[2],
            "display_skin": row[3],
            "icon_frame": row[4],
            "chat_frame": row[5],
            "icon_theme": row[6],
        })

    results.sort(key=lambda r: (-r["score"], r["time_data"], r["commander_id"]))
    if len(results) > MINI_GAME_FRIEND_RANK_LIMIT:
        results = results[:MINI_GAME_FRIEND_RANK_LIMIT]
    return results


def grant_mini_game_drops(commander_id: int, award_list: list):
    store = get_default_store()
    for award in award_list:
        drop_type = award.get("type", 0) if isinstance(award, dict) else (award.type if hasattr(award, "type") else 0)
        drop_id = award.get("id", 0) if isinstance(award, dict) else (award.id if hasattr(award, "id") else 0)
        drop_number = award.get("number", 0) if isinstance(award, dict) else (award.number if hasattr(award, "number") else 0)
        if drop_type == DROP_TYPE_RESOURCE:
            from src.orm.resource import add_resource
            add_resource(commander_id, drop_id, drop_number)
        elif drop_type in (DROP_TYPE_ITEM, DROP_TYPE_VITEM):
            from src.orm.item import add_item
            add_item(commander_id, drop_id, drop_number)


def apply_mini_game_command(hub_config: dict, hub_state: dict, cmd: int, args: list) -> tuple:
    awards = []
    if cmd == MINI_GAME_CMD_COMPLETE:
        if len(args) < 3 or args[2] == 0:
            return None, None, False
        if hub_state.get("available_cnt", 0) == 0:
            return None, None, False
        hub_state["available_cnt"] = hub_state.get("available_cnt", 0) - 1
        hub_state["used_cnt"] = hub_state.get("used_cnt", 0) + 1
        reward_need = hub_config.get("reward_need", 0)
        if reward_need > 0 and hub_state.get("used_cnt", 0) >= reward_need and hub_state.get("ultimate", 0) == 0:
            hub_state["ultimate"] = 1
            drop = mini_game_reward_drop(hub_config.get("reward_display", []))
            if drop is not None:
                awards.append(drop)
        data_state = get_or_create_mini_game_data_state(hub_state["commander_id"], args[2])
        data_state["datas"] = list(args)
        return data_state, awards, True
    elif cmd == MINI_GAME_CMD_PLAY:
        if len(args) < 1 or args[0] == 0:
            return None, None, False
        if hub_state.get("available_cnt", 0) == 0:
            return None, None, False
        hub_state["available_cnt"] = hub_state.get("available_cnt", 0) - 1
        hub_state["used_cnt"] = hub_state.get("used_cnt", 0) + 1
        data_state = get_or_create_mini_game_data_state(hub_state["commander_id"], args[0])
        data_state["datas"] = list(args)
        return data_state, awards, True
    elif cmd in (MINI_GAME_CMD_SPECIAL_GAME, MINI_GAME_CMD_SUCCESS_DATA):
        if len(args) < 1 or args[0] == 0:
            return None, None, False
        data_state = get_or_create_mini_game_data_state(hub_state["commander_id"], args[0])
        if len(args) > 1:
            data_state["datas"] = list(args[1:])
        return data_state, awards, True
    elif cmd == MINI_GAME_CMD_HIGH_SCORE:
        if len(args) < 2 or args[0] == 0:
            return None, None, False
        extra = args[2] if len(args) > 2 else 0
        max_scores = hub_state.get("max_scores", {})
        key = str(args[0])
        current = max_scores.get(key, {"score": 0, "extra": 0})
        if args[1] > current["score"] or (args[1] == current["score"] and (current.get("extra", 0) == 0 or extra < current.get("extra", 0))):
            max_scores[key] = {"score": args[1], "extra": extra}
        hub_state["max_scores"] = max_scores
        return None, awards, True
    elif cmd == MINI_GAME_CMD_ULTIMATE:
        hub_state["ultimate"] = 1
        return None, awards, True
    return None, None, False


def mini_game_reward_drop(reward_display: list):
    if len(reward_display) < 3 or reward_display[2] == 0:
        return None
    return {"type": reward_display[0], "id": reward_display[1], "number": reward_display[2]}


def build_mini_game_hub_proto(hub_state: dict):
    hub = protobuf.MINIGAMEHUB()
    hub.id = hub_state.get("hub_id", 0)
    hub.available_cnt = hub_state.get("available_cnt", 0)
    hub.used_cnt = hub_state.get("used_cnt", 0)
    hub.ultimate = hub_state.get("ultimate", 0)
    max_scores = hub_state.get("max_scores", {})
    keys = sorted(int(k) for k in max_scores.keys())
    for key in keys:
        entry = max_scores.get(str(key)) or max_scores.get(key, {})
        kv = protobuf.KVDATA2()
        kv.key = key
        kv.value1 = entry.get("score", 0)
        kv.value2 = entry.get("extra", 0)
        hub.maxscores.append(kv)
    return hub


def build_mini_game_data_proto(data_state: dict):
    data = protobuf.MINIGAMEDATA()
    data.id = data_state.get("game_id", 0)
    data.datas.extend(data_state.get("datas", []))
    for kv_list in data_state.get("kv_lists", []):
        lst = protobuf.KEYVALUELIST_P26()
        lst.key = kv_list.get("key", 0)
        for value in kv_list.get("values", []):
            v = protobuf.KEYVALUE_P26()
            v.key = value.get("key", 0)
            v.value = value.get("value", 0)
            v.value2 = value.get("value2", 0)
            lst.value_list.append(v)
        data.date1_key_value_list.append(lst)
    return data


def run_mini_game_operation(commander_id: int, hub_id: int, cmd: int, args: list) -> tuple:
    if commander_id == 0 or hub_id == 0 or cmd == 0:
        return MINI_GAME_OP_RESULT_FAILURE, None, None, []

    hub_config = get_mini_game_hub_config(hub_id)
    if hub_config is None:
        return MINI_GAME_OP_RESULT_FAILURE, None, None, []

    hub_state = get_or_create_mini_game_hub_state(commander_id, hub_config)

    data_state, awards, ok = apply_mini_game_command(hub_config, hub_state, cmd, args)
    if not ok:
        return MINI_GAME_OP_RESULT_FAILURE, None, None, []

    save_mini_game_hub_state(hub_state)
    if data_state is not None:
        save_mini_game_data_state(data_state)

    grant_mini_game_drops(commander_id, awards)

    response_hub = build_mini_game_hub_proto(hub_state)
    response_data = build_mini_game_data_proto(data_state) if data_state is not None else None
    return MINI_GAME_OP_RESULT_SUCCESS, response_hub, response_data, awards


def _time_from_config(parts: list):
    if not parts or len(parts) < 2:
        return None
    date_parts = parts[0]
    time_parts = parts[1]
    if not isinstance(date_parts, list) or not isinstance(time_parts, list):
        return None
    if len(date_parts) < 3 or len(time_parts) < 3:
        return None
    if date_parts[0] == 0 and date_parts[1] == 0 and date_parts[2] == 0:
        return None
    return datetime(date_parts[0], date_parts[1], date_parts[2],
                    time_parts[0], time_parts[1], time_parts[2], 0, tzinfo=timezone.utc)


def is_within_time(now_ts: int, ranges: list) -> bool:
    if not ranges or len(ranges) < 2:
        return True
    now = datetime.fromtimestamp(now_ts, tz=timezone.utc)
    start = _time_from_config(ranges[0])
    end = _time_from_config(ranges[1])
    if start is not None and end is not None:
        return not (now < start) and not (now > end)
    return False


def next_daily_reset(now_ts: int) -> int:
    from src.shopreset.framework import daily_window
    now = datetime.fromtimestamp(now_ts, tz=timezone.utc)
    return int(daily_window(now).end.timestamp())


def load_mini_game_shop_config(now_ts: int):
    entries = list_config_entries(GAME_ROOM_SHOP_CATEGORY)
    goods = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        if entry.get("id", 0) == 0:
            continue
        if not is_within_time(now_ts, entry.get("time", [])):
            continue
        goods.append(entry)
    goods.sort(key=lambda g: (g.get("order", 0), g.get("id", 0)))
    return {"goods": goods}





def build_mini_game_shop_goods_proto(goods: list) -> list:
    result = []
    for good in goods:
        g = protobuf.GOODS_INFO_P26()
        g.id = good.get("goods_id", 0)
        g.count = good.get("count", 0)
        result.append(g)
    return result


def build_goods(commander_id: int, shop_config: dict) -> list:
    if shop_config is None:
        return []
    goods = []
    for entry in shop_config.get("goods", []):
        # `count` is the buy count (already purchased). The client computes the
        # remaining stock as (limit - count), so a fresh shop starts at 0.
        goods.append({"commander_id": commander_id, "goods_id": entry.get("id", 0), "count": 0})
    return goods


def ensure_mini_game_shop_state(commander_id: int, now_ts: int, shop_config: dict) -> tuple:
    state = get_mini_game_shop_state(commander_id)
    if state is None:
        next_time = next_daily_reset(now_ts)
        create_mini_game_shop_state(commander_id, next_time)
        goods = build_goods(commander_id, shop_config)
        refresh_mini_game_shop_goods(commander_id, goods, next_time)
        return {"commander_id": commander_id, "next_refresh_time": next_time}, goods
    goods = list_mini_game_shop_goods(commander_id)
    return state, goods


def refresh_if_needed(commander_id: int, now_ts: int, shop_config: dict) -> tuple:
    state, goods = ensure_mini_game_shop_state(commander_id, now_ts, shop_config)
    cfg_ids = {int(g.get("id", 0)) for g in (shop_config or {}).get("goods", [])
               if g.get("id", 0)}
    existing_ids = {int(g["goods_id"]) for g in goods}
    # Heal anything a legitimate list can never be: more rows than the config
    # defines, or rows whose goods are not in the current config (stale list
    # from an earlier window). Never heals when the rows are merely a subset,
    # so opening the shop mid-window does not reset purchase counts.
    stale = bool(cfg_ids) and (len(goods) > len(cfg_ids) or not existing_ids <= cfg_ids)
    if now_ts >= state.get("next_refresh_time", 0) or len(goods) == 0 or stale:
        next_time = next_daily_reset(now_ts)
        goods = build_goods(commander_id, shop_config)
        refresh_mini_game_shop_goods(commander_id, goods, next_time)
        state = get_mini_game_shop_state(commander_id)
    return state, goods


def force_refresh(commander_id: int, now_ts: int, shop_config: dict) -> tuple:
    ensure_mini_game_shop_state(commander_id, now_ts, shop_config)
    next_time = next_daily_reset(now_ts)
    goods = build_goods(commander_id, shop_config)
    refresh_mini_game_shop_goods(commander_id, goods, next_time)
    state = get_mini_game_shop_state(commander_id)
    return state, goods


def find_good(shop_config: dict, goods_id: int):
    for good in shop_config.get("goods", []):
        if good.get("id", 0) == goods_id:
            return good
    return None


def resolve_purchase_rewards(entry: dict, selected: list) -> tuple:
    if not selected:
        return None, 0, "invalid"
    allowed = set()
    for gid in entry.get("goods", []):
        if gid == 0:
            continue
        allowed.add(gid)
    reward_units = {}
    total_units = 0
    for pick in selected:
        pick_id = pick.get("id", 0)
        pick_num = pick.get("num", 0)
        if pick_id == 0 or pick_num == 0:
            return None, 0, "invalid"
        if allowed and pick_id not in allowed:
            return None, 0, "invalid"
        total_units += pick_num
        reward_units[pick_id] = reward_units.get(pick_id, 0) + pick_num
    if total_units == 0:
        return None, 0, "invalid"
    reward_multiplier = entry.get("num", 1) or 1
    rewards = []
    for rid in sorted(reward_units.keys()):
        rewards.append({
            "type": entry.get("drop_type", 0),
            "id": rid,
            "number": reward_units[rid] * reward_multiplier,
        })
    return rewards, total_units, None


def purchase(commander_id: int, goods_id: int, selected: list, now_ts: int, shop_config: dict) -> tuple:
    if commander_id == 0 or goods_id == 0 or shop_config is None:
        return None, "invalid"

    refresh_if_needed(commander_id, now_ts, shop_config)

    entry = find_good(shop_config, goods_id)
    if entry is None:
        return None, "invalid"

    rewards, total_units, err = resolve_purchase_rewards(entry, selected)
    if err is not None:
        return None, err

    total_cost = entry.get("price", 0) * total_units
    buy_count = get_mini_game_shop_good_count(commander_id, goods_id)
    if buy_count is None:
        return None, "invalid"

    limit = entry.get("goods_purchase_limit", 1) or 1
    remaining = limit - buy_count
    if remaining < total_units:
        return None, "sold_out"

    from src.orm.resource import has_enough_resource, consume_resource
    if not has_enough_resource(commander_id, MINI_GAME_SHOP_TICKET_RESOURCE_ID, total_cost):
        return None, "insufficient_tickets"

    if not consume_resource(commander_id, MINI_GAME_SHOP_TICKET_RESOURCE_ID, total_cost):
        return None, "insufficient_tickets"

    increment_mini_game_shop_good_buy_count(commander_id, goods_id, total_units, limit)

    for reward in rewards:
        rtype = reward["type"]
        rid = reward["id"]
        rnum = reward["number"]
        if rtype == DROP_TYPE_RESOURCE:
            from src.orm.resource import add_resource
            add_resource(commander_id, rid, rnum)
        elif rtype in (DROP_TYPE_ITEM, DROP_TYPE_VITEM):
            from src.orm.item import add_item
            add_item(commander_id, rid, rnum)

    return rewards, None
