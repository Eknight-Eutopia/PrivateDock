import asyncio
from typing import Optional

from src.auth.password import verify_password, hash_password
from src.config.config import current as get_config
from src.connection.client import Client
from src.orm.commander import create_commander
from src.logger.logger import log_event, LOG_LEVEL_ERROR, LOG_LEVEL_WARN
from src.orm import get_local_account_by_account, get_yostarus_map_by_arg2
from src.orm import update_local_account_password

from .server_ticket import format_server_ticket

LOCAL_LOGIN_RESULT_OK = 0
LOCAL_LOGIN_RESULT_INVALID_ACCOUNT = 1010
LOCAL_LOGIN_RESULT_WRONG_PASSWORD = 1020
LOCAL_LOGIN_RESULT_DATABASE_ERROR = 11


def handle_local_login(
    payload,
    client: Client,
) -> tuple[int, int, Optional[Exception]]:
    if hasattr(payload, "arg1"):
        account = payload.arg1.strip() if payload.HasField("arg1") else ""
        password = payload.arg2 if payload.HasField("arg2") else ""
    else:
        account = payload.get("arg1", "").strip()
        password = payload.get("arg2", "")
    if not account:
        _send_local_login_failure(client, LOCAL_LOGIN_RESULT_INVALID_ACCOUNT)
        return 0, 10021, None

    asyncio.create_task(_do_local_login(account, password, client))
    return 0, 10021, None


async def _do_local_login(account: str, password: str, client: Client):
    try:
        local = await get_local_account_by_account(account)
    except Exception as e:
        log_event("Server", "SC_10021", f"failed to fetch local account: {e}", LOG_LEVEL_ERROR)
        _send_local_login_failure(client, LOCAL_LOGIN_RESULT_DATABASE_ERROR)
        return

    if local is None:
        _send_local_login_failure(client, LOCAL_LOGIN_RESULT_INVALID_ACCOUNT)
        return

    try:
        valid = verify_password(local["password"], password)
    except Exception as e:
        err_str = str(e)
        if "Invalid hash" in err_str or "not a valid" in err_str:
            if local["password"] != password:
                _send_local_login_failure(client, LOCAL_LOGIN_RESULT_WRONG_PASSWORD)
                return
            try:
                password_hash = hash_password(password)
            except Exception as hash_err:
                log_event("Server", "SC_10021", f"failed to hash legacy password: {hash_err}", LOG_LEVEL_ERROR)
                _send_local_login_failure(client, LOCAL_LOGIN_RESULT_DATABASE_ERROR)
                return
            try:
                await update_local_account_password(local["arg2"], password_hash)
            except Exception as update_err:
                log_event("Server", "SC_10021", f"failed to update password: {update_err}", LOG_LEVEL_ERROR)
                _send_local_login_failure(client, LOCAL_LOGIN_RESULT_DATABASE_ERROR)
                return
            valid = True
        else:
            log_event("Server", "SC_10021", f"failed to verify password: {err_str}", LOG_LEVEL_ERROR)
            _send_local_login_failure(client, LOCAL_LOGIN_RESULT_DATABASE_ERROR)
            return

    if not valid:
        _send_local_login_failure(client, LOCAL_LOGIN_RESULT_WRONG_PASSWORD)
        return

    client.auth_arg2 = local["arg2"]

    response = {
        "result": LOCAL_LOGIN_RESULT_OK,
        "account_id": 0,
        "server_ticket": format_server_ticket(client.auth_arg2),
        "device": 0,
        "serverlist": [],
    }

    try:
        mapping = await get_yostarus_map_by_arg2(local["arg2"])
        if mapping is not None:
            response["account_id"] = mapping["account_id"]
        else:
            cfg = get_config()
            if cfg.create_player.skip_onboarding:
                try:
                    response["account_id"] = await create_commander(client, local["arg2"], None, [201211])
                except Exception as e:
                    log_event("Server", "SC_10021", f"failed to create commander: {e}", LOG_LEVEL_ERROR)
                    response["result"] = LOCAL_LOGIN_RESULT_DATABASE_ERROR
                    await client.send_message(10021, response)
                    return
            else:
                response["account_id"] = 0
    except Exception as e:
        log_event("Server", "SC_10021", f"failed to fetch account mapping: {e}", LOG_LEVEL_ERROR)
        response["result"] = LOCAL_LOGIN_RESULT_DATABASE_ERROR
        await client.send_message(10021, response)
        return

    try:
        from .servers import build_server_info
        from .server_status_cache import get_server_status_cache
        servers_cfg = get_config().servers
        statuses = get_server_status_cache(servers_cfg)
        response["serverlist"] = build_server_info(servers_cfg, statuses)
    except Exception as e:
        log_event("Server", "SC_10021", f"failed to build server list: {e}", LOG_LEVEL_ERROR)

    log_event("Server", "SC_10021", f"sending {len(response['serverlist'])} servers", LOG_LEVEL_WARN)
    await client.send_message(10021, response)


def _send_local_login_failure(
    client: Client,
    result: int,
) -> None:
    response = {
        "result": result,
        "account_id": 0,
        "server_ticket": format_server_ticket(0),
        "device": 0,
        "serverlist": [],
    }
    asyncio.create_task(client.send_message(10021, response))
