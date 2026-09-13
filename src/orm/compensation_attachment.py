from __future__ import annotations
from sqlalchemy import BigInteger
from sqlalchemy.orm import Mapped, mapped_column

from src.db.session import Base


class CompensationAttachment(Base):
    __tablename__ = 'compensation_attachments'
    __table_args__ = {}
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    compensation_id: Mapped[int] = mapped_column(BigInteger)
    type: Mapped[int] = mapped_column(BigInteger, default=0)
    item_id: Mapped[int] = mapped_column(BigInteger, default=0)
    quantity: Mapped[int] = mapped_column(BigInteger, default=0)
