from typing import Any, Optional

from pydantic import BaseModel


class SkinPayload(BaseModel):
    id: int
    name: str
    ship_group: int
    desc: str
    bg: str
    bg_sp: str
    bgm: str
    painting: str
    prefab: str
    change_skin: Any
    show_skin: str
    skeleton_default_skin: str
    ship_l2d_id: Any
    l2d_animations: Any
    l2d_drag_rate: Any
    l2d_para_range: Any
    l2d_se: Any
    l2d_voice_calibrate: Any
    part_scale: str
    main_ui_fx: str
    spine_offset: Any
    spine_offset_profile: Any
    tag: Any
    time: Any
    get_showing: Any
    purchase_offset: Any
    shop_offset: Any
    rarity_bg: str
    special_effects: Any
    group_index: Optional[int] = None
    gyro: Optional[int] = None
    hand_id: Optional[int] = None
    illustrator: Optional[int] = None
    illustrator2: Optional[int] = None
    voice_actor: Optional[int] = None
    voice_actor_2: Optional[int] = None
    double_char: Optional[int] = None
    lip_smoothing: Optional[int] = None
    lip_sync_gain: Optional[int] = None
    l2d_ignore_drag: Optional[int] = None
    skin_type: Optional[int] = None
    shop_id: Optional[int] = None
    shop_type_id: Optional[int] = None
    shop_dynamic_hx: Optional[int] = None
    spine_action_offset: Any
    spine_use_live2d: Optional[int] = None
    live2d_offset: Any
    live2d_offset_profile: Any
    fx_container: Any
    bound_bone: Any
    smoke: Any
