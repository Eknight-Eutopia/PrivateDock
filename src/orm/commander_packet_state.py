from __future__ import annotations

from src.db.session import Base
from datetime import datetime
from typing import Optional
from sqlalchemy import BigInteger, Boolean, DateTime, String, JSON
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import BigInteger, Boolean, DateTime, String, JSON
from sqlalchemy.orm import Mapped, mapped_column

# ── SQLAlchemy model ──

class CommanderPacketState(Base):
    __tablename__ = 'commander_packet_states'
    owner_commander_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    commander_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    level: Mapped[int] = mapped_column(BigInteger, default=0)
    name: Mapped[str] = mapped_column(String, default='')
    is_locked: Mapped[bool] = mapped_column(Boolean, default=False)
    used_pt: Mapped[int] = mapped_column(BigInteger, default=0)
    ability_ids: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    ability_origin_ids: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    pending_ability_ids: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    ability_reset_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    rename_cooldown_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
