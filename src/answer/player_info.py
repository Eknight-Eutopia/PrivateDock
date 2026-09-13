from typing import Optional

from src.connection.client import Client
from src.connection.server import generate_packet_header
from src.logger.logger import log_event, LOG_LEVEL_ERROR
from src.misc.safe_ts import safe_ts
from src.orm.commander_attire import list_commander_attires
from src.orm.commander_common_flag import list_commander_common_flags
from src.orm.guild_core import get_guild_leave_wait
from src.orm.commander_medal_display import list_commander_medal_displays
from src.orm.commander_attire import list_commander_living_area_covers
from src.orm.resource import list_owned_resources
from src.orm.commander_story import list_commander_stories, list_commander_sound_stories
from src.orm import list_owned_secretaries, count_owned_ships, get_or_create_appreciation_state, update_commander_guide_indices
from src.orm.owned_ship import count_married_ships
from src.protobuf import protobuf


def handle_player_info(
    _buffer: bytes,
    client: Client,
) -> tuple[int, int, Optional[Exception]]:
    commander = client.commander
    if commander is None:
        log_event("Server", "PlayerInfo", f"commander is None for {client.ip}", LOG_LEVEL_ERROR)
        return 0, 11003, ValueError("commander not loaded")
    _ensure_guide_indices(commander)

    cid = commander.commander_id

    secretaries = []
    try:
        rows = list_owned_secretaries(cid)
        for r in rows:
            secretaries.append({
                "id": r.id,
                "ship_id": r.ship_id,
                "skin_id": r.skin_id,
                "secretary_phantom_id": r.secretary_phantom_id,
            })
    except Exception as e:
        log_event("Server", "PlayerInfo", f"Failed to load secretaries: {e}", LOG_LEVEL_ERROR)

    response = protobuf.SC_11003(
        id=commander.commander_id,
        name=commander.name or "",
        level=commander.level,
        exp=commander.exp,
        child_display=commander.child_display,
        attack_count=0,
        win_count=0,
        adv=commander.manifesto or "",
        ship_bag_max=150 + int(getattr(commander, "ship_bag_size", 0) or 0),
        equip_bag_max=300 + int(getattr(commander, "equip_bag_size", 0) or 0),
        gm_flag=0,
        rank=0,
        pvp_attack_count=0,
        pvp_win_count=0,
        collect_attack_count=commander.collect_attack_count,
        guide_index=commander.guide_index,
        buy_oil_count=0,
        chat_room_id=0,
        max_rank=0,
        register_time=0,
        ship_count=_count_owned_ships(cid),
        acc_pay_lv=int(getattr(commander, "acc_pay_lv", 0) or 0),
        guild_wait_time=_load_guild_wait_time(cid),
        chat_msg_ban_time=0,
        commander_bag_max=250 + int(getattr(commander, "commander_bag_size", 0) or 0),
        rmb=999,
        theme_upload_not_allowed_time=0,
        random_ship_mode=commander.random_ship_mode,
        marry_ship=_count_married_ships(cid),
        mail_storeroom_lv=commander.mail_storeroom_lv or 1,
        battle_ui=commander.selected_battle_ui_id or 0,
        new_guide_index=commander.new_guide_index or 1,
        loading_pic_open_flag=commander.loading_pic_open_flag or 0,
        loading_pic_id_list_1=list(commander.loading_pic_id_list_1 or []),
        loading_pic_id_list_2=list(commander.loading_pic_id_list_2 or []),
    )

    display = protobuf.DISPLAYINFO(
        icon=commander.display_icon_id or 0,
        skin=commander.display_skin_id or 0,
        icon_frame=commander.selected_icon_frame_id or 0,
        chat_frame=commander.selected_chat_frame_id or 0,
        icon_theme=commander.display_icon_theme_id or 0,
        marry_flag=0,
        transform_flag=0,
    )
    response.display.CopyFrom(display)

    appreciation = protobuf.APPRECIATIONINFO(music_no=0, music_mode=0)
    cover = protobuf.LIVINGAREA_COVER(id=commander.living_area_cover_id or 0)

    for s in secretaries:
        response.character.append(protobuf.KVDATA(key=s["id"], value=s["secretary_phantom_id"]))

    for res in _load_resources(cid):
        response.resource_list.append(protobuf.RESOURCE(type=res["key"], num=res["value"]))

    if display.icon == 0 and secretaries:
        display.icon = secretaries[0]["ship_id"]
    if display.skin == 0 and secretaries:
        display.skin = secretaries[0]["skin_id"]

    try:
        for flag in _load_common_flags(cid):
            response.flag_list.append(flag.flag_id)
    except Exception as e:
        return 0, 11003, e

    try:
        for st in _load_story_ids(cid):
            response.story_list.append(st.story_id)
    except Exception as e:
        return 0, 11003, e

    try:
        for st in _load_sound_story_ids(cid):
            response.soundstory.append(st.story_id)
    except Exception as e:
        return 0, 11003, e

    try:
        for mid in _load_medal_display(cid):
            response.medal_id.append(mid)
    except Exception as e:
        return 0, 11003, e

    try:
        appreciation_state = _load_or_create_appreciation_state(cid)
    except Exception as e:
        return 0, 11003, e

    appreciation.music_no = appreciation_state.get("music_no", 0)
    appreciation.music_mode = appreciation_state.get("music_mode", 0)
    for cid_val in (appreciation_state.get("cartoon_read_mark") or []):
        response.cartoon_read_mark.append(int(cid_val))
    for cid_val in (appreciation_state.get("cartoon_collect_mark") or []):
        response.cartoon_collect_mark.append(int(cid_val))
    for gid in (appreciation_state.get("gallery_unlocks") or []):
        appreciation.gallerys.append(int(gid))
    for gid in (appreciation_state.get("gallery_favor_ids") or []):
        appreciation.favor_gallerys.append(int(gid))
    for mid in (appreciation_state.get("music_favor_ids") or []):
        appreciation.favor_musics.append(int(mid))

    response.appreciation.CopyFrom(appreciation)

    try:
        attires = _load_attires(cid)
    except Exception as e:
        return 0, 11003, e

    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)
    battle_ui_list = []

    for attire in attires:
        if attire.expires_at is not None and attire.expires_at < now:
            continue
        expires = safe_ts(attire.expires_at)
        from src.consts.attire import (
            ATTIRE_TYPE_ICON_FRAME,
            ATTIRE_TYPE_CHAT_FRAME,
            ATTIRE_TYPE_COMBAT_UI,
        )
        if attire.type == ATTIRE_TYPE_ICON_FRAME:
            response.icon_frame_list.append(protobuf.IDTIMEINFO(id=attire.attire_id, time=expires))
        elif attire.type == ATTIRE_TYPE_CHAT_FRAME:
            response.chat_frame_list.append(protobuf.IDTIMEINFO(id=attire.attire_id, time=expires))
        elif attire.type == ATTIRE_TYPE_COMBAT_UI:
            battle_ui_list.append(attire.attire_id)

    if 0 not in battle_ui_list:
        battle_ui_list.insert(0, 0)
    for bid in battle_ui_list:
        response.battle_ui_list.append(bid)

    if commander.selected_battle_ui_id != 0 and commander.selected_battle_ui_id not in battle_ui_list:
        response.battle_ui_list.append(commander.selected_battle_ui_id)

    try:
        cover_entries = _load_living_area_covers(cid)
    except Exception as e:
        return 0, 11003, e

    living_cover = commander.living_area_cover_id or 0
    if living_cover == 0:
        cover.covers.append(0)
    for cover_entry in cover_entries:
        cover.covers.append(cover_entry.cover_id)
    if living_cover != 0 and living_cover not in cover.covers:
        cover.covers.append(living_cover)
    response.cover.CopyFrom(cover)

    if (hasattr(commander, "name_change_cooldown") and commander.name_change_cooldown and
            not _is_zero_time(commander.name_change_cooldown)):
        cd = protobuf.COOLDOWN(key=1, timestamp=safe_ts(commander.name_change_cooldown))
        response.cd_list.append(cd)

    response.chat_room_id = commander.room_id or 0

    import time as _time
    _t0 = _time.monotonic()
    data = response.SerializeToString()
    header = generate_packet_header(11003, data, client.packet_index)
    client.write_to_buffer(header + data)

    from src.answer.commandermisc.handlers import _build_manual_info_response
    data2 = _build_manual_info_response(client).SerializeToString()
    header2 = generate_packet_header(22300, data2, client.packet_index)
    client.write_to_buffer(header2 + data2)
    from src.logger.logger import log_event, LOG_LEVEL_WARN, LOG_LEVEL_DEBUG
    _ms = (_time.monotonic() - _t0) * 1000.0
    log_event("PlayerInfo", "SC_11003",
              f"cmd={cid} serialize+manual={_ms:.0f}ms (11003={len(data)}B 22300={len(data2)}B)"
              + (" SLOW" if _ms >= 500 else ""),
              LOG_LEVEL_WARN if _ms >= 500 else LOG_LEVEL_DEBUG)
    return 0, 11003, None


def _count_owned_ships(cid: int) -> int:
    try:
        return count_owned_ships(cid)
    except Exception:
        return 0


def _count_married_ships(cid: int) -> int:
    try:
        return count_married_ships(cid)
    except Exception:
        return 0


def _load_guild_wait_time(cid: int) -> int:
    try:
        return get_guild_leave_wait(cid) or 0
    except Exception:
        return 0


def _load_resources(cid: int) -> list[dict]:
    try:
        rows = list_owned_resources(cid)
        return [{"key": r.resource_id, "value": r.amount} for r in rows]
    except Exception:
        return []


def _load_common_flags(cid: int) -> list[str]:
    try:
        return list_commander_common_flags(cid)
    except Exception:
        return []


def _load_story_ids(cid: int) -> list[int]:
    try:
        return list_commander_stories(cid)
    except Exception:
        return []


def _load_sound_story_ids(cid: int) -> list[int]:
    try:
        return list_commander_sound_stories(cid)
    except Exception:
        return []


def _load_medal_display(cid: int) -> list[int]:
    try:
        rows = list_commander_medal_displays(cid)
        return [r.medal_id for r in rows]
    except Exception:
        return []


def _load_or_create_appreciation_state(cid: int) -> dict:
    import json
    try:
        state = get_or_create_appreciation_state(cid)
        def _parse_list(val):
            if isinstance(val, list):
                return val
            if isinstance(val, str):
                try:
                    return json.loads(val) if val else []
                except (json.JSONDecodeError, ValueError):
                    return []
            return []
        return {
            "music_no": state.music_no,
            "music_mode": state.music_mode,
            "gallery_unlocks": _parse_list(state.gallery_unlocks),
            "gallery_favor_ids": _parse_list(state.gallery_favor_ids),
            "music_favor_ids": _parse_list(state.music_favor_ids),
            "cartoon_read_mark": _parse_list(state.cartoon_read_mark),
            "cartoon_collect_mark": _parse_list(state.cartoon_collect_mark),
        }
    except Exception:
        return {
            "music_no": 0, "music_mode": 0,
            "gallery_unlocks": [], "gallery_favor_ids": [],
            "music_favor_ids": [], "cartoon_read_mark": [],
            "cartoon_collect_mark": [],
        }


def _load_attires(cid: int) -> list:
    try:
        return list_commander_attires(cid)
    except Exception:
        return []


def _load_living_area_covers(cid: int) -> list[dict]:
    try:
        return list_commander_living_area_covers(cid)
    except Exception:
        return []


def _ensure_guide_indices(commander) -> None:
    if commander is None:
        return
    guide_index = commander.guide_index
    new_guide_index = commander.new_guide_index
    needs_update = False
    if commander.guide_index == 0:
        guide_index = 1
        needs_update = True
    if commander.new_guide_index == 0:
        new_guide_index = 1
        needs_update = True
    if not needs_update:
        return
    try:
        update_commander_guide_indices(commander.commander_id, guide_index, new_guide_index)
    except Exception:
        pass
    commander.guide_index = guide_index
    commander.new_guide_index = new_guide_index


def _is_zero_time(dt) -> bool:
    from datetime import datetime, timezone
    epoch = datetime.fromtimestamp(0, tz=timezone.utc)
    return dt == epoch
