from fastapi import APIRouter, Request

from src.api.handlers.server import (
    status, config, update_config, maintenance, update_maintenance,
    stats, metrics, uptime, connections, connection_detail,
)

router = APIRouter(prefix="/api/v1/server", tags=["server"])


@router.get("/status")
async def server_status():
    from fastapi import Request as FastAPIRequest
    scope = {"type": "http", "query_string": b"", "headers": [], "method": "GET", "path": "", "scheme": "http", "server": ("localhost", 80)}
    return await status(FastAPIRequest(scope, receive=lambda: None))


@router.get("/config")
async def server_config_route():
    from fastapi import Request as FastAPIRequest
    scope = {"type": "http", "query_string": b"", "headers": [], "method": "GET", "path": "", "scheme": "http", "server": ("localhost", 80)}
    return await config(FastAPIRequest(scope, receive=lambda: None))


@router.put("/config")
async def server_update_config_route(req: Request):
    return await update_config(req)


@router.get("/maintenance")
async def server_maintenance_route():
    from fastapi import Request as FastAPIRequest
    scope = {"type": "http", "query_string": b"", "headers": [], "method": "GET", "path": "", "scheme": "http", "server": ("localhost", 80)}
    return await maintenance(FastAPIRequest(scope, receive=lambda: None))


@router.put("/maintenance")
async def server_update_maintenance_route(req: Request):
    return await update_maintenance(req)


@router.get("/stats")
async def server_stats_route():
    from fastapi import Request as FastAPIRequest
    scope = {"type": "http", "query_string": b"", "headers": [], "method": "GET", "path": "", "scheme": "http", "server": ("localhost", 80)}
    return await stats(FastAPIRequest(scope, receive=lambda: None))


@router.get("/metrics")
async def server_metrics_route():
    from fastapi import Request as FastAPIRequest
    scope = {"type": "http", "query_string": b"", "headers": [], "method": "GET", "path": "", "scheme": "http", "server": ("localhost", 80)}
    return await metrics(FastAPIRequest(scope, receive=lambda: None))


@router.get("/uptime")
async def server_uptime_route():
    from fastapi import Request as FastAPIRequest
    scope = {"type": "http", "query_string": b"", "headers": [], "method": "GET", "path": "", "scheme": "http", "server": ("localhost", 80)}
    return await uptime(FastAPIRequest(scope, receive=lambda: None))


@router.get("/connections")
async def server_connections_route():
    from fastapi import Request as FastAPIRequest
    scope = {"type": "http", "query_string": b"", "headers": [], "method": "GET", "path": "", "scheme": "http", "server": ("localhost", 80)}
    return await connections(FastAPIRequest(scope, receive=lambda: None))


@router.get("/connections/{conn_hash}")
async def server_connection_detail_route(req: Request):
    return await connection_detail(req)
