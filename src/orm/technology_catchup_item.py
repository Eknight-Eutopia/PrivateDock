from __future__ import annotations

from src.db.session import Base
from typing import Optional
from sqlalchemy import BigInteger, JSON
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import BigInteger, JSON
from sqlalchemy.orm import Mapped, mapped_column

# ── SQLAlchemy model ──

class TechnologyCatchupItem(Base):
    __tablename__ = 'technology_catchup_items'
    catchup_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    item_data: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
