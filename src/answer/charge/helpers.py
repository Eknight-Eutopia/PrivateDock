from dataclasses import dataclass
from typing import Optional

from src.connection.client import Client
from src.protobuf import protobuf
from src.db.store import get_default_store


@dataclass
class ChargeSuccessEvent:
    shop_id: int = 0
    pay_id: str = ""
    gem: int = 0
    gem_free: int = 0


async def apply_charge_success_event(
    commander_id: int,
    client: Optional[Client],
    event: ChargeSuccessEvent,
) -> Optional[Exception]:
    if event.shop_id == 0 or not event.pay_id:
        return ValueError("invalid charge success event")

    store = get_default_store()

    try:
        # INSERT ... ON CONFLICT DO NOTHING RETURNING doubles as the duplicate
        # guard: a replayed pay_id returns no row and grants nothing.
        row = await store.afetchval(
            "INSERT INTO commander_charge_success_events (commander_id, pay_id) "
            "VALUES ($1, $2) ON CONFLICT (commander_id, pay_id) DO NOTHING "
            "RETURNING commander_id",
            commander_id, event.pay_id,
        )
    except Exception as e:
        return e
    if row is None:
        return None

    # Grant through the orm helpers so the write happens even without a live
    # client (matching the old transactional behaviour); the orm keeps the
    # in-memory resource map of a connected commander in sync itself.
    from src.orm.resource import add_resource

    if event.gem > 0:
        add_resource(commander_id, 4, event.gem)
    if event.gem_free > 0:
        # 14 is the free-gem alias; add_resource deals it into the shared gem
        # wallet via RESOURCE_ALIASES, matching the rest of the codebase.
        add_resource(commander_id, 14, event.gem_free)

    if client is None:
        return None

    response = protobuf.SC_11503()
    response.shop_id = event.shop_id
    response.pay_id = event.pay_id
    response.gem = event.gem
    response.gem_free = event.gem_free
    await client.send_message(11503, response)
    return None
