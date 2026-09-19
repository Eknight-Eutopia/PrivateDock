from __future__ import annotations

from typing import Any

from fastapi import Request

from src.api.response import error, ok
from src.db.store import decode_json_value, get_default_store
from src.orm.mail import create_mail_attachment_sync, create_mail_sync
from src.orm.active_commander import get_active_client


_ITEM_CONFIG_CATEGORY = "sharecfgdata/item_data_statistics.json"
_VALID_ATTACHMENT_TYPES = {1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 12, 13, 14, 15, 17, 19, 21, 22, 23, 24, 25, 31}
# Ship templates at or above this id are shadow/enemy-only variants (for
# example the duplicate Specialized Bulin templates 900314/900377/900495).
_NPC_SHIP_TEMPLATE_ID_MIN = 900000


def _limit(request: Request, default: int = 20, maximum: int = 50) -> int:
    try:
        value = int(request.query_params.get("limit", str(default)))
    except (TypeError, ValueError):
        value = default
    return max(1, min(value, maximum))


def _query(request: Request) -> str:
    return request.query_params.get("q", "").strip()


def _pattern(query: str) -> str:
    return f"%{query}%"


async def search_target_players(request: Request):
    query = _query(request)
    if not query:
        return ok({"players": []})
    store = get_default_store()
    limit = _limit(request)
    rows = store.fetch(
        "SELECT commander_id, name, level, account_id FROM commanders "
        "WHERE LOWER(name) LIKE LOWER($1) OR CAST(commander_id AS TEXT) LIKE $1 "
        "ORDER BY commander_id LIMIT $2",
        _pattern(query),
        limit,
    )
    return ok({
        "players": [
            {
                "commander_id": int(row["commander_id"]),
                "name": row.get("name") or "",
                "level": int(row.get("level") or 0),
                "account_id": int(row.get("account_id") or 0),
            }
            for row in rows
        ]
    })


async def _item_icons(ids: list[int]) -> dict[int, str]:
    if not ids:
        return {}
    store = get_default_store()
    rows = store.fetch(
        "SELECT key, data FROM config_entries WHERE category = $1 AND key = ANY($2)",
        _ITEM_CONFIG_CATEGORY,
        [str(item_id) for item_id in ids],
    )
    icons = {}
    for row in rows:
        data = decode_json_value(row["data"]) or {}
        icons[int(row["key"])] = str(data.get("icon") or "")
    return icons


async def search_catalog(request: Request):
    category = request.query_params.get("category", "item").strip().lower()
    query = _query(request)
    limit = _limit(request)
    pattern = _pattern(query)
    store = get_default_store()
    if category == "resource":
        rows = store.fetch(
            "SELECT id, name FROM resources WHERE LOWER(name) LIKE LOWER($1) OR CAST(id AS TEXT) LIKE $1 "
            "ORDER BY id LIMIT $2",
            pattern,
            limit,
        )
        entries = [
            {"attachment_type": 1, "item_id": int(row["id"]), "name": row["name"] or "", "rarity": 0, "icon": ""}
            for row in rows
        ]
    elif category == "ship":
        rows = store.fetch(
            "SELECT template_id, name, rarity_id FROM ships "
            "WHERE template_id < $3 "
            "AND (LOWER(name) LIKE LOWER($1) OR CAST(template_id AS TEXT) LIKE $1) "
            "ORDER BY template_id LIMIT $2",
            pattern,
            limit,
            _NPC_SHIP_TEMPLATE_ID_MIN,
        )
        entries = [
            {"attachment_type": 4, "item_id": int(row["template_id"]), "name": row["name"] or "", "rarity": int(row["rarity_id"] or 0), "icon": ""}
            for row in rows
        ]
    elif category == "skin":
        rows = store.fetch(
            "SELECT id, name FROM skins WHERE LOWER(name) LIKE LOWER($1) OR CAST(id AS TEXT) LIKE $1 "
            "ORDER BY id LIMIT $2",
            pattern,
            limit,
        )
        entries = [
            {"attachment_type": 7, "item_id": int(row["id"]), "name": row["name"] or "", "rarity": 0, "icon": ""}
            for row in rows
        ]
    else:
        item_rows = store.fetch(
            "SELECT id, name, rarity, type, virtual_type FROM items "
            "WHERE LOWER(name) LIKE LOWER($1) OR CAST(id AS TEXT) LIKE $1 "
            "ORDER BY id LIMIT $2",
            pattern,
            limit,
        )
        found_ids = {int(row["id"]) for row in item_rows}
        if len(item_rows) < limit:
            icon_rows = store.fetch(
                "SELECT key FROM config_entries WHERE category = $1 "
                "AND LOWER(CAST(data AS TEXT)) LIKE LOWER($2) ORDER BY key LIMIT $3",
                _ITEM_CONFIG_CATEGORY,
                pattern,
                limit - len(item_rows),
            )
            for icon_row in icon_rows:
                try:
                    icon_id = int(icon_row["key"])
                except (TypeError, ValueError):
                    continue
                if icon_id in found_ids:
                    continue
                extra = store.fetchrow(
                    "SELECT id, name, rarity, type, virtual_type FROM items WHERE id = $1",
                    icon_id,
                )
                if extra is not None:
                    item_rows.append(extra)
                    found_ids.add(icon_id)
        icons = await _item_icons([int(row["id"]) for row in item_rows])
        entries = [
            {
                "attachment_type": 2,
                "item_id": int(row["id"]),
                "name": row["name"] or "",
                "rarity": int(row["rarity"] or 0),
                "icon": icons.get(int(row["id"]), ""),
                "item_type": int(row["type"] or 0),
                "virtual_type": int(row["virtual_type"] or 0),
            }
            for row in item_rows
        ]

    return ok({"category": category, "items": entries})


def _parse_attachment(raw: Any) -> tuple[int, int, int] | None:
    if not isinstance(raw, dict):
        return None
    try:
        attachment_type = int(raw.get("type", 0))
        item_id = int(raw.get("item_id", 0))
        quantity = int(raw.get("quantity", 0))
    except (TypeError, ValueError):
        return None
    if attachment_type not in _VALID_ATTACHMENT_TYPES or item_id <= 0 or quantity <= 0:
        return None
    if attachment_type == 4 and item_id >= _NPC_SHIP_TEMPLATE_ID_MIN:
        return None
    return attachment_type, item_id, quantity


async def send_target_mail(request: Request):
    try:
        body = await request.json()
    except Exception:
        return error("bad_request", "invalid request", status_code=400)

    try:
        commander_id = int(body.get("commander_id", 0))
    except (TypeError, ValueError):
        commander_id = 0
    store = get_default_store()
    if commander_id <= 0 or store.fetchrow(
        "SELECT commander_id FROM commanders WHERE commander_id = $1",
        commander_id,
    ) is None:
        return error("not_found", "commander not found", status_code=404)

    title = str(body.get("title") or "").strip()
    mail_body = str(body.get("body") or "").strip()
    sender = str(body.get("sender") or "").strip() or None
    if not title and not mail_body:
        return error("bad_request", "title or body is required", status_code=400)

    raw_attachments = body.get("attachments") or []
    if not isinstance(raw_attachments, list) or len(raw_attachments) > 30:
        return error("bad_request", "attachments must contain at most 30 entries", status_code=400)
    attachments = []
    for raw in raw_attachments:
        parsed = _parse_attachment(raw)
        if parsed is None:
            return error("bad_request", "invalid attachment", status_code=400)
        attachments.append(parsed)

    mail_id = create_mail_sync(commander_id, title, mail_body, sender)
    for attachment_type, item_id, quantity in attachments:
        create_mail_attachment_sync(mail_id, attachment_type, item_id, quantity)

    # Update an online target immediately. The client badge is driven by
    # SC_30001.unread_number; without this push a WebUI-created mail is only
    # visible after relogin. Offline players naturally receive it on next login.
    target_client = get_active_client(commander_id)
    if target_client is not None:
        try:
            from src.answer.mailbox import push_mail_count_sync
            push_mail_count_sync(target_client)
        except Exception:
            pass

    return ok({"mail_id": mail_id, "attachment_count": len(attachments)})
