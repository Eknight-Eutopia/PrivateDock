from __future__ import annotations


from sqlalchemy import BigInteger
from sqlalchemy.orm import Mapped, mapped_column

from src.db.session import Base


class ChapterProgress(Base):
    __tablename__ = 'chapter_progress'
    __table_args__ = {}
    commander_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    chapter_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    progress: Mapped[int] = mapped_column(BigInteger, default=0)
    kill_boss_count: Mapped[int] = mapped_column(BigInteger, default=0)
    kill_enemy_count: Mapped[int] = mapped_column(BigInteger, default=0)
    take_box_count: Mapped[int] = mapped_column(BigInteger, default=0)
    defeat_count: Mapped[int] = mapped_column(BigInteger, default=0)
    today_defeat_count: Mapped[int] = mapped_column(BigInteger, default=0)
    pass_count: Mapped[int] = mapped_column(BigInteger, default=0)
    star_rewarded: Mapped[int] = mapped_column(BigInteger, default=0)
    clear_rewarded: Mapped[int] = mapped_column(BigInteger, default=0)
    updated_at: Mapped[int] = mapped_column(BigInteger, default=0)
