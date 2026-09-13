from __future__ import annotations


from sqlalchemy import select

from src.db.session import get_session, get_sync_session
from src.orm.commander_packet_state import CommanderPacketState


async def get_or_create_commander_packet_state(commander_id: int):
    async with get_session() as session:
        result = await session.execute(
            select(CommanderPacketState).where(
                CommanderPacketState.commander_id == commander_id,
            )
        )
        state = result.scalar_one_or_none()
        if state is None:
            state = CommanderPacketState(commander_id=commander_id)
            session.add(state)
            await session.commit()
        return state


async def save_commander_packet_state(state: CommanderPacketState):
    async with get_session() as session:
        session.add(state)
        await session.commit()


def _sync_get_or_create_commander_packet_state(commander_id: int):
    with get_sync_session() as session:
        result = session.execute(
            select(CommanderPacketState).where(
                CommanderPacketState.commander_id == commander_id,
            )
        )
        state = result.scalar_one_or_none()
        if state is None:
            state = CommanderPacketState(commander_id=commander_id)
            session.add(state)
            session.commit()
        return state


def _sync_save_commander_packet_state(state: CommanderPacketState):
    with get_sync_session() as session:
        session.add(state)
        session.commit()


get_or_create_commander_packet_state = _sync_get_or_create_commander_packet_state
save_commander_packet_state = _sync_save_commander_packet_state
