from __future__ import annotations

import datetime
import json
from typing import Optional

from src.protobuf import protobuf
from src.orm.config_entry import get_config_entry, list_config_entries
from src.orm import NewServerShopState, NewServerShopGoodsState
from src.answer.activity_constants import (
    ACTIVITY_TYPE_NEW_SERVER_SHOP,
    ACTIVITY_TYPE_BLACK_FRIDAY_SHOP,
    parse_activity_time_window,
)


class NewServerShopTemplateEntry:
    def __init__(self, data: dict):
        self.id = int(data.get("id", 0))
        self.goods = list(data.get("goods", []) or [])
        self.goods_purchase_limit = int(data.get("goods_purchase_limit", 0))
        self.goods_type = int(data.get("goods_type", 0))
        self.num = int(data.get("num", 0))
        self.type = int(data.get("type", 0))
        self.resource_category = int(data.get("resource_category", 0))
        self.resource_type = int(data.get("resource_type", 0))
        self.resource_num = int(data.get("resource_num", 0))


class NewServerShopActivity:
    def __init__(self, activity_id: int, start_time: int, stop_time: int,
                 goods: list[NewServerShopTemplateEntry],
                 goods_by_id: dict[int, NewServerShopTemplateEntry]):
        self.activity_id = activity_id
        self.start_time = start_time
        self.stop_time = stop_time
        self.goods = goods
        self.goods_by_id = goods_by_id


def _load_config_entry_as_dict(category: str, key: str) -> Optional[dict]:
    raw = get_config_entry(category, key)
    if raw is None:
        return None
    return raw if isinstance(raw, dict) else json.loads(raw) if isinstance(raw, str) else raw


def _parse_activity_config_ids(config_data) -> list[int]:
    ids = []
    if isinstance(config_data, list):
        for v in config_data:
            if isinstance(v, int):
                ids.append(v)
            elif isinstance(v, float):
                ids.append(int(v))
            elif isinstance(v, str):
                try:
                    ids.append(int(v))
                except ValueError:
                    pass
    return ids


def load_new_server_shop_template_entry(entry_id: int, activity_type: int) -> Optional[NewServerShopTemplateEntry]:
    categories = ["ShareCfg/newserver_shop_template.json"]
    if activity_type == ACTIVITY_TYPE_BLACK_FRIDAY_SHOP:
        categories = ["ShareCfg/blackfriday_shop_template.json", "ShareCfg/newserver_shop_template.json"]

    for category in categories:
        data = _load_config_entry_as_dict(category, str(entry_id))
        if data is not None:
            if data.get("id") is None:
                data["id"] = entry_id
            return NewServerShopTemplateEntry(data)
    else:
        for category in categories:
            entries = list_config_entries(category)
            if not entries:
                continue
            for entry in entries:
                raw = entry if isinstance(entry, dict) else json.loads(entry) if isinstance(entry, str) else entry
                if isinstance(raw, dict):
                    if raw.get("id") == entry_id:
                        return NewServerShopTemplateEntry(raw)
                    continue
                if isinstance(raw, list):
                    for item in raw:
                        if isinstance(item, dict) and item.get("id") == entry_id:
                            return NewServerShopTemplateEntry(item)
    return None


def load_new_server_shop_activity(act_id: int) -> tuple[Optional[NewServerShopActivity], bool]:
    from src.answer.activity_templates import load_activity_template
    template = load_activity_template(act_id)
    if template is None:
        return None, False
    if template.type != ACTIVITY_TYPE_NEW_SERVER_SHOP and template.type != ACTIVITY_TYPE_BLACK_FRIDAY_SHOP:
        return None, False

    now = datetime.datetime.now(datetime.timezone.utc)
    start_time, stop_time, active, _ = parse_activity_time_window(template.time, now)
    if not active:
        return None, False

    config_ids = _parse_activity_config_ids(template.config_data)
    if not config_ids:
        return None, False

    goods = []
    goods_by_id = {}
    for gid in config_ids:
        entry = load_new_server_shop_template_entry(gid, template.type)
        if entry is None:
            return None, False
        goods.append(entry)
        goods_by_id[entry.id] = entry

    return NewServerShopActivity(
        activity_id=act_id,
        start_time=start_time,
        stop_time=stop_time,
        goods=goods,
        goods_by_id=goods_by_id,
    ), True


def default_new_server_shop_state(commander_id: int, activity_id: int,
                                   goods: list[NewServerShopTemplateEntry]) -> NewServerShopState:
    return NewServerShopState(
        commander_id=commander_id,
        activity_id=activity_id,
        goods=[
            NewServerShopGoodsState(
                id=g.id,
                count=g.goods_purchase_limit,
                bought_record=[],
            )
            for g in goods
        ],
    )


def normalize_new_server_shop_state(state: NewServerShopState,
                                     goods: list[NewServerShopTemplateEntry]) -> bool:
    if state is None:
        return False
    changed = False
    index = {g.id: i for i, g in enumerate(state.goods)}
    for gs in state.goods:
        if gs.bought_record is None:
            gs.bought_record = []
            changed = True
    ordered = []
    for entry in goods:
        i = index.get(entry.id)
        if i is None:
            ordered.append(NewServerShopGoodsState(
                id=entry.id,
                count=entry.goods_purchase_limit,
                bought_record=[],
            ))
            changed = True
            continue
        current = state.goods[i]
        if current.count > entry.goods_purchase_limit:
            current.count = entry.goods_purchase_limit
            changed = True
        ordered.append(current)
    if len(ordered) != len(state.goods):
        changed = True
    state.goods = ordered
    return changed


def new_server_shop_response_goods(activity: NewServerShopActivity,
                                    state: NewServerShopState) -> list:
    state_by_id = {g.id: g for g in state.goods}
    result = []
    for entry in activity.goods:
        gs = state_by_id.get(entry.id)
        if gs is None:
            continue
        result.append(protobuf.ACT_GOODS_INFO(
            id=entry.id,
            count=gs.count,
            bought_record=gs.bought_record or [],
        ))
    return result


def unmarshal_new_server_shop_data(payload: bytes) -> Optional[dict]:
    try:
        data = json.loads(payload.decode("utf-8", errors="replace"))
        return data if isinstance(data, dict) else None
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None


def validate_new_server_shop_request(payload: dict) -> bool:
    act_id = payload.get("act_id", 0)
    return act_id > 0


def sorted_unique_uint32(values: list[int]) -> list[int]:
    seen = set()
    out = []
    for v in values:
        if v and v not in seen:
            seen.add(v)
            out.append(v)
    out.sort()
    return out
