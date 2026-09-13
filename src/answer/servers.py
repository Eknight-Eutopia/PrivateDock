from typing import Optional

from src.config.config import ServerConfig as ConfigServerConfig
from src.connection.client import Client

SERVER_STATE_ONLINE = 0
SERVER_STATE_OFFLINE = 1  # == client Server.STATUS.VINDICATE ("Server Maintenance") — never advertise it
SERVER_STATE_FULL = 2
SERVER_STATE_BUSY = 3

_servers: list[dict] = []


def build_server_info(
    servers: list[ConfigServerConfig],
    statuses: dict[int, dict],
) -> list[dict]:
    output = []
    for i, server in enumerate(servers):
        status = statuses.get(server.id)
        state = SERVER_STATE_ONLINE
        name = server.ip
        if status is not None:
            if status.get("name"):
                name = status["name"]
            state = status.get("state", SERVER_STATE_ONLINE)
            name = _format_server_name(name, status.get("commit", ""))
        else:
            name = _format_server_name(name, "")
        proxy_ip = server.proxy_ip or ""
        proxy_port = server.proxy_port or 0
        info = {
            "ids": [server.id],
            "ip": server.ip,
            "port": server.port,
            "state": state,
            "name": name,
            "tag_state": 0,
            "sort": i + 1,
            "proxy_ip": proxy_ip,
            "proxy_port": proxy_port,
        }
        output.append(info)
    return output


def _format_server_name(name: str, commit: str) -> str:
    trimmed = name.strip()
    if not trimmed:
        trimmed = "Unknown"
    if not commit:
        return trimmed
    return f"{trimmed} ({commit})"


def build_gateway_addr_list(
    servers: list[ConfigServerConfig],
    statuses: dict[int, dict],
) -> list:
    from src.protobuf import protobuf
    output = []
    for server in servers:
        status = statuses.get(server.id)
        desc = server.ip
        if status is not None:
            name = status.get("name", server.ip)
            desc = _format_server_name(name, status.get("commit", ""))
        else:
            desc = _format_server_name(server.ip, "")
        addr = protobuf.LOGIN_ADDR(
            desc=desc,
            ip=server.ip,
            port=server.port,
            proxy_ip=server.proxy_ip or "",
            proxy_port=server.proxy_port or 0,
            type=0,
        )
        output.append(addr)
    return output


def update_server_list(servers_cfg):
    global _servers
    _servers = build_server_info(servers_cfg, {})


def handle_cs8239_http(
    _buffer: bytes,
    client: Client,
) -> tuple[int, int, Optional[Exception]]:
    import asyncio
    import json
    from src.config.config import current as get_config
    from .server_status_cache import get_server_status_cache

    packet_id = 8239
    cfg = get_config()
    statuses = get_server_status_cache(cfg.servers)
    global _servers
    _servers = build_server_info(cfg.servers, statuses)

    json_data = json.dumps(_servers)
    content_length = len(json_data)
    http_header = (
        "HTTP/1.1 200 OK\r\n"
        f"Content-Type: text/plain;charset=utf-8\r\n"
        "Access-Control-Allow-Origin: *\r\n"
        f"Content-Length: {content_length}\r\n"
        "\r\n"
    )
    response_data = http_header.encode("utf-8") + json_data.encode("utf-8")

    async def _do_write():
        client.writer.write(response_data)
        await client.writer.drain()

    asyncio.create_task(_do_write())
    return len(response_data), packet_id, None

handle_write_server_list = handle_cs8239_http
