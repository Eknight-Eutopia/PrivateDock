from __future__ import annotations
from datetime import datetime
from typing import Optional
from sqlalchemy import DateTime, LargeBinary, String
from sqlalchemy.orm import Mapped, mapped_column

from src.db.session import Base


class AuthChallenge(Base):
    __tablename__ = 'auth_challenges'
    __table_args__ = {}
    id: Mapped[str] = mapped_column(String, primary_key=True)
    account_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    challenge_type: Mapped[str] = mapped_column(String, default='')
    challenge_data: Mapped[str] = mapped_column(String, default='')
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    challenge_metadata: Mapped[Optional[bytes]] = mapped_column("metadata", LargeBinary, nullable=True)
