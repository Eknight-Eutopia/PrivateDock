from __future__ import annotations

from typing import Optional

from sqlalchemy import BigInteger, JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from src.db.session import Base, get_sync_session
from sqlalchemy import select
from src.orm.owned_skin import OwnedSkin, OwnedShipShadowSkin


class Skin(Base):
    __tablename__ = 'skins'
    __table_args__ = {}
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    name: Mapped[str] = mapped_column(String, default='')
    ship_group: Mapped[int] = mapped_column(BigInteger, default=0)
    desc: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    bg: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    bg_sp: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    bgm: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    painting: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    prefab: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    change_skin: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    show_skin: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    skeleton_skin: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    ship_l2_d_id: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    l2_d_animations: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    l2_d_drag_rate: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    l2_d_para_range: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    l2_dse: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    l2_d_voice_calib: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    part_scale: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    main_ui_fx: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    spine_offset: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    spine_profile: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    tag: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    time: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    get_showing: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    purchase_offset: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    shop_offset: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    rarity_bg: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    special_effects: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    group_index: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    gyro: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    hand_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    illustrator: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    voice_actor: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    voice_actor2: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    double_char: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    lip_smoothing: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    lip_sync_gain: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    l2_d_ignore_drag: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    skin_type: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    shop_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    shop_type_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    shop_dynamic_hx: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    spine_action: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    spine_use_live2_d: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    live2_d_offset: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    live2_d_profile: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    fx_container: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    bound_bone: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    smoke: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)




def give_skin(commander_id: int, skin_id: int) -> bool:
    with get_sync_session() as session:
        existing = session.execute(
            select(OwnedSkin).where(
                OwnedSkin.commander_id == commander_id,
                OwnedSkin.skin_id == skin_id,
            )
        ).scalar_one_or_none()
        if existing is not None:
            return False
        session.add(OwnedSkin(commander_id=commander_id, skin_id=skin_id))
        session.commit()
        # Keep the in-memory owned_skins_map in sync.
        try:
            from src.orm.active_commander import _set_value_map
            _set_value_map(commander_id, "owned_skins_map", skin_id)
        except Exception:
            pass
        return True


def get_owned_skin_expiry(commander_id: int, skin_id: int) -> int | None:
    with get_sync_session() as session:
        obj = session.execute(
            select(OwnedSkin).where(
                OwnedSkin.commander_id == commander_id,
                OwnedSkin.skin_id == skin_id,
            )
        ).scalar_one_or_none()
        if obj is None:
            return None
        return obj.expiry


def list_owned_ship_shadow_skins(commander_id: int, ship_ids: Optional[list] = None) -> list:
    with get_sync_session() as session:
        stmt = select(OwnedShipShadowSkin).where(
            OwnedShipShadowSkin.commander_id == commander_id
        )
        if ship_ids:
            stmt = stmt.where(OwnedShipShadowSkin.ship_id.in_(ship_ids))
        result = session.execute(stmt)
        return list(result.scalars().all())
