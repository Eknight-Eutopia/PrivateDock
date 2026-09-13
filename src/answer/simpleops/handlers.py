import asyncio

from src.connection.client import Client
from src.protobuf import protobuf
from src.db.store import get_default_store
from .helpers import (
    send_common_flag_push,
    clear_commander_common_flag,
    set_commander_common_flag,
    add_commander_story,
    get_config_entry,
    commander_has_living_area_cover,
    is_valid_guild_duty,
    update_guild_duty,
)


def handle_cancel_common_flag_command(buffer: bytes, client: Client) -> tuple:
    try:
        payload = protobuf.CS_11021()
        payload.ParseFromString(buffer)
    except Exception as e:
        return 0, 11022, e

    response = protobuf.SC_11022()
    response.result = 0
    try:
        clear_commander_common_flag(client.commander.commander_id, payload.flag_id)
    except Exception:
        response.result = 1
        asyncio.create_task(client.send_message(11022, response))
        return 0, 11022, None

    asyncio.create_task(client.send_message(11022, response))
    send_common_flag_push(client, payload.flag_id, False)
    return 0, 11022, None


def handle_change_living_area_cover(buffer: bytes, client: Client) -> tuple:
    try:
        payload = protobuf.CS_11030()
        payload.ParseFromString(buffer)
    except Exception as e:
        return 0, 11031, e

    response = protobuf.SC_11031()
    response.result = 0
    cover_id = payload.livingarea_cover_id

    if cover_id != 0:
        cfg = get_config_entry("ShareCfg/livingarea_cover.json", str(cover_id))
        if cfg is None:
            response.result = 1
            asyncio.create_task(client.send_message(11031, response))
            return 0, 11031, None

        if not commander_has_living_area_cover(client.commander.commander_id, cover_id):
            response.result = 2
            asyncio.create_task(client.send_message(11031, response))
            return 0, 11031, None

    async def _commit():
        store = get_default_store()
        await store.aexecute(
            "UPDATE commanders SET living_area_cover_id = $2 WHERE commander_id = $1",
            client.commander.commander_id, cover_id
        )

    asyncio.create_task(_commit())
    asyncio.create_task(client.send_message(11031, response))
    return 0, 11031, None


def handle_update_common_flag_command(buffer: bytes, client: Client) -> tuple:
    try:
        payload = protobuf.CS_11019()
        payload.ParseFromString(buffer)
    except Exception as e:
        return 0, 11020, e

    response = protobuf.SC_11020()
    response.result = 0
    try:
        set_commander_common_flag(client.commander.commander_id, payload.flag_id)
    except Exception:
        response.result = 1
        asyncio.create_task(client.send_message(11020, response))
        return 0, 11020, None

    asyncio.create_task(client.send_message(11020, response))
    send_common_flag_push(client, payload.flag_id, True)
    return 0, 11020, None


def handle_update_guide_index(buffer: bytes, client: Client) -> tuple:
    try:
        payload = protobuf.CS_11016()
        payload.ParseFromString(buffer)
    except Exception as e:
        return 0, 11018, e

    response = protobuf.SC_11018()
    response.result = 0
    del response.drop_list[:]

    commander_id = client.commander.commander_id

    async def _save():
        store = get_default_store()
        if payload.type == 1:
            await store.aexecute(
                "UPDATE commanders SET new_guide_index = $2 WHERE commander_id = $1",
                commander_id, payload.guide_index
            )
        else:
            await store.aexecute(
                "UPDATE commanders SET guide_index = $2 WHERE commander_id = $1",
                commander_id, payload.guide_index
            )

    asyncio.create_task(_save())
    asyncio.create_task(client.send_message(11018, response))
    return 0, 11018, None


def handle_update_secretaries(buffer: bytes, client: Client) -> tuple:
    try:
        payload = protobuf.CS_11011()
        payload.ParseFromString(buffer)
    except Exception as e:
        return 0, 11012, e

    response = protobuf.SC_11012()
    response.result = 0

    updates = []
    for entry in payload.character:
        updates.append({"ship_id": entry.key, "phantom_id": entry.value})

    commander_id = client.commander.commander_id
    owned_ships = client.commander.owned_ships_map

    for update in updates:
        if update["ship_id"] not in owned_ships:
            response.result = 1
            break

    if response.result == 0:
        async def _save_secretaries():
            store = get_default_store()
            await store.aexecute(
                """UPDATE owned_ships
                   SET is_secretary = false,
                       secretary_position = NULL,
                       secretary_phantom_id = 0
                   WHERE owner_id = $1
                     AND deleted_at IS NULL
                     AND is_secretary = true""",
                commander_id
            )
            for i, update in enumerate(updates):
                await store.aexecute(
                    """UPDATE owned_ships
                       SET is_secretary = true,
                           secretary_position = $3,
                           secretary_phantom_id = $4
                       WHERE owner_id = $1
                         AND id = $2
                         AND deleted_at IS NULL""",
                    commander_id, update["ship_id"], i, update["phantom_id"]
                )

            if len(updates) > 0:
                # the main secretary (first wire entry) defines the profile icon;
                # owned_ships_map entries carry no skin_id, so read it from the DB
                main = await store.afetchrow(
                    "SELECT ship_id, skin_id FROM owned_ships "
                    "WHERE owner_id = $1 AND id = $2 AND deleted_at IS NULL",
                    commander_id, updates[0]["ship_id"],
                )
                if main is not None:
                    await store.aexecute(
                        "UPDATE commanders SET display_icon_id = $2, display_skin_id = $3 WHERE commander_id = $1",
                        commander_id, main[0], main[1],
                    )

        asyncio.create_task(_save_secretaries())

    asyncio.create_task(client.send_message(11012, response))
    return 0, 11012, None


def handle_update_story_list(buffer: bytes, client: Client) -> tuple:
    try:
        payload = protobuf.CS_11032()
        payload.ParseFromString(buffer)
    except Exception as e:
        return 0, 11033, e

    response = protobuf.SC_11033()
    response.result = 0
    commander_id = client.commander.commander_id

    for story_id in payload.story_ids:
        try:
            add_commander_story(commander_id, story_id)
        except Exception:
            response.result = 1
            break

    asyncio.create_task(client.send_message(11033, response))
    return 0, 11033, None


def handle_update_story(buffer: bytes, client: Client) -> tuple:
    try:
        payload = protobuf.CS_11017()
        payload.ParseFromString(buffer)
    except Exception as e:
        return 0, 11018, e

    response = protobuf.SC_11018()
    response.result = 0

    try:
        add_commander_story(client.commander.commander_id, payload.story_id)
    except Exception:
        response.result = 1

    asyncio.create_task(client.send_message(11018, response))
    return 0, 11018, None


def handle_set_guild_duty(buffer: bytes, client: Client) -> tuple:
    try:
        payload = protobuf.CS_60012()
        payload.ParseFromString(buffer)
    except Exception as e:
        return 0, 60013, e

    response = protobuf.SC_60013()
    response.result = 1

    target_commander_id = payload.player_id
    duty_id = payload.duty_id

    if target_commander_id == 0 or not is_valid_guild_duty(duty_id):
        asyncio.create_task(client.send_message(60013, response))
        return 0, 60013, None

    err = update_guild_duty(client.commander.commander_id, target_commander_id, duty_id)
    if err is not None:
        asyncio.create_task(client.send_message(60013, response))
        return 0, 60013, None

    response.result = 0
    asyncio.create_task(client.send_message(60013, response))
    return 0, 60013, None


def handle_legacy_item_operation(buffer: bytes, client: Client) -> tuple:
    try:
        payload = protobuf.CS_15004()
        payload.ParseFromString(buffer)
    except Exception as e:
        return 0, 15005, e

    response = protobuf.SC_15005()
    response.result = 0
    asyncio.create_task(client.send_message(15005, response))
    return 0, 15005, None


def handle_new_tracking(_buffer: bytes, _client: Client) -> tuple:
    return 0, 0, None


def handle_main_scene_tracking(_buffer: bytes, _client: Client) -> tuple:
    return 0, 0, None


def handle_track_command(_buffer: bytes, _client: Client) -> tuple:
    return 0, 0, None


def handle_ur_exchange_tracking(_buffer: bytes, _client: Client) -> tuple:
    return 0, 0, None


def handle_apartment_track_event(buffer: bytes, _client: Client) -> tuple:
    try:
        payload = protobuf.CS_28090()
        payload.ParseFromString(buffer)
    except Exception:
        return 0, 28090, None
    return 0, 0, None
