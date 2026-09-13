from __future__ import annotations

import json
from typing import Any, Optional

from sqlalchemy import BigInteger, String, JSON
from sqlalchemy import select
from sqlalchemy.orm import Mapped, mapped_column

from src.db.session import Base
from src.db.session import get_sync_session
from src.db.store import decode_json_value, get_default_store


def upsert_config_entry(category: str, key: str, data: dict) -> None:
    with get_sync_session() as session:
        entry = session.execute(
            select(ConfigEntry).where(
                ConfigEntry.category == category, ConfigEntry.key == key
            )
        ).scalar_one_or_none()
        if entry is None:
            entry = ConfigEntry(category=category, key=key, data=data)
            session.add(entry)
        else:
            entry.data = data
        session.commit()


def entry_data(entry: Any) -> Optional[dict | list]:
    if entry is None:
        return None
    if isinstance(entry, (dict, list)):
        return entry
    d = getattr(entry, "data", entry)
    if isinstance(d, str):
        try:
            return json.loads(d)
        except (ValueError, TypeError):
            return None
    return d if isinstance(d, (dict, list)) else None


def get_config_entry_sync(category: str, key: str) -> ConfigEntry | None:
    with get_sync_session() as session:
        result = session.execute(
            select(ConfigEntry).where(
                ConfigEntry.category == category,
                ConfigEntry.key == key,
            )
        )
        return result.scalar_one_or_none()

def get_config_entries_sync(category: str, keys: list) -> dict[str, ConfigEntry | None]:
    """Batch variant of get_config_entry_sync: one roundtrip for the whole key
    set; missing keys are returned as None instead of raising."""
    str_keys = [str(k) for k in keys]
    if not str_keys:
        return {}
    with get_sync_session() as session:
        result = session.execute(
            select(ConfigEntry).where(
                ConfigEntry.category == category,
                ConfigEntry.key.in_(str_keys),
            )
        )
        found = {e.key: e for e in result.scalars().all()}
    return {k: found.get(k) for k in str_keys}


def list_config_entries_sync(category: str) -> list[ConfigEntry]:
    with get_sync_session() as session:
        result = session.execute(
            select(ConfigEntry).where(ConfigEntry.category == category)
        )
        return list(result.scalars().all())

get_config_entry = get_config_entry_sync
list_config_entries = list_config_entries_sync

# --------------------------------------------------------------------------- #
# Shared data accessors
# --------------------------------------------------------------------------- #
# ``config_entries.data`` is jsonb on PostgreSQL but JSON TEXT on SQLite, and
# psycopg2 parses it while asyncpg and the SQLite paths hand back text. Every
# reader therefore needs the same normalisation, and twelve feature packages
# used to carry a private copy of the whole helper (each with its own drift:
# some swallowed exceptions, one raised NotFoundError, one was async). These
# four functions are the single implementation; the per-package
# ``get_config_entry`` / ``list_config_entries`` names stay as thin aliases so
# their call sites are untouched.


def fetch_config_entry_data(category: str, key: Any) -> Optional[Any]:
    """Decoded ``data`` of one config entry, or ``None`` when it is missing."""
    store = get_default_store()
    if store is None:
        entry = get_config_entry_sync(category, str(key))
        if entry is None:
            return None
        return decode_json_value(entry.data)
    row = store.fetchrow(
        "SELECT data FROM config_entries WHERE category = $1 AND key = $2",
        category, str(key),
    )
    if row is None:
        return None
    return decode_json_value(row["data"])


def fetch_config_entries_data(category: str) -> list:
    """Decoded ``data`` of every entry in ``category`` (sync)."""
    store = get_default_store()
    if store is None:
        entries = list_config_entries_sync(category)
        return [decode_json_value(e.data) for e in entries]
    rows = store.fetch("SELECT data FROM config_entries WHERE category = $1", category)
    return [decode_json_value(row["data"]) for row in rows]


async def afetch_config_entry_data(category: str, key: Any) -> Optional[Any]:
    """Async variant of :func:`fetch_config_entry_data`."""
    store = get_default_store()
    if store is None:
        return None
    row = await store.afetchrow(
        "SELECT data FROM config_entries WHERE category = $1 AND key = $2",
        category, str(key),
    )
    if row is None:
        return None
    return decode_json_value(row["data"])


async def afetch_config_entries_data(category: str) -> list:
    """Async variant of :func:`fetch_config_entries_data`."""
    store = get_default_store()
    if store is None:
        return []
    rows = await store.afetch(
        "SELECT data FROM config_entries WHERE category = $1", category
    )
    return [decode_json_value(row["data"]) for row in rows]


def fetch_config_entries_map(category: str, keys: list[Any]) -> dict[str, Any]:
    """Decoded ``data`` keyed by string key for matching keys in ``category`` (sync)."""
    if not keys:
        return {}
    store = get_default_store()
    if store is None:
        entries_dict = get_config_entries_sync(category, keys)
        return {k: decode_json_value(e.data) for k, e in entries_dict.items() if e is not None}
    str_keys = [str(k) for k in keys]
    rows = store.fetch(
        "SELECT key, data FROM config_entries WHERE category = $1 AND key = ANY($2)",
        category, str_keys,
    )
    return {r["key"]: decode_json_value(r["data"]) for r in rows}


async def afetch_config_entries_map(category: str, keys: list[Any]) -> dict[str, Any]:
    """Decoded ``data`` keyed by string key for matching keys in ``category`` (async)."""
    if not keys:
        return {}
    store = get_default_store()
    if store is None:
        return {}
    str_keys = [str(k) for k in keys]
    rows = await store.afetch(
        "SELECT key, data FROM config_entries WHERE category = $1 AND key = ANY($2)",
        category, str_keys,
    )
    return {r["key"]: decode_json_value(r["data"]) for r in rows}


def _dump_config_value(data) -> str:
    """Serialise a config payload; already-serialised JSON text passes through."""
    if isinstance(data, (bytes, bytearray)):
        return bytes(data).decode("utf-8")
    if isinstance(data, str):
        return data
    return json.dumps(data, ensure_ascii=False)


def upsert_config_entry_data(category: str, key: Any, data) -> None:
    """Write ``data`` under ``(category, key)`` in a single roundtrip.

    ``data`` may be a Python object (dict/list/...) or JSON text. ``key`` is
    stringified so it always matches :func:`fetch_config_entry_data`, which
    reads with ``str(key)`` — passing an int here and a str there used to
    address two different rows.
    """
    store = get_default_store()
    if store is None:
        return
    store.execute(
        "INSERT INTO config_entries (category, key, data) "
        "VALUES ($1, $2, $3::jsonb) "
        "ON CONFLICT (category, key) DO UPDATE SET data = EXCLUDED.data",
        category, str(key), _dump_config_value(data),
    )


async def aupsert_config_entry_data(category: str, key: Any, data) -> None:
    """Async variant of :func:`upsert_config_entry_data`."""
    store = get_default_store()
    if store is None:
        return
    await store.aexecute(
        "INSERT INTO config_entries (category, key, data) "
        "VALUES ($1, $2, $3::jsonb) "
        "ON CONFLICT (category, key) DO UPDATE SET data = EXCLUDED.data",
        category, str(key), _dump_config_value(data),
    )


class ConfigEntry(Base):
    __tablename__ = 'config_entries'
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    category: Mapped[str] = mapped_column(String, default='')
    key: Mapped[str] = mapped_column(String, default='')
    data: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
