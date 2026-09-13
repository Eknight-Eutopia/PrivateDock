from pydantic import BaseModel

from src.api.types.player import PaginationMeta




class BuffPayload(BaseModel):
    id: int
    name: str
    desc: str
    max_time: int
    benefit_type: str




class BuffListResponse(BaseModel):
    buffs: list[BuffPayload]
    meta: PaginationMeta

