from __future__ import annotations

from src.db.session import Base
from typing import Optional
from sqlalchemy import BigInteger, JSON
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import BigInteger, JSON
from sqlalchemy.orm import Mapped, mapped_column

# ── SQLAlchemy model ──

class TransformDataTemplate(Base):
    __tablename__ = 'transform_data_templates'
    template_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    transform_data: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
