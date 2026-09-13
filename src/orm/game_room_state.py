from __future__ import annotations

from sqlalchemy import text

from src.db.session import get_session


async def load_game_room_state(commander_id: int):
    async with get_session() as session:
        result = await session.execute(
            text("SELECT * FROM game_room_states WHERE commander_id = :cid"),
            {"cid": commander_id},
        )
        return result.fetchone()


async def list_game_room_scores(commander_id: int):
    async with get_session() as session:
        result = await session.execute(
            text("SELECT * FROM game_room_scores WHERE commander_id = :cid"),
            {"cid": commander_id},
        )
        return result.fetchall()
