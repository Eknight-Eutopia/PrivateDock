from __future__ import annotations

from src.db.session import Base
from sqlalchemy import BigInteger
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import BigInteger
from sqlalchemy.orm import Mapped, mapped_column

# ── SQLAlchemy model ──

class AuthIdentityMap(Base):
    __tablename__ = 'yostarus_maps'
    arg2: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    account_id: Mapped[int] = mapped_column(BigInteger)
