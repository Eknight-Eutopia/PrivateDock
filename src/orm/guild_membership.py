from __future__ import annotations

from src.db.session import Base
from sqlalchemy import BigInteger
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import BigInteger
from sqlalchemy.orm import Mapped, mapped_column

# ── SQLAlchemy model ──

class GuildMembership(Base):
    __tablename__ = 'guild_members'
    guild_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    commander_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    duty: Mapped[int] = mapped_column(BigInteger, default=0)
    liveness: Mapped[int] = mapped_column(BigInteger, default=0)
    pre_online_time: Mapped[int] = mapped_column(BigInteger, default=0)
    join_time: Mapped[int] = mapped_column(BigInteger, default=0)
