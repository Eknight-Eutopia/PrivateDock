import json
from typing import Optional

from src.connection.client import Client
from src.connection.server import generate_packet_header


from src.orm.config_entry import entry_data as _unwrap


def _current_month_key(now) -> int:
    from src.shopreset.framework import monthly_window

    try:
        return monthly_window(now).key
    except Exception:
        return now.year * 100 + now.month


def _has_month_shop_content(entry: dict) -> bool:
    if entry.get("id", 0) != 0:
        return True
    fields = ["core_shop_goods", "blueprint_shop_goods", "blueprint_shop_limit_goods",
              "honormedal_shop_goods", "blueprint_shop_limit_goods_2", "blueprint_shop_goods_2",
              "blueprint_shop_limit_goods_3", "blueprint_shop_goods_3", "blueprint_shop_goods_4",
              "blueprint_shop_limit_goods_4"]
    return any(entry.get(f) for f in fields)


def _select_month_shop_template(entries: list, month: int) -> Optional[dict]:
    templates = []
    for entry_data in entries:
        d = _unwrap(entry_data)
        if isinstance(d, dict) and _has_month_shop_content(d):
            templates.append(d)
        elif isinstance(d, list):
            for item in d:
                if isinstance(item, dict) and _has_month_shop_content(item):
                    templates.append(item)
    if not templates:
        return None
    for t in templates:
        if t.get("id", 0) == month:
            return t
    entries_sorted = sorted(templates, key=lambda x: x.get("id", 0))
    index = (month - 1) % len(entries_sorted)
    return entries_sorted[index]


def _load_month_shop_template(now):
    from src.orm.config_entry import list_config_entries

    entries = list_config_entries("ShareCfg/month_shop_template.json")
    if not entries:
        return None, False
    month = _current_month_key(now) % 100
    template = _select_month_shop_template(entries, month)
    return template, template is not None


def _build_shop_info_list(ids: list, counts: dict) -> list:
    if not ids:
        return None
    entries = []
    for shop_id in ids:
        pay_count = counts.get(shop_id, 0)
        entries.append({"shop_id": shop_id, "pay_count": pay_count})
    return entries


def handle_shop_data(
    _buffer: bytes,
    client: Client,
) -> tuple[int, int, Optional[Exception]]:
    from datetime import datetime, timezone
    from src.protobuf import protobuf
    now = datetime.now(timezone.utc)
    month_key = _current_month_key(now)

    response = protobuf.SC_16200(month=month_key % 100)

    from src.orm.month_shop import list_month_shop_purchase_counts_sync
    try:
        counts = list_month_shop_purchase_counts_sync(client.commander.commander_id, month_key)
    except Exception as e:
        return 0, 16200, e

    template, ok = _load_month_shop_template(now)
    if not ok:
        data = response.SerializeToString()
        header = generate_packet_header(16200, data, client.packet_index)
        client.write_to_buffer(header + data)
        return 0, 16200, None

    blueprints = []
    for field in ["blueprint_shop_goods", "blueprint_shop_limit_goods",
                  "blueprint_shop_goods_2", "blueprint_shop_limit_goods_2",
                  "blueprint_shop_goods_3", "blueprint_shop_limit_goods_3",
                  "blueprint_shop_goods_4", "blueprint_shop_limit_goods_4"]:
        blueprints.extend(template.get(field, []) or [])

    def _add_shop_info_list(field_name, ids, counts_dict):
        if not ids:
            return
        field = getattr(response, field_name)
        for shop_id in ids:
            si = protobuf.SHOPINFO(shop_id=shop_id, pay_count=counts_dict.get(shop_id, 0))
            field.append(si)

    _add_shop_info_list("core_shop_list", template.get("core_shop_goods", []) or [], counts)
    _add_shop_info_list("blue_shop_list", blueprints, counts)
    _add_shop_info_list("normal_shop_list", template.get("honormedal_shop_goods", []) or [], counts)

    data = response.SerializeToString()
    header = generate_packet_header(16200, data, client.packet_index)
    client.write_to_buffer(header + data)
    return 0, 16200, None
