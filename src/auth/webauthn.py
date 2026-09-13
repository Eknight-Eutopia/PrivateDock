from typing import Optional, Protocol

from src.auth.config import normalize_admin_config
from src.auth.rate_limiter import RateLimiter
from src.config.config import AuthConfig


class WebAuthnProvider(Protocol):
    async def begin_registration(self, user, opts: Optional[list] = None):
        ...

    async def finish_registration(self, user, session, request):
        ...

    async def begin_login(self, user, opts: Optional[list] = None):
        ...

    async def begin_discoverable_login(self, opts: Optional[list] = None):
        ...

    async def finish_login(self, user, session, request):
        ...


class Manager:
    def __init__(self, cfg: AuthConfig):
        cfg = normalize_admin_config(cfg)
        self.config = cfg
        self.limiter = RateLimiter()
        self._webauthn: Optional[WebAuthnProvider] = None
        if cfg.webauthn_rp_id and cfg.webauthn_rp_name and cfg.webauthn_expected_origins:
            self._init_webauthn()

    def _init_webauthn(self):
        try:
            import webauthn as w3
            self._webauthn = _RealWebAuthn(
                rp_id=self.config.webauthn_rp_id,
                rp_name=self.config.webauthn_rp_name,
                origins=self.config.webauthn_expected_origins,
                challenge_ttl=self.config.webauthn_challenge_ttl_seconds,
            )
        except ImportError:
            pass

    def ensure_webauthn(self):
        if self._webauthn is None:
            raise RuntimeError("webauthn is not configured")
        return self._webauthn

    @property
    def webauthn(self):
        return self._webauthn


class _RealWebAuthn:
    def __init__(self, rp_id: str, rp_name: str, origins: list[str], challenge_ttl: int):
        self.rp_id = rp_id
        self.rp_name = rp_name
        self.origins = origins
        self.challenge_ttl = challenge_ttl
