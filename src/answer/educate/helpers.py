import json
import re
from typing import Any, Optional

from src.db.store import get_default_store
from src.orm.config_entry import afetch_config_entries_data, afetch_config_entry_data
from src.protobuf import protobuf

# ── Constants ──

educateResultOK = 0
educateResultFailed = 1

educateFlagHomeEventBase = 270140000
educateFlagSpecialEventBase = 270270000
educateFlagDiscountBase = 270271000
educateFlagTargetAwardBase = 270350000

educateUnsupportedTypeResult = 1
educatePlanValidationFailedResult = 1

legacyEducateResultOK = 0
legacyEducateResultFailure = 1

childSiteCategory = "ShareCfg/child_site.json"
childSiteOptionCategory = "ShareCfg/child_site_option.json"
childSiteOptionBranchCategory = "ShareCfg/child_site_option_branch.json"
childTaskCategory = "ShareCfg/child_task.json"
childTargetSetCategory = "ShareCfg/child_target_set.json"
childDataCategory = "ShareCfg/child_data.json"
childEndingCategory = "ShareCfg/child_ending.json"
secretarySpecialShipCategory = "ShareCfg/secretary_special_ship.json"

educateLegacyCategory = "ShareCfg/child_site.json"

legacyEducateCallNameMin = 4
legacyEducateCallNameMax = 14

# ── Config structs ──

class educateSpecialEventConfig:
    def __init__(self, id=0, show=0, type=0, result=0, drop_display=None):
        self.id = id
        self.show = show
        self.type = type
        self.result = result
        self.drop_display = drop_display or []

class educateEventConfig:
    def __init__(self, id=0):
        self.id = id

class educateShopConfig:
    def __init__(self, id=0, goods_num=0, goods_pool=None, goods_refresh_time=0):
        self.id = id
        self.goods_num = goods_num
        self.goods_pool = goods_pool or []
        self.goods_refresh_time = goods_refresh_time

class educateShopTemplateConfig:
    def __init__(self, id=0, item_id=0, resource=0, resource_num=0, buy_num=0):
        self.id = id
        self.item_id = item_id
        self.resource = resource
        self.resource_num = resource_num
        self.buy_num = buy_num or 1

class educateTargetSetConfig:
    def __init__(self, id=0, stage=0, ids=None, target_progress=0, drop_display=None):
        self.id = id
        self.stage = stage
        self.ids = ids or []
        self.target_progress = target_progress
        self.drop_display = drop_display or []

class educateTaskConfig:
    def __init__(self, id=0, task_target_progress=0):
        self.id = id
        self.task_target_progress = task_target_progress

class educateSiteConfig:
    def __init__(self, id=0, option_random=None):
        self.id = id
        self.option_random = option_random or []

class legacyChildSite:
    def __init__(self, id=0, option=None, option_random=None):
        self.id = id
        self.option = option or []
        self.option_random = option_random or []

class legacyChildSiteOption:
    def __init__(self, id=0, type=0, result=None, cost=None, count_limit=None):
        self.id = id
        self.type = type
        self.result = result or []
        self.cost = cost or []
        self.count_limit = count_limit or []

class legacyChildTask:
    def __init__(self, id=0, type_1=0, arg=0, drop_display=None):
        self.id = id
        self.type_1 = type_1
        self.arg = arg
        self.drop_display = drop_display or []

class legacyChildTargetSet:
    def __init__(self, id=0):
        self.id = id

class legacyChildData:
    def __init__(self, id=0, attr_2_list=None, attr_2_add=0, favor_level=0):
        self.id = id
        self.attr_2_list = attr_2_list or []
        self.attr_2_add = attr_2_add
        self.favor_level = favor_level

class legacySecretarySpecialShip:
    def __init__(self, id=0):
        self.id = id

class EducateShopGoodsState:
    def __init__(self, id=0, num=0):
        self.id = id
        self.num = num

class EducateShopState:
    def __init__(self, commander_id=0, shop_id=0, refresh_key=0, goods=None):
        self.commander_id = commander_id
        self.shop_id = shop_id
        self.refresh_key = refresh_key
        self.goods = goods or []

# ── Helpers ──

def bool_to_uint32(value: bool) -> int:
    return 1 if value else 0

def append_unique_uint32(values: list[int], value: int) -> list[int]:
    if value not in values:
        values.append(value)
    return values

def contains_uint32(values: list[int], target: int) -> bool:
    return target in values

def parse_any_uint32(value: Any) -> tuple:
    if isinstance(value, (int, float)):
        return max(0, int(value)), True
    return 0, False

def educate_flag_id(base: int, id: int) -> int:
    return base + id

# ── Config loaders ──

async def _fetch_config_list(category: str) -> list[dict]:
    # decode_json_value already drops NULL/blank/"null" payloads -> None.
    return [d for d in await afetch_config_entries_data(category) if d is not None]

async def _fetch_config_entry(category: str, key: str):
    # config_entries.data is JSONB on PG (auto-parsed) but TEXT on SQLite;
    # src.orm.config_entry normalises both.
    return await afetch_config_entry_data(category, key)

def _parse_entries(data_list: list[dict], cls) -> dict:
    result = {}
    for data in data_list:
        if isinstance(data, list):
            for item in data:
                if isinstance(item, dict) and item.get("id", 0):
                    obj = cls(**item)
                    result[obj.id] = obj
        elif isinstance(data, dict):
            if data.get("id", 0):
                obj = cls(**data)
                result[obj.id] = obj
    return result

async def load_educate_special_events() -> dict:
    data = await _fetch_config_list("ShareCfg/child_event_special.json")
    return _parse_entries(data, educateSpecialEventConfig)

async def load_educate_events() -> dict:
    data = await _fetch_config_list("ShareCfg/child_event.json")
    return _parse_entries(data, educateEventConfig)

async def load_educate_shop_configs() -> tuple:
    shops_data = await _fetch_config_list("ShareCfg/child_shop.json")
    templates_data = await _fetch_config_list("ShareCfg/child_shop_template.json")
    shops = _parse_entries(shops_data, educateShopConfig)
    templates = _parse_entries(templates_data, educateShopTemplateConfig)
    for t in templates.values():
        if t.buy_num == 0:
            t.buy_num = 1
    return shops, templates

async def load_educate_target_and_task_configs() -> tuple:
    targets_data = await _fetch_config_list("ShareCfg/child_target_set.json")
    tasks_data = await _fetch_config_list("ShareCfg/child_task.json")
    targets = _parse_entries(targets_data, educateTargetSetConfig)
    tasks = _parse_entries(tasks_data, educateTaskConfig)
    return targets, tasks

async def load_educate_site_options() -> list:
    data = await _fetch_config_list(educateLegacyCategory)
    if not data:
        return default_educate_site_options()
    options = []
    for entry in data:
        if isinstance(entry, list):
            for item in entry:
                cfg = educateSiteConfig(**item) if isinstance(item, dict) else None
                if cfg and cfg.id and cfg.option_random:
                    option_ids = _first_option_ids_from_buckets(cfg.option_random)
                    if option_ids:
                        options.append(protobuf.CHILD_SITE_OPTION(site_id=cfg.id, option_ids=option_ids))
        elif isinstance(entry, dict):
            cfg = educateSiteConfig(**entry)
            if cfg.id and cfg.option_random:
                option_ids = _first_option_ids_from_buckets(cfg.option_random)
                if option_ids:
                    options.append(protobuf.CHILD_SITE_OPTION(site_id=cfg.id, option_ids=option_ids))
    options.sort(key=lambda o: o.site_id)
    return options or default_educate_site_options()

def default_educate_site_options():
    return [
        protobuf.CHILD_SITE_OPTION(site_id=131, option_ids=[1314, 13142]),
        protobuf.CHILD_SITE_OPTION(site_id=141, option_ids=[1414, 14142]),
    ]

def _first_option_ids_from_buckets(buckets: list) -> list[int]:
    ids = []
    for bucket in buckets:
        if not bucket or not bucket[0]:
            continue
        option_id, ok = parse_any_uint32(bucket[0][0] if isinstance(bucket[0], list) else bucket[0])
        if ok and option_id:
            ids.append(option_id)
    return ids

# ── Legacy config loaders ──

async def load_legacy_config_by_id(category: str, tid: int) -> tuple:
    data = await _fetch_config_entry(category, tid)
    if data is None:
        return None, False
    return data, True

async def legacy_config_exists(category: str, tid: int) -> bool:
    _, exists = await load_legacy_config_by_id(category, tid)
    return exists

async def load_legacy_child_data() -> tuple:
    data = await _fetch_config_entry(childDataCategory, 1)
    if data is None:
        return None, False
    return legacyChildData(**data), True

async def _load_config_obj(category: str, tid: int, cls):
    data = await _fetch_config_entry(category, tid)
    if data is None:
        return None, False
    return cls(**data), True

def legacy_site_has_option(site: dict, option_id: int) -> bool:
    if site is None:
        return False
    option_list = site.get("option", [])
    if isinstance(option_list, list) and option_id in option_list:
        return True
    for row in site.get("option_random", []):
        try:
            groups = json.loads(json.dumps(row)) if not isinstance(row, list) else row
        except Exception:
            continue
        if isinstance(groups, list):
            for group in groups:
                if isinstance(group, list) and len(group) > 0:
                    values = group[0]
                    if isinstance(values, list) and len(values) > 0:
                        candidate, ok = parse_any_uint32(values[0])
                        if ok and candidate == option_id:
                            return True
    return False

# ── Educate state helpers ──

async def has_educate_flag(commander_id: int, flag_id: int) -> bool:
    store = get_default_store()
    row = await store.afetchrow(
        "SELECT 1 FROM commander_common_flags WHERE commander_id = $1 AND flag_id = $2 LIMIT 1",
        commander_id, flag_id,
    )
    return row is not None

async def set_educate_flag(commander_id: int, flag_id: int):
    if await has_educate_flag(commander_id, flag_id):
        return
    store = get_default_store()
    await store.aexecute(
        "INSERT INTO commander_common_flags (commander_id, flag_id) VALUES ($1, $2)",
        commander_id, flag_id,
    )

def to_child_drop(drop: list) -> Optional[protobuf.CHILD_DROP]:
    if len(drop) < 3:
        return None
    return protobuf.CHILD_DROP(type=drop[0], id=drop[1], number=int(drop[2]))

async def apply_educate_child_drop(client, drop: protobuf.CHILD_DROP):
    store = get_default_store()
    if drop.type == 5:
        # Child resources live in the legacy state's own `resources` wallet
        # (spends validate against it in handlers.py); the old UPDATE
        # targeted a commander_resources table that never existed on any
        # engine. JSONB round-trips stringify dict keys, so these sub-dicts
        # are always indexed by str.
        state = await get_or_create_legacy_educate_state(client.commander.commander_id)
        key = str(drop.id)
        state["resources"][key] = state["resources"].get(key, 0) + int(drop.number)
        await save_legacy_educate_state(state)
    elif drop.type == 3:
        # Items go to the player inventory (commander_items) via the same
        # grant path as every other drop; the old INSERT targeted `items`
        # (the item CATALOG, which has no commander_id column) and would
        # crash on any engine.
        from src.orm.item import add_item
        add_item(client.commander.commander_id, drop.id, int(drop.number))

def choose_educate_target_id(targets: dict) -> int:
    stage1 = [id for id, t in targets.items() if t.stage == 1]
    if stage1:
        stage1.sort()
        return stage1[0]
    ids = sorted(targets.keys())
    return ids[0] if ids else 0

def shop_refresh_key(now_ts: int, refresh_days: int) -> int:
    if refresh_days <= 0:
        return 0
    seconds = refresh_days * 86400
    if seconds <= 0:
        return 0
    return now_ts // seconds

def shop_goods_from_config(shop: educateShopConfig, templates: dict) -> list[EducateShopGoodsState]:
    good_ids = []
    for pool_entry in shop.goods_pool:
        if not pool_entry or len(pool_entry) == 0:
            continue
        if isinstance(pool_entry[0], list):
            gid, ok = parse_any_uint32(pool_entry[0][0])
        else:
            gid, ok = parse_any_uint32(pool_entry[0])
        if not ok or gid == 0 or gid not in templates:
            continue
        good_ids.append(gid)
    good_ids.sort()
    limit = int(shop.goods_num)
    if limit <= 0 or limit > len(good_ids):
        limit = len(good_ids)
    return [EducateShopGoodsState(id=gid, num=templates[gid].buy_num or 1) for gid in good_ids[:limit]]

async def ensure_educate_shop_state(commander_id: int, shop: educateShopConfig, templates: dict, now_ts: int):
    store = get_default_store()
    row = await store.afetchrow(
        "SELECT refresh_key, goods FROM educate_shop_states WHERE commander_id = $1 AND shop_id = $2",
        commander_id, shop.id,
    )
    if row is None:
        goods = shop_goods_from_config(shop, templates)
        goods_json = json.dumps([{"id": g.id, "num": g.num} for g in goods])
        await store.aexecute(
            "INSERT INTO educate_shop_states (commander_id, shop_id, refresh_key, goods) VALUES ($1, $2, $3, $4)",
            commander_id, shop.id, shop_refresh_key(now_ts, shop.goods_refresh_time), goods_json,
        )
        row = await store.afetchrow(
            "SELECT refresh_key, goods FROM educate_shop_states WHERE commander_id = $1 AND shop_id = $2",
            commander_id, shop.id,
        )
    key = shop_refresh_key(now_ts, shop.goods_refresh_time)
    if shop.goods_refresh_time > 0 and row["refresh_key"] != key:
        goods = shop_goods_from_config(shop, templates)
        goods_json = json.dumps([{"id": g.id, "num": g.num} for g in goods])
        await store.aexecute(
            "UPDATE educate_shop_states SET refresh_key = $3, goods = $4 WHERE commander_id = $1 AND shop_id = $2",
            commander_id, shop.id, key, goods_json,
        )
    return row

async def populate_educate_snapshot(commander_id: int, child) -> Optional[Exception]:
    if child is None:
        return None
    store = get_default_store()
    flags = await store.afetch(
        "SELECT flag_id FROM commander_common_flags WHERE commander_id = $1 ORDER BY flag_id",
        commander_id,
    )
    spec_events = []
    discount_events = []
    had_target_award = 0
    for row in flags:
        flag = row["flag_id"]
        if educateFlagSpecialEventBase <= flag < educateFlagSpecialEventBase + 100000:
            spec_events.append(flag - educateFlagSpecialEventBase)
        elif educateFlagDiscountBase <= flag < educateFlagDiscountBase + 100000:
            discount_events.append(flag - educateFlagDiscountBase)
        elif educateFlagTargetAwardBase <= flag < educateFlagTargetAwardBase + 100000:
            had_target_award = 1
    spec_events.sort()
    discount_events.sort()
    child.spec_events.extend(spec_events)
    child.discount_event_id.extend(discount_events)
    child.had_target_stage_award = had_target_award
    shop_rows = await store.afetch(
        "SELECT shop_id, goods FROM educate_shop_states WHERE commander_id = $1 ORDER BY shop_id",
        commander_id,
    )
    shops = []
    for row in shop_rows:
        goods_data = json.loads(row["goods"]) if isinstance(row["goods"], str) else (row.get("goods") or [])
        goods = [protobuf.CHILD_SHOP_GOODS(id=g["id"], num=g["num"]) for g in goods_data]
        shops.append(protobuf.CHILD_SHOP_DATA(shop_id=row["shop_id"], goods=goods))
    child.shop.extend(shops)
    return None

# ── Name validation ──

def is_valid_legacy_call_name(name: str, name_blacklist=None, illegal_pattern=None) -> bool:
    if not name:
        return False
    if not (legacyEducateCallNameMin <= len(name) <= legacyEducateCallNameMax):
        return False
    if name_blacklist:
        lower = name.lower()
        for blocked in name_blacklist:
            blocked = blocked.strip()
            if blocked and blocked.lower() in lower:
                return False
    if illegal_pattern:
        try:
            if re.search(illegal_pattern, name):
                return False
        except re.error:
            return False
    return True

def build_legacy_child_drop(drop_type: int, id: int, number: int) -> protobuf.CHILD_DROP:
    return protobuf.CHILD_DROP(type=drop_type, id=id, number=number)

# ── Legacy educate state ──

def _default_legacy_educate_state(commander_id: int) -> dict:
    return {
        "id": 0,
        "commander_id": commander_id,
        "favor_lv": 0,
        "favor_exp": 0,
        "target_id": 0,
        "call_name": "",
        "endings": [],
        "qualifieds": [],
        "attrs": {},
        "resources": {},
        "task_progress": {},
        "option_records": {},
        "had_adjustment": False,
        "child_display": 0,
    }


async def get_or_create_legacy_educate_state(commander_id: int) -> dict:
    # Missing-table fallback: asyncpg/SQLAlchemy map SQLSTATE 42P01 to
    # ProgrammingError, the sqlite3 driver to OperationalError.
    from sqlalchemy.exc import OperationalError, ProgrammingError
    store = get_default_store()
    try:
        row = await store.afetchrow(
            "SELECT id, commander_id, favor_lv, favor_exp, target_id, call_name, endings, qualifieds, "
            "attrs, resources, task_progress, option_records, had_adjustment, child_display "
            "FROM legacy_educate_states WHERE commander_id = $1",
            commander_id,
        )
    except (OperationalError, ProgrammingError):
        return _default_legacy_educate_state(commander_id)
    if row:
        return _row_to_state(row)
    try:
        await store.aexecute(
            "INSERT INTO legacy_educate_states (commander_id, favor_lv, favor_exp, target_id, call_name, "
            "endings, qualifieds, attrs, resources, task_progress, option_records, had_adjustment, child_display) "
            "VALUES ($1, 0, 0, 0, '', '[]', '[]', '{}', '{}', '{}', '{}', false, 0)",
            commander_id,
        )
    except (OperationalError, ProgrammingError):
        return _default_legacy_educate_state(commander_id)
    row = await store.afetchrow(
        "SELECT id, commander_id, favor_lv, favor_exp, target_id, call_name, endings, qualifieds, "
        "attrs, resources, task_progress, option_records, had_adjustment, child_display "
        "FROM legacy_educate_states WHERE commander_id = $1",
        commander_id,
    )
    if row is None:
        return _default_legacy_educate_state(commander_id)
    return _row_to_state(row)

def _row_to_state(row) -> dict:
    # JSONB round-trips stringify object keys: attrs / resources /
    # task_progress / option_records must always be indexed with str keys.
    return {
        "id": row["id"],
        "commander_id": row["commander_id"],
        "favor_lv": row.get("favor_lv", 0),
        "favor_exp": row.get("favor_exp", 0),
        "target_id": row.get("target_id", 0),
        "call_name": row.get("call_name") or "",
        "endings": json.loads(row["endings"]) if isinstance(row["endings"], str) else (list(row.get("endings") or [])),
        "qualifieds": json.loads(row["qualifieds"]) if isinstance(row["qualifieds"], str) else (list(row.get("qualifieds") or [])),
        "attrs": json.loads(row["attrs"]) if isinstance(row["attrs"], str) else (dict(row.get("attrs") or {})),
        "resources": json.loads(row["resources"]) if isinstance(row["resources"], str) else (dict(row.get("resources") or {})),
        "task_progress": json.loads(row["task_progress"]) if isinstance(row["task_progress"], str) else (dict(row.get("task_progress") or {})),
        "option_records": json.loads(row["option_records"]) if isinstance(row["option_records"], str) else (dict(row.get("option_records") or {})),
        "had_adjustment": row.get("had_adjustment", False),
        "child_display": row.get("child_display", 0),
    }

async def save_legacy_educate_state(state: dict):
    store = get_default_store()
    await store.aexecute(
        "UPDATE legacy_educate_states SET favor_lv=$2, favor_exp=$3, target_id=$4, call_name=$5, "
        "endings=$6, qualifieds=$7, attrs=$8, resources=$9, task_progress=$10, option_records=$11, "
        "had_adjustment=$12 WHERE commander_id=$1",
        state["commander_id"], state["favor_lv"], state["favor_exp"], state["target_id"], state["call_name"],
        json.dumps(state["endings"]), json.dumps(state["qualifieds"]),
        json.dumps(state["attrs"]), json.dumps(state["resources"]),
        json.dumps(state["task_progress"]), json.dumps(state["option_records"]),
        state["had_adjustment"],
    )
