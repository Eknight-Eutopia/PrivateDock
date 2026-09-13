import asyncio


def push_fleet_sync(client, fleet) -> None:
    if fleet is None:
        raise ValueError("fleet is required")
    push = {"group": _commander_fleet_group_info(fleet)}
    asyncio.create_task(client.send_message(12106, push))


def _commander_fleet_group_info(fleet) -> dict:
    return {
        "id": getattr(fleet, "id", 0),
        "ship_list": getattr(fleet, "ship_list", []),
    }
