from typing import Optional

from pydantic import BaseModel

from src.api.types.player import PaginationMeta






class ExchangeCodeRedeemRequest(BaseModel):
    commander_id: int




class ExchangeCodeRedeemSummary(BaseModel):
    commander_id: int
    redeemed_at: str






class ExchangeCodeRedeemListResponse(BaseModel):
    redeems: list[ExchangeCodeRedeemSummary]
    meta: PaginationMeta






class ExchangeReward(BaseModel):
    type: int
    id: int
    count: int






class ExchangeCodeRequest(BaseModel):
    code: str
    platform: str
    quota: Optional[int] = None
    rewards: list[ExchangeReward]






class ExchangeCodeSummary(BaseModel):
    id: int
    code: str
    platform: str
    quota: int
    rewards: list[ExchangeReward]






class ExchangeCodeListResponse(BaseModel):
    codes: list[ExchangeCodeSummary]
    meta: PaginationMeta




