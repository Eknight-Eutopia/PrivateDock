from __future__ import annotations
from sqlalchemy import BigInteger, String
from sqlalchemy.orm import Mapped, mapped_column
from src.db.session import Base


class Buff(Base):
    __tablename__ = 'buffs'
    __table_args__ = {}
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    name: Mapped[str] = mapped_column(String, default='')
    description: Mapped[str] = mapped_column(String, default='')
    max_time: Mapped[int] = mapped_column(BigInteger, default=0)
    benefit_type: Mapped[str] = mapped_column(String, default='')
