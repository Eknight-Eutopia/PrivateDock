from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import BigInteger, DateTime
from sqlalchemy.orm import Mapped, mapped_column

from src.db.session import Base


class CommanderBlacklist(Base):
    __tablename__ = "commander_blacklist"
    commander_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    blocked_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    created_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
