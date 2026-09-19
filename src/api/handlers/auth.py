from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import Request

from src.api.middleware.auth import is_auth_disabled, resolve_auth
from src.api.response import ok, error
from src.api.types.auth import AuthBootstrapRequest, AuthLoginRequest, AuthPasswordChangeRequest
from src.auth.cookies import build_session_cookie, clear_session_cookie
from src.auth.ip import normalize_ip
from src.auth.password import hash_password, verify_password
from src.auth.rate_limiter import RateLimiter
from src.auth.sessions import create_session, load_session, revoke_session, revoke_sessions
from src.config.config import current as current_config
from src.db.store import get_default_store


_login_limiter = RateLimiter()


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _client_ip(request: Request) -> str:
    if request.client is None:
        return ""
    return normalize_ip(request.client.host or "")


def _user_payload(row) -> dict:
    return {
        "id": row["id"],
        "username": row.get("username") or "",
        "is_admin": bool(row.get("is_admin")),
        "disabled": row.get("disabled_at") is not None,
        "last_login_at": row.get("last_login_at").isoformat() if row.get("last_login_at") else "",
        "created_at": row.get("created_at").isoformat() if row.get("created_at") else "",
    }


async def _fetch_account(username_normalized: str):
    store = get_default_store()
    return store.fetchrow(
        "SELECT id, username, username_normalized, commander_id, password_hash, "
        "password_algo, password_updated_at, is_admin, disabled_at, last_login_at, "
        "created_at, updated_at FROM accounts WHERE username_normalized = $1",
        username_normalized,
    )


async def _create_admin(username: str, password: str) -> str:
    now = _now()
    account_id = str(uuid.uuid4())
    store = get_default_store()
    store.execute(
        "INSERT INTO accounts (id, username, username_normalized, commander_id, "
        "password_hash, password_algo, password_updated_at, is_admin, created_at, updated_at) "
        "VALUES ($1, $2, $3, NULL, $4, 'argon2id', $5, true, $6, $7)",
        account_id,
        username,
        username.strip().lower(),
        hash_password(password),
        now,
        now,
        now,
    )
    return account_id


async def _admin_count() -> int:
    store = get_default_store()
    count = store.fetchval(
        "SELECT COUNT(*) FROM accounts WHERE is_admin = true",
    )
    return int(count or 0)


class AuthHandler:
    async def bootstrap(self, req: Request):
        if await _admin_count() > 0:
            return error("conflict", "admin account already exists", status_code=409)
        try:
            body = await req.json()
            payload = AuthBootstrapRequest(**body)
        except Exception:
            return error("bad_request", "invalid request", status_code=400)

        username = (payload.username or "").strip()
        cfg = current_config().auth
        if not username:
            return error("bad_request", "username is required", status_code=400)
        if len(payload.password or "") < max(1, cfg.password_min_length):
            return error("bad_request", f"password must be at least {cfg.password_min_length} characters", status_code=400)

        try:
            account_id = await _create_admin(username, payload.password)
            session = await create_session(
                account_id,
                _client_ip(req),
                req.headers.get("User-Agent", ""),
                cfg,
            )
        except Exception:
            return error("conflict", "username already exists", status_code=409)

        row = await _fetch_account(username.lower())
        response = ok({
            "user": _user_payload(row),
            "session": {
                "id": session.id,
                "expires_at": session.expires_at.isoformat() if session.expires_at else "",
            },
            "csrf_token": session.csrf_token,
        })
        response.set_cookie(**build_session_cookie(cfg, session))
        return response

    async def bootstrap_status(self):
        count = await _admin_count()
        return ok({"can_bootstrap": count == 0, "admin_count": count})

    async def login(self, req: Request):
        try:
            body = await req.json()
            payload = AuthLoginRequest(**body)
        except Exception:
            return error("bad_request", "invalid request", status_code=400)

        cfg = current_config().auth
        username = (payload.username or "").strip().lower()
        limiter_key = f"{_client_ip(req)}:{username}"
        if not _login_limiter.allow(limiter_key, cfg.rate_limit_login_max, cfg.rate_limit_window_seconds):
            return error("rate_limited", "too many login attempts", status_code=429)

        row = await _fetch_account(username)
        if row is None or row.get("disabled_at") is not None or not verify_password(row.get("password_hash") or "", payload.password):
            return error("auth.invalid_credentials", "invalid username or password", status_code=401)
        if not row.get("is_admin"):
            return error("permissions.denied", "admin access required", status_code=403)

        session = await create_session(
            row["id"],
            _client_ip(req),
            req.headers.get("User-Agent", ""),
            cfg,
        )
        store = get_default_store()
        store.execute(
            "UPDATE accounts SET last_login_at = $1, updated_at = $1 WHERE id = $2",
            _now(),
            row["id"],
        )
        response = ok({
            "user": _user_payload(row),
            "session": {
                "id": session.id,
                "expires_at": session.expires_at.isoformat() if session.expires_at else "",
            },
            "csrf_token": session.csrf_token,
        })
        response.set_cookie(**build_session_cookie(cfg, session))
        return response

    async def logout(self, req: Request):
        _account_state, session_state = await resolve_auth(req)
        if session_state and session_state.get("id"):
            await revoke_session(session_state["id"])
        response = ok()
        response.set_cookie(**clear_session_cookie(current_config().auth))
        return response

    async def session(self, req: Request):
        if is_auth_disabled(req):
            return ok({"auth_disabled": True, "user": None, "session": None, "csrf_token": ""})

        account_state, session_state = await resolve_auth(req)
        if account_state is None or session_state is None:
            return error("auth.session_missing", "session required", status_code=401)

        try:
            session, account = await load_session(session_state["id"])
        except Exception:
            return error("auth.session_missing", "session required", status_code=401)

        return ok({
            "auth_disabled": False,
            "user": {
                "id": account.id,
                "username": account.username or "",
                "is_admin": bool(account.is_admin),
                "disabled": account.disabled_at is not None,
                "last_login_at": account.last_login_at.isoformat() if account.last_login_at else "",
                "created_at": account.created_at.isoformat() if account.created_at else "",
            },
            "session": {
                "id": session.id,
                "expires_at": session.expires_at.isoformat() if session.expires_at else "",
            },
            "csrf_token": session.csrf_token,
        })

    async def change_password(self, req: Request):
        try:
            body = await req.json()
            payload = AuthPasswordChangeRequest(**body)
        except Exception:
            return error("bad_request", "invalid request", status_code=400)
        account_state, session_state = await resolve_auth(req)
        if account_state is None:
            return error("auth.session_missing", "session required", status_code=401)
        row = await _fetch_account((account_state.get("username") or "").lower())
        if row is None or not verify_password(row.get("password_hash") or "", payload.current_password):
            return error("auth.invalid_credentials", "current password is invalid", status_code=400)
        cfg = current_config().auth
        if len(payload.new_password or "") < max(1, cfg.password_min_length):
            return error("bad_request", f"password must be at least {cfg.password_min_length} characters", status_code=400)
        store = get_default_store()
        store.execute(
            "UPDATE accounts SET password_hash = $1, password_algo = 'argon2id', "
            "password_updated_at = $2, updated_at = $2 WHERE id = $3",
            hash_password(payload.new_password),
            _now(),
            account_state["id"],
        )
        await revoke_sessions(account_state["id"], except_session_id=(session_state or {}).get("id"))
        return ok()

    async def list_passkeys(self):
        return ok({"passkeys": []})

    async def passkey_register_options(self):
        return error("not_implemented", "passkeys are not implemented", status_code=501)

    async def passkey_register_verify(self):
        return error("not_implemented", "passkeys are not implemented", status_code=501)

    async def delete_passkey(self):
        return error("not_implemented", "passkeys are not implemented", status_code=501)

    async def passkey_authenticate_options(self):
        return error("not_implemented", "passkeys are not implemented", status_code=501)

    async def passkey_authenticate_verify(self):
        return error("not_implemented", "passkeys are not implemented", status_code=501)


_handler = AuthHandler()


def get_auth_handler() -> AuthHandler:
    return _handler
