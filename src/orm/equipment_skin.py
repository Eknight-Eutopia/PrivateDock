"""Equipment skin ownership (client EQUIPESKIN / SC_14101).

The client gates skin application on `SC_14101.equip_skin_list[].count >= 1`
(`EquipmentProxy.getEquipmnentSkinById`) and mirrors count changes locally
after each CS_12036 success (apply consumes the new skin, the previous skin is
returned). Originally send only OWNED skins with real counts — not the whole
template table with count=0.
"""
from __future__ import annotations

from sqlalchemy import text

from src.db.session import get_sync_session


def list_owned_equip_skins_sync(commander_id: int) -> list[tuple[int, int]]:
    """[(skin_id, count), ...] for skins the commander owns (count > 0)."""
    with get_sync_session() as session:
        rows = session.execute(
            text("SELECT skin_id, count FROM commander_equip_skins "
                 "WHERE commander_id = :cid AND count > 0"),
            {"cid": commander_id},
        ).all()
    return [(int(r[0]), int(r[1])) for r in rows]


def get_equip_skin_count_sync(commander_id: int, skin_id: int) -> int:
    with get_sync_session() as session:
        val = session.execute(
            text("SELECT count FROM commander_equip_skins "
                 "WHERE commander_id = :cid AND skin_id = :sid"),
            {"cid": commander_id, "sid": skin_id},
        ).scalar()
    return int(val or 0)


def grant_equip_skin_sync(commander_id: int, skin_id: int, count: int) -> None:
    if count <= 0:
        return
    with get_sync_session() as session:
        session.execute(
            text("INSERT INTO commander_equip_skins (commander_id, skin_id, count) "
                 "VALUES (:cid, :sid, :c) "
                 "ON CONFLICT (commander_id, skin_id) "
                 "DO UPDATE SET count = commander_equip_skins.count + :c"),
            {"cid": commander_id, "sid": skin_id, "c": count},
        )
        session.commit()


def consume_equip_skin_sync(commander_id: int, skin_id: int, count: int = 1) -> bool:
    """Take `count` skins from stock; False when not enough owned."""
    if count <= 0:
        return True
    with get_sync_session() as session:
        val = session.execute(
            text("SELECT count FROM commander_equip_skins "
                 "WHERE commander_id = :cid AND skin_id = :sid"),
            {"cid": commander_id, "sid": skin_id},
        ).scalar()
        if int(val or 0) < count:
            return False
        session.execute(
            text("UPDATE commander_equip_skins SET count = count - :c "
                 "WHERE commander_id = :cid AND skin_id = :sid"),
            {"cid": commander_id, "sid": skin_id, "c": count},
        )
        session.commit()
    return True
