from __future__ import annotations

from typing import Optional

from sqlalchemy import BigInteger, LargeBinary
from sqlalchemy.orm import Mapped, mapped_column

from src.db.session import Base


class ChapterState(Base):
    __tablename__ = 'chapter_states'
    __table_args__ = {}
    commander_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    chapter_id: Mapped[int] = mapped_column(BigInteger, default=0)
    state: Mapped[Optional[bytes]] = mapped_column(LargeBinary, nullable=True)
    updated_at: Mapped[int] = mapped_column(BigInteger, default=0)
