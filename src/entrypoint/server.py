import argparse
import asyncio
import os
import signal
import threading

from src.api.app import start as api_start
from src.api.config import load_config
from src.authz.authz import register_default
from src.config.config import load
from src.connection.server import Server
from src.db.dialect import current_dialect
from src.db.migrator import load_migrations_from_directory, run_migrations
from src.db.session import apply_schema_name, get_session
from src.db.store import Store, set_default_store
from src.debug.adb_watcher import ADBRoutine
from src.entrypoint.packet_registry import register_packets
from src.logger.logger import cleanup_logs, log_event, LOG_LEVEL_ERROR, LOG_LEVEL_INFO, init_file_logging
from src.misc.game_update import update_all_data
from src.packets.handler import dispatch
from src.region.region import set_current, current as get_current_region


def _register_packets():
    register_packets()


def _ensure_bootstrap():
    register_default("players", "read")
    register_default("players", "write")
    register_default("players", "admin")
    register_default("servers", "read")
    register_default("servers", "write")
    register_default("admin", "access")


async def run_server():
    parser = argparse.ArgumentParser(description="Azur Lane server emulator")
    parser.add_argument("--config", default="configurations/server.json", help="Path to JSON config file")
    parser.add_argument("--no-api", action="store_true", help="Disable the embedded REST API server")
    parser.add_argument("-s", "--reseed", action="store_true", help="Force reseed of the database")
    parser.add_argument("-a", "--adb", action="store_true", help="Parse ADB logs (experimental)")
    parser.add_argument("-f", "--flush-logcat", action="store_true", help="Flush logcat on ADB start")
    parser.add_argument("-r", "--restart", action="store_true", help="Restart game on ADB start")

    args = parser.parse_args()

    init_file_logging("server")
    _register_packets()
    _ensure_bootstrap()

    cfg = load(args.config)
    apply_schema_name(cfg.database.schema_name)
    set_current(cfg.region.default)
    log_event("Config", "Region", f"region set to {get_current_region()}", LOG_LEVEL_INFO)

    try:
        deleted, freed = cleanup_logs(max_age_days=cfg.logs.max_age_days, max_total_mb=cfg.logs.max_total_mb)
        if deleted:
            log_event(
                "Logger", "Cleanup",
                f"removed {deleted} old log file(s), freed {freed / (1024 * 1024):.1f} MB "
                f"(max_age_days={cfg.logs.max_age_days}, max_total_mb={cfg.logs.max_total_mb})",
                LOG_LEVEL_INFO,
            )
    except Exception as e:
        log_event("Logger", "Cleanup", f"log cleanup failed: {e}", LOG_LEVEL_ERROR)

    store = Store()
    await store.init_pool(cfg.database.dsn, cfg.database.schema_name)
    set_default_store(store)

    dialect = current_dialect()
    schema_name = cfg.database.schema_name
    migrations = load_migrations_from_directory(
        os.path.join(os.path.dirname(__file__), "..", "..", "sql")
    )

    if dialect.name == "postgresql":
        import asyncpg

        conn = await asyncpg.connect(dsn=cfg.database.dsn)
        if schema_name:
            await conn.execute(f'SET search_path TO "{schema_name}"')
        try:
            if migrations:
                await run_migrations(conn, migrations, schema_name, cfg.database.dsn)

            has_data = await conn.fetchval("SELECT EXISTS(SELECT 1 FROM items)")
            if not has_data:
                log_event("DB", "Seed", "No game data found, updating...", LOG_LEVEL_INFO)
                update_all_data(get_current_region())
        finally:
            await conn.close()
    else:
        # SQLite: run migrations through the SQLAlchemy async engine.
        async with get_session() as session:
            conn = await session.connection()
            if migrations:
                await run_migrations(conn, migrations, schema_name, cfg.database.dsn)
            result = await conn.exec_driver_sql("SELECT EXISTS(SELECT 1 FROM items)", ())
            has_data = result.fetchone()[0]
            await session.commit()
        if not has_data:
            log_event("DB", "Seed", "No game data found, updating...", LOG_LEVEL_INFO)
            update_all_data(get_current_region())

    if args.reseed:
        log_event("Reseed", "Forced", "Forcing reseed...", LOG_LEVEL_INFO)
        update_all_data(get_current_region())

    server = Server(cfg.server.bind_address, cfg.server.port, dispatch)
    server.set_maintenance(cfg.server.maintenance)
    server.set_require_private_clients(cfg.server.require_private_clients)

    # Background secretary-affinity ticker: applies due affinity ticks for
    # online commanders and pushes SC_12019{intimacy} when a point is granted.
    # Offline catch-up happens at login (see src/answer/join_server.py).
    from src.orm.secretary import secretary_affinity_loop
    asyncio.create_task(secretary_affinity_loop())

    if args.adb:
        log_event("ADB", "Init", "Starting ADB watcher in background thread...", LOG_LEVEL_INFO)
        t = threading.Thread(target=ADBRoutine, args=(args.flush_logcat, args.restart), daemon=True)
        t.start()

    if not args.no_api:
        api_cfg = load_config(cfg)
        asyncio.create_task(api_start(api_cfg))

    loop = asyncio.get_running_loop()
    stop = loop.create_future()

    def _signal_handler():
        if not stop.done():
            log_event("Server", "Shutdown", "SIGINT received, shutting down...", LOG_LEVEL_INFO)
            stop.set_result(True)

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, _signal_handler)
        except NotImplementedError:
            pass

    # On POSIX (Termux/Linux) add_signal_handler replaces the default
    # KeyboardInterrupt, so SIGINT only resolves `stop` — the server task
    # must be cancelled explicitly or Ctrl+C is silently swallowed.
    server_task = asyncio.create_task(server.run())
    await stop
    server_task.cancel()
    try:
        await server_task
    except asyncio.CancelledError:
        pass
    log_event("Server", "Shutdown", "Server stopped", LOG_LEVEL_INFO)


def main():
    asyncio.run(run_server())


if __name__ == "__main__":
    main()
#test1
