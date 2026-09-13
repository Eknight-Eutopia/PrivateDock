from pydantic import BaseModel



class ActivityAllowlistPatchPayload(BaseModel):
    add: list[int] = []
    remove: list[int] = []



class ActivityAllowlistPayload(BaseModel):
    ids: list[int] = []

