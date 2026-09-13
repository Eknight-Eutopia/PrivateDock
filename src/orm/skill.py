from __future__ import annotations
from typing import Optional
from sqlalchemy import BigInteger, String, JSON
from sqlalchemy.orm import Mapped, mapped_column

from src.db.session import Base


class Skill(Base):
    __tablename__ = 'skills'
    __table_args__ = {}
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    name: Mapped[str] = mapped_column(String, default='')
    desc: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    cd: Mapped[int] = mapped_column(BigInteger, default=0)
    painting: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    picture: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    ani_effect: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    ui_effect: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    effect_list: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
