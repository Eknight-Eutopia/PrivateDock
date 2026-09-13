from typing import Optional

from sqlalchemy import select, text, func

from src.db.session import get_session
from src.orm.commander import Commander
from src.orm.fleet import Fleet


async def load_commander_with_details(commander_id: int) -> Optional[Commander]:
    async with get_session() as session:
        result = await session.execute(
            select(Commander).where(
                Commander.commander_id == commander_id,
                Commander.deleted_at.is_(None),
            )
        )
        commander = result.scalar_one_or_none()
        return commander


async def get_commander_core_by_id(commander_id: int) -> Optional[Commander]:
    async with get_session() as session:
        result = await session.execute(
            select(Commander).where(
                Commander.commander_id == commander_id,
                Commander.deleted_at.is_(None),
            )
        )
        return result.scalar_one_or_none()


def get_commander_core_by_id_sync(commander_id: int) -> Optional[Commander]:
    from src.db.session import get_sync_session as gss
    with gss() as session:
        result = session.execute(
            select(Commander).where(
                Commander.commander_id == commander_id,
                Commander.deleted_at.is_(None),
            )
        )
        return result.scalar_one_or_none()


async def check_commander_name_availability(name: str) -> bool:
    async with get_session() as session:
        result = await session.execute(
            select(func.count()).select_from(Commander).where(
                Commander.name == name,
                Commander.deleted_at.is_(None),
            )
        )
        count = result.scalar()
        return count == 0


ERR_COMMANDER_NAME_EXISTS = ValueError("commander name already exists")


async def clear_commander_common_flag(commander_id: int, flag: int):
    async with get_session() as session:
        await session.execute(
            text("DELETE FROM commander_common_flags WHERE commander_id = :cid AND flag_id = :flag"),
            {"cid": commander_id, "flag": flag},
        )
        await session.commit()


async def commit_commander(commander_id: int):
    pass


async def is_commander_in_any_fleet(commander_id: int, ship_id: int) -> bool:
    async with get_session() as session:
        result = await session.execute(
            select(func.count()).select_from(Fleet).where(
                Fleet.commander_id == commander_id,
                text("fleet_data @> :ship_id_json"),
            ).params(ship_id_json=f'[{ship_id}]')
        )
        return result.scalar() > 0
