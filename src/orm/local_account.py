from __future__ import annotations

from src.db.session import Base
from datetime import datetime
from typing import Optional
from sqlalchemy import BigInteger, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import BigInteger, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

# ── SQLAlchemy model ──

class LocalAccount(Base):
    __tablename__ = 'local_accounts'
    arg2: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    account: Mapped[str] = mapped_column(String)
    password: Mapped[str] = mapped_column(String, default='')
    password_hash: Mapped[str] = mapped_column(String, default='')
    mail_box: Mapped[str] = mapped_column(String, default='')
    created_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
