from fastapi import FastAPI

from src.api.config import APIConfig
from src.api.middleware.recover import RecoverMiddleware
from src.api.middleware.logging import RequestLoggingMiddleware
from src.api.middleware.cors import setup_cors
from src.api.middleware.auth import AuthMiddleware
from src.api.middleware.audit import AuditMiddleware
from src.api.middleware.errors import ErrorHandlerMiddleware
from src.api.routes import health
from src.api.routes import auth
from src.api.routes import admin_authz
from src.api.routes import admin_users
from src.api.routes import admin_permission_policy
from src.api.routes import registration
from src.api.routes import user_auth
from src.api.routes import user_me
from src.api.routes import server
from src.api.routes import players
from src.api.routes import game_data
from src.api.routes import shop_notice
from src.api.routes import exchange_codes
from src.api.routes import juustagram
from src.api.routes import activities
from src.logger.logger import log_event, LOG_LEVEL_INFO


def create_app(cfg: APIConfig) -> FastAPI:
    app = FastAPI(
        title="PrivateDock API",
        description="Azur Lane server emulator REST API",
        version="0.1.0",
        docs_url="/swagger",
        swagger_ui_parameters={"url": "/swagger/doc.json"},
        redoc_url=None,
    )

    app.add_middleware(RecoverMiddleware)
    app.add_middleware(RequestLoggingMiddleware)
    setup_cors(app, cfg.cors_origins)
    app.add_middleware(AuthMiddleware, cfg=cfg.runtime_config)
    app.add_middleware(AuditMiddleware)
    app.add_middleware(ErrorHandlerMiddleware)

    app.include_router(health.router)
    app.include_router(auth.router)
    app.include_router(admin_authz.router)
    app.include_router(admin_users.router)
    app.include_router(admin_permission_policy.router)
    app.include_router(registration.router)
    app.include_router(user_auth.router)
    app.include_router(user_me.router)
    app.include_router(server.router)
    app.include_router(players.router)
    app.include_router(game_data.router)
    app.include_router(shop_notice.shop_router)
    app.include_router(shop_notice.notice_router)
    app.include_router(exchange_codes.router)
    app.include_router(juustagram.router)
    app.include_router(juustagram.player_router)
    app.include_router(activities.router)

    @app.on_event("startup")
    async def startup():
        log_event("API", "Startup", "API server starting", LOG_LEVEL_INFO)

    @app.on_event("shutdown")
    async def shutdown():
        log_event("API", "Shutdown", "API server shutting down", LOG_LEVEL_INFO)

    return app


async def start(cfg: APIConfig):
    import uvicorn

    if not cfg.enabled:
        log_event("API", "Start", "API server disabled", LOG_LEVEL_INFO)
        return

    app = create_app(cfg)
    log_event("API", "Start", f"listening on :{cfg.port}", LOG_LEVEL_INFO)
    config = uvicorn.Config(
        app,
        host="0.0.0.0",
        port=cfg.port,
        log_level="info" if cfg.env == "development" else "warning",
    )
    server = uvicorn.Server(config)
    await server.serve()
