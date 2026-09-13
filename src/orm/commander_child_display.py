from __future__ import annotations

from sqlalchemy import text

from src.db.session import get_sync_session


def update_commander_child_display(commander_id: int, child_display: int) -> None:
    with get_sync_session() as session:
        session.execute(
            text("""
                UPDATE commanders
                SET child_display = :child_display
                WHERE commander_id = :commander_id
            """),
            {"commander_id": commander_id, "child_display": child_display},
        )
        session.commit()
