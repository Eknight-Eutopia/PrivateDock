import time

from src.answer.friend.helpers import (
    friendOperationSuccess, friendOperationFailure, friendOperationMaxed,
    maxFriendCount, friendRecommendationLimit,
    friendBlacklistResultSuccess, friendBlacklistResultInvalidTarget,
    friendBlacklistResultNotFound,
    build_friend_info, build_player_info_p50,
    build_detail_info,
)
from src.db.store import get_default_store
from src.protobuf import protobuf


# ── SearchFriend (50002) ──

async def SearchFriend(buffer: bytes, client) -> tuple:
    request = protobuf.CS_50001()
    request.ParseFromString(buffer)
    keyword = request.keyword.strip()
    response = protobuf.SC_50002(result=1)

    store = get_default_store()
    profile = None

    if request.type == 0:
        if not keyword:
            return await client.send_message(50002, response)
        try:
            commander_id = int(keyword)
        except ValueError:
            return await client.send_message(50002, response)
        row = await store.afetchrow(
            "SELECT c.commander_id, c.name, c.level, c.manifesto, "
            "c.collect_attack_count, "
            "(SELECT COUNT(*) FROM owned_ships WHERE owner_id = c.commander_id AND deleted_at IS NULL) AS ship_count, "
            "c.display_icon_id, c.display_skin_id, c.selected_icon_frame_id, "
            "c.selected_chat_frame_id, c.display_icon_theme_id, "
            "EXTRACT(EPOCH FROM c.last_login) AS last_login_unix "
            "FROM commanders c WHERE c.commander_id = $1",
            commander_id,
        )
        if row:
            profile = dict(row)
    elif request.type == 1:
        if not keyword:
            return await client.send_message(50002, response)
        row = await store.afetchrow(
            "SELECT c.commander_id, c.name, c.level, c.manifesto, "
            "c.collect_attack_count, "
            "(SELECT COUNT(*) FROM owned_ships WHERE owner_id = c.commander_id AND deleted_at IS NULL) AS ship_count, "
            "c.display_icon_id, c.display_skin_id, c.selected_icon_frame_id, "
            "c.selected_chat_frame_id, c.display_icon_theme_id, "
            "EXTRACT(EPOCH FROM c.last_login) AS last_login_unix "
            "FROM commanders c WHERE LOWER(c.name) = LOWER($1)",
            keyword,
        )
        if row:
            profile = dict(row)
    else:
        return await client.send_message(50002, response)

    if profile is None:
        return await client.send_message(50002, response)

    medal_rows = await store.afetch(
        "SELECT medal_id FROM commander_medal_displays WHERE commander_id = $1 ORDER BY medal_id",
        profile["commander_id"],
    )
    medal_ids = [r["medal_id"] for r in medal_rows]

    response.Result = 0
    response.Player = build_detail_info(profile, client, medal_ids)
    return await client.send_message(50002, response)


# ── FriendSearchList (50015) ──

async def FriendSearchList(buffer: bytes, client) -> tuple:
    request = protobuf.CS_50014()
    request.ParseFromString(buffer)
    response = protobuf.SC_50015(player_list=[])
    if request.type != 0:
        return await client.send_message(50015, response)

    store = get_default_store()
    rows = await store.afetch(
        "SELECT c.commander_id, c.name, c.level, c.manifesto, "
        "c.collect_attack_count, "
        "(SELECT COUNT(*) FROM owned_ships WHERE owner_id = c.commander_id AND deleted_at IS NULL) AS ship_count, "
        "c.display_icon_id, c.display_skin_id, c.selected_icon_frame_id, "
        "c.selected_chat_frame_id, c.display_icon_theme_id, "
        "EXTRACT(EPOCH FROM c.last_login) AS last_login_unix "
        "FROM commanders c WHERE c.commander_id != $1 "
        "ORDER BY RANDOM() LIMIT $2",
        client.commander.commander_id, friendRecommendationLimit,
    )
    response.player_list = [build_player_info_p50(dict(r)) for r in rows]
    return await client.send_message(50015, response)


# ── SendFriendRequest (50004) ──

async def SendFriendRequest(buffer: bytes, client) -> tuple:
    request = protobuf.CS_50003()
    request.ParseFromString(buffer)
    response = protobuf.SC_50004(result=friendOperationFailure)
    requester_id = client.commander.commander_id
    target_id = request.id

    if target_id == 0 or target_id == requester_id:
        return await client.send_message(50004, response)

    store = get_default_store()
    exists = await store.fetchval(
        "SELECT 1 FROM commanders WHERE commander_id = $1", target_id,
    )
    if not exists:
        return await client.send_message(50004, response)

    already = await store.afetchrow(
        "SELECT 1 FROM friend_relationships WHERE "
        "(commander_id = $1 AND friend_id = $2) OR (commander_id = $2 AND friend_id = $1) "
        "LIMIT 1",
        requester_id, target_id,
    )
    if already:
        return await client.send_message(50004, response)

    created = False
    existing_req = await store.afetchrow(
        "SELECT 1 FROM friend_requests WHERE requester_id = $1 AND target_id = $2 LIMIT 1",
        requester_id, target_id,
    )
    if not existing_req:
        await store.aexecute(
            "INSERT INTO friend_requests (requester_id, target_id, content, created_at) "
            "VALUES ($1, $2, $3, EXTRACT(EPOCH FROM NOW())::int)",
            requester_id, target_id, request.content,
        )
        created = True

    if created:
        response.Result = friendOperationSuccess
    else:
        response.Result = friendOperationFailure

    n, packet_id, send_err = await client.send_message(50004, response)
    if send_err:
        return n, packet_id, send_err
    if not created or client.server is None:
        return n, packet_id, None

    target_client = client.server.find_client_by_commander(target_id)
    if target_client is None:
        return n, packet_id, None

    requester_row = await store.afetchrow(
        "SELECT commander_id, name, level, display_icon_id, display_skin_id, "
        "selected_icon_frame_id, selected_chat_frame_id, display_icon_theme_id, "
        "EXTRACT(EPOCH FROM last_login) AS last_login_unix FROM commanders WHERE commander_id = $1",
        requester_id,
    )
    if requester_row is None:
        return n, packet_id, None
    requester_profile = dict(requester_row)

    push = protobuf.SC_50005(
        msg=protobuf.MSG_INFO_P50(
            timestamp=int(time.time()),
            player=build_player_info_p50(requester_profile),
            content=request.content,
        ),
    )
    _, _, _ = await target_client.send_message(50005, push)
    return n, packet_id, None


# ── AcceptFriendRequest (50007) ──

async def AcceptFriendRequest(buffer: bytes, client) -> tuple:
    request = protobuf.CS_50006()
    request.ParseFromString(buffer)
    response = protobuf.SC_50007(result=friendOperationFailure)
    target_id = client.commander.commander_id
    requester_id = request.id

    if requester_id == 0 or requester_id == target_id:
        return await client.send_message(50007, response)

    store = get_default_store()
    exists = await store.fetchval(
        "SELECT 1 FROM commanders WHERE commander_id = $1", requester_id,
    )
    if not exists:
        return await client.send_message(50007, response)

    target_count = await store.fetchval(
        "SELECT COUNT(*) FROM friend_relationships WHERE commander_id = $1 OR friend_id = $1", target_id,
    ) or 0
    if target_count >= maxFriendCount:
        response.Result = friendOperationMaxed
        return await client.send_message(50007, response)

    requester_count = await store.fetchval(
        "SELECT COUNT(*) FROM friend_relationships WHERE commander_id = $1 OR friend_id = $1", requester_id,
    ) or 0
    if requester_count >= maxFriendCount:
        response.Result = friendOperationMaxed
        return await client.send_message(50007, response)

    deleted = await store.aexecute(
        "DELETE FROM friend_requests WHERE requester_id = $1 AND target_id = $2",
        requester_id, target_id,
    )
    if deleted is None or (hasattr(deleted, 'lower') and deleted.lower() == 'delete 0'):
        return await client.send_message(50007, response)

    c1, c2 = (min(target_id, requester_id), max(target_id, requester_id))
    await store.aexecute(
        "INSERT INTO friend_relationships (commander_id, friend_id, created_at) "
        "VALUES ($1, $2, $3) ON CONFLICT (commander_id, friend_id) DO NOTHING",
        c1, c2, int(time.time()),
    )

    response.Result = friendOperationSuccess
    n, packet_id, send_err = await client.send_message(50007, response)
    if send_err:
        return n, packet_id, send_err
    if client.server is None:
        return n, packet_id, None

    target_row = await store.afetchrow(
        "SELECT commander_id, name, level, display_icon_id, display_skin_id, "
        "selected_icon_frame_id, selected_chat_frame_id, display_icon_theme_id, "
        "EXTRACT(EPOCH FROM last_login) AS last_login_unix FROM commanders WHERE commander_id = $1",
        target_id,
    )
    requester_row = await store.afetchrow(
        "SELECT commander_id, name, level, display_icon_id, display_skin_id, "
        "selected_icon_frame_id, selected_chat_frame_id, display_icon_theme_id, "
        "EXTRACT(EPOCH FROM last_login) AS last_login_unix FROM commanders WHERE commander_id = $1",
        requester_id,
    )
    if target_row and requester_row:
        target_profile = dict(target_row)
        requester_profile = dict(requester_row)

        acceptor_push = protobuf.SC_50008(player=build_friend_info(requester_profile, client))
        _, _, _ = await client.send_message(50008, acceptor_push)

        requester_client = client.server.find_client_by_commander(requester_id)
        if requester_client:
            requester_push = protobuf.SC_50008(player=build_friend_info(target_profile, requester_client))
            _, _, _ = await requester_client.send_message(50008, requester_push)

    return n, packet_id, None


# ── RejectFriendRequest (50010) ──

async def RejectFriendRequest(buffer: bytes, client) -> tuple:
    request = protobuf.CS_50009()
    request.ParseFromString(buffer)
    response = protobuf.SC_50010(result=friendOperationSuccess)
    target_id = client.commander.commander_id
    requester_id = request.id

    store = get_default_store()
    if requester_id == 0:
        await store.aexecute(
            "DELETE FROM friend_requests WHERE target_id = $1", target_id,
        )
        return await client.send_message(50010, response)

    result = await store.aexecute(
        "DELETE FROM friend_requests WHERE target_id = $1 AND requester_id = $2",
        target_id, requester_id,
    )
    return await client.send_message(50010, response)


# ── DeleteFriend (50012) ──

async def DeleteFriend(buffer: bytes, client) -> tuple:
    request = protobuf.CS_50011()
    request.ParseFromString(buffer)
    target_commander_id = request.id
    response = protobuf.SC_50012(result=1)

    if target_commander_id == 0 or target_commander_id == client.commander.commander_id:
        return await client.send_message(50012, response)

    store = get_default_store()
    result = await store.aexecute(
        "DELETE FROM friend_relationships WHERE (commander_id = $1 AND friend_id = $2) "
        "OR (commander_id = $2 AND friend_id = $1)",
        client.commander.commander_id, target_commander_id,
    )
    if not result:
        return await client.send_message(50012, response)

    response.Result = 0
    _, _, err = await client.send_message(50012, response)
    if err:
        return 0, 50012, err

    push = protobuf.SC_50013(id=target_commander_id)
    _, _, err = await client.send_message(50013, push)
    if err:
        return 0, 50013, err

    if client.server is not None:
        target_client = client.server.find_client_by_commander(target_commander_id)
        if target_client:
            peer_push = protobuf.SC_50013(id=client.commander.commander_id)
            _, _, _ = await target_client.send_message(50013, peer_push)

    return 0, 50013, None


# ── AddFriendBlacklist (50110) ──

async def AddFriendBlacklist(buffer: bytes, client) -> tuple:
    request = protobuf.CS_50109()
    request.ParseFromString(buffer)
    target_id = request.id

    if target_id == 0 or target_id == client.commander.commander_id:
        response = protobuf.SC_50110(result=friendBlacklistResultInvalidTarget)
        return await client.send_message(50110, response)

    store = get_default_store()
    exists = await store.fetchval(
        "SELECT 1 FROM commanders WHERE commander_id = $1", target_id,
    )
    if not exists:
        response = protobuf.SC_50110(result=friendBlacklistResultInvalidTarget)
        return await client.send_message(50110, response)

    await store.aexecute(
        "INSERT INTO commander_blacklist (commander_id, blocked_id) VALUES ($1, $2) "
        "ON CONFLICT DO NOTHING",
        client.commander.commander_id, target_id,
    )
    response = protobuf.SC_50110(result=friendBlacklistResultSuccess)
    return await client.send_message(50110, response)


# ── GetFriendBlacklist (50017) ──

async def GetFriendBlacklist(buffer: bytes, client) -> tuple:
    request = protobuf.CS_50016()
    request.ParseFromString(buffer)

    store = get_default_store()
    blacklist_rows = await store.afetch(
        "SELECT blocked_id FROM commander_blacklist WHERE commander_id = $1 ORDER BY blocked_id",
        client.commander.commander_id,
    )
    blacklist = [r["blocked_id"] for r in blacklist_rows]

    response = protobuf.SC_50017(black_list=[])
    if not blacklist:
        return await client.send_message(50017, response)

    rows = await store.afetch(
        "SELECT commander_id, name, level FROM commanders WHERE commander_id = ANY($1)",
        blacklist,
    )
    commanders = {r["commander_id"]: r for r in rows}
    for blocked_id in blacklist:
        c = commanders.get(blocked_id)
        if c is None:
            continue
        response.black_list.append(protobuf.PLAYER_INFO_P50(
            id=c["commander_id"], name=c["name"], lv=c["level"],
        ))

    return await client.send_message(50017, response)


# ── RelieveFriendBlacklist (50108) ──

async def RelieveFriendBlacklist(buffer: bytes, client) -> tuple:
    request = protobuf.CS_50107()
    request.ParseFromString(buffer)
    target_id = request.id

    if target_id == 0 or target_id == client.commander.commander_id:
        response = protobuf.SC_50108(result=friendBlacklistResultInvalidTarget)
        return await client.send_message(50108, response)

    store = get_default_store()
    result = await store.aexecute(
        "DELETE FROM commander_blacklist WHERE commander_id = $1 AND blocked_id = $2",
        client.commander.commander_id, target_id,
    )
    if not result:
        response = protobuf.SC_50108(result=friendBlacklistResultNotFound)
        return await client.send_message(50108, response)

    response = protobuf.SC_50108(result=friendBlacklistResultSuccess)
    return await client.send_message(50108, response)
