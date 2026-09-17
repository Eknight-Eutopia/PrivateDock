import asyncio


def send_trophy_progress_update(client, progress_updates: list) -> None:
    if not progress_updates:
        return
    seen = set()
    from src.protobuf import protobuf
    msg = protobuf.SC_17002()
    for row in progress_updates:
        trophy_id = row.get("trophy_id", 0) if isinstance(row, dict) else getattr(row, "trophy_id", 0)
        if trophy_id == 0 or trophy_id in seen:
            continue
        seen.add(trophy_id)
        if isinstance(row, dict):
            msg.progress_list.append(protobuf.ACHIEVEMENT_INFO(
                id=row["trophy_id"],
                progress=row["progress"],
                timestamp=row.get("timestamp", 0) or 0,
            ))
        else:
            msg.progress_list.append(protobuf.ACHIEVEMENT_INFO(
                id=row.trophy_id,
                progress=row.progress,
                timestamp=getattr(row, "timestamp", 0) or 0,
            ))
    if not msg.progress_list:
        return
    asyncio.create_task(client.send_message(17002, msg))


def send_collection_ship_group_update(client, ship_group_id: int) -> None:
    from src.protobuf import protobuf
    from src.answer.commander_collection import _load_ship_stats
    from src.answer.evaluate_ship import _count_ship_hearts

    cid = client.commander.commander_id if client.commander else 0
    stats = _load_ship_stats(cid)
    matched = next((s for s in stats if s["id"] == ship_group_id), None)
    if matched:
        si = protobuf.SHIP_STATISTICS_INFO(
            id=matched["id"],
            star=matched["star"],
            heart_flag=matched["heart_flag"],
            heart_count=matched["heart_count"],
            marry_flag=matched["marry_flag"],
            intimacy_max=matched["intimacy_max"],
            lv_max=matched["lv_max"],
        )
    else:
        si = protobuf.SHIP_STATISTICS_INFO(
            id=ship_group_id,
            star=1,
            heart_flag=1,
            heart_count=_count_ship_hearts(ship_group_id),
            marry_flag=0,
            intimacy_max=5000,
            lv_max=1,
        )

    msg = protobuf.SC_17004()
    msg.ship_info.CopyFrom(si)
    asyncio.create_task(client.send_message(17004, msg))
