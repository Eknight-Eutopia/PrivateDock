from __future__ import annotations

from src.db.session import Base
from typing import Optional
from sqlalchemy import BigInteger, JSON
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import BigInteger, JSON
from sqlalchemy.orm import Mapped, mapped_column

# ── SQLAlchemy model ──

class AtelierState(Base):
    __tablename__ = 'atelier_states'
    commander_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    data: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
