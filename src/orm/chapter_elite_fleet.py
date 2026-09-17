from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import BigInteger, DateTime, JSON
from sqlalchemy.orm import Mapped, mapped_column

from src.db.session import Base
from src.db.store import decode_json_value, get_default_store


class ChapterEliteFleet(Base):
    __tablename__ = "chapter_elite_fleets"

    commander_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    formation_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    main_team: Mapped[list] = mapped_column(JSON, default=list)
    submarine_team: Mapped[list] = mapped_column(JSON, default=list)
    support_team: Mapped[list] = mapped_column(JSON, default=list)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


def _normalize_team_list(raw: Any) -> list[dict]:
    decoded = decode_json_value(raw)
    if isinstance(decoded, str):
        try:
            decoded = json.loads(decoded)
        except Exception:
            decoded = []
    if not isinstance(decoded, list):
        return []
    teams = []
    for t in decoded:
        if isinstance(t, dict):
            teams.append({
                "id": int(t.get("id", 0)),
                "ship_list": [int(s) for s in t.get("ship_list", []) if s],
                "commander_main": int(t.get("commander_main", 0)),
                "commander_sub": int(t.get("commander_sub", 0)),
            })
    return teams


def _row_to_dict(row: Any) -> dict:
    return {
        "commander_id": int(row[0]),
        "formation_id": int(row[1]),
        "main_team": _normalize_team_list(row[2]),
        "submarine_team": _normalize_team_list(row[3]),
        "support_team": _normalize_team_list(row[4]),
    }


def list_chapter_elite_fleets_sync(commander_id: int) -> list[dict]:
    store = get_default_store()
    if store is None:
        return []
    rows = store.fetch(
        "SELECT commander_id, formation_id, main_team, submarine_team, support_team "
        "FROM chapter_elite_fleets WHERE commander_id = $1 ORDER BY formation_id",
        commander_id,
    )
    return [_row_to_dict(r) for r in (rows or [])]


async def list_chapter_elite_fleets(commander_id: int) -> list[dict]:
    store = get_default_store()
    if store is None:
        return []
    rows = await store.afetch(
        "SELECT commander_id, formation_id, main_team, submarine_team, support_team "
        "FROM chapter_elite_fleets WHERE commander_id = $1 ORDER BY formation_id",
        commander_id,
    )
    return [_row_to_dict(r) for r in (rows or [])]


def save_chapter_elite_fleet_sync(
    commander_id: int,
    formation_id: int,
    main_team: list[dict],
    submarine_team: list[dict],
    support_team: list[dict],
) -> None:
    store = get_default_store()
    if store is None:
        return
    store.execute(
        "INSERT INTO chapter_elite_fleets ("
        "  commander_id, formation_id, main_team, submarine_team, support_team, updated_at"
        ") VALUES ($1, $2, $3, $4, $5, NOW()) "
        "ON CONFLICT (commander_id, formation_id) "
        "DO UPDATE SET "
        "  main_team = EXCLUDED.main_team, "
        "  submarine_team = EXCLUDED.submarine_team, "
        "  support_team = EXCLUDED.support_team, "
        "  updated_at = NOW()",
        commander_id,
        formation_id,
        json.dumps(main_team),
        json.dumps(submarine_team),
        json.dumps(support_team),
    )


async def save_chapter_elite_fleet(
    commander_id: int,
    formation_id: int,
    main_team: list[dict],
    submarine_team: list[dict],
    support_team: list[dict],
) -> None:
    store = get_default_store()
    if store is None:
        return
    await store.aexecute(
        "INSERT INTO chapter_elite_fleets ("
        "  commander_id, formation_id, main_team, submarine_team, support_team, updated_at"
        ") VALUES ($1, $2, $3, $4, $5, NOW()) "
        "ON CONFLICT (commander_id, formation_id) "
        "DO UPDATE SET "
        "  main_team = EXCLUDED.main_team, "
        "  submarine_team = EXCLUDED.submarine_team, "
        "  support_team = EXCLUDED.support_team, "
        "  updated_at = NOW()",
        commander_id,
        formation_id,
        json.dumps(main_team),
        json.dumps(submarine_team),
        json.dumps(support_team),
    )


def remove_ship_from_elite_fleets_sync(commander_id: int, ship_id: int) -> list[dict]:
    fleets = list_chapter_elite_fleets_sync(commander_id)
    updated_fleets = []
    for f in fleets:
        modified = False
        for team_key in ("main_team", "submarine_team", "support_team"):
            for t in f[team_key]:
                if ship_id in t["ship_list"]:
                    t["ship_list"] = [s for s in t["ship_list"] if s != ship_id]
                    modified = True
        if modified:
            save_chapter_elite_fleet_sync(
                commander_id,
                f["formation_id"],
                f["main_team"],
                f["submarine_team"],
                f["support_team"],
            )
        updated_fleets.append(f)
    return updated_fleets


async def remove_ship_from_elite_fleets(commander_id: int, ship_id: int) -> list[dict]:
    fleets = await list_chapter_elite_fleets(commander_id)
    updated_fleets = []
    for f in fleets:
        modified = False
        for team_key in ("main_team", "submarine_team", "support_team"):
            for t in f[team_key]:
                if ship_id in t["ship_list"]:
                    t["ship_list"] = [s for s in t["ship_list"] if s != ship_id]
                    modified = True
        if modified:
            await save_chapter_elite_fleet(
                commander_id,
                f["formation_id"],
                f["main_team"],
                f["submarine_team"],
                f["support_team"],
            )
        updated_fleets.append(f)
    return updated_fleets
