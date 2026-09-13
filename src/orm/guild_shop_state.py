from __future__ import annotations

from sqlalchemy import BigInteger
from sqlalchemy.orm import Mapped, mapped_column

from src.db.session import Base


class GuildShopState(Base):
    __tablename__ = 'guild_shop_states'
    __table_args__ = {}
    commander_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    refresh_count: Mapped[int] = mapped_column(BigInteger, default=0)
    next_refresh_time: Mapped[int] = mapped_column(BigInteger, default=0)
