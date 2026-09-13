import time
from typing import Optional

from src.connection.client import Client
from src.connection.server import generate_packet_header
from src.protobuf import protobuf

from src.orm import event_collection as ec


def _send_fail(client: Client, result: int):
    msg = protobuf.SC_13008(result=result)
    data = msg.SerializeToString()
    client.write_to_buffer(generate_packet_header(13008, data, client.packet_index) + data)


def handle_event_give_up(buffer: bytes, client: Client) -> tuple[int, int, Optional[Exception]]:
    try:
        payload = protobuf.CS_13007()
        payload.ParseFromString(buffer)
    except Exception as e:
        return 0, 13008, e

    collection_id = payload.id
    if collection_id == 0:
        _send_fail(client, 1)
        return 0, 13008, None

    now = int(time.time())
    template = _load_collection_template(collection_id)
    if isinstance(template, Exception):
        return 0, 13008, template
    if template is not None:
        over_time = template.get("over_time", 0)
        if over_time > 0 and now >= over_time:
            _send_fail(client, 3)
            return 0, 13008, None

    # The client sends the template id; only a started (state=1) commission can
    # Be given up in any state (available offer or in-progress commission).
    row = ec.get_commission_by_template_sync(
        client.commander.commander_id, collection_id
    )
    if row is None:
        _send_fail(client, 2)
        return 0, 13008, None

    # Effective deadline: for an in-progress commission the completion time
    # (finish_time) is authoritative; otherwise the template's over_time (for
    # limited-time/event commissions) or the row's availability window.
    if row.state == ec.STATE_STARTED:
        deadline = row.finish_time or 0
    else:
        over_time = template.get("over_time", 0) if template else 0
        deadline = over_time if over_time > 0 else (row.expires_at or 0)

    expired = deadline > 0 and now >= deadline

    if expired:
        # Time ran out: the commission is gone.
        ec.delete_commission_sync(row.id)
    else:
        # Still valid: free the ships and return it to the available pool.
        from src.answer.event_collection_spawn import (
            DAILY_EXPIRE_MIN_SECONDS,
            DAILY_EXPIRE_MAX_SECONDS,
        )
        import random
        window = random.randint(DAILY_EXPIRE_MIN_SECONDS, DAILY_EXPIRE_MAX_SECONDS)
        ec.update_commission_sync(
            row.id,
            state=ec.STATE_AVAILABLE,
            start_time=0,
            finish_time=0,
            ship_ids=[],
            expires_at=now + window,
        )

    _send_fail(client, 0)
    return 0, 13008, None


def _load_collection_template(collection_id: int):
    from src.orm.config_entry import get_config_entry
    from src.db.store import NotFoundError
    try:
        raw = get_config_entry("ShareCfg/collection_template.json", str(collection_id))
    except NotFoundError:
        return None
    except Exception as e:
        return e
    if isinstance(raw, dict):
        return raw
    if hasattr(raw, "data"):
        raw = raw.data
    if isinstance(raw, dict):
        return raw
    try:
        import json
        return json.loads(raw) if isinstance(raw, str) else dict(raw)
    except Exception:
        return None
