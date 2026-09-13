import asyncio
import json
import time
from typing import Optional

from src.connection.client import Client
from src.orm import backyard_theme_id
from src.orm.backyard import add_backyard_theme_collection, count_backyard_theme_collections, \
    increment_backyard_theme_fav_count
from src.orm.backyard import add_backyard_theme_like, increment_backyard_theme_like_count
from src.orm.backyard import check_backyard_theme_collection_exists, check_backyard_theme_like_exists
from src.orm.backyard import create_backyard_published_theme_version
from src.orm.backyard import delete_backyard_custom_theme_template
from src.orm.backyard import delete_backyard_published_theme_versions_by_theme_id
from src.orm.backyard import get_backyard_custom_theme_template
from src.orm.backyard import get_backyard_published_theme_count
from src.orm.backyard import latest_backyard_published_theme_version
from src.orm.backyard import list_backyard_custom_theme_templates, list_latest_backyard_published_theme_versions
from src.orm.backyard import list_backyard_published_theme_ids_by_page
from src.orm.backyard import list_backyard_theme_collection_upload_times, remove_backyard_theme_collection, \
    decrement_backyard_theme_fav_count
from src.orm.backyard import list_backyard_theme_collections
from src.orm.backyard import upsert_backyard_custom_theme_template
from src.orm.commander_dorm_state import get_or_create_commander_dorm_state
from src.protobuf import protobuf
from .backyard_validation import dorm_static_map_size
from .backyard_validation import validate_furniture_put_list
from src.orm.backyard import latest_backyard_published_theme_version
from src.orm.backyard import insert_backyard_theme_inform

MAX_LEGACY_THEME_LIST_PAYLOAD_BYTES = 65535 - 5
COLLECTION_MAX_COUNT = 30


def handle_get_theme_upload_credentials(_buffer: bytes, client: Client) -> tuple[int, int, Optional[Exception]]:
    packet_id = 19104
    response = protobuf.SC_19104(result=0, access_id="", access_secret="", expire_time=0, security_token="")
    asyncio.create_task(client.send_message(packet_id, response))
    return 0, packet_id, None


def handle_list_custom_theme_templates(buffer: bytes, client: Client) -> tuple[int, int, Optional[Exception]]:
    packet_id = 19106
    payload = protobuf.CS_19105()
    payload.ParseFromString(buffer)

    commander_id = client.commander.commander_id
    try:
        entries = list_backyard_custom_theme_templates(commander_id)
    except Exception as e:
        return 0, packet_id, e

    response = protobuf.SC_19106(result=0)
    for entry in entries:
        response.theme_list.append(_build_dorm_theme_from_custom_template(commander_id, entry))
    asyncio.create_task(client.send_message(packet_id, response))
    return 0, packet_id, None


def handle_list_legacy_theme_templates(buffer: bytes, client: Client) -> tuple[int, int, Optional[Exception]]:
    packet_id = 19108
    payload = protobuf.CS_19107()
    payload.ParseFromString(buffer)

    theme_type = payload.typ
    if theme_type not in (1, 2, 3):
        response = protobuf.SC_19108(result=1)
        asyncio.create_task(client.send_message(packet_id, response))
        return 0, packet_id, None

    try:
        versions = list_latest_backyard_published_theme_versions()
    except Exception:
        response = protobuf.SC_19108(result=1)
        asyncio.create_task(client.send_message(packet_id, response))
        return 0, packet_id, None

    response = _build_legacy_theme_list_response(versions)
    asyncio.create_task(client.send_message(packet_id, response))
    return 0, packet_id, None


def _build_legacy_theme_list_response(versions: list):
    theme_list = []
    for version in versions:
        theme_list.append(_build_dorm_theme_from_published_version(version))
        if len(json.dumps({"result": 0, "theme_list": theme_list})) > MAX_LEGACY_THEME_LIST_PAYLOAD_BYTES:
            theme_list = theme_list[:-1]
            break
    response = protobuf.SC_19108(result=0)
    for t in theme_list:
        response.theme_list.append(t)
    return response


def handle_save_custom_theme_template(buffer: bytes, client: Client) -> tuple[int, int, Optional[Exception]]:
    packet_id = 19110
    payload = protobuf.CS_19109()
    payload.ParseFromString(buffer)

    commander_id = client.commander.commander_id

    try:
        state = get_or_create_commander_dorm_state(commander_id)
    except Exception as e:
        return 0, packet_id, e

    level = state.get("level", 0) if isinstance(state, dict) else getattr(state, "level", 0)
    map_size = dorm_static_map_size(level)

    try:
        validate_furniture_put_list(payload.furniture_put_list, 1, map_size)
    except Exception:
        response = protobuf.SC_19110(result=1)
        asyncio.create_task(client.send_message(packet_id, response))
        return 0, packet_id, None

    stored = []
    for f in payload.furniture_put_list:
        children = []
        for c in f.child:
            child_entry = {"id": c.id, "x": c.x, "y": c.y}
            children.append(child_entry)
        stored.append({
            "id": f.id,
            "x": f.x,
            "y": f.y,
            "dir": f.dir,
            "child": children,
            "parent": f.parent,
            "ship_id": f.shipId,
        })

    try:
        upsert_backyard_custom_theme_template(
            commander_id,
            payload.pos,
            payload.name,
            stored,
            payload.icon_image_md5,
            payload.image_md5,
        )
    except Exception:
        response = protobuf.SC_19110(result=1)
        asyncio.create_task(client.send_message(packet_id, response))
        return 0, packet_id, None

    response = protobuf.SC_19110(result=0)
    asyncio.create_task(client.send_message(packet_id, response))
    return 0, packet_id, None


def handle_publish_custom_theme_template(buffer: bytes, client: Client) -> tuple[int, int, Optional[Exception]]:
    packet_id = 19112
    payload = protobuf.CS_19111()
    payload.ParseFromString(buffer)

    commander_id = client.commander.commander_id
    pos = payload.pos

    try:
        entry = get_backyard_custom_theme_template(commander_id, pos)
    except Exception:
        response = protobuf.SC_19112(result=1)
        asyncio.create_task(client.send_message(packet_id, response))
        return 0, packet_id, None

    upload_time = entry.get("upload_time", 0) if isinstance(entry, dict) else getattr(entry, "upload_time", 0)
    if upload_time == 0:
        published_count = get_backyard_published_theme_count(commander_id)
        if published_count >= 2:
            response = protobuf.SC_19112(result=1)
            asyncio.create_task(client.send_message(packet_id, response))
            return 0, packet_id, None

    name = entry.get("name", "") if isinstance(entry, dict) else getattr(entry, "name", "")
    fur_put = entry.get("furniture_put_list", "") if isinstance(entry, dict) else getattr(entry, "furniture_put_list", "")
    icon_md5 = entry.get("icon_image_md5", "") if isinstance(entry, dict) else getattr(entry, "icon_image_md5", "")
    img_md5 = entry.get("image_md5", "") if isinstance(entry, dict) else getattr(entry, "image_md5", "")

    try:
        create_backyard_published_theme_version(commander_id, pos, name, fur_put, icon_md5, img_md5)
    except Exception:
        response = protobuf.SC_19112(result=1)
        asyncio.create_task(client.send_message(packet_id, response))
        return 0, packet_id, None

    response = protobuf.SC_19112(result=0)
    asyncio.create_task(client.send_message(packet_id, response))
    return 0, packet_id, None


def handle_unpublish_custom_theme_template(buffer: bytes, client: Client) -> tuple[int, int, Optional[Exception]]:
    packet_id = 19126
    payload = protobuf.CS_19125()
    payload.ParseFromString(buffer)

    commander_id = client.commander.commander_id
    pos = payload.pos

    try:
        entry = get_backyard_custom_theme_template(commander_id, pos)
    except Exception:
        response = protobuf.SC_19126(result=1)
        asyncio.create_task(client.send_message(packet_id, response))
        return 0, packet_id, None

    upload_time = entry.get("upload_time", 0) if isinstance(entry, dict) else getattr(entry, "upload_time", 0)
    if upload_time == 0:
        response = protobuf.SC_19126(result=0)
        asyncio.create_task(client.send_message(packet_id, response))
        return 0, packet_id, None

    theme_id = backyard_theme_id(commander_id, pos)
    try:
        delete_backyard_published_theme_versions_by_theme_id(theme_id)
    except Exception:
        response = protobuf.SC_19126(result=1)
        asyncio.create_task(client.send_message(packet_id, response))
        return 0, packet_id, None

    response = protobuf.SC_19126(result=0)
    asyncio.create_task(client.send_message(packet_id, response))
    return 0, packet_id, None


def handle_delete_custom_theme_template(buffer: bytes, client: Client) -> tuple[int, int, Optional[Exception]]:
    packet_id = 19124
    payload = protobuf.CS_19123()
    payload.ParseFromString(buffer)

    commander_id = client.commander.commander_id
    pos = payload.pos

    try:
        delete_backyard_custom_theme_template(commander_id, pos)
        delete_backyard_published_theme_versions_by_theme_id(backyard_theme_id(commander_id, pos))
    except Exception:
        response = protobuf.SC_19124(result=1)
        asyncio.create_task(client.send_message(packet_id, response))
        return 0, packet_id, None

    response = protobuf.SC_19124(result=0)
    asyncio.create_task(client.send_message(packet_id, response))
    return 0, packet_id, None


def handle_list_published_theme_ids(buffer: bytes, client: Client) -> tuple[int, int, Optional[Exception]]:
    packet_id = 19118
    payload = protobuf.CS_19117()
    payload.ParseFromString(buffer)

    try:
        ids = list_backyard_published_theme_ids_by_page(payload.page, payload.num)
    except Exception:
        response = protobuf.SC_19118(result=1)
        asyncio.create_task(client.send_message(packet_id, response))
        return 0, packet_id, None

    response = protobuf.SC_19118(result=0)
    response.theme_id_list.extend(ids)
    asyncio.create_task(client.send_message(packet_id, response))
    return 0, packet_id, None


def handle_list_collected_themes(buffer: bytes, client: Client) -> tuple[int, int, Optional[Exception]]:
    packet_id = 19116
    payload = protobuf.CS_19115()
    payload.ParseFromString(buffer)

    commander_id = client.commander.commander_id
    try:
        entries = list_backyard_theme_collections(commander_id)
    except Exception:
        response = protobuf.SC_19116(result=1)
        asyncio.create_task(client.send_message(packet_id, response))
        return 0, packet_id, None

    response = protobuf.SC_19116(result=0)
    for entry in entries:
        profile = protobuf.DORMTHEME_PROFILE()
        profile.id = entry.get("theme_id", "") if isinstance(entry, dict) else getattr(entry, "theme_id", "")
        profile.upload_time = entry.get("upload_time", 0) if isinstance(entry, dict) else getattr(entry, "upload_time", 0)
        response.theme_profile_list.append(profile)
    asyncio.create_task(client.send_message(packet_id, response))
    return 0, packet_id, None


def handle_get_theme_preview_md5s(buffer: bytes, client: Client) -> tuple[int, int, Optional[Exception]]:
    packet_id = 19132
    payload = protobuf.CS_19131()
    payload.ParseFromString(buffer)

    response = protobuf.SC_19132()
    for theme_id in payload.id_list:
        try:
            ver = latest_backyard_published_theme_version(theme_id)
            icon_md5 = ver.get("icon_image_md5", "") if isinstance(ver, dict) else getattr(ver, "icon_image_md5", "")
            entry = protobuf.THEME_MD5()
            entry.id = theme_id
            entry.md5 = icon_md5
            response.list.append(entry)
        except Exception:
            continue

    asyncio.create_task(client.send_message(packet_id, response))
    return 0, packet_id, None


def handle_get_theme_by_id(buffer: bytes, client: Client) -> tuple[int, int, Optional[Exception]]:
    packet_id = 19114
    payload = protobuf.CS_19113()
    payload.ParseFromString(buffer)

    commander_id = client.commander.commander_id
    theme_id = payload.theme_id

    try:
        ver = latest_backyard_published_theme_version(theme_id)
    except Exception:
        response = protobuf.SC_19114(result=20)
        asyncio.create_task(client.send_message(packet_id, response))
        return 0, packet_id, None

    base_theme = _build_dorm_theme_from_published_version(ver)

    has_fav = False
    has_like = False
    if isinstance(ver, dict):
        upload_time = ver.get("upload_time", 0)
    else:
        upload_time = getattr(ver, "upload_time", 0)

    try:
        has_fav = check_backyard_theme_collection_exists(commander_id, theme_id, upload_time)
    except Exception:
        pass
    try:
        has_like = check_backyard_theme_like_exists(commander_id, theme_id, upload_time)
    except Exception:
        pass

    response = protobuf.SC_19114(result=0, has_fav=has_fav, has_like=has_like)
    response.theme.CopyFrom(base_theme)
    asyncio.create_task(client.send_message(packet_id, response))
    return 0, packet_id, None


def handle_like_theme(buffer: bytes, client: Client) -> tuple[int, int, Optional[Exception]]:
    packet_id = 19122
    payload = protobuf.CS_19121()
    payload.ParseFromString(buffer)

    commander_id = client.commander.commander_id
    try:
        inserted = add_backyard_theme_like(commander_id, payload.theme_id, payload.upload_time)
        if inserted:
            increment_backyard_theme_like_count(payload.theme_id, payload.upload_time)
    except Exception:
        response = protobuf.SC_19122(result=1)
        asyncio.create_task(client.send_message(packet_id, response))
        return 0, packet_id, None

    response = protobuf.SC_19122(result=0)
    asyncio.create_task(client.send_message(packet_id, response))
    return 0, packet_id, None


def handle_collect_theme(buffer: bytes, client: Client) -> tuple[int, int, Optional[Exception]]:
    packet_id = 19120
    payload = protobuf.CS_19119()
    payload.ParseFromString(buffer)

    commander_id = client.commander.commander_id
    try:
        inserted = add_backyard_theme_collection(commander_id, payload.theme_id, payload.upload_time)
        if inserted:
            count = count_backyard_theme_collections(commander_id)
            if count > COLLECTION_MAX_COUNT:
                remove_backyard_theme_collection(commander_id, payload.theme_id)
                response = protobuf.SC_19120(result=1)
                asyncio.create_task(client.send_message(packet_id, response))
                return 0, packet_id, None
            increment_backyard_theme_fav_count(payload.theme_id, payload.upload_time)
    except Exception:
        response = protobuf.SC_19120(result=1)
        asyncio.create_task(client.send_message(packet_id, response))
        return 0, packet_id, None

    response = protobuf.SC_19120(result=0)
    asyncio.create_task(client.send_message(packet_id, response))
    return 0, packet_id, None


def handle_cancel_theme_collection(buffer: bytes, client: Client) -> tuple[int, int, Optional[Exception]]:
    packet_id = 19128
    payload = protobuf.CS_19127()
    payload.ParseFromString(buffer)

    commander_id = client.commander.commander_id
    try:
        upload_times = list_backyard_theme_collection_upload_times(commander_id, payload.theme_id)
        remove_backyard_theme_collection(commander_id, payload.theme_id)
        for ut in upload_times:
            decrement_backyard_theme_fav_count(payload.theme_id, ut)
    except Exception:
        response = protobuf.SC_19128(result=1)
        asyncio.create_task(client.send_message(packet_id, response))
        return 0, packet_id, None

    response = protobuf.SC_19128(result=0)
    asyncio.create_task(client.send_message(packet_id, response))
    return 0, packet_id, None


def handle_report_theme(buffer: bytes, client: Client) -> tuple[int, int, Optional[Exception]]:
    packet_id = 19130
    payload = protobuf.CS_19129()
    payload.ParseFromString(buffer)

    try:
        insert_backyard_theme_inform({
            "reporter_id": client.commander.commander_id,
            "target_id": payload.target_id,
            "target_name": payload.target_name,
            "theme_id": payload.theme_id,
            "theme_name": payload.theme_name,
            "reason": payload.reason,
            "created_at": int(time.time()),
        })
    except Exception:
        response = protobuf.SC_19130(result=1)
        asyncio.create_task(client.send_message(packet_id, response))
        return 0, packet_id, None

    response = protobuf.SC_19130(result=0)
    asyncio.create_task(client.send_message(packet_id, response))
    return 0, packet_id, None


def _build_dorm_theme_from_custom_template(commander_id: int, entry):
    theme = protobuf.DORMTHEME()
    if isinstance(entry, dict):
        theme.id = backyard_theme_id(commander_id, entry.get("pos", 0))
        theme.name = entry.get("name", "")
        theme.user_id = commander_id
        theme.pos = entry.get("pos", 0)
        theme.like_count = 0
        theme.fav_count = 0
        theme.upload_time = entry.get("upload_time", 0)
        theme.icon_image_md5 = entry.get("icon_image_md5", "")
        theme.image_md5 = entry.get("image_md5", "")
    else:
        theme.id = backyard_theme_id(commander_id, entry.pos)
        theme.name = entry.name
        theme.user_id = commander_id
        theme.pos = entry.pos
        theme.like_count = 0
        theme.fav_count = 0
        theme.upload_time = entry.upload_time
        theme.icon_image_md5 = entry.icon_image_md5
        theme.image_md5 = entry.image_md5
    return theme


def _build_dorm_theme_from_published_version(version):
    theme = protobuf.DORMTHEME()
    if isinstance(version, dict):
        theme.id = version.get("theme_id", "")
        theme.name = version.get("name", "")
        theme.user_id = version.get("owner_id", 0)
        theme.pos = version.get("pos", 0)
        theme.like_count = version.get("like_count", 0)
        theme.fav_count = version.get("fav_count", 0)
        theme.upload_time = version.get("upload_time", 0)
        theme.icon_image_md5 = version.get("icon_image_md5", "")
        theme.image_md5 = version.get("image_md5", "")
    else:
        theme.id = version.theme_id
        theme.name = version.name
        theme.user_id = version.owner_id
        theme.pos = version.pos
        theme.like_count = version.like_count
        theme.fav_count = version.fav_count
        theme.upload_time = version.upload_time
        theme.icon_image_md5 = version.icon_image_md5
        theme.image_md5 = version.image_md5
    return theme
