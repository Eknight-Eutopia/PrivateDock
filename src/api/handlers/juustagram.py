from fastapi import Request
from src.api.response.response import ok as success, error
from src.api.types import *
from .players import parse_pagination, parse_path_uint32, fmt_val as _fmt_val
from src.orm import juustagram_template as _tmpl
from src.orm import juustagram_npc_template as _npctmpl
from src.orm import juustagram_ship_group_template as _sg
from src.orm import juustagram_language as _lang
from src.orm import juustagram_message_state as _ms
from src.orm import juustagram_player_discuss as _pd
from src.orm import juustagram_group as _grp
from src.orm import juustagram_chat_group as _cg
from src.orm import juustagram_reply as _reply
from src.orm.commander import get_commander
import datetime


async def list_templates(request: Request):
    try:
        pagination = parse_pagination(request)
    except ValueError as e:
        return error("bad_request", str(e), status_code=400)
    total = await _tmpl.count_templates()
    rows = await _tmpl.list_templates(pagination.offset, pagination.limit)
    templates = [JuustagramTemplate(
        id=r["id"], group_id=r.get("group_id", 0), ship_group=r.get("ship_group", 0),
        name=r.get("name", ""), sculpture=r.get("sculpture", ""),
        picture_persist=r.get("picture_persist", ""), message_persist=r.get("message_persist", ""),
        is_active=r.get("is_active", False), npc_discuss_persist=r.get("npc_discuss_persist", ""),
        time=r.get("time", 0), time_persist=r.get("time_persist", ""),
    ) for r in rows]
    return success(data=JuustagramTemplateListResponse(
        templates=templates,
        meta=PaginationMeta(offset=pagination.offset, limit=pagination.limit, total=total),
    ).model_dump())


async def template_detail(request: Request):
    try:
        tid = parse_path_uint32(request.path_params.get("id", ""), "template id")
    except ValueError as e:
        return error("bad_request", str(e), status_code=400)
    r = await _tmpl.get_template(tid)
    if r is None:
        return error("not_found", "juustagram template not found", status_code=404)
    return success(data=JuustagramTemplate(
        id=r["id"], group_id=r.get("group_id", 0), ship_group=r.get("ship_group", 0),
        name=r.get("name", ""), sculpture=r.get("sculpture", ""),
        picture_persist=r.get("picture_persist", ""), message_persist=r.get("message_persist", ""),
        is_active=r.get("is_active", False), npc_discuss_persist=r.get("npc_discuss_persist", ""),
        time=r.get("time", 0), time_persist=r.get("time_persist", ""),
    ).model_dump())


async def create_template(request: Request):
    try:
        body = await request.json()
    except Exception:
        return error("bad_request", "invalid payload", status_code=400)
    req = JuustagramTemplate(**body)
    name = req.name.strip() if req.name else ""
    sculpture = req.sculpture.strip() if req.sculpture else ""
    picture_persist = req.picture_persist.strip() if req.picture_persist else ""
    message_persist = req.message_persist.strip() if req.message_persist else ""
    if req.id == 0:
        return error("bad_request", "id is required", status_code=400)
    if not name:
        return error("bad_request", "name is required", status_code=400)
    if not sculpture:
        return error("bad_request", "sculpture is required", status_code=400)
    if not picture_persist:
        return error("bad_request", "picture_persist is required", status_code=400)
    if not message_persist:
        return error("bad_request", "message_persist is required", status_code=400)
    await _tmpl.create_template(
        req.id, req.group_id, req.ship_group, name, sculpture,
        picture_persist, message_persist, req.is_active,
        req.npc_discuss_persist, req.time, req.time_persist,
    )
    return success(data=None)


async def update_template(request: Request):
    try:
        body = await request.json()
    except Exception:
        return error("bad_request", "invalid payload", status_code=400)
    req = JuustagramTemplate(**body)
    name = req.name.strip() if req.name else ""
    sculpture = req.sculpture.strip() if req.sculpture else ""
    picture_persist = req.picture_persist.strip() if req.picture_persist else ""
    message_persist = req.message_persist.strip() if req.message_persist else ""
    if req.id == 0:
        return error("bad_request", "id is required", status_code=400)
    if not name:
        return error("bad_request", "name is required", status_code=400)
    if not sculpture:
        return error("bad_request", "sculpture is required", status_code=400)
    if not picture_persist:
        return error("bad_request", "picture_persist is required", status_code=400)
    if not message_persist:
        return error("bad_request", "message_persist is required", status_code=400)
    existing = await _tmpl.get_template(req.id)
    if existing is None:
        return error("not_found", "juustagram template not found", status_code=404)
    await _tmpl.update_template(
        req.id, req.group_id, req.ship_group, name, sculpture,
        picture_persist, message_persist, req.is_active,
        req.npc_discuss_persist, req.time, req.time_persist,
    )
    return success(data=None)


async def delete_template(request: Request):
    try:
        body = await request.json()
    except Exception:
        return error("bad_request", "invalid payload", status_code=400)
    tid = body.get("id", 0)
    if not tid:
        return error("bad_request", "id is required", status_code=400)
    if not await _tmpl.delete_template(tid):
        return error("not_found", "juustagram template not found", status_code=404)
    return success(data=None)


async def list_npc_templates(request: Request):
    try:
        pagination = parse_pagination(request)
    except ValueError as e:
        return error("bad_request", str(e), status_code=400)
    total = await _npctmpl.count_npc_templates()
    rows = await _npctmpl.list_npc_templates(pagination.offset, pagination.limit)
    templates = [JuustagramNpcTemplate(
        id=r["id"], ship_group=r.get("ship_group", 0),
        message_persist=r.get("message_persist", ""),
        npc_reply_persist=r.get("npc_reply_persist", ""),
        time_persist=r.get("time_persist", ""),
    ) for r in rows]
    return success(data=JuustagramNpcTemplateListResponse(
        templates=templates,
        meta=PaginationMeta(offset=pagination.offset, limit=pagination.limit, total=total),
    ).dict())


async def npc_template_detail(request: Request):
    try:
        tid = parse_path_uint32(request.path_params.get("id", ""), "npc template id")
    except ValueError as e:
        return error("bad_request", str(e), status_code=400)
    r = await _npctmpl.get_npc_template(tid)
    if r is None:
        return error("not_found", "juustagram npc template not found", status_code=404)
    return success(data=JuustagramNpcTemplate(
        id=r["id"], ship_group=r.get("ship_group", 0),
        message_persist=r.get("message_persist", ""),
        npc_reply_persist=r.get("npc_reply_persist", ""),
        time_persist=r.get("time_persist", ""),
    ).dict())


async def create_npc_template(request: Request):
    try:
        body = await request.json()
    except Exception:
        return error("bad_request", "invalid payload", status_code=400)
    req = JuustagramNpcTemplate(**body)
    message_persist = req.message_persist.strip() if req.message_persist else ""
    if req.id == 0:
        return error("bad_request", "id is required", status_code=400)
    if not message_persist:
        return error("bad_request", "message_persist is required", status_code=400)
    await _npctmpl.create_npc_template(req.id, req.ship_group, message_persist, req.npc_reply_persist, req.time_persist)
    return success(data=None)


async def update_npc_template(request: Request):
    try:
        body = await request.json()
    except Exception:
        return error("bad_request", "invalid payload", status_code=400)
    req = JuustagramNpcTemplate(**body)
    message_persist = req.message_persist.strip() if req.message_persist else ""
    if req.id == 0:
        return error("bad_request", "id is required", status_code=400)
    if not message_persist:
        return error("bad_request", "message_persist is required", status_code=400)
    existing = await _npctmpl.get_npc_template(req.id)
    if existing is None:
        return error("not_found", "juustagram npc template not found", status_code=404)
    await _npctmpl.update_npc_template(req.id, req.ship_group, message_persist, req.npc_reply_persist, req.time_persist)
    return success(data=None)


async def delete_npc_template(request: Request):
    try:
        body = await request.json()
    except Exception:
        return error("bad_request", "invalid payload", status_code=400)
    tid = body.get("id", 0)
    if not tid:
        return error("bad_request", "id is required", status_code=400)
    if not await _npctmpl.delete_npc_template(tid):
        return error("not_found", "juustagram npc template not found", status_code=404)
    return success(data=None)


async def list_ship_groups(request: Request):
    try:
        pagination = parse_pagination(request)
    except ValueError as e:
        return error("bad_request", str(e), status_code=400)
    total = await _sg.count_ship_group_templates()
    rows = await _sg.list_ship_group_templates(pagination.offset, pagination.limit)
    groups = [JuustagramShipGroupTemplate(
        ship_group=r["ship_group"], name=r.get("name", ""), background=r.get("background", ""),
        sculpture=r.get("sculpture", ""), sculpture_ii=r.get("sculpture_ii", ""),
        nationality=r.get("nationality", 0), type=r.get("type", 0),
    ) for r in rows]
    return success(data=JuustagramShipGroupListResponse(
        groups=groups,
        meta=PaginationMeta(offset=pagination.offset, limit=pagination.limit, total=total),
    ).dict())


async def ship_group_detail(request: Request):
    try:
        sg = parse_path_uint32(request.path_params.get("id", ""), "ship group id")
    except ValueError as e:
        return error("bad_request", str(e), status_code=400)
    r = await _sg.get_ship_group_template(sg)
    if r is None:
        return error("not_found", "juustagram ship group not found", status_code=404)
    return success(data=JuustagramShipGroupTemplate(
        ship_group=r["ship_group"], name=r.get("name", ""), background=r.get("background", ""),
        sculpture=r.get("sculpture", ""), sculpture_ii=r.get("sculpture_ii", ""),
        nationality=r.get("nationality", 0), type=r.get("type", 0),
    ).dict())


async def create_ship_group(request: Request):
    try:
        body = await request.json()
    except Exception:
        return error("bad_request", "invalid payload", status_code=400)
    req = JuustagramShipGroupTemplate(**body)
    name = req.name.strip() if req.name else ""
    background = req.background.strip() if req.background else ""
    sculpture = req.sculpture.strip() if req.sculpture else ""
    sculpture_ii = req.sculpture_ii.strip() if req.sculpture_ii else ""
    if req.ship_group == 0:
        return error("bad_request", "ship_group is required", status_code=400)
    if not name:
        return error("bad_request", "name is required", status_code=400)
    if not background:
        return error("bad_request", "background is required", status_code=400)
    if not sculpture:
        return error("bad_request", "sculpture is required", status_code=400)
    if not sculpture_ii:
        return error("bad_request", "sculpture_ii is required", status_code=400)
    await _sg.create_ship_group_template(req.ship_group, name, background, sculpture, sculpture_ii, req.nationality, req.type)
    return success(data=None)


async def update_ship_group(request: Request):
    try:
        body = await request.json()
    except Exception:
        return error("bad_request", "invalid payload", status_code=400)
    req = JuustagramShipGroupTemplate(**body)
    name = req.name.strip() if req.name else ""
    background = req.background.strip() if req.background else ""
    sculpture = req.sculpture.strip() if req.sculpture else ""
    sculpture_ii = req.sculpture_ii.strip() if req.sculpture_ii else ""
    if req.ship_group == 0:
        return error("bad_request", "ship_group is required", status_code=400)
    if not name:
        return error("bad_request", "name is required", status_code=400)
    if not background:
        return error("bad_request", "background is required", status_code=400)
    if not sculpture:
        return error("bad_request", "sculpture is required", status_code=400)
    if not sculpture_ii:
        return error("bad_request", "sculpture_ii is required", status_code=400)
    existing = await _sg.get_ship_group_template(req.ship_group)
    if existing is None:
        return error("not_found", "juustagram ship group not found", status_code=404)
    await _sg.update_ship_group_template(req.ship_group, name, background, sculpture, sculpture_ii, req.nationality, req.type)
    return success(data=None)


async def delete_ship_group(request: Request):
    try:
        body = await request.json()
    except Exception:
        return error("bad_request", "invalid payload", status_code=400)
    sg = body.get("ship_group", 0)
    if not sg:
        return error("bad_request", "ship_group is required", status_code=400)
    if not await _sg.delete_ship_group_template(sg):
        return error("not_found", "juustagram ship group not found", status_code=404)
    return success(data=None)


async def list_language(request: Request):
    prefix = request.query_params.get("prefix", "").strip()
    rows = await _lang.list_languages(prefix if prefix else None)
    entries = [JuustagramLanguage(key=r["key"], value=r["value"]) for r in rows]
    return success(data=JuustagramLanguageListResponse(entries=entries).dict())


async def language_detail(request: Request):
    key = request.path_params.get("key", "")
    if not key:
        return error("bad_request", "language key is required", status_code=400)
    r = await _lang.get_language(key)
    if r is None:
        return error("not_found", "language entry not found", status_code=404)
    return success(data=JuustagramLanguage(key=key, value=r["value"]).dict())


async def create_language(request: Request):
    try:
        body = await request.json()
    except Exception:
        return error("bad_request", "invalid payload", status_code=400)
    req = JuustagramLanguage(**body)
    key = req.key.strip() if req.key else ""
    value = req.value.strip() if req.value else ""
    if not key:
        return error("bad_request", "key is required", status_code=400)
    if not value:
        return error("bad_request", "value is required", status_code=400)
    await _lang.create_language(key, value)
    return success(data=None)


async def update_language(request: Request):
    try:
        body = await request.json()
    except Exception:
        return error("bad_request", "invalid payload", status_code=400)
    req = JuustagramLanguage(**body)
    key = req.key.strip() if req.key else ""
    value = req.value.strip() if req.value else ""
    if not key:
        return error("bad_request", "key is required", status_code=400)
    if not value:
        return error("bad_request", "value is required", status_code=400)
    existing = await _lang.get_language(key)
    if existing is None:
        return error("not_found", "language entry not found", status_code=404)
    await _lang.update_language(key, value)
    return success(data=None)


async def delete_language(request: Request):
    try:
        body = await request.json()
    except Exception:
        return error("bad_request", "invalid payload", status_code=400)
    key = body.get("key", "").strip()
    if not key:
        return error("bad_request", "key is required", status_code=400)
    if not await _lang.delete_language(key):
        return error("not_found", "language entry not found", status_code=404)
    return success(data=None)


async def list_messages(request: Request):
    commander, err_resp = await _load_commander(request)
    if err_resp:
        return err_resp
    try:
        pagination = parse_pagination(request)
    except ValueError as e:
        return error("bad_request", str(e), status_code=400)
    total = await _tmpl.count_templates()
    rows = await _tmpl.list_templates(pagination.offset, pagination.limit)
    now = int(datetime.datetime.now(datetime.timezone.utc).timestamp())
    messages = []
    for r in rows:
        state = await _get_message_state(commander["commander_id"], r["id"], now)
        messages.append(_build_message(r, state))
    return success(data=JuustagramMessageListResponse(
        messages=messages,
        meta=PaginationMeta(offset=pagination.offset, limit=pagination.limit, total=total),
    ).dict())


async def message_detail(request: Request):
    commander, err_resp = await _load_commander(request)
    if err_resp:
        return err_resp
    try:
        message_id = parse_path_uint32(request.path_params.get("message_id", ""), "message id")
    except ValueError as e:
        return error("bad_request", str(e), status_code=400)
    r = await _tmpl.get_template(message_id)
    if r is None:
        return error("not_found", "juustagram message not found", status_code=404)
    now = int(datetime.datetime.now(datetime.timezone.utc).timestamp())
    state = await _get_message_state(commander["commander_id"], message_id, now)
    msg = _build_message(r, state)
    return success(data=JuustagramMessageResponse(message=msg).dict())


async def update_message(request: Request):
    commander, err_resp = await _load_commander(request)
    if err_resp:
        return err_resp
    try:
        message_id = parse_path_uint32(request.path_params.get("message_id", ""), "message id")
    except ValueError as e:
        return error("bad_request", str(e), status_code=400)
    try:
        body = await request.json()
    except Exception:
        return error("bad_request", "invalid payload", status_code=400)
    read = body.get("read")
    like = body.get("like")
    now = int(datetime.datetime.now(datetime.timezone.utc).timestamp())
    state = await _get_message_state(commander["commander_id"], message_id, now)
    if read is not None:
        state["is_read"] = 1 if read else 0
    if like is not None:
        if like:
            if state["is_good"] == 0:
                state["is_good"] = 1
                state["good_count"] += 1
        else:
            if state["is_good"] == 1:
                state["is_good"] = 0
                if state["good_count"] > 0:
                    state["good_count"] -= 1
    state["updated_at"] = now
    await _ms.upsert_message_state(
        commander["commander_id"], message_id,
        state["is_read"], state["is_good"], state["good_count"], now,
    )
    r = await _tmpl.get_template(message_id)
    msg = _build_message(r, state)
    return success(data=JuustagramMessageResponse(message=msg).dict())


async def list_message_states(request: Request):
    commander, err_resp = await _load_commander(request)
    if err_resp:
        return err_resp
    rows = await _ms.list_message_states_by_commander(commander["commander_id"])
    states = [JuustagramMessageState(
        message_id=r["message_id"], is_read=r.get("is_read", 0),
        is_good=r.get("is_good", 0), good_count=r.get("good_count", 0),
        updated_at=r.get("updated_at", 0),
    ) for r in rows]
    return success(data=JuustagramMessageStateListResponse(states=states).dict())


async def message_state_detail(request: Request):
    commander, err_resp = await _load_commander(request)
    if err_resp:
        return err_resp
    try:
        message_id = parse_path_uint32(request.path_params.get("message_id", ""), "message id")
    except ValueError as e:
        return error("bad_request", str(e), status_code=400)
    r = await _ms.get_message_state(commander["commander_id"], message_id)
    if r is None:
        now = int(datetime.datetime.now(datetime.timezone.utc).timestamp())
        state = JuustagramMessageState(message_id=message_id, is_read=0, is_good=0, good_count=0, updated_at=now)
        return success(data=JuustagramMessageStateResponse(state=state).dict())
    state = JuustagramMessageState(
        message_id=r["message_id"], is_read=r.get("is_read", 0),
        is_good=r.get("is_good", 0), good_count=r.get("good_count", 0),
        updated_at=r.get("updated_at", 0),
    )
    return success(data=JuustagramMessageStateResponse(state=state).dict())


async def update_message_state(request: Request):
    commander, err_resp = await _load_commander(request)
    if err_resp:
        return err_resp
    try:
        message_id = parse_path_uint32(request.path_params.get("message_id", ""), "message id")
    except ValueError as e:
        return error("bad_request", str(e), status_code=400)
    try:
        body = await request.json()
    except Exception:
        return error("bad_request", "invalid payload", status_code=400)
    req = JuustagramMessageStateUpdateRequest(**body)
    await _ms.upsert_message_state(
        commander["commander_id"], message_id,
        req.is_read, req.is_good, req.good_count, req.updated_at,
    )
    return success(data=None)


async def delete_message_state(request: Request):
    commander, err_resp = await _load_commander(request)
    if err_resp:
        return err_resp
    try:
        message_id = parse_path_uint32(request.path_params.get("message_id", ""), "message id")
    except ValueError as e:
        return error("bad_request", str(e), status_code=400)
    await _ms.delete_message_state(commander["commander_id"], message_id)
    return success(data=None)


async def list_player_discuss(request: Request):
    commander, err_resp = await _load_commander(request)
    if err_resp:
        return err_resp
    rows = await _pd.list_player_discusses(commander["commander_id"])
    entries = [JuustagramPlayerDiscussEntry(
        message_id=r["message_id"], discuss_id=r.get("discuss_id", 0),
        option_index=r.get("option_index", 0), npc_reply_id=r.get("npc_reply_id", 0),
        comment_time=r.get("comment_time", 0),
    ) for r in rows]
    return success(data=JuustagramPlayerDiscussListResponse(entries=entries).dict())


async def get_player_discuss(request: Request):
    commander, err_resp = await _load_commander(request)
    if err_resp:
        return err_resp
    try:
        discuss_id = parse_path_uint32(request.path_params.get("discuss_id", ""), "discuss id")
    except ValueError as e:
        return error("bad_request", str(e), status_code=400)
    r = await _pd.get_player_discuss(commander["commander_id"], discuss_id)
    if r is None:
        return error("not_found", "player discuss not found", status_code=404)
    return success(data=JuustagramPlayerDiscussEntry(
        message_id=r["message_id"], discuss_id=r["discuss_id"],
        option_index=r.get("option_index", 0), npc_reply_id=r.get("npc_reply_id", 0),
        comment_time=r.get("comment_time", 0),
    ).dict())


async def update_player_discuss(request: Request):
    commander, err_resp = await _load_commander(request)
    if err_resp:
        return err_resp
    try:
        discuss_id = parse_path_uint32(request.path_params.get("discuss_id", ""), "discuss id")
    except ValueError as e:
        return error("bad_request", str(e), status_code=400)
    try:
        body = await request.json()
    except Exception:
        return error("bad_request", "invalid payload", status_code=400)
    req = JuustagramPlayerDiscussUpdateRequest(**body)
    existing = await _pd.get_player_discuss(commander["commander_id"], discuss_id)
    if existing is None:
        return error("not_found", "player discuss not found", status_code=404)
    await _pd.update_player_discuss(commander["commander_id"], discuss_id, req.option_index, req.npc_reply_id, req.comment_time)
    return success(data=None)


async def discuss_message(request: Request):
    commander, err_resp = await _load_commander(request)
    if err_resp:
        return err_resp
    try:
        discuss_id = parse_path_uint32(request.path_params.get("discuss_id", ""), "discuss id")
    except ValueError as e:
        return error("bad_request", str(e), status_code=400)
    try:
        body = await request.json()
    except Exception:
        return error("bad_request", "invalid payload", status_code=400)
    option_index = body.get("option_index", 0)
    npc_reply_id = body.get("npc_reply_id", 0)
    comment_time = body.get("comment_time", 0)
    message_id = body.get("discuss_id", 0)
    await _pd.create_player_discuss(commander["commander_id"], message_id, discuss_id, option_index, npc_reply_id, comment_time)
    return success(data=None)


async def list_player_groups(request: Request):
    commander, err_resp = await _load_commander(request)
    if err_resp:
        return err_resp
    group_rows = await _grp.list_groups_by_commander(commander["commander_id"])
    group_ids = [g["id"] for g in group_rows]
    chat_rows_map = {}
    if group_ids:
        cg_rows = await _cg.list_chat_groups_by_group_record(commander["commander_id"], group_ids)
        for cg in cg_rows:
            gri = cg["group_record_id"]
            chat_rows_map.setdefault(gri, []).append(cg)
    reply_map = {}
    all_cg_ids = [cg["id"] for cgs in chat_rows_map.values() for cg in cgs]
    if all_cg_ids:
        reply_rows = await _reply.list_replies_by_chat_group_ids(all_cg_ids)
        for rp in reply_rows:
            cgri = rp["chat_group_record_id"]
            reply_map.setdefault(cgri, []).append(rp)
    groups = []
    for g in group_rows:
        chat_groups = []
        for cg in chat_rows_map.get(g["id"], []):
            reply_list = [JuustagramReply(
                sequence=rp["sequence"], key=rp.get("key", 0), value=rp.get("value", 0),
            ) for rp in reply_map.get(cg["id"], [])]
            chat_groups.append(JuustagramChatGroup(
                chat_group_id=cg["chat_group_id"], op_time=cg.get("op_time", 0),
                read_flag=cg.get("read_flag", 0), reply_list=reply_list,
            ))
        groups.append(JuustagramGroup(
            group_id=g["group_id"], skin_id=g.get("skin_id", 0),
            favorite=g.get("favorite", 0), cur_chat_group=g.get("cur_chat_group", 0),
            chat_groups=chat_groups,
        ))
    return success(data=JuustagramGroupListResponse(groups=groups).dict())


async def get_player_group(request: Request):
    commander, err_resp = await _load_commander(request)
    if err_resp:
        return err_resp
    try:
        group_id = parse_path_uint32(request.path_params.get("group_id", ""), "group id")
    except ValueError as e:
        return error("bad_request", str(e), status_code=400)
    g = await _grp.get_group(commander["commander_id"], group_id)
    if g is None:
        return error("not_found", "group not found", status_code=404)
    cg_rows = await _cg.list_chat_groups_by_group_record(commander["commander_id"], [g["id"]])
    chat_groups = []
    for cg in cg_rows:
        reply_rows = await _reply.list_replies_by_chat_group(cg["id"])
        reply_list = [JuustagramReply(sequence=rp["sequence"], key=rp.get("key", 0), value=rp.get("value", 0)) for rp in reply_rows]
        chat_groups.append(JuustagramChatGroup(
            chat_group_id=cg["chat_group_id"], op_time=cg.get("op_time", 0),
            read_flag=cg.get("read_flag", 0), reply_list=reply_list,
        ))
    return success(data=JuustagramGroup(
        group_id=g["group_id"], skin_id=g.get("skin_id", 0),
        favorite=g.get("favorite", 0), cur_chat_group=g.get("cur_chat_group", 0),
        chat_groups=chat_groups,
    ).dict())


async def create_player_group(request: Request):
    commander, err_resp = await _load_commander(request)
    if err_resp:
        return err_resp
    try:
        body = await request.json()
    except Exception:
        return error("bad_request", "invalid payload", status_code=400)
    req = JuustagramGroupCreateRequest(**body)
    await _grp.create_group(commander["commander_id"], req.group_id, req.skin_id, req.favorite, req.chat_group_id)
    return success(data=None)


async def update_player_group(request: Request):
    commander, err_resp = await _load_commander(request)
    if err_resp:
        return err_resp
    try:
        group_id = parse_path_uint32(request.path_params.get("group_id", ""), "group id")
    except ValueError as e:
        return error("bad_request", str(e), status_code=400)
    try:
        body = await request.json()
    except Exception:
        return error("bad_request", "invalid payload", status_code=400)
    req = JuustagramGroupUpdateRequest(**body)
    fields = {}
    if req.skin_id is not None:
        fields["skin_id"] = req.skin_id
    if req.favorite is not None:
        fields["favorite"] = req.favorite
    if req.cur_chat_group is not None:
        fields["cur_chat_group"] = req.cur_chat_group
    if not fields:
        return error("bad_request", "no updates provided", status_code=400)
    await _grp.update_group_dynamic(commander["commander_id"], group_id, **fields)
    return success(data=None)


async def delete_player_group(request: Request):
    commander, err_resp = await _load_commander(request)
    if err_resp:
        return err_resp
    try:
        group_id = parse_path_uint32(request.path_params.get("group_id", ""), "group id")
    except ValueError as e:
        return error("bad_request", str(e), status_code=400)
    await _grp.delete_group(commander["commander_id"], group_id)
    return success(data=None)


async def create_chat_group(request: Request):
    commander, err_resp = await _load_commander(request)
    if err_resp:
        return err_resp
    try:
        group_id = parse_path_uint32(request.path_params.get("group_id", ""), "group id")
    except ValueError as e:
        return error("bad_request", str(e), status_code=400)
    try:
        body = await request.json()
    except Exception:
        return error("bad_request", "invalid payload", status_code=400)
    req = JuustagramChatGroupCreateRequest(**body)
    g = await _grp.get_group(commander["commander_id"], group_id)
    if g is None:
        return error("not_found", "group not found", status_code=404)
    record_id = g["id"]
    await _cg.create_chat_group(commander["commander_id"], record_id, req.chat_group_id, req.op_time)
    await _grp.update_group_dynamic(commander["commander_id"], group_id, cur_chat_group=req.chat_group_id)
    return success(data=None)


async def delete_chat_group(request: Request):
    commander, err_resp = await _load_commander(request)
    if err_resp:
        return err_resp
    try:
        chat_group_id = parse_path_uint32(request.path_params.get("chat_group_id", ""), "chat group id")
    except ValueError as e:
        return error("bad_request", str(e), status_code=400)
    await _cg.delete_chat_group(commander["commander_id"], chat_group_id)
    return success(data=None)


async def create_chat_reply(request: Request):
    commander, err_resp = await _load_commander(request)
    if err_resp:
        return err_resp
    try:
        chat_group_id = parse_path_uint32(request.path_params.get("chat_group_id", ""), "chat group id")
    except ValueError as e:
        return error("bad_request", str(e), status_code=400)
    try:
        body = await request.json()
    except Exception:
        return error("bad_request", "invalid payload", status_code=400)
    req = JuustagramChatReplyRequest(**body)
    cg = await _cg.get_chat_group(commander["commander_id"], chat_group_id)
    if cg is None:
        return error("not_found", "chat group not found", status_code=404)
    next_seq = (await _reply.get_max_reply_sequence(cg["id"])) + 1
    await _reply.create_reply(cg["id"], next_seq, req.chat_id, req.value)
    return success(data=None)


async def delete_chat_reply(request: Request):
    commander, err_resp = await _load_commander(request)
    if err_resp:
        return err_resp
    try:
        chat_group_id = parse_path_uint32(request.path_params.get("chat_group_id", ""), "chat group id")
        sequence = parse_path_uint32(request.path_params.get("sequence", ""), "sequence")
    except ValueError as e:
        return error("bad_request", str(e), status_code=400)
    await _reply.delete_reply(commander["commander_id"], chat_group_id, sequence)
    return success(data=None)


async def mark_chat_groups_read(request: Request):
    commander, err_resp = await _load_commander(request)
    if err_resp:
        return err_resp
    try:
        body = await request.json()
    except Exception:
        return error("bad_request", "invalid payload", status_code=400)
    req = JuustagramChatReadRequest(**body)
    await _cg.mark_chat_groups_read(commander["commander_id"], req.chat_group_ids if req.chat_group_ids else None)
    return success(data=None)


async def _load_commander(request: Request):
    try:
        commander_id = int(request.path_params.get("player_id", ""))
    except (ValueError, TypeError):
        return None, error("bad_request", "invalid commander id", status_code=400)
    row = await get_commander(commander_id)
    if row is None:
        return None, error("not_found", "commander not found", status_code=404)
    return row, None


async def _get_message_state(commander_id, message_id, now):
    r = await _ms.get_message_state(commander_id, message_id)
    if r is None:
        return {"is_read": 0, "is_good": 0, "good_count": 0, "updated_at": now}
    return {
        "is_read": r.get("is_read", 0),
        "is_good": r.get("is_good", 0),
        "good_count": r.get("good_count", 0),
        "updated_at": r.get("updated_at", now),
    }


def _build_message(template, state):
    return JuustagramMessage(
        id=template["id"],
        time=template.get("time", 0),
        text=template.get("name", ""),
        picture=template.get("picture_persist", ""),
        oalist_pic="",
        player_discuss=[],
        npc_discuss=[],
        npc_reply=[],
        good=state.get("good_count", 0),
        is_good=state.get("is_good", 0),
        is_read=state.get("is_read", 0),
    )
