from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import BigInteger, DateTime, text
from sqlalchemy.orm import Mapped, mapped_column

from src.db.session import Base, get_sync_session


class Like(Base):
    __tablename__ = "likes"
    group_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    liker_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    created_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)


def create_like(group_id: int, liker_id: int) -> None:
    with get_sync_session() as session:
        session.execute(
            text("""
                INSERT INTO likes (group_id, liker_id, created_at)
                VALUES (:gid, :lid, CURRENT_TIMESTAMP)
                ON CONFLICT (group_id, liker_id) DO NOTHING
            """),
            {"gid": group_id, "lid": liker_id},
        )
        session.commit()


def delete_like(group_id: int, liker_id: int) -> bool:
    with get_sync_session() as session:
        result = session.execute(
            text("DELETE FROM likes WHERE group_id = :gid AND liker_id = :lid"),
            {"gid": group_id, "lid": liker_id},
        )
        session.commit()
        return result.rowcount > 0


def count_likes_by_group_id(group_id: int) -> int:
    with get_sync_session() as session:
        return session.execute(
            text("SELECT COUNT(*) FROM likes WHERE group_id = :gid"),
            {"gid": group_id},
        ).scalar() or 0


create_like_sync = create_like
delete_like_sync = delete_like
count_likes_by_group_id_sync = count_likes_by_group_id
