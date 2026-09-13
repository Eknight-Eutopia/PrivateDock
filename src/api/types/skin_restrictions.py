from pydantic import BaseModel

from src.api.types.player import PaginationMeta






class SkinRestrictionCreateRequest(BaseModel):
    skin_id: int
    type: int






class SkinRestrictionPayload(BaseModel):
    skin_id: int
    type: int






class SkinRestrictionListResponse(BaseModel):
    skin_restrictions: list[SkinRestrictionPayload]
    meta: PaginationMeta






class SkinRestrictionUpdateRequest(BaseModel):
    type: int






class SkinRestrictionWindowCreateRequest(BaseModel):
    id: int
    skin_id: int
    type: int
    start_time: int
    stop_time: int






class SkinRestrictionWindowPayload(BaseModel):
    id: int
    skin_id: int
    type: int
    start_time: int
    stop_time: int






class SkinRestrictionWindowListResponse(BaseModel):
    windows: list[SkinRestrictionWindowPayload]
    meta: PaginationMeta




class SkinRestrictionWindowUpdateRequest(BaseModel):
    skin_id: int
    type: int
    start_time: int
    stop_time: int




