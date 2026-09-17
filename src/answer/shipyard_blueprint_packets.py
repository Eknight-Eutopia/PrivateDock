import time
from typing import Optional

from src.connection.client import Client
from src.protobuf import protobuf


def _dict_to_shipinfo(d: dict):
    info = protobuf.SHIPINFO(
        id=d.get("id", 0),
        template_id=d.get("template_id", 0),
        level=d.get("level", 1),
        exp=d.get("exp", 0),
        energy=d.get("energy", 0),
        is_locked=d.get("is_locked", 0),
        create_time=d.get("create_time", 0),
        skin_id=d.get("skin_id", 0),
        propose=d.get("propose", 0),
        max_level=d.get("max_level", 0),
        intimacy=d.get("intimacy", 0),
        proficiency=d.get("proficiency", 0),
        activity_npc=d.get("activity_npc", 0),
    )
    name = d.get("name")
    if name:
        info.name = name
    change_name_timestamp = d.get("change_name_timestamp")
    if change_name_timestamp:
        info.change_name_timestamp = change_name_timestamp
    common_flag = d.get("common_flag")
    if common_flag:
        info.common_flag = common_flag
    for sid in d.get("skill_id_list", []):
        info.skill_id_list.append(sid)
    for tid in d.get("transform_list", []):
        info.transform_list.append(tid)
    meta_repair_list = d.get("meta_repair_list", [])
    for mr in meta_repair_list:
        info.meta_repair_list.append(protobuf.METAREPAIRINFO(id=mr.get("id", 0), repair_count=mr.get("repair_count", 0)))
    spweapon = d.get("spweapon")
    if spweapon:
        info.spweapon.CopyFrom(protobuf.SPWEAPONINFO(id=spweapon.get("id", 0), template_id=spweapon.get("template_id", 0)))
    for cf in d.get("strength_list", []):
        info.strength_list.append(protobuf.STRENGTHINFO(id=cf.get("id", 0), exp=cf.get("exp", 0)))
    equip_info_list = d.get("equip_info_list", [])
    for ei in equip_info_list:
        info.equip_info_list.append(protobuf.EQUIPINFO(id=ei.get("id", 0), count=ei.get("count", 0)))
    return info


def _parse_cs(buffer: bytes, msg_cls):
    """Parse a client protobuf request; the CS_632xx family is protobuf, not JSON."""
    msg = msg_cls()
    try:
        msg.ParseFromString(buffer)
    except Exception as e:
        return None, e
    return msg, None


def _load_blueprint_cfg(blueprint_id) -> Optional[dict]:
    """ship_data_blueprint row from config_entries (returns a plain dict)."""
    from src.orm.config_entry import get_config_entry_sync
    try:
        entry = get_config_entry_sync("ShareCfg/ship_data_blueprint.json", str(int(blueprint_id)))
    except Exception:
        return None
    if entry is None:
        return None
    data = entry.data
    if isinstance(data, str):
        try:
            return __import__("json").loads(data)
        except Exception:
            return None
    return data if isinstance(data, dict) else None


def _load_strengthen_blueprint_cfg(strength_id) -> Optional[dict]:
    """ship_strengthen_blueprint row (need_lv / need_exp per dev level)."""
    from src.orm.config_entry import get_config_entry_sync
    try:
        entry = get_config_entry_sync("ShareCfg/ship_strengthen_blueprint.json", str(int(strength_id)))
    except Exception:
        return None
    if entry is None:
        return None
    data = entry.data
    if isinstance(data, str):
        try:
            return __import__("json").loads(data)
        except Exception:
            return None
    return data if isinstance(data, dict) else None


def _blueprint_chain_task_ids(cfg: dict) -> list:
    """Research chain task ids (first element of each [task_id, offset] pair)."""
    out = []
    for group in cfg.get("unlock_task", []):
        if isinstance(group, (list, tuple)) and group:
            tid = int(group[0] or 0)
            if tid and tid not in out:
                out.append(tid)
    return out


from src.orm.commander_task import (
    fetch_commander_tasks,
    seed_commander_tasks,
    upsert_task_progress_least,
)


def _seed_commander_tasks(commander_id: int, task_ids: list):
    """Insert research-chain rows (progress 0, not submitted). Existing rows are
    kept untouched (ON CONFLICT DO NOTHING) so partial progress survives."""
    if not task_ids:
        return
    seed_commander_tasks(commander_id, task_ids, int(time.time()))


async def _push_task_rows(client: Client, commander_id: int, task_ids: list):
    """Push SC_20001 with the current state of the given tasks so newly added
    research-chain tasks reach the client mid-session (the client accumulates
    SC_20001 payloads)."""
    if not task_ids:
        return
    resp = protobuf.SC_20001()
    try:
        rows = fetch_commander_tasks(commander_id, task_ids)
    except Exception:
        rows = []
    for r in rows:
        resp.info.append(protobuf.TASKINFO(
            id=r.task_id, progress=r.progress, accept_time=r.accept_time, submit_time=r.submit_time))
    if resp.info:
        await client.send_message(20001, resp)


async def _ship_blueprint_template_id(cfg: dict, blueprint_id: int) -> int:
    """The ship template granted when a development completes. Blueprint ids are
    ship *group* ids, so the default-skin template is group*10+1."""
    tid = cfg.get("ship_template_id") or 0
    if not tid:
        tid = int(blueprint_id) * 10 + 1
    return int(tid)


async def handle_start_ship_blueprint_development(
    buffer: bytes, client: Client,
) -> tuple[int, int, Optional[Exception]]:
    PACKET_ID = 63201

    payload, err = _parse_cs(buffer, protobuf.CS_63200)
    if err is not None:
        return 0, PACKET_ID, err
    blueprint_id = int(payload.blueprint_id or 0)
    if blueprint_id == 0:
        await client.send_message(PACKET_ID, protobuf.SC_63201(result=1, time=0))
        return 0, PACKET_ID, None

    from .shipyard_blueprint_helpers import (
        SHIPYARD_RESULT_OK, SHIPYARD_COOLDOWN_SECONDS,
        ensure_commander_loaded_for_shipyard, is_shipyard_task_satisfied,
        get_or_init_shipyard_blueprint, shipyard_now_unix,
    )

    err = ensure_commander_loaded_for_shipyard(client.commander)
    if err is not None:
        return 0, PACKET_ID, err

    cfg = _load_blueprint_cfg(blueprint_id)
    if cfg is None:
        await client.send_message(PACKET_ID, protobuf.SC_63201(result=1, time=0))
        return 0, PACKET_ID, None

    now = shipyard_now_unix()
    cid = client.commander.commander_id

    try:
        from src.orm.shipyard import (
            get_or_create_commander_shipyard_state, upsert_commander_shipyard_state,
            list_commander_shipyard_blueprints, upsert_commander_shipyard_blueprint,
        )
        state = get_or_create_commander_shipyard_state(cid)
        if int(state.cold_time or 0) > now:
            await client.send_message(PACKET_ID, protobuf.SC_63201(result=1, time=0))
            return 0, PACKET_ID, None

        # Every open condition must be satisfied (claimed or progress reached).
        for task_id in cfg.get("unlock_task_open_condition", []):
            if not task_id:
                continue
            ok, _ = is_shipyard_task_satisfied(cid, int(task_id))
            if not ok:
                await client.send_message(PACKET_ID, protobuf.SC_63201(result=1, time=0))
                return 0, PACKET_ID, None

        # Only one development may run at a time.
        all_rows = list_commander_shipyard_blueprints(cid)
        for row in all_rows:
            if int(getattr(row, "blueprint_id", 0) or 0) == blueprint_id:
                continue
            if int(getattr(row, "ship_id", 0) or 0) == 0 and int(getattr(row, "start_time", 0) or 0) > 0:
                await client.send_message(PACKET_ID, protobuf.SC_63201(result=1, time=0))
                return 0, PACKET_ID, None

        entry = get_or_init_shipyard_blueprint(cid, blueprint_id)
        if int(getattr(entry, "ship_id", 0) or 0) != 0 or int(getattr(entry, "start_time", 0) or 0) > 0:
            await client.send_message(PACKET_ID, protobuf.SC_63201(result=1, time=0))
            return 0, PACKET_ID, None

        start_duration = int(getattr(entry, "start_duration", 0) or 0)
        if start_duration > 0:
            entry.start_time = now - start_duration
        else:
            entry.start_time = now
        upsert_commander_shipyard_blueprint(entry)

        state.cold_time = now + SHIPYARD_COOLDOWN_SECONDS
        upsert_commander_shipyard_state(state)

        # The research chain (unlock_task: [task_id, open_offset] entries) becomes
        # the commander's missions so the client's ShipBluePrint dev card can
        # render each stage; progress advances through the regular task pipeline.
        chain_ids = _blueprint_chain_task_ids(cfg)
        _seed_commander_tasks(cid, chain_ids)
        await _push_task_rows(client, cid, chain_ids)
    except Exception as e:
        return 0, PACKET_ID, e

    await client.send_message(PACKET_ID, protobuf.SC_63201(result=SHIPYARD_RESULT_OK, time=entry.start_time))
    try:
        from src.answer.task_handlers import schedule_emit, schedule_possession_sync
        schedule_emit(client, 99, 0, 1)
        schedule_emit(client, 210, 0, 1)
        schedule_possession_sync(client)
    except Exception:
        pass
    return 0, PACKET_ID, None


async def handle_stop_ship_blueprint(
    buffer: bytes, client: Client,
) -> tuple[int, int, Optional[Exception]]:
    PACKET_ID = 63207

    payload, err = _parse_cs(buffer, protobuf.CS_63206)
    if err is not None:
        return 0, PACKET_ID, err
    blueprint_id = int(payload.blueprint_id or 0)
    if blueprint_id == 0:
        await client.send_message(PACKET_ID, protobuf.SC_63207(result=1))
        return 0, PACKET_ID, None

    from .shipyard_blueprint_helpers import (
        SHIPYARD_RESULT_OK, is_blueprint_development_finished, shipyard_now_unix,
    )
    from src.orm.shipyard import get_commander_shipyard_blueprint, upsert_commander_shipyard_blueprint

    now = shipyard_now_unix()
    cid = client.commander.commander_id

    try:
        cfg = _load_blueprint_cfg(blueprint_id)
        entry = get_commander_shipyard_blueprint(cid, blueprint_id)
        if entry is None or cfg is None:
            await client.send_message(PACKET_ID, protobuf.SC_63207(result=1))
            return 0, PACKET_ID, None
        finished, _ = is_blueprint_development_finished(entry, cfg)
        if int(getattr(entry, "ship_id", 0) or 0) != 0 or (int(getattr(entry, "start_time", 0) or 0) == 0 and not finished):
            await client.send_message(PACKET_ID, protobuf.SC_63207(result=1))
            return 0, PACKET_ID, None
        elapsed = int(getattr(entry, "start_duration", 0) or 0)
        st = int(getattr(entry, "start_time", 0) or 0)
        if st > 0 and now > st:
            elapsed = now - st
        entry.start_time = 0
        entry.start_duration = elapsed
        upsert_commander_shipyard_blueprint(entry)
    except Exception as e:
        return 0, PACKET_ID, e

    await client.send_message(PACKET_ID, protobuf.SC_63207(result=SHIPYARD_RESULT_OK))
    return 0, PACKET_ID, None


async def handle_resume_ship_blueprint(
    buffer: bytes, client: Client,
) -> tuple[int, int, Optional[Exception]]:
    PACKET_ID = 63209

    payload, err = _parse_cs(buffer, protobuf.CS_63208)
    if err is not None:
        return 0, PACKET_ID, err
    blueprint_id = int(payload.blueprint_id or 0)
    if blueprint_id == 0:
        await client.send_message(PACKET_ID, protobuf.SC_63209(result=1))
        return 0, PACKET_ID, None

    from .shipyard_blueprint_helpers import SHIPYARD_RESULT_OK, shipyard_now_unix
    from src.orm.shipyard import (
        list_commander_shipyard_blueprints, get_commander_shipyard_blueprint,
        upsert_commander_shipyard_blueprint,
    )

    now = shipyard_now_unix()
    cid = client.commander.commander_id

    try:
        for row in list_commander_shipyard_blueprints(cid):
            if int(getattr(row, "blueprint_id", 0) or 0) == blueprint_id:
                continue
            if int(getattr(row, "ship_id", 0) or 0) == 0 and int(getattr(row, "start_time", 0) or 0) > 0:
                await client.send_message(PACKET_ID, protobuf.SC_63209(result=1))
                return 0, PACKET_ID, None
        entry = get_commander_shipyard_blueprint(cid, blueprint_id)
        if entry is None:
            await client.send_message(PACKET_ID, protobuf.SC_63209(result=1))
            return 0, PACKET_ID, None
        if int(getattr(entry, "ship_id", 0) or 0) != 0 or int(getattr(entry, "start_time", 0) or 0) > 0:
            await client.send_message(PACKET_ID, protobuf.SC_63209(result=1))
            return 0, PACKET_ID, None
        sd = int(getattr(entry, "start_duration", 0) or 0)
        if sd > now:
            entry.start_time = 0
        else:
            entry.start_time = now - sd
        entry.start_duration = 0
        upsert_commander_shipyard_blueprint(entry)
    except Exception as e:
        return 0, PACKET_ID, e

    await client.send_message(PACKET_ID, protobuf.SC_63209(result=SHIPYARD_RESULT_OK))
    return 0, PACKET_ID, None


async def handle_finish_ship_blueprint(
    buffer: bytes, client: Client,
) -> tuple[int, int, Optional[Exception]]:
    PACKET_ID = 63203

    payload, err = _parse_cs(buffer, protobuf.CS_63202)
    if err is not None:
        return 0, PACKET_ID, err
    blueprint_id = int(payload.blueprint_id or 0)
    if blueprint_id == 0:
        await client.send_message(PACKET_ID, protobuf.SC_63203(result=1))
        return 0, PACKET_ID, None

    from .shipyard_blueprint_helpers import (
        SHIPYARD_RESULT_OK,
        ensure_commander_loaded_for_shipyard, is_shipyard_blueprint_ready_to_finish,
    )
    from src.orm.shipyard import get_commander_shipyard_blueprint, upsert_commander_shipyard_blueprint

    err = ensure_commander_loaded_for_shipyard(client.commander)
    if err is not None:
        return 0, PACKET_ID, err

    cid = client.commander.commander_id

    try:
        cfg = _load_blueprint_cfg(blueprint_id)
        entry = get_commander_shipyard_blueprint(cid, blueprint_id)
        if entry is None or cfg is None:
            await client.send_message(PACKET_ID, protobuf.SC_63203(result=1))
            return 0, PACKET_ID, None
        ready, _ = is_shipyard_blueprint_ready_to_finish(cid, entry, cfg)
        if not ready or int(getattr(entry, "ship_id", 0) or 0) != 0:
            await client.send_message(PACKET_ID, protobuf.SC_63203(result=1))
            return 0, PACKET_ID, None

        ship = client.commander.add_ship(await _ship_blueprint_template_id(cfg, blueprint_id))
        if ship is None:
            await client.send_message(PACKET_ID, protobuf.SC_63203(result=1))
            return 0, PACKET_ID, None
        entry.ship_id = int(ship.get("id", 0) or 0)
        entry.start_time = 0
        entry.start_duration = 0
        upsert_commander_shipyard_blueprint(entry)
    except Exception as e:
        return 0, PACKET_ID, e

    resp = protobuf.SC_63203(result=SHIPYARD_RESULT_OK)
    resp.ship.CopyFrom(_dict_to_shipinfo(ship))
    await client.send_message(PACKET_ID, resp)
    # Server-authoritative task progress: finishing a PR/DR development adds a
    # real ship -> "Obtain any shipgirl of PR or DR rarity" (sub_type 211,
    # state-based via the possession sync) and "Finish building any Series 1 PR
    # ship" (sub_type 1014, target_id = blueprint ids).
    try:
        from src.answer.task_handlers import schedule_emit, schedule_possession_sync
        schedule_emit(client, 1014, blueprint_id, 1)
        schedule_possession_sync(client)
    except Exception:
        pass
    return 0, PACKET_ID, None


async def handle_use_tech_speedup_item(
    buffer: bytes, client: Client,
) -> tuple[int, int, Optional[Exception]]:
    PACKET_ID = 63211

    payload, err = _parse_cs(buffer, protobuf.CS_63210)
    if err is not None:
        return 0, PACKET_ID, err
    blueprint_id = int(payload.blueprintid or 0)
    item_id = int(payload.itemid or 0)
    task_id = int(payload.task_id or 0)
    number = int(payload.number or 0)

    if blueprint_id == 0 or item_id == 0 or task_id == 0 or number <= 0:
        await client.send_message(PACKET_ID, protobuf.SC_63211(result=1))
        return 0, PACKET_ID, None

    from .shipyard_blueprint_helpers import (
        SHIPYARD_RESULT_OK, SHIPYARD_RESULT_NO_ITEMS,
        ensure_commander_loaded_for_shipyard,
        is_dev_chain_task_open,
    )

    err = ensure_commander_loaded_for_shipyard(client.commander)
    if err is not None:
        return 0, PACKET_ID, err

    cfg = _load_blueprint_cfg(blueprint_id)
    if cfg is None:
        await client.send_message(PACKET_ID, protobuf.SC_63211(result=1))
        return 0, PACKET_ID, None

    # The catch-up item id and exp per blueprint version come from gameset
    # technology_catchup_itemid.description ([[20101, 10000], ...] by version).
    from src.orm.config_entry import get_config_entry_sync
    try:
        gameset = get_config_entry_sync("ShareCfg/gameset.json", "technology_catchup_itemid")
    except Exception:
        gameset = None
    catchup_item_id = 0
    catchup_exp = 0
    version = int(cfg.get("blueprint_version", 0) or 0)
    if gameset is not None:
        data = gameset.data
        if isinstance(data, str):
            import json
            try:
                data = json.loads(data)
            except Exception:
                data = None
        if isinstance(data, dict):
            desc = data.get("description") or []
            if isinstance(desc, list) and 0 < version <= len(desc):
                pair = desc[version - 1]
                if isinstance(pair, list):
                    if len(pair) >= 1:
                        catchup_item_id = int(pair[0] or 0)
                    if len(pair) >= 2:
                        catchup_exp = int(pair[1] or 0)
    if item_id != catchup_item_id:
        await client.send_message(PACKET_ID, protobuf.SC_63211(result=1))
        return 0, PACKET_ID, None

    chain = _blueprint_chain_task_ids(cfg)
    if task_id not in chain:
        await client.send_message(PACKET_ID, protobuf.SC_63211(result=1))
        return 0, PACKET_ID, None

    cid = client.commander.commander_id
    now = int(time.time())

    # Task must be open and not already submitted
    if is_dev_chain_task_open(cid, task_id, now) is False:
        await client.send_message(PACKET_ID, protobuf.SC_63211(result=1))
        return 0, PACKET_ID, None

    item_exp = catchup_exp
    if item_exp <= 0:
        from src.orm.item_usage_config import load_item_usage_exp
        try:
            item_exp = await load_item_usage_exp(item_id)
        except Exception:
            item_exp = 0
    if item_exp <= 0:
        await client.send_message(PACKET_ID, protobuf.SC_63211(result=1))
        return 0, PACKET_ID, None

    target_num = 0
    try:
        entry_tpl = get_config_entry_sync("sharecfgdata/task_data_template.json", str(task_id))
    except Exception:
        entry_tpl = None
    if entry_tpl is not None:
        tpl_data = entry_tpl.data
        if isinstance(tpl_data, str):
            import json
            try:
                tpl_data = json.loads(tpl_data)
            except Exception:
                tpl_data = None
        if isinstance(tpl_data, dict):
            target_num = int(tpl_data.get("target_num", 0) or 0)

    delta = number * item_exp

    try:
        if not client.commander.has_enough_item(item_id, number):
            await client.send_message(PACKET_ID, protobuf.SC_63211(result=SHIPYARD_RESULT_NO_ITEMS))
            return 0, PACKET_ID, None
        client.commander.consume_item(item_id, number)
        if target_num > 0:
            upsert_task_progress_least(cid, task_id, delta, target_num, now)
            await _push_task_rows(client, cid, [task_id])
    except Exception as e:
        return 0, PACKET_ID, e

    await client.send_message(PACKET_ID, protobuf.SC_63211(result=SHIPYARD_RESULT_OK))
    return 0, PACKET_ID, None


async def handle_mod_ship_blueprint(
    buffer: bytes, client: Client,
) -> tuple[int, int, Optional[Exception]]:
    PACKET_ID = 63205

    payload, err = _parse_cs(buffer, protobuf.CS_63204)
    if err is not None:
        return 0, PACKET_ID, err
    ship_id = int(payload.ship_id or 0)
    count = int(payload.count or 0)
    if ship_id == 0 or count == 0:
        await client.send_message(PACKET_ID, protobuf.SC_63205(result=1))
        return 0, PACKET_ID, None

    from .shipyard_blueprint_helpers import (
        SHIPYARD_RESULT_OK,
        ensure_commander_loaded_for_shipyard, apply_blueprint_exp_gain,
    )

    err = ensure_commander_loaded_for_shipyard(client.commander)
    if err is not None:
        return 0, PACKET_ID, err

    ship = (client.commander.owned_ships_map or {}).get(ship_id)
    if ship is None:
        await client.send_message(PACKET_ID, protobuf.SC_63205(result=1))
        return 0, PACKET_ID, None

    blueprint_id = int(ship.get("ship_id", 0) or 0) // 10
    cfg = _load_blueprint_cfg(blueprint_id)
    if cfg is None:
        await client.send_message(PACKET_ID, protobuf.SC_63205(result=1))
        return 0, PACKET_ID, None

    from src.orm.item_usage_config import load_item_usage_exp
    try:
        item_exp = await load_item_usage_exp(cfg.get("strengthen_item", 0))
    except Exception:
        item_exp = 0
    if item_exp <= 0:
        await client.send_message(PACKET_ID, protobuf.SC_63205(result=1))
        return 0, PACKET_ID, None

    gain = count * item_exp

    from src.orm.shipyard import get_commander_shipyard_blueprint, upsert_commander_shipyard_blueprint
    from src.orm.owned_ship_strength import upsert_owned_ship_strength

    entry = get_commander_shipyard_blueprint(client.commander.commander_id, blueprint_id)
    if entry is None or int(getattr(entry, "ship_id", 0) or 0) != ship_id:
        await client.send_message(PACKET_ID, protobuf.SC_63205(result=1))
        return 0, PACKET_ID, None

    updated, err = apply_blueprint_exp_gain(entry, cfg, int(ship.get("level", 0) or 0), gain)
    if err is not None or not updated:
        await client.send_message(PACKET_ID, protobuf.SC_63205(result=1))
        return 0, PACKET_ID, None

    strengthen_item = cfg.get("strengthen_item", 0)
    try:
        if not client.commander.has_enough_item(strengthen_item, count):
            await client.send_message(PACKET_ID, protobuf.SC_63205(result=1))
            return 0, PACKET_ID, None
        client.commander.consume_item(strengthen_item, count)
        upsert_commander_shipyard_blueprint(entry)
        upsert_owned_ship_strength({
            "owner_id": client.commander.commander_id,
            "ship_id": ship_id,
            "strength_id": 1,
            "exp": int(getattr(entry, "exp", 0) or 0),
        })
    except Exception as e:
        return 0, PACKET_ID, e

    await client.send_message(PACKET_ID, protobuf.SC_63205(result=SHIPYARD_RESULT_OK))
    # Server-authoritative task progress: feeding blueprints to a PR ship
    # advances "Enhance a blueprint ship N times" (sub_type 212).
    try:
        from src.answer.task_handlers import schedule_emit
        schedule_emit(client, 212, 0, count)
    except Exception:
        pass
    return 0, PACKET_ID, None


async def handle_pursue_ship_blueprint(
    buffer: bytes, client: Client,
) -> tuple[int, int, Optional[Exception]]:
    PACKET_ID = 63213

    payload, err = _parse_cs(buffer, protobuf.CS_63212)
    if err is not None:
        return 0, PACKET_ID, err
    ship_id = int(payload.ship_id or 0)
    count = int(payload.count or 0)
    if ship_id == 0 or count == 0:
        await client.send_message(PACKET_ID, protobuf.SC_63213(result=1))
        return 0, PACKET_ID, None

    from .shipyard_blueprint_helpers import (
        SHIPYARD_RESULT_OK,
        ensure_commander_loaded_for_shipyard, apply_blueprint_exp_gain,
    )

    err = ensure_commander_loaded_for_shipyard(client.commander)
    if err is not None:
        return 0, PACKET_ID, err

    ship = (client.commander.owned_ships_map or {}).get(ship_id)
    if ship is None:
        await client.send_message(PACKET_ID, protobuf.SC_63213(result=1))
        return 0, PACKET_ID, None

    blueprint_id = int(ship.get("ship_id", 0) or 0) // 10
    cfg = _load_blueprint_cfg(blueprint_id)
    if cfg is None:
        await client.send_message(PACKET_ID, protobuf.SC_63213(result=1))
        return 0, PACKET_ID, None

    if int(cfg.get("is_pursuing", 0) or 0) != 1:
        await client.send_message(PACKET_ID, protobuf.SC_63213(result=1))
        return 0, PACKET_ID, None

    from src.orm.item_usage_config import load_item_usage_exp
    try:
        item_exp = await load_item_usage_exp(cfg.get("strengthen_item", 0))
    except Exception:
        item_exp = 0
    if item_exp <= 0:
        await client.send_message(PACKET_ID, protobuf.SC_63213(result=1))
        return 0, PACKET_ID, None

    use_ur_discount = int(cfg.get("blueprint_version", 0) or 0) >= 4
    from src.orm.shipyard import (
        get_or_create_commander_shipyard_state, get_commander_shipyard_blueprint,
        get_shipyard_pursue_discounts, upsert_commander_shipyard_state,
        upsert_commander_shipyard_blueprint,
    )
    from src.orm.owned_ship_strength import upsert_owned_ship_strength

    state = get_or_create_commander_shipyard_state(client.commander.commander_id)
    entry = get_commander_shipyard_blueprint(client.commander.commander_id, blueprint_id)
    if entry is None or int(getattr(entry, "ship_id", 0) or 0) != ship_id:
        await client.send_message(PACKET_ID, protobuf.SC_63213(result=1))
        return 0, PACKET_ID, None

    try:
        discounts = get_shipyard_pursue_discounts(use_ur_discount)
    except Exception:
        discounts = []
    if not discounts:
        await client.send_message(PACKET_ID, protobuf.SC_63213(result=1))
        return 0, PACKET_ID, None

    counter_key = "daily_catchup_strengthen_ur" if use_ur_discount else "daily_catchup_strengthen"
    counter = int(getattr(state, counter_key, 0) or 0)
    price = int(cfg.get("price", 0) or 0)
    total_cost = 0
    for i in range(count):
        index = int(counter + i)
        if index >= len(discounts):
            index = len(discounts) - 1
        discount = int(discounts[index])
        if discount > 100:
            discount = 100
        total_cost += (price * (100 - discount)) // 100

    if not client.commander.has_enough_gold(total_cost):
        await client.send_message(PACKET_ID, protobuf.SC_63213(result=1))
        return 0, PACKET_ID, None

    gain = count * item_exp
    updated, err = apply_blueprint_exp_gain(entry, cfg, int(ship.get("level", 0) or 0), gain)
    if err is not None or not updated:
        await client.send_message(PACKET_ID, protobuf.SC_63213(result=1))
        return 0, PACKET_ID, None

    try:
        client.commander.consume_resource(1, total_cost)
        setattr(state, counter_key, int(getattr(state, counter_key, 0) or 0) + count)
        upsert_commander_shipyard_state(state)
        upsert_commander_shipyard_blueprint(entry)
        upsert_owned_ship_strength({
            "owner_id": client.commander.commander_id,
            "ship_id": ship_id,
            "strength_id": 1,
            "exp": int(getattr(entry, "exp", 0) or 0),
        })
    except Exception as e:
        return 0, PACKET_ID, e

    await client.send_message(PACKET_ID, protobuf.SC_63213(result=SHIPYARD_RESULT_OK))
    return 0, PACKET_ID, None


async def handle_item_unlock_ship_blueprint(
    buffer: bytes, client: Client,
) -> tuple[int, int, Optional[Exception]]:
    PACKET_ID = 63215

    payload, err = _parse_cs(buffer, protobuf.CS_63214)
    if err is not None:
        return 0, PACKET_ID, err
    group = int(payload.group or 0)
    item_id = int(payload.itemid or 0)
    if group == 0 or item_id == 0:
        await client.send_message(PACKET_ID, protobuf.SC_63215(result=1))
        return 0, PACKET_ID, None

    from .shipyard_blueprint_helpers import (
        SHIPYARD_RESULT_OK, SHIPYARD_RESULT_NO_ITEMS,
        ensure_commander_loaded_for_shipyard, get_or_init_shipyard_blueprint,
    )

    err = ensure_commander_loaded_for_shipyard(client.commander)
    if err is not None:
        return 0, PACKET_ID, err

    cfg = _load_blueprint_cfg(group)
    if cfg is None:
        await client.send_message(PACKET_ID, protobuf.SC_63215(result=1))
        return 0, PACKET_ID, None

    allowed = any(int(candidate or 0) == item_id for candidate in cfg.get("gain_item_id", []))
    if not allowed:
        await client.send_message(PACKET_ID, protobuf.SC_63215(result=1))
        return 0, PACKET_ID, None

    ship = None
    try:
        entry = get_or_init_shipyard_blueprint(client.commander.commander_id, group)
        if int(getattr(entry, "ship_id", 0) or 0) != 0:
            await client.send_message(PACKET_ID, protobuf.SC_63215(result=1))
            return 0, PACKET_ID, None
        if not client.commander.has_enough_item(item_id, 1):
            await client.send_message(PACKET_ID, protobuf.SC_63215(result=SHIPYARD_RESULT_NO_ITEMS))
            return 0, PACKET_ID, None
        client.commander.consume_item(item_id, 1)
        ship = client.commander.add_ship(await _ship_blueprint_template_id(cfg, group))
        if ship is None:
            await client.send_message(PACKET_ID, protobuf.SC_63215(result=1))
            return 0, PACKET_ID, None
        entry.ship_id = int(ship.get("id", 0) or 0)
        entry.start_time = 0
        entry.start_duration = 0
        from src.orm.shipyard import upsert_commander_shipyard_blueprint
        upsert_commander_shipyard_blueprint(entry)
    except Exception as e:
        return 0, PACKET_ID, e

    resp = protobuf.SC_63215(result=SHIPYARD_RESULT_OK)
    resp.ship.CopyFrom(_dict_to_shipinfo(ship))
    await client.send_message(PACKET_ID, resp)
    return 0, PACKET_ID, None
