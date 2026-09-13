
from src.config.config import AuthConfig

_DEFAULT_SESSION_TTL = 86400
_DEFAULT_CSRF_TTL = 7200
_DEFAULT_WEBAUTHN_CHALLENGE_TTL = 300
_DEFAULT_COOKIE_NAME = "privatedock_admin_session"
_DEFAULT_COOKIE_SAME_SITE = "lax"
_DEFAULT_RATE_LIMIT_WINDOW = 60
_DEFAULT_RATE_LIMIT_LOGIN_MAX = 5
_DEFAULT_RATE_LIMIT_PASSKEY_MAX = 5


def normalize_admin_config(cfg: AuthConfig) -> AuthConfig:
    return _normalize(cfg, _DEFAULT_COOKIE_NAME)


def normalize_user_config(cfg: AuthConfig) -> AuthConfig:
    return _normalize(cfg, _DEFAULT_COOKIE_NAME)


def _normalize(cfg: AuthConfig, default_cookie: str) -> AuthConfig:
    if cfg.session_ttl_seconds <= 0:
        cfg.session_ttl_seconds = _DEFAULT_SESSION_TTL
    if not cfg.cookie_name:
        cfg.cookie_name = default_cookie
    if not cfg.cookie_same_site:
        cfg.cookie_same_site = _DEFAULT_COOKIE_SAME_SITE
    if cfg.csrf_ttl_seconds <= 0:
        cfg.csrf_ttl_seconds = _DEFAULT_CSRF_TTL
    if cfg.webauthn_challenge_ttl_seconds <= 0:
        cfg.webauthn_challenge_ttl_seconds = _DEFAULT_WEBAUTHN_CHALLENGE_TTL
    if cfg.rate_limit_window_seconds <= 0:
        cfg.rate_limit_window_seconds = _DEFAULT_RATE_LIMIT_WINDOW
    if cfg.rate_limit_login_max <= 0:
        cfg.rate_limit_login_max = _DEFAULT_RATE_LIMIT_LOGIN_MAX
    if cfg.rate_limit_passkey_max <= 0:
        cfg.rate_limit_passkey_max = _DEFAULT_RATE_LIMIT_PASSKEY_MAX
    expected = []
    for origin in cfg.webauthn_expected_origins:
        origin = origin.strip()
        if origin:
            expected.append(origin)
    cfg.webauthn_expected_origins = expected
    return cfg


def session_ttl(cfg: AuthConfig) -> float:
    return float(cfg.session_ttl_seconds)


def csrf_ttl(cfg: AuthConfig) -> float:
    return float(cfg.csrf_ttl_seconds)


def webauthn_challenge_ttl(cfg: AuthConfig) -> float:
    return float(cfg.webauthn_challenge_ttl_seconds)


def rate_limit_window(cfg: AuthConfig) -> float:
    return float(cfg.rate_limit_window_seconds)
