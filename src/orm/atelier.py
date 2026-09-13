from sqlalchemy import select

from src.db.session import get_session
from src.orm.atelier_state import AtelierState


async def get_or_create_atelier_state(commander_id: int):
    async with get_session() as session:
        result = await session.execute(
            select(AtelierState).where(
                AtelierState.commander_id == commander_id,
            )
        )
        state = result.scalar_one_or_none()
        if state is None:
            state = AtelierState(commander_id=commander_id)
            session.add(state)
            await session.commit()
        return state


async def lock_atelier_state(commander_id: int):
    async with get_session() as session:
        result = await session.execute(
            select(AtelierState).where(
                AtelierState.commander_id == commander_id,
            ).with_for_update()
        )
        return result.scalar_one_or_none()


async def save_atelier_state(state: AtelierState):
    async with get_session() as session:
        session.add(state)
        await session.commit()
