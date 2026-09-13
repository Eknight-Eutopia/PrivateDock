from typing import Optional

from pydantic import BaseModel
from src.api.types.player import PaginationMeta



class JuustagramLanguage(BaseModel):
    key: str = ""
    value: str = ""





class JuustagramLanguageDeleteRequest(BaseModel):
    key: str





class JuustagramLanguageListResponse(BaseModel):
    entries: list[JuustagramLanguage] = []





class JuustagramMessage(BaseModel):
    id: int = 0
    time: int = 0
    text: str = ""
    picture: str = ""
    oalist_pic: str = ""
    player_discuss: list = []
    npc_discuss: list = []
    npc_reply: list = []
    good: int = 0
    is_good: int = 0
    is_read: int = 0





class JuustagramMessageListResponse(BaseModel):
    messages: list[JuustagramMessage] = []
    meta: PaginationMeta = PaginationMeta()





class JuustagramMessageResponse(BaseModel):
    message: Optional[JuustagramMessage] = None





class JuustagramMessageState(BaseModel):
    message_id: int = 0
    is_read: int = 0
    is_good: int = 0
    good_count: int = 0
    updated_at: int = 0





class JuustagramMessageStateListResponse(BaseModel):
    states: list[JuustagramMessageState] = []





class JuustagramMessageStateResponse(BaseModel):
    state: JuustagramMessageState





class JuustagramMessageStateUpdateRequest(BaseModel):
    is_read: int = 0
    is_good: int = 0
    good_count: int = 0
    updated_at: int = 0





class JuustagramMessageUpdateRequest(BaseModel):
    read: Optional[bool] = None
    like: Optional[bool] = None





class JuustagramNpcComment(BaseModel):
    id: int
    time: int
    text: str
    npc_reply: list[int]





class JuustagramNpcTemplate(BaseModel):
    id: int = 0
    ship_group: int = 0
    message_persist: str = ""
    npc_reply_persist: str = ""
    time_persist: str = ""





class JuustagramNpcTemplateDeleteRequest(BaseModel):
    id: int





class JuustagramNpcTemplateListResponse(BaseModel):
    templates: list[JuustagramNpcTemplate] = []
    meta: PaginationMeta = PaginationMeta()





class JuustagramPlayerDiscuss(BaseModel):
    id: int
    time: int
    text_list: list[str]
    text: str
    npc_reply: list[int]






class JuustagramPlayerDiscussEntry(BaseModel):
    message_id: int = 0
    discuss_id: int = 0
    option_index: int = 0
    npc_reply_id: int = 0
    comment_time: int = 0





class JuustagramPlayerDiscussListResponse(BaseModel):
    entries: list[JuustagramPlayerDiscussEntry] = []





class JuustagramPlayerDiscussResponse(BaseModel):
    entry: JuustagramPlayerDiscussEntry





class JuustagramPlayerDiscussUpdateRequest(BaseModel):
    option_index: int = 0
    npc_reply_id: int = 0
    comment_time: int = 0




class JuustagramShipGroupDeleteRequest(BaseModel):
    ship_group: int





class JuustagramShipGroupTemplate(BaseModel):
    ship_group: int = 0
    name: str = ""
    background: str = ""
    sculpture: str = ""
    sculpture_ii: str = ""
    nationality: int = 0
    type: int = 0





class JuustagramShipGroupListResponse(BaseModel):
    groups: list[JuustagramShipGroupTemplate] = []
    meta: PaginationMeta = PaginationMeta()





class JuustagramTemplate(BaseModel):
    id: int = 0
    group_id: int = 0
    ship_group: int = 0
    name: str = ""
    sculpture: str = ""
    picture_persist: str = ""
    message_persist: str = ""
    is_active: bool = False
    npc_discuss_persist: str = ""
    time: str = ""
    time_persist: str = ""





class JuustagramTemplateDeleteRequest(BaseModel):
    id: int





class JuustagramTemplateListResponse(BaseModel):
    templates: list[JuustagramTemplate] = []
    meta: PaginationMeta = PaginationMeta()



