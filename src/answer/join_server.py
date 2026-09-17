from typing import Optional

from src.config.config import current as get_config
from src.connection.client import Client
from src.orm.commander import create_commander
from src.logger.logger import log_event, LOG_LEVEL_ERROR, LOG_LEVEL_INFO, LOG_LEVEL_WARN
from src.protobuf import protobuf

from src.orm import get_commander_core_by_id

from .server_ticket import parse_server_ticket

USER_STATUS_OK = 0
USER_STATUS_BANNED = 17
# Unhandled by the client's SC_10023 dispatch -> generic SERVER_LOGIN_FAILED:
# the client shows an error and returns to the title screen instead of
# entering the new-player flow.
JOIN_RESULT_FAILED = 1


def _make_sc10023(result, user_id, server_load, db_load, server_ticket="=*=*=*=PrivateDock=*=*=*="):
    return protobuf.SC_10023(result=result, user_id=user_id, server_load=server_load, db_load=db_load, server_ticket=server_ticket)


async def handle_join_server(
    buffer: bytes,
    client: Client,
) -> tuple[int, int, Optional[Exception]]:
    proto_data = protobuf.CS_10022()
    try:
        proto_data.ParseFromString(buffer)
    except Exception as e:
        return 0, 10023, e

    try:
        await _do_join_server(proto_data, client)
    except Exception as e:
        log_event("Server", "SC_10023", f"join_server failed: {e}", LOG_LEVEL_ERROR)
        return 0, 10023, e
    return 0, 10023, None


async def _do_join_server(proto_data, client):
    server_load, db_load = _resolve_server_db_load()

    account_id = proto_data.account_id if proto_data.HasField("account_id") else 0
    device_id = proto_data.device_id if proto_data.HasField("device_id") else ""

    if device_id:
        from src.orm import get_device_auth_map_by_device_id
        try:
            device_mapping = await get_device_auth_map_by_device_id(device_id)
            if device_mapping is not None:
                if client.auth_arg2 == 0:
                    client.auth_arg2 = device_mapping["arg2"]
                if account_id == 0 and device_mapping.get("account_id", 0) != 0:
                    account_id = device_mapping["account_id"]
        except Exception as e:
            log_event("Server", "SC_10023", f"failed to fetch device mapping: {e}", LOG_LEVEL_ERROR)
            return

    if client.auth_arg2 == 0:
        client.auth_arg2 = parse_server_ticket(proto_data.server_ticket if proto_data.HasField("server_ticket") else "")

    if client.auth_arg2 != 0:
        from src.orm import get_yostarus_map_by_arg2
        try:
            mapping = await get_yostarus_map_by_arg2(client.auth_arg2)
            if mapping is not None:
                account_id = mapping["account_id"]
        except Exception as e:
            log_event("Server", "SC_10023", f"failed to fetch account mapping: {e}", LOG_LEVEL_ERROR)
            return

    if account_id == 0:
        if get_config().create_player.skip_onboarding and client.auth_arg2 != 0:
            try:
                account_id = await create_commander(client, client.auth_arg2, None, [201211])
            except Exception as e:
                log_event("Server", "SC_10023", f"failed to create commander: {e}", LOG_LEVEL_ERROR)
                return
        if account_id == 0:
            if device_id and client.auth_arg2 != 0:
                from src.orm import upsert_device_auth_map
                try:
                    await upsert_device_auth_map(device_id, client.auth_arg2, 0)
                except Exception as e:
                    log_event("Server", "SC_10023", f"failed to save device mapping: {e}", LOG_LEVEL_ERROR)
            await client.send_message(10023, _make_sc10023(USER_STATUS_OK, 0, server_load, db_load))
            return

    from src.db.store import NotFoundError
    from src.orm.active_commander import register_active_client
    try:
        client.commander = await get_commander_core_by_id(account_id)
        if client.commander is not None:
            if client.auth_arg2 != 0:
                from src.orm import get_yostarus_map_by_arg2
                try:
                    mapping = await get_yostarus_map_by_arg2(client.auth_arg2)
                    if mapping is None or mapping["account_id"] != client.commander.account_id:
                        # Loaded commander belongs to a different user/arg2 on this server
                        client.commander = None
                except Exception as e:
                    log_event("Server", "SC_10023", f"failed to verify commander ownership: {e}", LOG_LEVEL_ERROR)
            if client.commander is not None:
                client.commander.load()
                register_active_client(client.commander.commander_id, client)
                # Secretary affinity catch-up: the leftmost (main) secretary keeps
                # accruing 1 affinity point per 300-320 min while the player is
                # offline; apply everything due right now so the login dock sync
                # (SC_12001/SC_12010) already carries the fresh intimacy value.
                try:
                    from src.orm.secretary import tick_secretary_affinity
                    await tick_secretary_affinity(client.commander.commander_id, client)
                except Exception as e:
                    log_event("Server", "JoinServer",
                              f"secretary affinity catch-up failed: {e}", LOG_LEVEL_ERROR)
    except NotFoundError:
        await client.send_message(10023, _make_sc10023(USER_STATUS_OK, 0, server_load, db_load))
        return
    except Exception as e:
        log_event("Server", "SC_10023", f"failed to fetch commander (id={account_id}): {e}", LOG_LEVEL_ERROR)
        return

    if client.commander is None:
        if client.auth_arg2 == 0:
            # Client joined with an account_id this server doesn't know AND
            # without an auth identity — it skipped CS_10020 (a stale cached
            # session, e.g. after the server DB was recreated). The CS_10024
            # creation flow needs auth_arg2, so entry would dead-end at the
            # tutorial name screen; reject the login instead so the client
            # shows an error and goes back to re-authenticate.
            log_event("Server", "SC_10023",
                      f"account_id={account_id} unknown and no auth ticket (client skipped CS_10020) — rejecting login",
                      LOG_LEVEL_WARN)
            await client.send_message(10023, _make_sc10023(JOIN_RESULT_FAILED, 0, server_load, db_load))
            return
        # Normal new-player path: the client replies to user_id=0 by walking the
        # tutorial and creating the account via CS_10024 (auth_arg2 was set by
        # CS_10020 earlier in the same session).
        log_event("Server", "SC_10023",
                  f"no commander for account_id={account_id} — replying user_id=0 (new-player flow)",
                  LOG_LEVEL_INFO)
        await client.send_message(10023, _make_sc10023(USER_STATUS_OK, 0, server_load, db_load))
        return

    if client.server is not None:
        from src.consts.disconnect_reasons import DR_LOGGED_IN_ON_ANOTHER_DEVICE
        try:
            existing_kicked = await client.server.disconnect_commander(
                client.commander.commander_id,
                DR_LOGGED_IN_ON_ANOTHER_DEVICE,
                client,
            )
            if existing_kicked:
                log_event("Server", "LoginKick",
                          f"kicked previous session for commander {client.commander.commander_id}",
                          LOG_LEVEL_INFO)
        except AttributeError:
            pass

    punishments = await _fetch_active_punishments(account_id)
    if punishments:
        active = punishments[0]
        if active.get("is_permanent") or active.get("lift_timestamp") is None:
            log_event("Database", "Punishments",
                      f"Permanent punishment found for uid={account_id}", LOG_LEVEL_ERROR)
            user_id = 0
        else:
            log_event("Database", "Punishments",
                      f"Temporary punishment found for uid={account_id}, lifting at {active['lift_timestamp']}",
                      LOG_LEVEL_INFO)
            user_id = int(active["lift_timestamp"].timestamp())
        result = USER_STATUS_BANNED
    else:
        log_event("Database", "Punishments",
                  f"No punishments found for uid={account_id}", LOG_LEVEL_INFO)
        result = USER_STATUS_OK
        user_id = client.commander.commander_id

    if device_id and client.auth_arg2 != 0:
        from src.orm import upsert_device_auth_map
        try:
            await upsert_device_auth_map(device_id, client.auth_arg2, account_id)
        except Exception as e:
            log_event("Server", "SC_10023", f"failed to save device mapping: {e}", LOG_LEVEL_ERROR)

    await client.send_message(10023, _make_sc10023(result, user_id, server_load, db_load))


async def _fetch_active_punishments(commander_id: int) -> list:
    from src.db.store import get_default_store
    store = get_default_store()
    try:
        rows = await store.afetch(
            "SELECT * FROM punishments WHERE punished_id = $1 AND "
            "(lift_timestamp IS NULL OR lift_timestamp > NOW()) "
            "ORDER BY id DESC LIMIT 1",
            commander_id,
        )
        result = []
        for row in rows:
            d = dict(row)
            result.append(d)
        return result
    except Exception:
        return []


def _resolve_server_db_load() -> tuple[int, int]:
    from src.db.session import get_engine
    engine = get_engine()
    try:
        pool = engine.pool
        if pool is None:
            return 0, 0
        max_conns = pool.size() + pool.overflow()
        if max_conns <= 0:
            return 0, 0
        acquired = pool.checkedout()
        if acquired <= 0:
            return 0, 0
        db_load = (acquired * 100) // max_conns
        if db_load > 100:
            db_load = 100
        return 0, db_load
    except Exception:
        return 0, 0
