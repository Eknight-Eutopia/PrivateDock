from __future__ import annotations
from datetime import datetime
from typing import Optional
from sqlalchemy import BigInteger, Boolean, DateTime, LargeBinary, String, JSON
from sqlalchemy.orm import Mapped, mapped_column

from src.db.session import Base


class WebAuthnCredential(Base):
    __tablename__ = 'web_authn_credentials'
    __table_args__ = {}
    id: Mapped[str] = mapped_column(String, primary_key=True)
    account_id: Mapped[str] = mapped_column(String)
    credential_id: Mapped[str] = mapped_column(String, unique=True)
    public_key: Mapped[Optional[bytes]] = mapped_column(LargeBinary, nullable=True)
    attestation_fmt: Mapped[str] = mapped_column(String, default='')
    transports: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    aaguid: Mapped[str] = mapped_column(String, default='')
    sign_count: Mapped[int] = mapped_column(BigInteger, default=0)
    backup_eligible: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    backup_state: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    created_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
