from __future__ import annotations

from src.db.session import Base
from datetime import datetime
from typing import Optional
from sqlalchemy import BigInteger, DateTime, JSON
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import BigInteger, DateTime, JSON
from sqlalchemy.orm import Mapped, mapped_column

# ── SQLAlchemy model ──

class ChallengeModeState(Base):
    __tablename__ = 'challenge_mode_states'
    commander_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    activity_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    mode: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    season_id: Mapped[int] = mapped_column(BigInteger, default=0)
    level: Mapped[int] = mapped_column(BigInteger, default=0)
    current_score: Mapped[int] = mapped_column(BigInteger, default=0)
    issl: Mapped[int] = mapped_column(BigInteger, default=0)
    regular_group_id: Mapped[int] = mapped_column(BigInteger, default=0)
    submarine_group_id: Mapped[int] = mapped_column(BigInteger, default=0)
    regular_ship_ids: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    submarine_ship_ids: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    regular_commanders: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    submarine_commanders: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
