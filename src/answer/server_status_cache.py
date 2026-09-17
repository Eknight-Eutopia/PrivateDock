import asyncio
import struct
import time
from typing import Optional

from src.config.config import ServerConfig

SERVER_STATUS_CACHE_TTL = 30.0
SERVER_STATUS_TIMEOUT = 2.0
SERVER_TICKET_PREFIX = "=*=*=*=PrivateDock=*=*=*="

SSTATE_OFFLINE = 1

_cache_entries: Optional[dict[int, dict]] = None
_cache_refreshed_at: float = 0.0
_refresh_pending = False


def _now() -> float:
    return time.time()


def _default_entries(servers: list[ServerConfig]) -> dict[int, dict]:
    entries = {}
    for server in servers:
        name = server.name.strip() or server.ip
        entries[server.id] = {
            "name": name,
            "commit": "",
            "state": SSTATE_OFFLINE,
            "server_load": 0,
            "db_load": 0,
        }
    return entries


def get_server_status_cache(servers: list[ServerConfig]) -> dict[int, dict]:
    global _cache_entries, _cache_refreshed_at, _refresh_pending
    if not servers:
        return {}
    now = _now()
    if _cache_entries is not None and (now - _cache_refreshed_at) < SERVER_STATUS_CACHE_TTL:
        return _cache_entries
    if _cache_entries is None:
        _cache_entries = _default_entries(servers)
        _cache_refreshed_at = now
    if not _refresh_pending:
        _refresh_pending = True
        try:
            loop = asyncio.get_running_loop()
            asyncio.run_coroutine_threadsafe(_do_refresh(servers), loop)
        except RuntimeError:
            _refresh_pending = False
    return _cache_entries


async def _do_refresh(servers: list[ServerConfig]) -> None:
    global _cache_entries, _cache_refreshed_at, _refresh_pending
    try:
        new_entries = {}
        for server in servers:
            entry = await _probe_server(server)
            new_entries[server.id] = entry
        _cache_entries = new_entries
        _cache_refreshed_at = _now()
    finally:
        _refresh_pending = False


def _build_probe_packet(server_id: int) -> bytes:
    from src.protobuf import protobuf
    msg = protobuf.CS_10022(
        account_id=0,
        server_ticket=SERVER_TICKET_PREFIX,
        platform="0",
        serverid=server_id,
        check_key="status_probe",
        device_id="",
    )
    payload = msg.SerializeToString()
    body_size = len(payload) + 5
    header = struct.pack("!H", body_size) + b"\x00" + struct.pack("!H", 10022) + struct.pack("!H", 0)
    return header + payload


def _parse_status_response(data: bytes) -> tuple[int, int]:
    if len(data) < 7:
        return 0, 0
    body_size = struct.unpack("!H", data[:2])[0]
    packet_id = struct.unpack("!H", data[3:5])[0]
    if packet_id != 10023:
        return 0, 0
    payload = data[7:body_size]
    from src.protobuf import protobuf
    resp = protobuf.SC_10023()
    try:
        resp.ParseFromString(payload)
    except Exception:
        return 0, 0
    return resp.server_load, resp.db_load


async def _probe_server(server: ServerConfig) -> dict:
    from src.logger.logger import log_event, LOG_LEVEL_WARN
    entry = {
        "name": server.name.strip() or server.ip,
        "commit": "",
        "state": SSTATE_OFFLINE,
        "server_load": 0,
        "db_load": 0,
    }
    try:
        packet_data = _build_probe_packet(server.id)
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(server.ip, server.port),
            timeout=SERVER_STATUS_TIMEOUT,
        )
        try:
            writer.write(packet_data)
            await asyncio.wait_for(writer.drain(), timeout=SERVER_STATUS_TIMEOUT)
            size_hdr = await asyncio.wait_for(reader.readexactly(2), timeout=SERVER_STATUS_TIMEOUT)
            total_size = struct.unpack("!H", size_hdr)[0] + 2
            resp_raw = size_hdr + await asyncio.wait_for(
                reader.readexactly(total_size - 2), timeout=SERVER_STATUS_TIMEOUT
            )
            server_load, db_load = _parse_status_response(resp_raw)
            entry["server_load"] = server_load
            entry["db_load"] = db_load
            if server_load >= 80 or db_load >= 80:
                entry["state"] = 3
            else:
                entry["state"] = 0
        except asyncio.TimeoutError:
            log_event("Server", "StatusRefresh",
                      f"status probe timeout for {server.ip}:{server.port}", LOG_LEVEL_WARN)
        finally:
            try:
                writer.close()
            except Exception:
                pass
    except (OSError, asyncio.TimeoutError) as e:
        log_event("Server", "StatusRefresh",
                  f"status probe failed for {server.ip}:{server.port}: {e}", LOG_LEVEL_WARN)
    return entry


def build_server_status_config(client_statuses: dict) -> dict:
    return {
        "code": 0,
        "statuses": client_statuses if isinstance(client_statuses, dict) else {},
    }


def parse_server_status_payload(payload: bytes) -> Optional[dict]:
    try:
        import json
        data = json.loads(payload.decode("utf-8", errors="replace"))
        return data if isinstance(data, dict) else None
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None
