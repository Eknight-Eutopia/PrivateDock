from typing import Any

from pydantic import BaseModel

from src.api.types.player import PaginationMeta




class SkillPayload(BaseModel):
    id: int
    name: str
    desc: str
    cd: int
    painting: Any
    picture: str
    ani_effect: Any
    ui_effect: str
    effect_list: Any




class SkillListResponse(BaseModel):
    skills: list[SkillPayload]
    meta: PaginationMeta

