import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class ServerConfig:
    id: int = 0
    name: str = ""
    ip: str = ""
    port: int = 0
    proxy_ip: Optional[str] = None
    proxy_port: Optional[int] = None


@dataclass
class PrivateDockConfig:
    bind_address: str = "0.0.0.0"
    port: int = 81
    maintenance: bool = False
    name: str = "Private Dock (Local)"
    require_private_clients: bool = True


@dataclass
class APIConfig:
    enabled: bool = True
    port: int = 2289
    environment: str = "development"
    cors_origins: list[str] = field(default_factory=lambda: ["*"])


@dataclass
class AuthConfig:
    disable_auth: bool = False
    session_ttl_seconds: int = 86400
    session_sliding: bool = True
    cookie_name: str = "privatedock_admin_session"
    cookie_secure: bool = True
    cookie_same_site: str = "lax"
    csrf_ttl_seconds: int = 7200
    password_min_length: int = 4
    webauthn_rp_id: str = "localhost"
    webauthn_rp_name: str = "Private Dock Admin"
    webauthn_expected_origins: list[str] = field(default_factory=lambda: ["http://localhost:3000"])
    webauthn_challenge_ttl_seconds: int = 300
    rate_limit_window_seconds: int = 60
    rate_limit_login_max: int = 5
    rate_limit_passkey_max: int = 5


@dataclass
class DatabaseConfig:
    dsn: str = ""
    schema_name: str = ""
    # Optional override: "postgres" or "sqlite". When empty the driver is
    # inferred from the DSN, so existing configurations keep working untouched.
    driver: str = ""
    # sqlite file path (``"database": {"path": "app.db"}``). Empty when the DSN
    # form is used. ``load()`` folds it into ``dsn`` so the rest of the
    # codebase only ever looks at ``dsn``/``driver``.
    path: str = ""


@dataclass
class RegionConfig:
    default: str = "EN"


@dataclass
class CreatePlayerConfig:
    skip_onboarding: bool = False
    name_blacklist: list[str] = field(default_factory=list)
    name_illegal_pattern: str = ""


@dataclass
class LogsConfig:
    # Log-file cleanup applied at server startup (src/logger/logger.py).
    # Files in the logs directory older than max_age_days are deleted, then
    # oldest-first deletion trims the directory to max_total_mb. A value <= 0
    # disables the respective rule. The active session log is never deleted.
    max_age_days: int = 14
    max_total_mb: int = 30


@dataclass
class Config:
    server: PrivateDockConfig = field(default_factory=PrivateDockConfig)
    api: APIConfig = field(default_factory=APIConfig)
    auth: AuthConfig = field(default_factory=AuthConfig)
    database: DatabaseConfig = field(default_factory=DatabaseConfig)
    region: RegionConfig = field(default_factory=RegionConfig)
    create_player: CreatePlayerConfig = field(default_factory=CreatePlayerConfig)
    logs: LogsConfig = field(default_factory=LogsConfig)
    servers: list[ServerConfig] = field(default_factory=list)



_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
_current: Config | None = None


def current() -> Config:
    global _current
    if _current is not None:
        return _current
    for candidate in (
        _PROJECT_ROOT / "configurations" / "server.json",
        _PROJECT_ROOT / "server.json",
    ):
        if candidate.is_file():
            _current = load(str(candidate))
            return _current
    _current = Config()
    return _current


def _to_snake_case(value: str) -> str:
    trimmed = value.strip()
    if not trimmed:
        return ""
    result = []
    underscore = False
    for ch in trimmed:
        if "A" <= ch <= "Z":
            ch = chr(ord(ch) + 32)
        if ("a" <= ch <= "z") or ("0" <= ch <= "9"):
            result.append(ch)
            underscore = False
            continue
        if not underscore and len(result) > 0:
            result.append("_")
            underscore = True
    if result and result[-1] == "_":
        result.pop()
    return "".join(result)


def _resolve_schema_name(cfg: Config) -> str:
    if cfg.database.schema_name:
        return cfg.database.schema_name
    if cfg.server.name:
        return _to_snake_case(cfg.server.name)
    return ""


def _parse_servers(data: dict) -> list[ServerConfig]:
    return [
        ServerConfig(
            id=s.get("id", 0),
            name=s.get("name", ""),
            ip=s.get("ip", ""),
            port=s.get("port", 0),
            proxy_ip=s.get("proxy_ip"),
            proxy_port=s.get("proxy_port"),
        )
        for s in data.get("servers", [])
    ]


def _read_json(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def load(path: str) -> Config:
    data = _read_json(path)

    cfg = Config()

    if "privatedock" in data:
        b = data["privatedock"]
        cfg.server.bind_address = b.get("bind_address", "0.0.0.0")
        cfg.server.port = b.get("port", 81)
        cfg.server.maintenance = b.get("maintenance", False)
        cfg.server.name = b.get("name", "Private Dock (Local)")
        req = b.get("require_private_clients")
        if req is not None:
            cfg.server.require_private_clients = req

    if "api" in data:
        a = data["api"]
        cfg.api.enabled = a.get("enabled", True)
        cfg.api.port = a.get("port", 2289)
        cfg.api.environment = a.get("environment", "development")
        cfg.api.cors_origins = a.get("cors_origins", ["*"])

    if "auth" in data:
        a = data["auth"]
        cfg.auth.disable_auth = a.get("disable_auth", False)
        cfg.auth.session_ttl_seconds = a.get("session_ttl_seconds", 86400)
        cfg.auth.session_sliding = a.get("session_sliding", True)
        cfg.auth.cookie_name = a.get("cookie_name", "privatedock_admin_session")
        cfg.auth.cookie_secure = a.get("cookie_secure", True)
        cfg.auth.cookie_same_site = a.get("cookie_same_site", "lax")
        cfg.auth.csrf_ttl_seconds = a.get("csrf_ttl_seconds", 7200)
        cfg.auth.password_min_length = a.get("password_min_length", 4)
        cfg.auth.webauthn_rp_id = a.get("webauthn_rp_id", "localhost")
        cfg.auth.webauthn_rp_name = a.get("webauthn_rp_name", "Private Dock Admin")
        cfg.auth.webauthn_expected_origins = a.get("webauthn_expected_origins", ["http://localhost:3000"])
        cfg.auth.webauthn_challenge_ttl_seconds = a.get("webauthn_challenge_ttl_seconds", 300)
        cfg.auth.rate_limit_window_seconds = a.get("rate_limit_window_seconds", 60)
        cfg.auth.rate_limit_login_max = a.get("rate_limit_login_max", 5)
        cfg.auth.rate_limit_passkey_max = a.get("rate_limit_passkey_max", 5)

    if "database" in data:
        d = data["database"]
        cfg.database.dsn = d.get("dsn", "")
        cfg.database.schema_name = d.get("schema_name", "")
        cfg.database.driver = d.get("driver", "")
        cfg.database.path = d.get("path", "")
        # ``driver = "sqlite"`` + ``path = "app.db"`` is the file-based form
        # documented in configurations/server.json; fold it into a canonical
        # DSN so every consumer only ever sees dsn/driver.
        if not cfg.database.dsn and cfg.database.path:
            cfg.database.dsn = f"sqlite:///{cfg.database.path}"

    if "region" in data:
        cfg.region.default = data["region"].get("default", "EN")

    if "create_player" in data:
        cp = data["create_player"]
        cfg.create_player.skip_onboarding = cp.get("skip_onboarding", False)
        cfg.create_player.name_blacklist = cp.get("name_blacklist", [])
        cfg.create_player.name_illegal_pattern = cp.get("name_illegal_pattern", "")

    if "logs" in data:
        l = data["logs"]
        cfg.logs.max_age_days = int(l.get("max_age_days", 14))
        cfg.logs.max_total_mb = int(l.get("max_total_mb", 30))

    cfg.servers = _parse_servers(data)

    if cfg.server.port == 0:
        cfg.server.port = 80

    schema_name = _resolve_schema_name(cfg)
    if schema_name and not cfg.database.schema_name:
        cfg.database.schema_name = schema_name

    global _current
    _current = cfg
    return cfg
