import asyncio
from typing import Optional

from sqlalchemy import text

from src.connection.client import Client
from src.db.session import get_sync_session
from src.protobuf import protobuf
from src.orm.config_entry import list_config_entries
from src.answer.remaster_config import load_gameset_value
from src.answer.love_letter_handlers import (
    _item_group_key,
    _group_year_key,
    _load_love_letter_config_bundle,
)
from src.answer.meta.helpers import (
    accumulate_drop,
    drop_map_to_sorted_list,
    apply_love_letter_drops_tx,
)
from src.consts.drop_types import DROP_TYPE_LOVE_LETTER
from src.orm.mail import fetch_mail_titles


MAIL_CHUNK_RESULT_SUCCESS = 0
MAIL_CHUNK_RESULT_FAILED = 1

MAIL_STOREROOM_GOLD_RESOURCE = 1
MAIL_STOREROOM_OIL_RESOURCE = 2
MAIL_STOREROOM_GEM_RESOURCE = 4
MAIL_STOREROOM_STORED_GOLD = 16
MAIL_STOREROOM_STORED_OIL = 17

MAIL_STOREROOM_CONFIG_CATEGORY = "ShareCfg/mail_storeroom.json"

LOVE_LETTER_REPAIR_INVALID = 6
LOVE_LETTER_REPAIR_MISSING_ITEM = 7
LOVE_LETTER_REPAIR_INVENTORY_CAP = 40


def _load_mail_storeroom_config_by_level() -> dict:
    configs = {}
    for entry in list_config_entries(MAIL_STOREROOM_CONFIG_CATEGORY):
        data = entry
        if not isinstance(data, dict):
            continue
        level = data.get("level", 0)
        if level == 0:
            continue
        configs[level] = data
    return configs


def _resolve_mail_storeroom_upgrade_cost(arg: int, cfg: dict) -> tuple:
    if arg == MAIL_STOREROOM_GOLD_RESOURCE:
        cost = cfg.get("upgrade_gold", 0)
        if cost == 0:
            return 0, 0, False
        return MAIL_STOREROOM_GOLD_RESOURCE, cost, True
    if arg == MAIL_STOREROOM_GEM_RESOURCE:
        cost = cfg.get("upgrade_gem", 0)
        if cost == 0:
            return 0, 0, False
        return MAIL_STOREROOM_GEM_RESOURCE, cost, True
    return 0, 0, False


def _load_mail_storeroom_withdraw_caps() -> tuple:
    max_oil = load_gameset_value("max_oil") or 0
    max_gold = load_gameset_value("max_gold") or 0
    return max_oil, max_gold


def _mail_title_with_sender(mail: dict) -> str:
    full_title = mail.get("title", "")
    custom_sender = mail.get("custom_sender")
    if custom_sender:
        full_title += "||" + str(custom_sender)
    return full_title


def handle_extend_mail_storeroom_capacity(buffer: bytes, client: Client) -> tuple[int, int, Optional[Exception]]:
    try:
        payload = protobuf.CS_30010()
        payload.ParseFromString(buffer)
    except Exception as e:
        return 0, 30011, e

    response = protobuf.SC_30011(result=MAIL_CHUNK_RESULT_FAILED)
    c = client.commander
    if c is None:
        asyncio.create_task(client.send_message(30011, response))
        return 0, 30011, None

    configs = _load_mail_storeroom_config_by_level()
    current_level = c.mail_storeroom_lv or 1
    current_cfg = configs.get(current_level)
    if current_cfg is None:
        asyncio.create_task(client.send_message(30011, response))
        return 0, 30011, None
    if current_level + 1 not in configs:
        asyncio.create_task(client.send_message(30011, response))
        return 0, 30011, None

    resource_id, cost, ok = _resolve_mail_storeroom_upgrade_cost(payload.arg, current_cfg)
    if not ok or not c.has_enough_resource(resource_id, cost):
        asyncio.create_task(client.send_message(30011, response))
        return 0, 30011, None

    old_level = c.mail_storeroom_lv
    try:
        c.consume_resource(resource_id, cost)
        with get_sync_session() as session:
            session.execute(
                text("UPDATE commanders SET mail_storeroom_lv = :lv WHERE commander_id = :cid"),
                {"lv": current_level + 1, "cid": c.commander_id},
            )
            session.commit()
        c.mail_storeroom_lv = current_level + 1
    except Exception:
        c.mail_storeroom_lv = old_level
        c.load()
        asyncio.create_task(client.send_message(30011, response))
        return 0, 30011, None

    response.result = MAIL_CHUNK_RESULT_SUCCESS
    asyncio.create_task(client.send_message(30011, response))
    return 0, 30011, None


def handle_withdraw_mail_storeroom_resources(buffer: bytes, client: Client) -> tuple[int, int, Optional[Exception]]:
    try:
        payload = protobuf.CS_30012()
        payload.ParseFromString(buffer)
    except Exception as e:
        return 0, 30012, e

    response = protobuf.SC_30013(result=MAIL_CHUNK_RESULT_FAILED)
    c = client.commander
    if c is None:
        asyncio.create_task(client.send_message(30013, response))
        return 0, 30013, None

    oil = payload.oil
    gold = payload.gold
    if oil == 0 and gold == 0:
        asyncio.create_task(client.send_message(30013, response))
        return 0, 30013, None

    stored_oil = MAIL_STOREROOM_STORED_OIL
    stored_gold = MAIL_STOREROOM_STORED_GOLD

    if (oil > 0 and not c.has_enough_resource(stored_oil, oil)) or \
       (gold > 0 and not c.has_enough_resource(stored_gold, gold)):
        asyncio.create_task(client.send_message(30013, response))
        return 0, 30013, None

    max_oil, max_gold = _load_mail_storeroom_withdraw_caps()
    if max_oil > 0 and c.get_resource_count(MAIL_STOREROOM_OIL_RESOURCE) + oil > max_oil:
        asyncio.create_task(client.send_message(30013, response))
        return 0, 30013, None
    if max_gold > 0 and c.get_resource_count(MAIL_STOREROOM_GOLD_RESOURCE) + gold > max_gold:
        asyncio.create_task(client.send_message(30013, response))
        return 0, 30013, None

    try:
        if oil > 0:
            c.consume_resource(stored_oil, oil)
            c.add_resource(MAIL_STOREROOM_OIL_RESOURCE, oil)
        if gold > 0:
            c.consume_resource(stored_gold, gold)
            c.add_resource(MAIL_STOREROOM_GOLD_RESOURCE, gold)
    except Exception:
        c.load()
        asyncio.create_task(client.send_message(30013, response))
        return 0, 30013, None

    response.result = MAIL_CHUNK_RESULT_SUCCESS
    asyncio.create_task(client.send_message(30013, response))
    return 0, 30013, None


def handle_get_mail_title_list(buffer: bytes, client: Client) -> tuple[int, int, Optional[Exception]]:
    try:
        payload = protobuf.CS_30014()
        payload.ParseFromString(buffer)
    except Exception as e:
        return 0, 30015, e

    response = protobuf.SC_30015()
    c = client.commander
    if c is None:
        asyncio.create_task(client.send_message(30015, response))
        return 0, 30015, None

    mail_ids = list(payload.id_list)
    if not mail_ids:
        asyncio.create_task(client.send_message(30015, response))
        return 0, 30015, None

    rows = fetch_mail_titles(c.commander_id, mail_ids)
    for row in rows:
        title = protobuf.MAIL_TITLE(
            id=row["id"],
            title=_mail_title_with_sender(row),
        )
        response.mail_title_list.append(title)

    asyncio.create_task(client.send_message(30015, response))
    return 0, 30015, None


def handle_check_love_letter_item_mail(buffer: bytes, client: Client) -> tuple[int, int, Optional[Exception]]:
    try:
        payload = protobuf.CS_30016()
        payload.ParseFromString(buffer)
    except Exception as e:
        return 0, 30017, e

    response = protobuf.SC_30017()
    bundle = _load_love_letter_config_bundle()
    key = _item_group_key(payload.item_id, payload.groupid)
    year_map = bundle.item_group_to_years.get(key, {})
    if not year_map:
        asyncio.create_task(client.send_message(30017, response))
        return 0, 30017, None

    sorted_years = sorted(year_map.keys())
    years_list = [0] + sorted_years
    response.years.extend(years_list)
    asyncio.create_task(client.send_message(30017, response))
    return 0, 30017, None


def _resolve_love_letter_repair_target(bundle, item_id: int, group_id: int, year: int) -> tuple:
    candidates = {}
    if group_id > 0:
        year_map = bundle.item_group_to_years.get(_item_group_key(item_id, group_id), {})
        for cyear, cgroup in year_map.items():
            candidates[cyear] = cgroup
    else:
        prefix = f"{item_id}_"
        for key, year_map in bundle.item_group_to_years.items():
            if not key.startswith(prefix):
                continue
            for cyear, cgroup in year_map.items():
                existing = candidates.get(cyear)
                if existing is not None and existing != cgroup:
                    candidates[cyear] = 0
                else:
                    candidates[cyear] = cgroup
    if not candidates:
        return 0, 0, 0, False

    if year > 0:
        canonical_group = candidates.get(year, 0)
        if canonical_group == 0:
            return 0, 0, 0, False
        letter_id = bundle.letter_by_group_year.get(_group_year_key(canonical_group, year), 0)
        if letter_id == 0:
            return 0, 0, 0, False
        return year, canonical_group, letter_id, True

    selected_year = 0
    selected_group = 0
    for cyear, cgroup in candidates.items():
        if cgroup == 0:
            continue
        if bundle.letter_by_group_year.get(_group_year_key(cgroup, cyear), 0) == 0:
            continue
        if selected_year != 0:
            return 0, 0, 0, False
        selected_year = cyear
        selected_group = cgroup
    if selected_year == 0:
        return 0, 0, 0, False
    letter_id = bundle.letter_by_group_year.get(_group_year_key(selected_group, selected_year), 0)
    if letter_id == 0:
        return 0, 0, 0, False
    return selected_year, selected_group, letter_id, True


def _resolve_love_letter_repair_failure(err: Exception) -> int:
    if err is None:
        return MAIL_CHUNK_RESULT_SUCCESS
    msg = str(err).lower()
    if "not enough items" in msg or "not enough item" in msg:
        return LOVE_LETTER_REPAIR_MISSING_ITEM
    return LOVE_LETTER_REPAIR_INVENTORY_CAP


def handle_repair_love_letter_item_mail(buffer: bytes, client: Client) -> tuple[int, int, Optional[Exception]]:
    try:
        payload = protobuf.CS_30018()
        payload.ParseFromString(buffer)
    except Exception as e:
        return 0, 30019, e

    response = protobuf.SC_30019(ret=LOVE_LETTER_REPAIR_INVALID)
    c = client.commander
    if c is None:
        asyncio.create_task(client.send_message(30019, response))
        return 0, 30019, None

    bundle = _load_love_letter_config_bundle()
    _, _, letter_id, ok = _resolve_love_letter_repair_target(
        bundle, payload.item_id, payload.groupid, payload.year,
    )
    if not ok:
        asyncio.create_task(client.send_message(30019, response))
        return 0, 30019, None

    drop_map = {}
    accumulate_drop(drop_map, DROP_TYPE_LOVE_LETTER, letter_id, 1)

    err = None
    try:
        c.consume_item(payload.item_id, 1)
        apply_love_letter_drops_tx(client, drop_map)
    except Exception as e:
        err = e

    if err is not None:
        response.ret = _resolve_love_letter_repair_failure(err)
        c.load()
        asyncio.create_task(client.send_message(30019, response))
        return 0, 30019, None

    response.ret = MAIL_CHUNK_RESULT_SUCCESS
    response.drop_list.extend(drop_map_to_sorted_list(drop_map))
    asyncio.create_task(client.send_message(30019, response))
    return 0, 30019, None
