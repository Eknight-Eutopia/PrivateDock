from typing import Any, Optional

from pydantic import BaseModel

from src.api.types.player import PaginationMeta




class EquipmentPayload(BaseModel):
    id: int
    base: Optional[int] = None
    destory_gold: int
    destory_item: Any
    equip_limit: int
    group: int
    important: int
    level: int
    next: int
    prev: int
    restore_gold: int
    restore_item: Any
    ship_type_forbidden: Any
    trans_use_gold: int
    trans_use_item: Any
    type: int
    upgrade_formula_id: Any




class EquipmentListResponse(BaseModel):
    equipment: list[EquipmentPayload]
    meta: PaginationMeta

