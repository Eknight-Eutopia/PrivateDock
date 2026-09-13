from __future__ import annotations

import json
import os
from typing import Optional

from src.logger.logger import log_event, LOG_LEVEL_INFO

DATA_DIR = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "..", "data"))

# Server-owned config files (build pools/times, requisition list, drop overrides ...)
# live inside the repo: <PrivateDock>/configurations/
CONFIGURATIONS_DIR = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "..", "configurations"))

order = [
    "Items", "Buffs", "Ships", "Skins", "Resources", "Pools",
    "Requisition", "BuildTimes", "ShopOffers", "Weapons", "Equipments",
    "Skills", "Configs", "ServerCfg", "ServerActivities", "JuustagramTemplates", "JuustagramNpcTemplates",
    "JuustagramLanguage", "JuustagramShipGroups",
]


def get_privatedock_data(region: str, file: str):
    if region:
        file_path = os.path.join(DATA_DIR, region, file)
    else:
        file_path = os.path.join(DATA_DIR, file)
    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)
        #print(data)
        print(type(data))
        print(file_path)
        if isinstance(data, dict):
            data.pop('all', None)
        return data


def get_configuration_data(file: str):
    file_path = os.path.join(CONFIGURATIONS_DIR, file)
    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)
        if isinstance(data, dict):
            data.pop('all', None)
        return data


def list_privatedock_data_files(region: str, directory: str) -> list[str]:
    dir_path = os.path.join(DATA_DIR, region, directory)
    if not os.path.isdir(dir_path):
        return []
    files = []
    for name in os.listdir(dir_path):
        file_path = os.path.join(dir_path, name)
        if os.path.isfile(file_path) and name.endswith(".json"):
            files.append(f"{directory}/{name}")
    return files


def filter_config_files(files: list[str], prefixes: Optional[list[str]], include: Optional[list[str]]) -> list[str]:
    allowed: set[str] = set()
    for f in files:
        name = f
        if name.startswith("ShareCfg/"):
            name = name[len("ShareCfg/"):]
        if name.startswith("GameCfg/"):
            name = name[len("GameCfg/"):]
        if prefixes:
            for prefix in prefixes:
                if name.startswith(prefix):
                    allowed.add(f)
                    break
    if include:
        for f in include:
            allowed.add(f)
    return list(allowed)


def config_entry_key(raw, index: int) -> str:
    if isinstance(raw, dict):
        for field in ("id", "ID", "Id", "key", "Key", "level", "Level", "map", "Map"):
            value = raw.get(field)
            if value is not None:
                key = _parse_config_key(value)
                if key is not None:
                    return key
    elif isinstance(raw, str):
        try:
            d = json.loads(raw)
            if isinstance(d, dict):
                for field in ("id", "ID", "Id", "key", "Key", "level", "Level", "map", "Map"):
                    value = d.get(field)
                    if value is not None:
                        key = _parse_config_key(value)
                        if key is not None:
                            return key
        except (json.JSONDecodeError, ValueError):
            pass
    return str(index)


def _parse_config_key(value) -> Optional[str]:
    if isinstance(value, str):
        return value if value else None
    if isinstance(value, (int, float)):
        return str(int(value))
    return None


def update_all_data(region: str):
    log_event("GameData", "Updating", "Updating all game data.. this may take a while.", LOG_LEVEL_INFO)
    from src.misc.update_data_importers import update_all_data_sqlc
    update_all_data_sqlc(region)
