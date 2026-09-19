import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

from src.auth.tokens import new_token
from src.config.config import AuthConfig
from src.orm.session import Session
from src.orm.account import Account
from src.db.store import get_default_store


class SessionNotFound(Exception):
    pass


async def create_session(account_id: str, ip: str, user_agent: str, cfg: AuthConfig) -> Session:
    csrf_token = new_token(32)
    now = datetime.now(timezone.utc)
    ttl = cfg.session_ttl_seconds if cfg.session_ttl_seconds > 0 else 86400
    csrf_ttl_sec = cfg.csrf_ttl_seconds if cfg.csrf_ttl_seconds > 0 else 7200
    session = Session(
        id=str(uuid.uuid4()),
        account_id=account_id,
        created_at=now,
        last_seen_at=now,
        expires_at=now + timedelta(seconds=ttl),
        ip_address=ip,
        user_agent=user_agent,
        csrf_token=csrf_token,
        csrf_expires_at=now + timedelta(seconds=csrf_ttl_sec),
    )
    store = get_default_store()
    store.execute(
        "INSERT INTO sessions (id, account_id, created_at, last_seen_at, expires_at, ip_address, user_agent, csrf_token, csrf_expires_at) "
        "VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9)",
        session.id, session.account_id, session.created_at, session.last_seen_at, session.expires_at,
        session.ip_address, session.user_agent, session.csrf_token, session.csrf_expires_at,
    )
    return session


async def load_session(session_id: str) -> tuple[Session, Account]:
    store = get_default_store()
    row = store.fetchrow(
        "SELECT s.id, s.account_id, s.created_at, s.last_seen_at, s.expires_at, s.ip_address, s.user_agent, s.revoked_at, s.csrf_token, s.csrf_expires_at, "
        "a.id as a_id, a.username, a.username_normalized, a.commander_id, a.password_hash, a.password_algo, a.password_updated_at, "
        "a.is_admin, a.disabled_at, a.last_login_at, a.web_authn_user_handle, a.created_at as a_created_at, a.updated_at as a_updated_at "
        "FROM sessions s JOIN accounts a ON a.id = s.account_id WHERE s.id = $1 AND s.revoked_at IS NULL",
        session_id,
    )
    if row is None:
        raise SessionNotFound("session not found")
    session = _row_to_session(row)
    now = datetime.now(timezone.utc)
    if session.expires_at and session.expires_at < now:
        raise SessionNotFound("session expired")
    account = Account(
        id=row["a_id"],
        username=row.get("username"),
        username_normalized=row.get("username_normalized"),
        commander_id=row.get("commander_id"),
        password_hash=row.get("password_hash") or "",
        password_algo=row.get("password_algo") or "",
        password_updated_at=row.get("password_updated_at"),
        is_admin=row.get("is_admin") or False,
        disabled_at=row.get("disabled_at"),
        last_login_at=row.get("last_login_at"),
        web_authn_user_handle=row.get("web_authn_user_handle"),
        created_at=row.get("a_created_at"),
        updated_at=row.get("a_updated_at"),
    )
    return session, account


async def touch_session(session_id: str, last_seen: Optional[datetime] = None, expires_at: Optional[datetime] = None):
    store = get_default_store()
    if expires_at is None:
        store.execute(
            "UPDATE sessions SET last_seen_at = $1 WHERE id = $2",
            last_seen or datetime.now(timezone.utc), session_id,
        )
    else:
        store.execute(
            "UPDATE sessions SET last_seen_at = $1, expires_at = $2 WHERE id = $3",
            last_seen or datetime.now(timezone.utc), expires_at, session_id,
        )


async def refresh_csrf(session_id: str, cfg: AuthConfig) -> tuple[str, datetime]:
    token = new_token(32)
    expires_at = datetime.now(timezone.utc) + timedelta(seconds=cfg.csrf_ttl_seconds)
    store = get_default_store()
    store.execute(
        "UPDATE sessions SET csrf_token = $1, csrf_expires_at = $2 WHERE id = $3",
        token, expires_at, session_id,
    )
    return token, expires_at


async def revoke_session(session_id: str):
    store = get_default_store()
    store.execute(
        "UPDATE sessions SET revoked_at = $1 WHERE id = $2",
        datetime.now(timezone.utc), session_id,
    )


async def revoke_sessions(account_id: str, except_session_id: Optional[str] = None):
    store = get_default_store()
    now = datetime.now(timezone.utc)
    if except_session_id:
        store.execute(
            "UPDATE sessions SET revoked_at = $1 WHERE account_id = $2 AND id != $3 AND revoked_at IS NULL",
            now, account_id, except_session_id,
        )
    else:
        store.execute(
            "UPDATE sessions SET revoked_at = $1 WHERE account_id = $2 AND revoked_at IS NULL",
            now, account_id,
        )


def _row_to_session(row) -> Session:
    return Session(
        id=row["id"],
        account_id=row["account_id"],
        created_at=row.get("created_at"),
        last_seen_at=row.get("last_seen_at"),
        expires_at=row.get("expires_at"),
        ip_address=row.get("ip_address") or "",
        user_agent=row.get("user_agent") or "",
        revoked_at=row.get("revoked_at"),
        csrf_token=row.get("csrf_token") or "",
        csrf_expires_at=row.get("csrf_expires_at"),
    )
