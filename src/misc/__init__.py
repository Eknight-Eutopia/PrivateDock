from __future__ import annotations

import json
import os
import pickle
import struct
import time
from typing import Optional

from src.config.regions import REGION_GATEWAYS, REGION_PROXIES
from src.logger.logger import log_event, LOG_LEVEL_ERROR, LOG_LEVEL_INFO

DATA_DIR = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "..", "data"))
CACHE_FILE = ".cached_hashes"

_azur_lane_hashes: Optional[list[dict]] = None
_azur_lane_versions: dict[str, str] = {}


def _get_latest_versions() -> dict:
    global _azur_lane_versions
    if _azur_lane_versions:
        return _azur_lane_versions
    versions_path = os.path.join(DATA_DIR, "versions.json")
    try:
        with open(versions_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        _azur_lane_versions = data
        return data
    except Exception as e:
        log_event("GameUpdate", "init", f"failed to read versions.json: {e}", LOG_LEVEL_ERROR)
        return {}


class GameChecksum:
    def __init__(self, category: str, hash_str: str):
        self.category = category
        self.hash = hash_str


def _hash_from_cache(region: str, version: str) -> Optional[list[dict]]:
    try:
        with open(CACHE_FILE, "rb") as f:
            cache = pickle.load(f)
        if cache.get("region") != region:
            return None
        if cache.get("version") != version:
            return None
        return cache.get("hashes")
    except (FileNotFoundError, pickle.UnpicklingError, EOFError):
        return None


def _hash_to_cache(region: str, version: str, hashes: list[dict]):
    try:
        with open(CACHE_FILE, "wb") as f:
            pickle.dump({"region": region, "version": version, "hashes": hashes}, f)
    except Exception as e:
        log_event("GameUpdate", "Cache", f"failed to cache hashes: {e}", LOG_LEVEL_ERROR)


def _fetch_hashes_from_server(region: str) -> Optional[list[dict]]:
    from src.protobuf import protobuf
    from src.connection.server import generate_packet_header
    import asyncio

    gateway_addr = REGION_GATEWAYS.get(region, "")
    if not gateway_addr:
        return None

    try:
        import socket
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(10)
        sock.connect((gateway_addr, 80))

        prompt = protobuf.CS_10800(
            state=59,
            platform="1",
        )
        packet = prompt.SerializeToString()
        header = generate_packet_header(10800, packet, 0)
        sock.sendall(header + packet)

        response_raw = sock.recv(1024)
        sock.close()

        if len(response_raw) < 8:
            return None

        response_data = response_raw[7:]
        sc = protobuf.SC_10801()
        sc.ParseFromString(response_data)

        hashes = []
        for ver in sc.version:
            if "$" not in ver:
                continue
            fields = ver.split("$")
            hashes.append({"category": fields[1], "hash": ver})
        return hashes
    except Exception as e:
        log_event("GameUpdate", "GetHashes", f"failed: {e}", LOG_LEVEL_ERROR)
        return None


def get_game_hashes() -> list[dict]:
    global _azur_lane_hashes
    region = "EN"
    versions = _get_latest_versions()
    version = versions.get(region, "")

    if _azur_lane_hashes is not None:
        return _azur_lane_hashes

    cached = _hash_from_cache(region, version)
    if cached is not None:
        _azur_lane_hashes = cached
        return cached

    hashes = _fetch_hashes_from_server(region)
    if hashes is None:
        _azur_lane_hashes = []
        return []

    _hash_to_cache(region, version, hashes)
    _azur_lane_hashes = hashes
    return hashes


def resolve_region_version(region: str) -> str:
    global _azur_lane_versions
    if _azur_lane_versions:
        entry = _azur_lane_versions.get(region)
        if entry:
            if isinstance(entry, dict):
                return entry.get("version", entry.get("Version", ""))
            return str(entry)
    versions_path = os.path.join(DATA_DIR, "versions.json")
    try:
        with open(versions_path, "r", encoding="utf-8") as f:
            local_versions = json.load(f)
        entry = local_versions.get(region, {})
        if isinstance(entry, dict):
            return entry.get("version", entry.get("Version", ""))
        return str(entry)
    except (FileNotFoundError, json.JSONDecodeError):
        raise ValueError(f"missing version for region {region!r}")


def get_game_hashes_with_update() -> list[dict]:
    hashes = get_game_hashes()
    from src.misc.game_update import update_all_data
    from src.region.region import current as get_region
    update_all_data(get_region())
    return hashes


# Re-export new sub-module APIs
from src.misc.escort import EscortTemplate, EscortMapTemplate, EscortConfig, get_escort_config, load_escort_state, update_escort_timestamps
from src.misc.get_packet_fields import Field, get_packet_fields
from src.misc.git_hash import get_git_hash
