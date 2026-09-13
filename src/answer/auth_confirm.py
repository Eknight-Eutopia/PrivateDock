import asyncio
from typing import Optional

import src.answer.servers as sv_mod
from src.config.config import current as get_config
from src.connection.client import Client
from src.logger.logger import log_event, LOG_LEVEL_ERROR, LOG_LEVEL_WARN
from src.protobuf import protobuf
from .auth_confirm_local import handle_local_login
from .server_status_cache import get_server_status_cache
from .server_ticket import format_server_ticket
from .servers import build_server_info


def handle_auth_confirm(
    buffer: bytes,
    client: Client,
) -> tuple[int, int, Optional[Exception]]:
    payload = protobuf.CS_10020()
    payload.ParseFromString(buffer)

    if payload.login_type == 2:
        return handle_local_login(payload, client)

    try:
        int_arg2 = int(payload.arg2 if payload.HasField("arg2") else "0")
    except (ValueError, TypeError):
        return 0, 10021, ValueError("failed to convert arg2 to int")

    client.auth_arg2 = int_arg2

    asyncio.create_task(_do_auth_confirm(int_arg2, client))
    return 0, 10021, None


async def _do_auth_confirm(int_arg2: int, client: Client):
    from src.orm import get_yostarus_map_by_arg2

    response = protobuf.SC_10021(
        result=0,
        account_id=0,
        server_ticket=format_server_ticket(client.auth_arg2),
        device=0,
    )
    try:
        mapping = await get_yostarus_map_by_arg2(int_arg2)
        if mapping is not None:
            response.account_id = mapping["account_id"]
        else:
            cfg = get_config()
            if cfg.create_player.skip_onboarding:
                from src.orm.commander import create_commander
                response.account_id = await create_commander(client, int_arg2, None, [201211])
            else:
                response.account_id = 0
    except Exception as e:
        log_event("Server", "SC_10021", f"failed to fetch account for arg2 {int_arg2}: {e}", LOG_LEVEL_ERROR)
        response.account_id = 0

    try:
        servers_cfg = get_config().servers
        statuses = get_server_status_cache(servers_cfg)
        server_list = build_server_info(servers_cfg, statuses)
        sv_mod._servers = server_list
        for sv in server_list:
            entry = protobuf.SERVERINFO(
                ids=sv["ids"],
                ip=sv["ip"],
                port=sv["port"],
                state=sv["state"],
                name=sv["name"],
                tag_state=sv.get("tag_state", 0),
                sort=sv.get("sort", 0),
                proxy_ip=sv.get("proxy_ip", ""),
                proxy_port=sv.get("proxy_port", 0),
            )
            response.serverlist.append(entry)

        log_event("Server", "SC_10021", f"sending {len(server_list)} servers", LOG_LEVEL_WARN)
        await client.send_message(10021, response)
    except Exception as e:
        log_event("Server", "SC_10021", f"Error: {e}", LOG_LEVEL_ERROR)
