from typing import Optional

from pydantic import BaseModel








class PlayerAttireCreateRequest(BaseModel):
    type: int
    attire_id: int
    expires_at: Optional[str] = None







class PlayerAttireEntry(BaseModel):
    type: int = 0
    attire_id: int = 0
    expires_at: Optional[str] = None







class PlayerAttireResponse(BaseModel):
    attires: list[PlayerAttireEntry]








class PlayerAttireSelectionUpdateRequest(BaseModel):
    type: int
    attire_id: int







class PlayerAttireUpdateRequest(BaseModel):
    expires_at: Optional[str] = None







class PlayerAttiresResponse(BaseModel):
    attires: list[PlayerAttireEntry] = []







class PlayerFlagCreateRequest(BaseModel):
    flag_id: int
    value: int = 0







class PlayerFlagEntry(BaseModel):
    flag_id: int = 0
    value: int = 0
    updated_at: str = ""







class PlayerFlagRequest(BaseModel):
    flag_id: int








class PlayerFlagsResponse(BaseModel):
    flags: list[PlayerFlagEntry] = []







class PlayerGuideResponse(BaseModel):
    guide_index: int = 0
    new_guide_index: int = 0







class PlayerGuideUpdateRequest(BaseModel):
    guide_index: Optional[int] = None
    new_guide_index: Optional[int] = None







class PlayerLikeCreateRequest(BaseModel):
    group_id: int
    like_id: int







class PlayerLikeEntry(BaseModel):
    group_id: int = 0
    like_id: int = 0
    timestamp: int = 0







class PlayerLikeRequest(BaseModel):
    group_id: int






class PlayerLikesResponse(BaseModel):
    likes: list[PlayerLikeEntry] = []







class PlayerLivingAreaCoverCreateRequest(BaseModel):
    cover_id: int







class PlayerLivingAreaCoverEntry(BaseModel):
    cover_id: int = 0
    state: int = 0







class PlayerLivingAreaCoverRequest(BaseModel):
    cover_id: int








class PlayerLivingAreaCoverResponse(BaseModel):
    selected: int
    owned: list[int]








class PlayerLivingAreaCoverSelectRequest(BaseModel):
    cover_id: int







class PlayerLivingAreaCoverStateUpdateRequest(BaseModel):
    state: int







class PlayerLivingAreaCoverUpdateRequest(BaseModel):
    is_new: Optional[bool] = None







class PlayerLivingAreaCoversResponse(BaseModel):
    covers: list[PlayerLivingAreaCoverEntry] = []







class PlayerRandomFlagShipEntry(BaseModel):
    ship_id: int = 0
    phantom_id: int = 0







class PlayerRandomFlagShipListResponse(BaseModel):
    entries: list[PlayerRandomFlagShipEntry]








class PlayerRandomFlagShipModeRequest(BaseModel):
    mode: int








class PlayerRandomFlagShipModeResponse(BaseModel):
    enabled: bool = False







class PlayerRandomFlagShipModeUpdateRequest(BaseModel):
    enabled: bool







class PlayerRandomFlagShipRequest(BaseModel):
    enabled: bool








class PlayerRandomFlagShipResponse(BaseModel):
    ship_id: int = 0
    phantom_id: int = 0
    ship_template_id: int = 0
    locked: bool = False







class PlayerRandomFlagShipUpdateRequest(BaseModel):
    ship_id: Optional[int] = None
    phantom_id: Optional[int] = None
    ship_template_id: Optional[int] = None
    locked: Optional[bool] = None







class PlayerRandomFlagShipUpsertRequest(BaseModel):
    ship_id: int
    phantom_id: int







class PlayerRandomFlagShipsResponse(BaseModel):
    ships: list[PlayerRandomFlagShipEntry] = []







class PlayerSecretaryEntry(BaseModel):
    ship_id: int
    phantom_id: int
    is_secretary: bool
    position: Optional[int] = None








class PlayerSecretariesResponse(BaseModel):
    ships: list[PlayerSecretaryEntry]








class PlayerSecretaryUpdate(BaseModel):
    ship_id: int
    phantom_id: int








class PlayerSecretariesReplaceRequest(BaseModel):
    secretaries: list[PlayerSecretaryUpdate]








class PlayerStoryCreateRequest(BaseModel):
    story_id: str
    timestamp: int = 0







class PlayerStoryEntry(BaseModel):
    story_id: str = ""
    timestamp: int = 0







class PlayerStoriesResponse(BaseModel):
    stories: list[PlayerStoryEntry] = []







class PlayerStoryRequest(BaseModel):
    story_id: int








class PlayerStoryUpsertRequest(BaseModel):
    story_id: str
    timestamp: int = 0





