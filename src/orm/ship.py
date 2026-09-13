from __future__ import annotations
from sqlalchemy import BigInteger, String
from sqlalchemy.orm import Mapped, mapped_column

from src.db.session import Base


class Ship(Base):
    __tablename__ = 'ships'
    __table_args__ = {}
    template_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    name: Mapped[str] = mapped_column(String, default='')
    english_name: Mapped[str] = mapped_column(String, default='')
    rarity_id: Mapped[int] = mapped_column(BigInteger, default=0)
    star: Mapped[int] = mapped_column(BigInteger, default=0)
    type: Mapped[int] = mapped_column(BigInteger, default=0)
    nationality: Mapped[int] = mapped_column(BigInteger, default=0)
    build_time: Mapped[int] = mapped_column(BigInteger, default=0)
