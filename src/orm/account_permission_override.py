from __future__ import annotations
from datetime import datetime
from typing import Optional
from sqlalchemy import Boolean, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from src.db.session import Base


class AccountPermissionOverride(Base):
    __tablename__ = 'account_permission_overrides'
    __table_args__ = {}
    account_id: Mapped[str] = mapped_column(String, primary_key=True)
    permission_id: Mapped[str] = mapped_column(String, primary_key=True)
    mode: Mapped[str] = mapped_column(String, default='')
    can_read_self: Mapped[bool] = mapped_column(Boolean, default=False)
    can_read_any: Mapped[bool] = mapped_column(Boolean, default=False)
    can_write_self: Mapped[bool] = mapped_column(Boolean, default=False)
    can_write_any: Mapped[bool] = mapped_column(Boolean, default=False)
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
