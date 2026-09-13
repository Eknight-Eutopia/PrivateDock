from __future__ import annotations
from datetime import datetime
from typing import Optional
from sqlalchemy import BigInteger, DateTime, JSON
from sqlalchemy.orm import Mapped, mapped_column

from src.db.session import Base


class EscortState(Base):
    __tablename__ = 'escort_states'
    __table_args__ = {}
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    account_id: Mapped[int] = mapped_column(BigInteger)
    line_id: Mapped[int] = mapped_column(BigInteger, default=0)
    award_timestamp: Mapped[int] = mapped_column(BigInteger, default=0)
    flash_timestamp: Mapped[int] = mapped_column(BigInteger, default=0)
    map_positions: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
