from pydantic import BaseModel




class RequisitionShipListResponse(BaseModel):
    ship_ids: list[int]



class RequisitionShipRequest(BaseModel):
    ship_id: int


