from fastapi import Request
from src.api.response.response import ok as success, error
from src.api.types import *


async def status(_request: Request):
    from src.connection.server import get_instance
    server = get_instance()
    if not server:
        payload = ServerStatusResponse()
        return success(data=payload.model_dump())
    import time
    uptime = time.monotonic() - (server.start_time or time.monotonic())
    payload = ServerStatusResponse(
        name=getattr(server, "name", ""),
        commit="",
        running=True,
        accepting=server.is_accepting_connections,
        maintenance=server.maintenance_enabled,
        uptime_sec=int(uptime),
        uptime_human=f"{int(uptime)}s",
        client_count=server.client_count() if hasattr(server, "client_count") else 0,
    )
    return success(data=payload.model_dump())


async def start(_request: Request):
    from src.connection.server import get_instance
    server = get_instance()
    if server and hasattr(server, "set_accepting_connections"):
        server.set_accepting_connections(True)
    return success(data=None)


async def stop(_request: Request):
    from src.connection.server import get_instance
    server = get_instance()
    if server and hasattr(server, "set_accepting_connections"):
        server.set_accepting_connections(False)
    return success(data=None)


async def restart(_request: Request):
    from src.connection.server import get_instance
    server = get_instance()
    if server and hasattr(server, "set_accepting_connections"):
        server.set_accepting_connections(False)
        server.set_accepting_connections(True)
    return success(data=None)


async def update_maintenance(request: Request):
    try:
        body = await request.json()
    except Exception:
        return error("bad_request", "invalid request", status_code=400)
    req = ServerMaintenanceUpdate(**body)
    from src.connection.server import get_instance
    server = get_instance()
    if server and hasattr(server, "set_maintenance"):
        server.set_maintenance(req.enabled)
    payload = ServerMaintenanceResponse(enabled=req.enabled)
    return success(data=payload.model_dump())


async def maintenance(_request: Request):
    from src.connection.server import get_instance
    server = get_instance()
    enabled = False
    if server and hasattr(server, "maintenance_enabled"):
        enabled = server.maintenance_enabled
    payload = ServerMaintenanceResponse(enabled=enabled)
    return success(data=payload.model_dump())


async def config(_request: Request):
    from src.config.config import Config
    cfg = Config()
    payload = ServerConfigResponse(
        bind_address=getattr(cfg, "bind_address", ""),
        port=getattr(cfg, "port", 0),
        region=getattr(cfg, "region", ""),
    )
    return success(data=payload.model_dump())


async def update_config(request: Request):
    try:
        body = await request.json()
    except Exception:
        return error("bad_request", "invalid request", status_code=400)
    req = ServerConfigUpdate(**body)
    if not req.bind_address.strip():
        return error("bad_request", "bind_address is required", status_code=400)
    if req.port < 1 or req.port > 65535:
        return error("bad_request", "port must be between 1 and 65535", status_code=400)
    from src.config.config import Config
    cfg = Config()
    cfg.bind_address = req.bind_address
    cfg.port = req.port
    cfg.region = req.region
    return success(data=None)


async def stats(_request: Request):
    from src.connection.server import get_instance
    server = get_instance()
    count = server.client_count() if server and hasattr(server, "client_count") else 0
    payload = ServerStatsResponse(client_count=count)
    return success(data=payload.dict())


async def metrics(_request: Request):
    from src.connection.server import get_instance
    server = get_instance()
    if not server:
        return success(data=ServerMetricsResponse().dict())
    clients = server.list_clients() if hasattr(server, "list_clients") else []
    payload = ServerMetricsResponse(
        client_count=len(clients),
        queue_max=0,
        queue_blocks=0,
        handler_errors=0,
        write_errors=0,
        packets_per_sec=0.0,
    )
    return success(data=payload.dict())


async def connections(_request: Request):
    from src.connection.server import get_instance
    server = get_instance()
    clients = server.list_clients() if server and hasattr(server, "list_clients") else []
    summaries = []
    for c in clients:
        summaries.append(ConnectionSummary(
            hash=getattr(c, "hash", 0),
            remote_addr=str(getattr(c, "remote_addr", "")),
            connected_at=str(getattr(c, "connected_at", "")),
            commander_id=getattr(c, "commander_id", 0),
        ))
    return success(data=[s.dict() for s in summaries])


async def connection_detail(request: Request):
    try:
        conn_id = str(request.path_params.get("id"))
        hash_val = int(conn_id)
    except (ValueError, TypeError):
        return error("bad_request", "invalid connection id", status_code=400)
    from src.connection.server import get_instance
    server = get_instance()
    if not server or not hasattr(server, "find_client"):
        return error("not_found", "connection not found", status_code=404)
    client = server.find_client(hash_val)
    if client is None:
        return error("not_found", "connection not found", status_code=404)
    payload = ConnectionDetail(
        hash=getattr(client, "hash", 0),
        remote_addr=str(getattr(client, "remote_addr", "")),
        connected_at=str(getattr(client, "connected_at", "")),
        commander_id=getattr(client, "commander_id", 0),
    )
    return success(data=payload.dict())


async def disconnect_connection(request: Request):
    try:
        conn_id = str(request.path_params.get("id"))
        hash_val = int(conn_id)
    except (ValueError, TypeError):
        return error("bad_request", "invalid connection id", status_code=400)
    from src.connection.server import get_instance
    server = get_instance()
    if not server or not hasattr(server, "find_client") or not hasattr(server, "remove_client"):
        return error("not_found", "connection not found", status_code=404)
    client = server.find_client(hash_val)
    if client is None:
        return error("not_found", "connection not found", status_code=404)
    server.remove_client(client)
    return success(data=None)


async def uptime(_request: Request):
    from src.connection.server import get_instance
    server = get_instance()
    import time
    uptime_sec = 0
    if server and server.start_time:
        uptime_sec = int(time.monotonic() - server.start_time)
    payload = ServerUptimeResponse(
        uptime_sec=uptime_sec,
        uptime_human=f"{uptime_sec}s",
    )
    return success(data=payload.model_dump())
