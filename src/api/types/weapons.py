from typing import Any

from pydantic import BaseModel

from src.api.types.player import PaginationMeta




class WeaponPayload(BaseModel):
    id: int
    action_index: str
    aim_type: int
    angle: int
    attack_attribute: int
    attack_attribute_ratio: int
    auto_aftercast: Any
    axis_angle: int
    barrage_id: Any
    bullet_id: Any
    charge_param: Any
    corrected: int
    damage: int
    effect_move: int
    expose: int
    fire_fx: str
    fire_fx_loop_type: int
    fire_sfx: str
    initial_over_heat: int
    min_range: int
    oxy_type: Any
    precast_param: Any
    queue: int
    range: int
    recover_time: Any
    reload_max: int
    search_condition: Any
    search_type: int
    shakescreen: int
    spawn_bound: Any
    suppress: int
    torpedo_ammo: int
    type: int




class WeaponListResponse(BaseModel):
    weapons: list[WeaponPayload]
    meta: PaginationMeta

