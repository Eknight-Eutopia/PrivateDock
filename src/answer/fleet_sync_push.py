import asyncio
import json

from src.protobuf import protobuf


def push_fleet_sync(client, fleet) -> None:
    if fleet is None:
        raise ValueError("fleet is required")

    cid = getattr(getattr(client, "commander", None), "commander_id", None)
    if cid is not None:
        from src.orm.fleet import get_fleet_by_game_id
        target_gid = fleet if isinstance(fleet, int) else getattr(fleet, "game_id", None)
        if target_gid is not None:
            f = get_fleet_by_game_id(cid, int(target_gid))
            if f is not None:
                fleet = f

    game_id = getattr(fleet, "game_id", None) or getattr(fleet, "id", 1)
    name = getattr(fleet, "name", "") or ""

    raw_ships = getattr(fleet, "ship_list", [])
    if isinstance(raw_ships, str):
        try:
            raw_ships = json.loads(raw_ships)
        except Exception:
            raw_ships = []
    ship_list = [int(s) for s in (raw_ships or []) if str(s).isdigit()]

    raw_meow = getattr(fleet, "meowfficer_list", [])
    if isinstance(raw_meow, str):
        try:
            raw_meow = json.loads(raw_meow)
        except Exception:
            raw_meow = []

    group = protobuf.GROUPINFO_P12(
        id=int(game_id),
        name=str(name),
        ship_list=ship_list,
    )
    if isinstance(raw_meow, list):
        for pos, mid in enumerate(raw_meow, start=1):
            if pos in (1, 2) and mid and int(mid) > 0:
                c = protobuf.COMMANDERSINFO(pos=pos, id=int(mid))
                group.commanders.append(c)

    resp = protobuf.SC_12106()
    resp.group.CopyFrom(group)
    asyncio.create_task(client.send_message(12106, resp))
