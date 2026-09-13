import json
from typing import Optional

from src.connection.client import Client
from src.connection.server import generate_packet_header
from src.protobuf import protobuf

from src.protobuf.varint import encode_varint


def _encode_sc_19027(exp: int, food: int, next_timestamp: int) -> bytes:
    # SC_19027: field1 exp (uint32), field2 food (uint32), field3 next_timestamp (uint32)
    out = bytearray()
    out.append(0x08)
    out.extend(encode_varint(int(exp)))
    out.append(0x10)
    out.extend(encode_varint(int(food)))
    out.append(0x18)
    out.extend(encode_varint(int(next_timestamp)))
    return bytes(out)


def _apply_gained_exp(ship: dict, gained: int) -> dict:
    """Apply dorm exp to an owned_ships row dict (mutates level/exp/surplus_exp)."""
    if gained <= 0:
        return ship
    from src.answer.event_finish import _add_surplus_exp, _load_ship_level_config
    max_level = int(ship.get("max_level", 100))
    if int(ship.get("level", 1)) >= max_level:
        if max_level >= 100:
            ship["surplus_exp"] = _add_surplus_exp(
                int(ship.get("surplus_exp", 0)), gained)
    else:
        new_exp = int(ship.get("exp", 0)) + gained
        level = int(ship.get("level", 1))
        while level < max_level:
            config = _load_ship_level_config(level)
            if config is None:
                break
            required = int(config.get("exp", 0))
            if int(ship.get("rarity_id", 0)) == 6:
                required = int(config.get("exp_ur", required))
            if required == 0 or new_exp < required:
                break
            new_exp -= required
            level += 1
        ship["exp"] = new_exp
        ship["level"] = level
        if level >= max_level and max_level >= 100 and new_exp > 0:
            ship["surplus_exp"] = _add_surplus_exp(
                int(ship.get("surplus_exp", 0)), new_exp)
            ship["exp"] = 0
    return ship


async def handle_add_dorm_ship(
    buffer: bytes, client: Client,
) -> tuple[int, int, Optional[Exception]]:
    PACKET_ID = 19003

    try:
        payload = protobuf.CS_19002()
        payload.ParseFromString(buffer)
    except Exception as e:
        return 0, PACKET_ID, e

    commander_id = client.commander.commander_id
    ship_id = payload.ship_id
    ship_type = payload.type

    from src.orm.commander_dorm_state import get_or_create_commander_dorm_state, save_commander_dorm_state

    state = get_or_create_commander_dorm_state(commander_id)
    import time
    now = int(time.time())

    try:
        from src.db.store import get_default_store

        store = get_default_store()
        row = await store.afetchrow(
            """SELECT ship_id, id, level, exp, surplus_exp, max_level, intimacy,
                      state, state_info1, state_info2, state_info3, state_info4
             FROM owned_ships
             WHERE owner_id = $1 AND id = $2 AND deleted_at IS NULL""",
            int(commander_id), int(ship_id),
        )
        if row is None:
            await client.send_message(PACKET_ID, {"result": 1})
            return 0, PACKET_ID, None

        ship = dict(row)
        ship["id"] = int(ship["id"])

        if ship_type == 1:
            ship["state"] = 5
            ship["state_info1"] = now
            ship["state_info2"] = 0
            if state.next_timestamp == 0:
                state.next_timestamp = now + 15
                state.load_time = now
        elif ship_type == 2:
            ship["state"] = 2
            ship["state_info1"] = now

        await store.aexecute(
            """UPDATE owned_ships SET state = $3, state_info1 = $4, state_info2 = $5
             WHERE owner_id = $1 AND id = $2 AND deleted_at IS NULL""",
            int(commander_id), int(ship_id), int(ship["state"]),
            int(ship["state_info1"]), int(ship.get("state_info2", 0)),
        )
        save_commander_dorm_state(state)

        try:
            from src.answer.task_handlers import schedule_emit, schedule_possession_sync
            schedule_emit(client, 62, 0, 1)
            schedule_possession_sync(client)
        except Exception:
            pass

        await client.send_message(PACKET_ID, protobuf.SC_19003(result=0))
        return 0, PACKET_ID, None
    except Exception as e:
        return 0, PACKET_ID, e


async def handle_exit_dorm_ship(
    buffer: bytes, client: Client,
) -> tuple[int, int, Optional[Exception]]:
    PACKET_ID = 19005

    try:
        payload = protobuf.CS_19004()
        payload.ParseFromString(buffer)
    except Exception as e:
        return 0, PACKET_ID, e

    commander_id = client.commander.commander_id
    ship_id = payload.ship_id

    from .dorm_simulation import tick_dorm_state
    from src.db.store import get_default_store
    import time

    gained = 0

    try:
        store = get_default_store()
        await tick_dorm_state(commander_id, int(time.time()))
        row = await store.afetchrow(
            """SELECT os.ship_id, os.id, os.level, os.exp, os.surplus_exp, os.max_level,
                      os.intimacy, os.state, os.state_info1, os.state_info2, os.state_info3,
                      os.state_info4, COALESCE(s.rarity_id, 0) as rarity_id
             FROM owned_ships os
             LEFT JOIN ships s ON s.template_id = os.ship_id
             WHERE os.owner_id = $1 AND os.id = $2 AND os.deleted_at IS NULL""",
            int(commander_id), int(ship_id),
        )
        if row is None:
            await client.send_message(PACKET_ID, protobuf.SC_19005(result=0, exp=0))
            return 0, PACKET_ID, None
        ship = dict(row)
        ship["id"] = int(ship["id"])
        gained = int(ship.get("state_info2", 0))
        ship["state"] = 0
        ship["state_info1"] = int(time.time())
        ship["state_info2"] = 0
        ship["state_info3"] = 0
        ship["state_info4"] = 0
        if gained > 0:
            _apply_gained_exp(ship, gained)
        await store.aexecute(
            """UPDATE owned_ships SET state = $3, state_info1 = $4, state_info2 = $5,
                      state_info3 = $6, state_info4 = $7, level = $8, exp = $9, surplus_exp = $10
             WHERE owner_id = $1 AND id = $2 AND deleted_at IS NULL""",
            int(commander_id), int(ship_id), int(ship["state"]),
            int(ship["state_info1"]), int(ship["state_info2"]),
            int(ship["state_info3"]), int(ship["state_info4"]),
            int(ship.get("level", 1)), int(ship.get("exp", 0)),
            int(ship.get("surplus_exp", 0)),
        )

        await client.send_message(PACKET_ID, protobuf.SC_19005(result=0, exp=gained))
        return 0, PACKET_ID, None
    except Exception as e:
        return 0, PACKET_ID, e


def handle_buy_dorm_furniture(
    buffer: bytes, client: Client,
) -> tuple[int, int, Optional[Exception]]:
    PACKET_ID = 19007

    try:
        payload = protobuf.CS_19006()
        payload.ParseFromString(buffer)
    except Exception as e:
        return 0, PACKET_ID, e

    commander_id = client.commander.commander_id
    currency = payload.currency
    ids = list(payload.furniture_id)
    if not ids:
        _write_sync(client, PACKET_ID, protobuf.SC_19007(result=0))
        return 0, PACKET_ID, None

    from src.orm.config_entry import get_config_entry
    from src.orm.commander_furniture import add_commander_furniture
    import time

    total_cost = 0
    for furniture_id in ids:
        shop = get_config_entry("ShareCfg/furniture_shop_template.json", str(furniture_id))
        if shop is None:
            return 0, PACKET_ID, Exception(f"furniture {furniture_id} not found")
        raw = shop.data if hasattr(shop, 'data') else shop
        if isinstance(raw, str):
            raw = json.loads(raw)
        if currency == 4:
            cost = raw.get("gem_price", 0)
        elif currency == 6:
            cost = raw.get("dorm_icon_price", 0)
        else:
            return 0, PACKET_ID, Exception(f"unsupported currency {currency}")
        if cost == 0:
            return 0, PACKET_ID, Exception(f"furniture {furniture_id} not purchasable with currency {currency}")
        total_cost += cost

    try:
        if not client.commander.has_enough_resource(currency, total_cost):
            _write_sync(client, PACKET_ID, protobuf.SC_19007(result=1))
            return 0, PACKET_ID, None
        client.commander.consume_resource(currency, total_cost)
        now = int(time.time())
        for furniture_id in ids:
            add_commander_furniture(commander_id, furniture_id, 1, now)
    except Exception as e:
        _write_sync(client, PACKET_ID, protobuf.SC_19007(result=1))
        return 0, PACKET_ID, e

    _write_sync(client, PACKET_ID, protobuf.SC_19007(result=0))
    # Server-authoritative task progress: buying dorm furniture advances
    # "Obtain/purchase furniture" tasks (sub_type 65).
    try:
        from src.answer.task_handlers import schedule_emit, schedule_possession_sync
        schedule_emit(client, 65, 0, len(ids))
        schedule_possession_sync(client)
    except Exception:
        pass
    return 0, PACKET_ID, None


def _write_sync(client: Client, packet_id: int, msg) -> int:
    data = msg.SerializeToString()
    header = generate_packet_header(packet_id, data, client.packet_index)
    client.write_to_buffer(header + data)
    return len(data)


def handle_save_dorm_furniture_layout(
    buffer: bytes, client: Client,
) -> tuple[int, int, Optional[Exception]]:
    PACKET_ID = 19008

    try:
        payload = protobuf.CS_19008()
        payload.ParseFromString(buffer)
    except Exception as e:
        return 0, PACKET_ID, e

    commander_id = client.commander.commander_id
    floor = payload.floor

    from src.orm.commander_dorm_state import get_or_create_commander_dorm_state
    from src.orm.commander_dorm_floor_layout import upsert_commander_dorm_floor_layout
    from .backyard_validation import dorm_static_map_size, validate_furniture_put_list

    state = get_or_create_commander_dorm_state(commander_id)
    max_dorm_floor = 3
    state_floor = state.floor_num if hasattr(state, 'floor_num') else 0
    if floor == 0 or floor > max_dorm_floor or floor > state_floor:
        return 0, PACKET_ID, None

    map_size = dorm_static_map_size(state.level if hasattr(state, 'level') else 1)
    furniture_put_list = payload.furniture_put_list
    try:
        validate_furniture_put_list(furniture_put_list, floor, map_size)
    except ValueError as e:
        from src.logger.logger import log_event, LOG_LEVEL_ERROR
        details = []
        for f in furniture_put_list:
            details.append(
                f"id={f.id} x={f.x} y={f.y} dir={f.dir} parent={f.parent} "
                f"child=[{(','.join(str(c.id) for c in f.child))}]"
            )
        log_event("Dorm", "SaveLayoutRejected", f"CS_19008 floor={floor}: {e} | {len(details)} items: {'; '.join(details)}", LOG_LEVEL_ERROR)
        return 0, PACKET_ID, None

    stored = []
    for f in furniture_put_list:
        children = []
        for c in f.child:
            children.append({"id": c.id, "x": c.x, "y": c.y})
        stored.append({
            "id": f.id,
            "x": f.x,
            "y": f.y,
            "dir": f.dir,
            "child": children,
            "parent": f.parent,
            "shipId": f.shipId,
        })

    try:
        upsert_commander_dorm_floor_layout(commander_id, floor, stored)
    except Exception as e:
        return 0, PACKET_ID, e

    return 0, PACKET_ID, None


async def handle_dorm_food_data(
    _buffer: bytes, client: Client,
) -> tuple[int, int, Optional[Exception]]:
    PACKET_ID = 19010

    # Its sole field `type` (uint32 #1) is unused here anyway; the packet is a
    # fire-and-forget 30-min poll, so skip parsing entirely.
    #
    # This poll must roll ONLY pop events (hearts/coins). Exp/food settlement
    # stays exclusive to CS_19026: official SC_19010 carries ONLY pop_list, so
    # anything settled here is invisible to the client -- food would drain
    # silently (client only calls consumeFood on the SC_19027 reply) and exp
    # parked in state_info2 would pair with the wrong "snacks used" number in
    # the next "while you were away" popup (e.g. 98490 EXP / 18 snacks).
    import time
    from .dorm_simulation import settle_dorm_pops_at_login
    try:
        pop_list = await settle_dorm_pops_at_login(
            client.commander.commander_id, int(time.time())
        )
    except Exception as e:
        return 0, PACKET_ID, e

    msg = protobuf.SC_19010()
    for entry in pop_list or []:
        pop = msg.pop_list.add()
        pop.id = entry["id"]
        pop.intimacy = entry["intimacy"]
        pop.dorm_icon = entry["dorm_icon"]
    await client.send_message(PACKET_ID, msg)
    return 0, PACKET_ID, None


async def handle_claim_dorm_intimacy(
    buffer: bytes, client: Client,
) -> tuple[int, int, Optional[Exception]]:
    PACKET_ID = 19012

    try:
        payload = protobuf.CS_19011()
        payload.ParseFromString(buffer)
    except Exception as e:
        return 0, PACKET_ID, e

    commander_id = client.commander.commander_id
    requested_id = payload.id
    from src.db.store import get_default_store

    try:
        store = get_default_store()
        if requested_id != 0:
            row = await store.afetchrow(
                """SELECT ship_id, id, level, exp, surplus_exp, max_level, intimacy,
                          state, state_info1, state_info2, state_info3, state_info4
                 FROM owned_ships
                 WHERE owner_id = $1 AND id = $2 AND deleted_at IS NULL""",
                int(commander_id), int(requested_id),
            )
            if row is None:
                await client.send_message(PACKET_ID, protobuf.SC_19012(result=1))
                return 0, PACKET_ID, None
            ship = dict(row)
            ship["id"] = int(ship["id"])
            si3 = int(ship.get("state_info3", 0) or 0)
            si4 = int(ship.get("state_info4", 0) or 0)
            new_intimacy = int(ship["intimacy"]) + (si3 if si3 > 0 else 0)
            await store.aexecute(
                """UPDATE owned_ships SET intimacy = $3, state_info3 = 0, state_info4 = 0
                 WHERE owner_id = $1 AND id = $2 AND deleted_at IS NULL""",
                int(commander_id), int(requested_id), new_intimacy,
            )
            if si4 > 0:
                await store.aexecute(
                    """INSERT INTO owned_resources (commander_id, resource_id, amount)
                       VALUES ($1, 6, $2)
                       ON CONFLICT (commander_id, resource_id)
                       DO UPDATE SET amount = owned_resources.amount + EXCLUDED.amount""",
                    int(commander_id), int(si4),
                )
        else:
            rows = await store.afetch(
                """SELECT ship_id, id, level, exp, surplus_exp, max_level, intimacy,
                          state, state_info1, state_info2, state_info3, state_info4
                  FROM owned_ships
                  WHERE owner_id = $1 AND deleted_at IS NULL AND (state = 5 OR state = 2)""",
                int(commander_id),
            )
            dorm_money = 0
            for row in rows:
                ship = dict(row)
                ship_id = int(ship["id"])
                si3 = int(ship.get("state_info3", 0))
                si4 = int(ship.get("state_info4", 0))
                dorm_money += si4
                new_intimacy = int(ship["intimacy"]) + (si3 if si3 > 0 else 0)
                await store.aexecute(
                    """UPDATE owned_ships SET intimacy = $3, state_info3 = 0, state_info4 = 0
                     WHERE owner_id = $1 AND id = $2 AND deleted_at IS NULL""",
                    int(commander_id), ship_id, new_intimacy,
                )
            if dorm_money > 0:
                await store.aexecute(
                    """INSERT INTO owned_resources (commander_id, resource_id, amount)
                       VALUES ($1, 6, $2)
                       ON CONFLICT (commander_id, resource_id)
                       DO UPDATE SET amount = owned_resources.amount + EXCLUDED.amount""",
                    int(commander_id), int(dorm_money),
                )

        await client.send_message(PACKET_ID, protobuf.SC_19012(result=0))
        return 0, PACKET_ID, None
    except Exception as e:
        return 0, PACKET_ID, e


async def handle_claim_dorm_money(
    buffer: bytes, client: Client,
) -> tuple[int, int, Optional[Exception]]:
    PACKET_ID = 19014

    try:
        payload = protobuf.CS_19013()
        payload.ParseFromString(buffer)
    except Exception as e:
        return 0, PACKET_ID, e

    commander_id = client.commander.commander_id
    ship_id = payload.id
    from src.db.store import get_default_store

    try:
        store = get_default_store()
        row = await store.afetchrow(
            """SELECT ship_id, id, level, exp, surplus_exp, max_level, intimacy,
                      state, state_info1, state_info2, state_info3, state_info4
             FROM owned_ships
             WHERE owner_id = $1 AND id = $2 AND deleted_at IS NULL""",
            int(commander_id), int(ship_id),
        )
        if row is None:
            await client.send_message(PACKET_ID, protobuf.SC_19014(result=1))
            return 0, PACKET_ID, None
        ship = dict(row)
        ship_id_db = int(ship["id"])
        amount = int(ship.get("state_info4", 0))
        await store.aexecute(
            """UPDATE owned_ships SET state_info4 = 0
             WHERE owner_id = $1 AND id = $2 AND deleted_at IS NULL""",
            int(commander_id), ship_id_db,
        )
        if amount > 0:
            await store.aexecute(
                """INSERT INTO owned_resources (commander_id, resource_id, amount)
                   VALUES ($1, 6, $2)
                   ON CONFLICT (commander_id, resource_id)
                   DO UPDATE SET amount = owned_resources.amount + EXCLUDED.amount""",
                int(commander_id), int(amount),
            )

        await client.send_message(PACKET_ID, protobuf.SC_19014(result=0))
        return 0, PACKET_ID, None
    except Exception as e:
        return 0, PACKET_ID, e


async def handle_poll_dorm_exp_events(
    _buffer: bytes, client: Client,
) -> tuple[int, int, Optional[Exception]]:
    from .dorm_simulation import tick_dorm_and_push
    try:
        await tick_dorm_and_push(client)
    except Exception:
        pass
    return 0, 0, None


async def handle_rename_dorm(
    buffer: bytes, client: Client,
) -> tuple[int, int, Optional[Exception]]:
    PACKET_ID = 19017

    try:
        payload = protobuf.CS_19016()
        payload.ParseFromString(buffer)
    except Exception as e:
        return 0, PACKET_ID, e

    client.commander.dorm_name = payload.name
    from src.db.store import get_default_store
    store = get_default_store()

    try:
        await store.aexecute(
            "UPDATE commanders SET dorm_name = $2 WHERE commander_id = $1",
            int(client.commander.commander_id), client.commander.dorm_name,
        )

        await client.send_message(PACKET_ID, protobuf.SC_19017(result=0))
        return 0, PACKET_ID, None
    except Exception:
        await client.send_message(PACKET_ID, protobuf.SC_19017(result=1))
        return 0, PACKET_ID, None


def handle_list_dorm_themes(
    buffer: bytes, client: Client,
) -> tuple[int, int, Optional[Exception]]:
    PACKET_ID = 19019

    try:
        payload = protobuf.CS_19018()
        payload.ParseFromString(buffer)
    except Exception as e:
        return 0, PACKET_ID, e

    commander_id = client.commander.commander_id
    requested_id = payload.id

    from src.orm.commander_dorm_theme import list_commander_dorm_themes
    entries = list_commander_dorm_themes(commander_id)

    response = protobuf.SC_19019()
    for e in entries:
        if requested_id != 0 and e.get("theme_slot_id", 0) != requested_id:
            continue
        stored_raw = e.get("furniture_put_list", [])
        if isinstance(stored_raw, (bytes, bytearray)):
            stored_raw = stored_raw.decode("utf-8", errors="replace")
        if isinstance(stored_raw, str):
            stored_raw = json.loads(stored_raw)
        theme = protobuf.DORMTHEME(
            id=str(e.get("theme_slot_id", 0)),
            name=e.get("name", ""),
            user_id=commander_id,
            pos=e.get("theme_slot_id", 0),
            like_count=0,
            fav_count=0,
            upload_time=0,
            icon_image_md5="",
            image_md5="",
        )
        for f in stored_raw:
            f_info = protobuf.FURNITUREPUTINFO(
                id=f.get("id", ""),
                x=f.get("x", 0),
                y=f.get("y", 0),
                dir=f.get("dir", 0),
                parent=f.get("parent", 0),
                shipId=f.get("shipId", 0),
            )
            for c in f.get("child", []):
                child = protobuf.CHILDINFO(id=c.get("id", ""), x=c.get("x", 0), y=c.get("y", 0))
                f_info.child.append(child)
            theme.furniture_put_list.append(f_info)
        response.theme_list.append(theme)
    _write_sync(client, PACKET_ID, response)
    return 0, PACKET_ID, None


def handle_save_dorm_theme(
    buffer: bytes, client: Client,
) -> tuple[int, int, Optional[Exception]]:
    PACKET_ID = 19021

    try:
        payload = protobuf.CS_19020()
        payload.ParseFromString(buffer)
    except Exception as e:
        return 0, PACKET_ID, e

    commander_id = client.commander.commander_id

    from src.orm.commander_dorm_state import get_or_create_commander_dorm_state
    from src.orm.commander_dorm_theme import upsert_commander_dorm_theme
    from .backyard_validation import dorm_static_map_size, validate_furniture_put_list

    state = get_or_create_commander_dorm_state(commander_id)
    map_size = dorm_static_map_size(state.level if hasattr(state, 'level') else 1)

    furniture_put_list = payload.furniture_put_list
    try:
        validate_furniture_put_list(furniture_put_list, 1, map_size)
    except ValueError:
        _write_sync(client, PACKET_ID, protobuf.SC_19021(result=1))
        return 0, PACKET_ID, None

    stored = []
    for f in furniture_put_list:
        children = []
        for c in f.child:
            children.append({"id": c.id, "x": c.x, "y": c.y})
        stored.append({
            "id": f.id,
            "x": f.x,
            "y": f.y,
            "dir": f.dir,
            "child": children,
            "parent": f.parent,
            "shipId": f.shipId,
        })

    try:
        b = json.dumps(stored)
        upsert_commander_dorm_theme(commander_id, payload.id, payload.name, b)
    except Exception:
        _write_sync(client, PACKET_ID, protobuf.SC_19021(result=1))
        return 0, PACKET_ID, None

    _write_sync(client, PACKET_ID, protobuf.SC_19021(result=0))
    return 0, PACKET_ID, None


def handle_delete_dorm_theme(
    buffer: bytes, client: Client,
) -> tuple[int, int, Optional[Exception]]:
    PACKET_ID = 19023

    try:
        payload = protobuf.CS_19022()
        payload.ParseFromString(buffer)
    except Exception as e:
        return 0, PACKET_ID, e

    commander_id = client.commander.commander_id

    from src.orm.commander_dorm_theme import delete_commander_dorm_theme
    try:
        delete_commander_dorm_theme(commander_id, payload.id)
    except Exception:
        _write_sync(client, PACKET_ID, protobuf.SC_19023(result=1))
        return 0, PACKET_ID, None

    _write_sync(client, PACKET_ID, protobuf.SC_19023(result=0))
    return 0, PACKET_ID, None


def handle_get_backyard_visitor(
    _buffer: bytes, client: Client,
) -> tuple[int, int, Optional[Exception]]:
    PACKET_ID = 19025

    commander_id = client.commander.commander_id

    from src.orm.commander_dorm_floor_layout import list_commander_dorm_floor_layouts
    layouts = list_commander_dorm_floor_layouts(commander_id)

    response = protobuf.SC_19025()
    for layout in layouts:
        stored_raw = layout.furniture_put_list if hasattr(layout, 'furniture_put_list') else layout.get("furniture_put_list", [])
        if isinstance(stored_raw, (bytes, bytearray)):
            stored_raw = stored_raw.decode("utf-8", errors="replace")
        if isinstance(stored_raw, str):
            stored_raw = json.loads(stored_raw)
        floor_val = layout.floor if hasattr(layout, 'floor') else layout.get("floor", 0)
        floor_info = protobuf.FURFLOORPUTINFO(floor=floor_val)
        for f in stored_raw:
            f_info = protobuf.FURNITUREPUTINFO(
                id=f.get("id", ""),
                x=f.get("x", 0),
                y=f.get("y", 0),
                dir=f.get("dir", 0),
                parent=f.get("parent", 0),
                shipId=0,
            )
            for c in f.get("child", []):
                child = protobuf.CHILDINFO(id=c.get("id", ""), x=c.get("x", 0), y=c.get("y", 0))
                f_info.child.append(child)
            floor_info.furniture_put_list.append(f_info)
        response.furniture_put_list.append(floor_info)
    from src.connection.server import generate_packet_header
    data = response.SerializeToString()
    header = generate_packet_header(PACKET_ID, data, client.packet_index)
    client.write_to_buffer(header + data)
    return len(data), PACKET_ID, None


async def handle_get_ship_exp_for_dorm_training(
    _buffer: bytes, client: Client,
) -> tuple[int, int, Optional[Exception]]:
    PACKET_ID = 19027
    from .dorm_simulation import tick_dorm_state
    import time

    try:
        res = await tick_dorm_state(client.commander.commander_id, int(time.time()))
    except Exception as e:
        return 0, PACKET_ID, e

    if res is None:
        res = {}
    # exp here is the per-ship exp accrued since the last grant (state_info2).
    # The client applies the SAME exp to each floor-1 ship locally via SC_19027;
    # we must persist the same amount into each owned_ships.exp so a re-login
    # does not lose it and the client/server stay consistent.
    food = res.get("food_consume", 0)
    next_ts = res.get("next_timestamp", 0)
    exp = 0
    try:
        from src.db.store import get_default_store
        store = get_default_store()
        rows = await store.afetch(
            """SELECT os.id, os.ship_id, os.level, os.exp, os.surplus_exp, os.max_level,
                      os.state_info2, COALESCE(s.rarity_id, 0) AS rarity_id
             FROM owned_ships os
             LEFT JOIN ships s ON s.template_id = os.ship_id
             WHERE os.owner_id = $1 AND os.deleted_at IS NULL AND os.state = 5""",
            int(client.commander.commander_id),
        )
        gains = [int(r.get("state_info2", 0)) for r in rows]
        if gains:
            exp = max(gains)
        if exp > 0:
            for row in rows:
                ship = dict(row)
                ship["id"] = int(ship["id"])
                _apply_gained_exp(ship, exp)
                await store.aexecute(
                    """UPDATE owned_ships SET level = $3, exp = $4, surplus_exp = $5, state_info2 = 0
                     WHERE owner_id = $1 AND id = $2 AND deleted_at IS NULL""",
                    int(client.commander.commander_id), int(ship["id"]),
                    int(ship.get("level", 1)), int(ship.get("exp", 0)),
                    int(ship.get("surplus_exp", 0)),
                )
    except Exception as e:
        return 0, PACKET_ID, e

    data = _encode_sc_19027(exp, food, next_ts)
    header = generate_packet_header(PACKET_ID, data, client.packet_index)
    client.write_to_buffer(header + data)
    return len(data), PACKET_ID, None


