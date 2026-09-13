"""Region helpers for the server-link (CS_10802 -> SC_10803) flow.

Thin re-export layer: the active region lives in :mod:`src.region.region`, and
the per-region gateway/proxy hosts live in ``configurations/regions.json``
(:mod:`src.config.regions`). Both used to be duplicated here — do not
re-introduce local copies, import from the canonical modules instead.
"""

from src.config.regions import REGION_GATEWAYS, REGION_PROXIES
from src.region.region import current as current_region
from src.region.region import set_current as set_current_region

__all__ = [
    "current_region",
    "set_current_region",
    "REGION_GATEWAYS",
    "REGION_PROXIES",
]
