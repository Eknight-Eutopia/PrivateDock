from __future__ import annotations

from src.db.session import Base
from typing import Optional
from sqlalchemy import BigInteger, JSON
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import BigInteger, JSON
from sqlalchemy.orm import Mapped, mapped_column

# ── SQLAlchemy model ──

class ComposeDataTemplate(Base):
    __tablename__ = 'compose_data_templates'
    template_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    template_data: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
