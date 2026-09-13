from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from src.api.response import error
from src.config.config import Config

AUTH_ACCOUNT_KEY = "auth.account"
AUTH_SESSION_KEY = "auth.session"
AUTH_DISABLED_KEY = "auth.disabled"

_public_route_prefixes = [
    "/swagger",
    "/api/v1/registration/",
]

_public_route_methods = {
    "/health": None,
    "/api/v1/auth/bootstrap": {"POST"},
    "/api/v1/auth/bootstrap/status": {"GET"},
    "/api/v1/auth/login": {"POST"},
    "/api/v1/server/status": {"GET"},
    "/api/v1/auth/passkeys/authenticate/options": {"POST"},
    "/api/v1/auth/passkeys/authenticate/verify": {"POST"},
    "/api/v1/user/auth/login": {"POST"},
}


def _is_public_route(method: str, path: str) -> bool:
    for prefix in _public_route_prefixes:
        if path.startswith(prefix):
            return True
    methods = _public_route_methods.get(path)
    if methods is None:
        return False
    return method in methods


def _requires_csrf(method: str) -> bool:
    return method in ("POST", "PUT", "PATCH", "DELETE")


def is_auth_disabled(request: Request) -> bool:
    return getattr(request.state, AUTH_DISABLED_KEY, False)


def get_account(request: Request) -> Optional[dict]:
    return getattr(request.state, AUTH_ACCOUNT_KEY, None)


def get_session(request: Request) -> Optional[dict]:
    return getattr(request.state, AUTH_SESSION_KEY, None)


class AuthMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, cfg: Optional[Config] = None):
        super().__init__(app)
        if cfg:
            self.disable_auth = cfg.auth.disable_auth
            self.cookie_name = cfg.auth.cookie_name
            self.session_sliding = cfg.auth.session_sliding
            self.session_ttl = cfg.auth.session_ttl_seconds
            self.cookie_secure = cfg.auth.cookie_secure
        else:
            self.disable_auth = False
            self.cookie_name = "privatedock_admin_session"
            self.session_sliding = True
            self.session_ttl = 86400
            self.cookie_secure = True

    async def dispatch(self, request: Request, call_next):
        request.state.auth_disabled = self.disable_auth

        if self.disable_auth:
            session_id = request.cookies.get(self.cookie_name)
            if session_id:
                from src.auth.sessions import load_session
                try:
                    session, account = await load_session(session_id)
                    username = account.username or ""
                    request.state.auth_account = {"id": session.account_id, "username": username}
                    request.state.auth_session = {"id": session_id}
                except Exception:
                    pass
            return await call_next(request)

        if request.method == "OPTIONS":
            return await call_next(request)

        if _is_public_route(request.method, request.url.path):
            return await call_next(request)

        session_id = request.cookies.get(self.cookie_name)
        if not session_id:
            return JSONResponse(
                error("auth.session_missing", "session required"),
                status_code=401,
            )

        from src.auth.sessions import load_session, touch_session
        try:
            session, account = await load_session(session_id)
        except Exception:
            return JSONResponse(
                error("auth.session_missing", "session required"),
                status_code=401,
            )

        if _requires_csrf(request.method):
            csrf_token = request.headers.get("X-CSRF-Token", "")
            if not csrf_token:
                return JSONResponse(
                    error("auth.csrf_invalid", "csrf token required"),
                    status_code=403,
                )

        if self.session_sliding:
            now = datetime.now(timezone.utc)
            if session.last_seen_at is None or (now - session.last_seen_at).total_seconds() > self.session_ttl * 0.5:
                new_expires = now.replace(second=int(now.timestamp() + self.session_ttl))
                await touch_session(session_id, now, new_expires)

        request.state.auth_account = {"id": session.account_id, "username": account.username or ""}
        request.state.auth_session = {"id": session_id}
        return await call_next(request)
