import asyncio
import json
import traceback
from typing import Optional

from src.connection.client import Client
from src.logger.logger import log_event, LOG_LEVEL_ERROR, LOG_LEVEL_WARN
from src.orm.commander import (
    aincrement_commander_exchange_count,
    atry_decrement_commander_exchange_count,
)
from src.orm.config_entry import afetch_config_entry_data
from src.protobuf import protobuf

# Client: EN/const.lua -> REGULAR_BUILD_POOL_EXCHANGE_ID = 1
REGULAR_BUILD_POOL_EXCHANGE_ID = 1
EXCHANGE_CONFIG_CATEGORY = "ShareCfg/ship_data_create_exchange.json"

# Fallback copy of the EN client's ship_data_create_exchange[1] (the 400-build
# UR-exchange pool). Used only when config_entries lacks the imported row; the
# config_entries value (imported from data/ by
# scripts/import_wishing_well_configs.py) is authoritative when present.
FALLBACK_EXCHANGE_CONFIG = {
    "exchange_request": 400,
    "exchange_ship_id": [
        105171, 307081, 301291, 405031, 718011,
        205131, 305101, 107101, 207071, 405051,
    ],
}


def _decode_config_entry(raw) -> Optional[dict]:
    if isinstance(raw, (bytes, bytearray)):
        raw = raw.decode()
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except Exception:
            return None
    if isinstance(raw, dict) and raw.get("exchange_ship_id"):
        return raw
    return None


async def _load_regular_exchange_config() -> dict:
    """ship_data_create_exchange[REGULAR_BUILD_POOL_EXCHANGE_ID] as config dict."""
    try:
        raw = await afetch_config_entry_data(
            EXCHANGE_CONFIG_CATEGORY, REGULAR_BUILD_POOL_EXCHANGE_ID
        )
    except Exception as e:
        log_event("ExchangeShip", "ConfigLoadError",
                  f"failed to read {EXCHANGE_CONFIG_CATEGORY}: {e}", LOG_LEVEL_ERROR)
        raw = None
    data = _decode_config_entry(raw)
    if data is None:
        log_event("ExchangeShip", "ConfigFallback",
                  f"no usable {EXCHANGE_CONFIG_CATEGORY}[{REGULAR_BUILD_POOL_EXCHANGE_ID}] "
                  "in config_entries, using built-in fallback", LOG_LEVEL_WARN)
        return FALLBACK_EXCHANGE_CONFIG
    return data


def handle_exchange_ship(
    buffer: bytes, client: Client,
) -> tuple[int, int, Optional[Exception]]:
    payload = protobuf.CS_12047()
    payload.ParseFromString(buffer)
    asyncio.create_task(_do_exchange_ship(client, payload.ship_tid))
    return 0, 12048, None


async def _do_exchange_ship(client: Client, ship_tid: int):
    """Regular build pool UR exchange: after `exchange_request` (400) builds the
    player picks one of `exchange_ship_id` ships; the counter is then reset by
    the request amount. Client flow: EN/controller/command/activity/
    buildpoolregularexchangecommand.lua (gates on BuildShipProxy
    regularExchangeCount from SC_12024, applies the SC_12048 drop_list)."""
    cid = client.commander.commander_id
    try:
        cfg = await _load_regular_exchange_config()
        request = int(cfg.get("exchange_request") or 400)
        allowed = {int(t) for t in (cfg.get("exchange_ship_id") or [])}

        if ship_tid not in allowed:
            log_event("ExchangeShip", "Rejected",
                      f"cid={cid} ship_tid={ship_tid} not in exchange pool {sorted(allowed)}",
                      LOG_LEVEL_WARN)
            await client.send_message(12048, protobuf.SC_12048(result=2))
            return

        # Atomic decrement: only succeeds when the player still has enough
        # builds banked (prevents double-claim from racing requests).
        row = await atry_decrement_commander_exchange_count(cid, request)
        if not row:
            await client.send_message(12048, protobuf.SC_12048(result=1))
            return

        try:
            from src.orm.owned_ship import add_ship
            new_ship = add_ship(cid, ship_tid)
        except Exception as e:
            # Refund the consumed counter so the player can retry.
            await aincrement_commander_exchange_count(cid, request)
            log_event("ExchangeShip", "AddShipError",
                      f"cid={cid} ship_tid={ship_tid}: {e}\n{traceback.format_exc()}",
                      LOG_LEVEL_ERROR)
            await client.send_message(12048, protobuf.SC_12048(result=3))
            return

        response = protobuf.SC_12048(result=0)
        drop = protobuf.DROPINFO()
        drop.type = 4  # DROP_TYPE_SHIP
        drop.id = ship_tid
        drop.number = 1
        response.drop_list.append(drop)
        await client.send_message(12048, response)
        log_event("ExchangeShip", "Exchanged",
                  f"cid={cid} ship_tid={ship_tid} cost={request} "
                  f"remaining={row['exchange_count']} new_ship_id={new_ship.id}")

        # BayProxy.on(12042) is what actually adds the ship to the dock view.
        push = protobuf.SC_12042()
        # Full SHIPINFO snapshot (skills, equip slots, ...) from the single
        # shipinfo builder — the old minimal builder omitted equips/strengths.
        from src.answer.shipinfo.builder import build_ship_info, load_shipinfo_context
        context = load_shipinfo_context(cid, [new_ship.id])
        push.ship_list.append(build_ship_info(new_ship, context))
        await client.send_message(12042, push)

        try:
            from src.answer.task_handlers import schedule_emit, schedule_possession_sync
            schedule_emit(client, 193, 0, 1)
            schedule_possession_sync(client)
        except Exception:
            pass
    except Exception as e:
        log_event("ExchangeShip", "Error",
                  f"cid={cid}: {e}\n{traceback.format_exc()}", LOG_LEVEL_ERROR)
        try:
            await client.send_message(12048, protobuf.SC_12048(result=3))
        except Exception:
            pass

