from __future__ import annotations

from src.db.session import Base
from datetime import datetime
from typing import Optional
from sqlalchemy import BigInteger, DateTime, JSON
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import BigInteger, DateTime, JSON
from sqlalchemy.orm import Mapped, mapped_column

# ── SQLAlchemy model ──

class NewServerShopStateTable(Base):
    __tablename__ = 'new_server_shop_states'
    commander_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    activity_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    goods: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
