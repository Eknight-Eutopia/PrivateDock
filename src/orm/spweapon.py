from __future__ import annotations

from typing import Optional, Union
from sqlalchemy import select, text

from src.db.session import get_session, get_sync_session
from src.orm.owned_spweapon import OwnedSpweapon
from src.protobuf import protobuf


def create_owned_sp_weapon(commander_id: int, template_id: int) -> OwnedSpweapon:
    with get_sync_session() as session:
        result = session.execute(
            text("""
                INSERT INTO owned_spweapons (
                    owner_id, template_id, attr_1, attr_2, attr_temp_1, attr_temp_2, effect, pt, equipped_ship_id
                ) VALUES (
                    :cid, :tid, 0, 0, 0, 0, 0, 0, 0
                )
                RETURNING id
            """),
            {"cid": commander_id, "tid": template_id},
        )
        row = result.fetchone()
        session.commit()
        return OwnedSpweapon(
            id=row[0],
            owner_id=commander_id,
            template_id=template_id,
            attr_1=0,
            attr_2=0,
            attr_temp_1=0,
            attr_temp_2=0,
            effect=0,
            pt=0,
            equipped_ship_id=0,
        )


def save_owned_sp_weapon(spw: Union[OwnedSpweapon, dict]) -> None:
    with get_sync_session() as session:
        if isinstance(spw, dict):
            session.execute(
                text("""
                    UPDATE owned_spweapons
                    SET template_id = :tid,
                        attr_1 = :a1,
                        attr_2 = :a2,
                        attr_temp_1 = :at1,
                        attr_temp_2 = :at2,
                        effect = :eff,
                        pt = :pt,
                        equipped_ship_id = :esid
                    WHERE id = :id
                """),
                {
                    "id": spw.get("id"),
                    "tid": spw.get("template_id", 0),
                    "a1": spw.get("attr_1", spw.get("attr1", 0)),
                    "a2": spw.get("attr_2", spw.get("attr2", 0)),
                    "at1": spw.get("attr_temp_1", spw.get("attr_temp1", 0)),
                    "at2": spw.get("attr_temp_2", spw.get("attr_temp2", 0)),
                    "eff": spw.get("effect", 0),
                    "pt": spw.get("pt", 0),
                    "esid": spw.get("equipped_ship_id", 0),
                },
            )
        else:
            session.merge(spw)
        session.commit()


def remove_owned_sp_weapon(commander_id: int, spw_id: int) -> None:
    with get_sync_session() as session:
        session.execute(
            text("DELETE FROM owned_spweapons WHERE owner_id = :cid AND id = :spwid"),
            {"cid": commander_id, "spwid": spw_id},
        )
        session.commit()


def upsert_owned_sp_weapon(*args, **kwargs) -> None:
    if len(args) == 1:
        save_owned_sp_weapon(args[0])
    elif len(args) >= 2:
        commander_id, spw_id = args[0], args[1]
        with get_sync_session() as session:
            keys = ", ".join(f"{k} = :{k}" for k in kwargs)
            session.execute(
                text(f"""
                    UPDATE owned_spweapons SET {keys}
                    WHERE owner_id = :cid AND id = :spwid
                """),
                {"cid": commander_id, "spwid": spw_id, **kwargs},
            )
            session.commit()


def update_sp_weapon_equip(commander_id: int, spw_id: int, ship_id: int) -> None:
    with get_sync_session() as session:
        session.execute(
            text("""
                UPDATE owned_spweapons SET equipped_ship_id = :sid
                WHERE owner_id = :cid AND id = :spwid
            """),
            {"cid": commander_id, "spwid": spw_id, "sid": ship_id},
        )
        session.commit()


def update_sp_weapon_unequip_others(commander_id: int, ship_id: int, exclude_spw_id: int) -> None:
    with get_sync_session() as session:
        session.execute(
            text("""
                UPDATE owned_spweapons SET equipped_ship_id = 0
                WHERE owner_id = :cid AND equipped_ship_id = :sid AND id != :exclude
            """),
            {"cid": commander_id, "sid": ship_id, "exclude": exclude_spw_id},
        )
        session.commit()


def update_sp_weapon_unequip_ship(commander_id: int, ship_id: int) -> None:
    with get_sync_session() as session:
        session.execute(
            text("""
                UPDATE owned_spweapons SET equipped_ship_id = 0
                WHERE owner_id = :cid AND equipped_ship_id = :sid
            """),
            {"cid": commander_id, "sid": ship_id},
        )
        session.commit()



def list_owned_sp_weapons_sync(commander_id: int) -> list[OwnedSpweapon]:
    with get_sync_session() as session:
        result = session.execute(
            select(OwnedSpweapon).where(OwnedSpweapon.owner_id == commander_id).order_by(OwnedSpweapon.id)
        )
        return list(result.scalars().all())


def get_owned_sp_weapon_sync(commander_id: int, spw_id: int) -> Optional[OwnedSpweapon]:
    with get_sync_session() as session:
        result = session.execute(
            select(OwnedSpweapon).where(
                OwnedSpweapon.owner_id == commander_id,
                OwnedSpweapon.id == spw_id,
            )
        )
        return result.scalar_one_or_none()


async def list_owned_sp_weapons(commander_id: int) -> list[dict]:
    async with get_session() as session:
        result = await session.execute(
            text("SELECT * FROM owned_spweapons WHERE owner_id = :cid ORDER BY id"),
            {"cid": commander_id},
        )
        return [dict(r) for r in result.mappings().all()]


def to_proto_owned_sp_weapon(spw) -> Optional[protobuf.SPWEAPONINFO]:
    if spw is None:
        return None
    if isinstance(spw, dict):
        return protobuf.SPWEAPONINFO(
            id=int(spw.get("id", 0)),
            template_id=int(spw.get("template_id", 0)),
            attr_1=int(spw.get("attr_1", spw.get("attr1", 0))),
            attr_2=int(spw.get("attr_2", spw.get("attr2", 0))),
            attr_temp_1=int(spw.get("attr_temp_1", spw.get("attr_temp1", 0))),
            attr_temp_2=int(spw.get("attr_temp_2", spw.get("attr_temp2", 0))),
            effect=int(spw.get("effect", 0)),
            pt=int(spw.get("pt", 0)),
        )
    return protobuf.SPWEAPONINFO(
        id=int(getattr(spw, "id", 0)),
        template_id=int(getattr(spw, "template_id", 0)),
        attr_1=int(getattr(spw, "attr_1", getattr(spw, "attr1", 0))),
        attr_2=int(getattr(spw, "attr_2", getattr(spw, "attr2", 0))),
        attr_temp_1=int(getattr(spw, "attr_temp_1", getattr(spw, "attr_temp1", 0))),
        attr_temp_2=int(getattr(spw, "attr_temp_2", getattr(spw, "attr_temp2", 0))),
        effect=int(getattr(spw, "effect", 0)),
        pt=int(getattr(spw, "pt", 0)),
    )


def to_proto_owned_sp_weapon_list(spw_list) -> list[protobuf.SPWEAPONINFO]:
    if not spw_list:
        return []
    return [to_proto_owned_sp_weapon(spw) for spw in spw_list if spw is not None]

