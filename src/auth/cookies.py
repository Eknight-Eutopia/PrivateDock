from typing import Optional

from src.config.config import AuthConfig
from src.orm.session import Session


def build_session_cookie(cfg: AuthConfig, session: Optional[Session]) -> dict:
    if session is None:
        return {}
    return {
        "key": cfg.cookie_name,
        "value": session.id,
        "path": "/",
        "httponly": True,
        "secure": cfg.cookie_secure,
        "samesite": cfg.cookie_same_site.lower() if cfg.cookie_same_site else "lax",
        "max_age": cfg.session_ttl_seconds,
    }


def clear_session_cookie(cfg: AuthConfig) -> dict:
    return {
        "key": cfg.cookie_name,
        "value": "",
        "path": "/",
        "httponly": True,
        "secure": cfg.cookie_secure,
        "samesite": cfg.cookie_same_site.lower() if cfg.cookie_same_site else "lax",
        "max_age": -1,
    }
