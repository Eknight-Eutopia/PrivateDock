import asyncio
import time
from typing import Optional

from src.connection.client import Client
from src.protobuf import protobuf
from src.db.store import get_default_store
from src.logger.logger import log_event, LOG_LEVEL_DEBUG, LOG_LEVEL_ERROR, LOG_LEVEL_INFO
from .helpers import propose_ship_db


def handle_propose_ship(buffer: bytes, client: Client) -> tuple[int, int, Optional[Exception]]:
    try:
        payload = protobuf.CS_12032()
        payload.ParseFromString(buffer)
    except Exception as e:
        return 0, 12033, e

    commander_id = client.commander.commander_id
    ship_id = payload.ship_id

    log_event("Dock", "Propose", f"uid={commander_id} has proposed ship id={ship_id}", LOG_LEVEL_DEBUG)

    success, err_msg = propose_ship_db(commander_id, ship_id)
    if not success:
        log_event("Dock", "Propose", f"uid={commander_id} propose ship id={ship_id} failed: {err_msg}", LOG_LEVEL_ERROR)
        response = protobuf.SC_12033()
        response.result = 1
        response.time = int(time.time())
        asyncio.create_task(client.send_message(12033, response))
        return 0, 12033, None

    response = protobuf.SC_12033()
    response.result = 0
    response.time = int(time.time())
    asyncio.create_task(client.send_message(12033, response))
    # Server-authoritative task progress: making a Promise/Oath advances
    # "Make a Promise to any ship" (sub_type 1015) and the possession sync
    # covers any proposed-ship state.
    try:
        from src.answer.task_handlers import schedule_emit, schedule_possession_sync
        schedule_emit(client, 1015, 0, 1)
        schedule_possession_sync(client)
    except Exception:
        pass
    return 0, 12033, None


def handle_confirm_ship(_buffer: bytes, client: Client) -> tuple[int, int, Optional[Exception]]:
    commander_id = client.commander.commander_id
    try:
        from .helpers import grant_marriage_furniture
        granted = grant_marriage_furniture(commander_id)
        if granted:
            log_event("Dock", "Propose", f"uid={commander_id} marriage furniture granted: {granted}", LOG_LEVEL_INFO)
    except Exception as e:
        log_event("Dock", "Propose", f"uid={commander_id} marriage furniture grant failed: {e}", LOG_LEVEL_ERROR)

    response = protobuf.SC_12046()
    response.result = 0
    asyncio.create_task(client.send_message(12046, response))
    return 0, 12046, None


def handle_rename_proposed_ship(buffer: bytes, client: Client) -> tuple[int, int, Optional[Exception]]:
    try:
        payload = protobuf.CS_12034()
        payload.ParseFromString(buffer)
    except Exception as e:
        return 0, 12035, e

    commander_id = client.commander.commander_id
    ship_id = payload.ship_id
    new_name = payload.name

    response = protobuf.SC_12035()
    response.result = 1

    store = get_default_store()
    row = store.fetchrow(
        "SELECT id, propose, custom_name, change_name_timestamp FROM owned_ships "
        "WHERE id = $1 AND owner_id = $2 AND deleted_at IS NULL",
        ship_id, commander_id,
    )
    if row is None:
        asyncio.create_task(client.send_message(12035, response))
        return 0, 12035, None

    if not row["propose"]:
        asyncio.create_task(client.send_message(12035, response))
        return 0, 12035, None

    change_name_ts = row["change_name_timestamp"]
    if change_name_ts is not None:
        import datetime
        cooldown_end = change_name_ts + datetime.timedelta(days=30)
        if datetime.datetime.utcnow() < cooldown_end:
            response.result = 4
            asyncio.create_task(client.send_message(12035, response))
            return 0, 12035, None

    store.execute(
        "UPDATE owned_ships SET custom_name = $1, change_name_timestamp = NOW() WHERE id = $2 AND owner_id = $3",
        new_name, ship_id, commander_id,
    )
    response.result = 0
    asyncio.create_task(client.send_message(12035, response))
    return 0, 12035, None
