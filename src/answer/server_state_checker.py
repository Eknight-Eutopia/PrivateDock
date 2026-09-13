import asyncio
from typing import Optional

from src.config.config import current as get_config
from src.connection.client import Client
from src.logger.logger import log_event, LOG_LEVEL_WARN
from src.protobuf import protobuf


def handle_server_state_check(
    _buffer: bytes, client: Client,
) -> tuple[int, int, Optional[Exception]]:
    cfg = get_config()
    from .server_status_cache import get_server_status_cache
    from .servers import build_server_info
    statuses = get_server_status_cache(cfg.servers)
    server_list = build_server_info(cfg.servers, statuses)
    import src.answer.servers as sv_mod
    sv_mod._servers = server_list
    log_event("Server", "SC_10019", f"sending {len(server_list)} servers", LOG_LEVEL_WARN)
    response = protobuf.SC_10019()
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
    asyncio.create_task(client.send_message(10019, response))
    return 0, 10019, None
