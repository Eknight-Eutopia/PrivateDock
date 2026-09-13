from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from src.config.config import Config as RuntimeConfig


@dataclass
class APIConfig:
    enabled: bool = False
    env: str = "development"
    port: int = 2289
    cors_origins: list[str] = field(default_factory=list)
    runtime_config: Optional[RuntimeConfig] = None


def load_config(cfg: RuntimeConfig) -> APIConfig:
    api_cfg = APIConfig(
        enabled=cfg.api.enabled,
        env=cfg.api.environment,
        port=cfg.api.port,
        cors_origins=list(cfg.api.cors_origins),
        runtime_config=cfg,
    )
    if api_cfg.env == "development" and len(api_cfg.cors_origins) == 0:
        api_cfg.cors_origins = ["*"]
    api_cfg.cors_origins = [o.strip() for o in api_cfg.cors_origins if o.strip()]
    return api_cfg
