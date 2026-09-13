from __future__ import annotations
from typing import Optional

from sqlalchemy import text

from src.db.session import get_session


async def get_ship_name(template_id: int) -> Optional[str]:
    async with get_session() as session:
        result = await session.execute(
            text("SELECT name FROM ships WHERE template_id = :tid"),
            {"tid": template_id},
        )
        row = result.first()
        return row[0] if row else None
