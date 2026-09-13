from __future__ import annotations

from sqlalchemy import BigInteger
from sqlalchemy.orm import Mapped, mapped_column

from src.db.session import Base


class MedalShopGood(Base):
    __tablename__ = 'medal_shop_goods'
    __table_args__ = {}
    commander_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    index: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    goods_id: Mapped[int] = mapped_column(BigInteger, default=0)
    count: Mapped[int] = mapped_column(BigInteger, default=0)
