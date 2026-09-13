from __future__ import annotations
from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from src.db.session import Base


class RolePermission(Base):
    __tablename__ = 'role_permissions'
    __table_args__ = {}
    role_id: Mapped[str] = mapped_column(String, primary_key=True)
    permission_id: Mapped[str] = mapped_column(String, primary_key=True)
