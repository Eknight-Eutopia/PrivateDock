from __future__ import annotations

from src.db.session import Base
from sqlalchemy import BigInteger
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import BigInteger
from sqlalchemy.orm import Mapped, mapped_column

# ── SQLAlchemy model ──

class ShipyardTaskTemplateConfig(Base):
    __tablename__ = 'shipyard_task_template_configs'
    task_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    ship_id: Mapped[int] = mapped_column(BigInteger)
    blueprint_id: Mapped[int] = mapped_column(BigInteger, default=0)
