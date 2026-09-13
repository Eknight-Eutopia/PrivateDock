from __future__ import annotations
from typing import Optional
from sqlalchemy import BigInteger, String, JSON
from sqlalchemy.orm import Mapped, mapped_column

from src.db.session import Base


class Weapon(Base):
    __tablename__ = 'weapons'
    __table_args__ = {}
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    action_index: Mapped[str] = mapped_column(String, default='')
    aim_type: Mapped[int] = mapped_column(BigInteger, default=0)
    angle: Mapped[int] = mapped_column(BigInteger, default=0)
    attack_attribute: Mapped[int] = mapped_column(BigInteger, default=0)
    attack_attribute_ratio: Mapped[int] = mapped_column(BigInteger, default=0)
    auto_aftercast: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    axis_angle: Mapped[int] = mapped_column(BigInteger, default=0)
    barrage_id: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    bullet_id: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    charge_param: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    corrected: Mapped[int] = mapped_column(BigInteger, default=0)
    damage: Mapped[int] = mapped_column(BigInteger, default=0)
    effect_move: Mapped[int] = mapped_column(BigInteger, default=0)
    expose: Mapped[int] = mapped_column(BigInteger, default=0)
    fire_fx: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    fire_fx_loop_type: Mapped[int] = mapped_column(BigInteger, default=0)
    fire_sfx: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    initial_over_heat: Mapped[int] = mapped_column(BigInteger, default=0)
    min_range: Mapped[int] = mapped_column(BigInteger, default=0)
    oxy_type: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    precast_param: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    queue: Mapped[int] = mapped_column(BigInteger, default=0)
    range: Mapped[int] = mapped_column(BigInteger, default=0)
    recover_time: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    reload_max: Mapped[int] = mapped_column(BigInteger, default=0)
    search_condition: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    search_type: Mapped[int] = mapped_column(BigInteger, default=0)
    shake_screen: Mapped[int] = mapped_column(BigInteger, default=0)
    spawn_bound: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    suppress: Mapped[int] = mapped_column(BigInteger, default=0)
    torpedo_ammo: Mapped[int] = mapped_column(BigInteger, default=0)
    type: Mapped[int] = mapped_column(BigInteger, default=0)
