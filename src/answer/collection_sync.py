import asyncio


def send_trophy_progress_update(client, progress_updates: list) -> None:
    if not progress_updates:
        return
    seen = set()
    updates = []
    for row in progress_updates:
        trophy_id = row.get("trophy_id", 0) if isinstance(row, dict) else getattr(row, "trophy_id", 0)
        if trophy_id == 0 or trophy_id in seen:
            continue
        seen.add(trophy_id)
        if isinstance(row, dict):
            updates.append({
                "id": row["trophy_id"],
                "progress": row["progress"],
                "timestamp": row["timestamp"],
            })
        else:
            updates.append({
                "id": row.trophy_id,
                "progress": row.progress,
                "timestamp": row.timestamp,
            })
    if not updates:
        return
    payload = {"progress_list": updates}
    asyncio.create_task(client.send_message(17002, payload))


def send_collection_ship_group_update(client, ship_group_id: int) -> None:
    payload = {"result": 0, "ship_info": {"id": ship_group_id}}
    asyncio.create_task(client.send_message(17004, payload))
