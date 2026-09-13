from typing import Any, Optional

from pydantic import BaseModel, RootModel


class ArenaShopItem(BaseModel):
    shop_id: int
    count: int


class ArenaShopState(BaseModel):
    flash_count: int
    next_flash_time: int
    last_refresh_time: int


class ArenaShopResponse(BaseModel):
    state: ArenaShopState
    items: list[ArenaShopItem]


class ArenaShopUpdateRequest(BaseModel):
    flash_count: Optional[int] = None
    next_flash_time: Optional[int] = None
    last_refresh_time: Optional[int] = None


class BanPlayerRequest(BaseModel):
    permanent: bool
    lift_timestamp: Optional[str] = None
    duration_sec: Optional[int] = None


class CompensationAttachmentDTO(BaseModel):
    type: int
    item_id: int
    quantity: int


class CompensationCreateRequest(BaseModel):
    compensation_id: int
    title: str = ""
    body: str = ""
    items: Any = None


class CompensationUpdateRequest(BaseModel):
    title: Optional[str] = None
    body: Optional[str] = None
    items: Optional[Any] = None


class CreateCompensationRequest(BaseModel):
    title: str
    text: str
    send_time: Optional[str] = None
    expires_at: str
    attachments: list[CompensationAttachmentDTO] = []



class GiveItemRequest(BaseModel):
    item_id: int
    amount: int = 1


class GiveShipRequest(BaseModel):
    ship_id: int


class GiveSkinRequest(BaseModel):
    skin_id: int
    expires_at: Optional[str] = None


class GuildShopGood(BaseModel):
    index: int
    goods_id: int
    count: int


class GuildShopGoodCreateRequest(BaseModel):
    index: int
    goods_id: int
    count: int


class GuildShopGoodPatchRequest(BaseModel):
    goods_id: Optional[int] = None
    count: Optional[int] = None


class GuildShopGoodsResponse(BaseModel):
    goods: list[GuildShopGood]


class GuildShopState(BaseModel):
    refresh_count: int
    next_refresh_time: int


class GuildShopResponse(BaseModel):
    state: GuildShopState
    goods: list[GuildShopGood]


class GuildShopUpdateRequest(BaseModel):
    refresh_count: Optional[int] = None
    next_refresh_time: Optional[int] = None


class ItemCreateRequest(BaseModel):
    id: int
    name: str
    rarity: int
    shop_id: int
    type: int
    virtual_type: int


class ItemSummary(BaseModel):
    id: int
    name: str
    rarity: int
    shop_id: int
    type: int
    virtual_type: int


class ItemUpdateRequest(BaseModel):
    name: str
    rarity: int
    shop_id: int
    type: int
    virtual_type: int


class KickPlayerRequest(BaseModel):
    reason: int = 0


class KickPlayerResponse(BaseModel):
    disconnected: bool


class MedalShopGood(BaseModel):
    index: int
    goods_id: int
    count: int


class MedalShopGoodCreateRequest(BaseModel):
    index: int
    goods_id: int
    count: int


class MedalShopGoodPatchRequest(BaseModel):
    goods_id: Optional[int] = None
    count: Optional[int] = None


class MedalShopGoodsResponse(BaseModel):
    goods: list[MedalShopGood]


class MedalShopItem(BaseModel):
    id: int
    count: int
    index: int


class MedalShopState(BaseModel):
    next_refresh_time: int


class MedalShopResponse(BaseModel):
    state: MedalShopState
    items: list[MedalShopItem]


class MedalShopUpdateRequest(BaseModel):
    next_refresh_time: Optional[int] = None


class MiniGameShopGood(BaseModel):
    goods_id: int
    count: int


class MiniGameShopGoodCreateRequest(BaseModel):
    goods_id: int
    count: int


class MiniGameShopGoodPatchRequest(BaseModel):
    count: Optional[int] = None


class MiniGameShopGoodsResponse(BaseModel):
    goods: list[MiniGameShopGood]


class MiniGameShopState(BaseModel):
    next_refresh_time: int


class MiniGameShopResponse(BaseModel):
    state: MiniGameShopState
    goods: list[MiniGameShopGood]


class MiniGameShopUpdateRequest(BaseModel):
    next_refresh_time: Optional[int] = None


class NoticeSummary(BaseModel):
    id: int = 0
    version: int = 0
    btn_title: str = ""
    title: str = ""
    title_image: str = ""
    time_desc: str = ""
    content: str = ""
    tag_type: int = 0
    icon: int = 0
    track: int = 0


class NoticeActiveResponse(RootModel):
    root: list[NoticeSummary] = []


class PaginationMeta(BaseModel):
    offset: int = 0
    limit: int = 50
    total: int = 0


class ItemListResponse(BaseModel):
    items: list[ItemSummary]
    meta: PaginationMeta


class NoticeListResponse(BaseModel):
    notices: list[NoticeSummary] = []
    meta: PaginationMeta = PaginationMeta()


class PlayerArenaShopResponse(BaseModel):
    refresh_count: int = 0


class PlayerArenaShopUpdateRequest(BaseModel):
    refresh_count: Optional[int] = None


class PlayerBanStatus(BaseModel):
    banned: bool = False


class PlayerBuffAddRequest(BaseModel):
    buff_id: int
    expires_at: str


class PlayerBuffEntry(BaseModel):
    buff_id: int = 0
    timestamp: int = 0
    instigator: int = 0


class PlayerBuffResponse(BaseModel):
    buffs: list[PlayerBuffEntry]


class PlayerBuffUpdateRequest(BaseModel):
    timestamp: Optional[int] = None
    instigator: Optional[int] = None


class PlayerBuffsResponse(BaseModel):
    buffs: list[PlayerBuffEntry] = []


class PlayerBuildCounterUpdateRequest(BaseModel):
    draw_count_1: Optional[int] = None
    draw_count_10: Optional[int] = None
    exchange_count: Optional[int] = None


class PlayerBuildCountersUpdateRequest(BaseModel):
    draw_count1: Optional[int] = None
    draw_count10: Optional[int] = None


class PlayerBuildCreateRequest(BaseModel):
    build_id: int
    ship_id: int
    finish_time: str
    room_id: int = 0


class PlayerBuildEntry(BaseModel):
    build_id: int = 0
    ship_id: int = 0
    finish_time: str = ""
    room_id: int = 0


class PlayerBuildQueueEntry(BaseModel):
    slot: int
    pool_id: int
    remaining_seconds: int
    finish_time: int


class PlayerBuildQueueResponse(BaseModel):
    queue_size: int = 0
    slots: int = 0


class PlayerBuildResponse(BaseModel):
    builds: list[PlayerBuildEntry]


class PlayerBuildUpdateRequest(BaseModel):
    finish_time: Optional[str] = None


class PlayerBuildsResponse(BaseModel):
    builds: list[PlayerBuildEntry] = []


class PlayerCompensationAttachment(BaseModel):
    type: int
    item_id: int
    quantity: int


class PlayerCompensationEntry(BaseModel):
    compensation_id: int = 0
    title: str = ""
    body: str = ""
    items: Any = None
    created_at: str = ""


class PlayerCompensationPushRequest(BaseModel):
    message: str = ""


class PlayerCompensationResponse(BaseModel):
    compensations: list[PlayerCompensationEntry]


class PlayerCompensationsResponse(BaseModel):
    compensations: list[PlayerCompensationEntry] = []


class PlayerCreateRequest(BaseModel):
    commander_id: int
    account_id: int = 0
    name: str
    level: Optional[int] = None
    exp: Optional[int] = None
    last_login: Optional[str] = None
    guide_index: Optional[int] = None
    new_guide_index: Optional[int] = None
    name_change_cooldown: Optional[str] = None
    room_id: Optional[int] = None
    exchange_count: Optional[int] = None
    draw_count1: Optional[int] = None
    draw_count10: Optional[int] = None
    support_requisition_count: Optional[int] = None
    support_requisition_month: Optional[int] = None
    acc_pay_lv: Optional[int] = None
    living_area_cover_id: Optional[int] = None
    selected_icon_frame_id: Optional[int] = None
    selected_chat_frame_id: Optional[int] = None
    selected_battle_ui_id: Optional[int] = None
    display_icon_id: Optional[int] = None
    display_skin_id: Optional[int] = None
    display_icon_theme_id: Optional[int] = None
    random_ship_mode: Optional[int] = None
    random_flag_ship_enabled: Optional[bool] = None
    manifesto: Optional[str] = None
    dorm_name: Optional[str] = None
    ship_id: Optional[int] = 106011


class PlayerDetailResponse(BaseModel):
    commander_id: int = 0
    account_id: int = 0
    name: str = ""
    level: int = 0
    exp: int = 0
    last_login: str = ""
    banned: bool = False
    online: bool = False


class PlayerEquipmentEntry(BaseModel):
    equipment_id: int = 0
    count: int = 0


class PlayerEquipmentResponse(BaseModel):
    equipment: list[PlayerEquipmentEntry] = []


class PlayerEquipmentUpsertRequest(BaseModel):
    equipment_id: int
    count: int


class PlayerFleetCreateRequest(BaseModel):
    fleet_id: int
    name: str = ""
    ships: list[int] = []


class PlayerFleetEntry(BaseModel):
    fleet_id: int = 0
    name: str = ""
    ships: list[int] = []


class PlayerFleetResponse(BaseModel):
    fleets: list[PlayerFleetEntry] = []


class PlayerFleetUpdateRequest(BaseModel):
    name: Optional[str] = None
    ships: Optional[list[int]] = None



class PlayerGuildShopGoodCreateRequest(BaseModel):
    index: int
    goods_id: int


class PlayerGuildShopGoodEntry(BaseModel):
    index: int = 0
    goods_id: int = 0
    bought: bool = False


class PlayerGuildShopGoodUpdateRequest(BaseModel):
    bought: Optional[bool] = None


class PlayerGuildShopGoodsResponse(BaseModel):
    goods: list[PlayerGuildShopGoodEntry] = []


class PlayerGuildShopResponse(BaseModel):
    refresh_count: int = 0


class PlayerGuildShopUpdateRequest(BaseModel):
    refresh_count: Optional[int] = None


class PlayerItemEntry(BaseModel):
    item_id: int = 0
    count: int = 0
    name: str = ""


class PlayerItemQuantityUpdateRequest(BaseModel):
    quantity: int


class PlayerItemResponse(BaseModel):
    items: list[PlayerItemEntry] = []


class PlayerListItem(BaseModel):
    commander_id: int
    name: str = ""
    level: int = 0
    account_id: int = 0
    online: bool = False
    banned: bool = False
    last_login: str = ""


class ListPlayersResponse(BaseModel):
    players: list[PlayerListItem] = []
    meta: PaginationMeta = PaginationMeta()


class PlayerMailAttachment(BaseModel):
    type: int
    item_id: int
    quantity: int


class PlayerMailEntry(BaseModel):
    mail_id: int = 0
    title: str = ""
    body: str = ""
    read: bool = False
    received: bool = False
    created_at: str = ""


class PlayerMailResponse(BaseModel):
    mails: list[PlayerMailEntry]








class PlayerMailUpdateRequest(BaseModel):
    read: Optional[bool] = None
    received: Optional[bool] = None







class PlayerMailsResponse(BaseModel):
    mails: list[PlayerMailEntry] = []







class PlayerMedalShopGoodCreateRequest(BaseModel):
    index: int
    goods_id: int
    discount: int = 0
    pay_count: int = 0







class PlayerMedalShopGoodEntry(BaseModel):
    index: int = 0
    goods_id: int = 0
    bought: bool = False
    discount: int = 0
    pay_count: int = 0







class PlayerMedalShopGoodUpdateRequest(BaseModel):
    bought: Optional[bool] = None
    discount: Optional[int] = None
    pay_count: Optional[int] = None







class PlayerMedalShopGoodsResponse(BaseModel):
    goods: list[PlayerMedalShopGoodEntry] = []







class PlayerMedalShopResponse(BaseModel):
    refresh_count: int = 0
    manual_refresh_count: int = 0







class PlayerMedalShopUpdateRequest(BaseModel):
    refresh_count: Optional[int] = None
    manual_refresh_count: Optional[int] = None







class PlayerMiniGameShopGoodCreateRequest(BaseModel):
    goods_id: int
    buy_count: int = 0







class PlayerMiniGameShopGoodEntry(BaseModel):
    goods_id: int = 0
    bought: bool = False
    buy_count: int = 0







class PlayerMiniGameShopGoodUpdateRequest(BaseModel):
    bought: Optional[bool] = None
    buy_count: Optional[int] = None







class PlayerMiniGameShopGoodsResponse(BaseModel):
    goods: list[PlayerMiniGameShopGoodEntry] = []







class PlayerMiniGameShopResponse(BaseModel):
    refresh_count: int = 0







class PlayerMiniGameShopUpdateRequest(BaseModel):
    refresh_count: Optional[int] = None







class PlayerMutationResponse(BaseModel):
    commander_id: int = 0
    account_id: int = 0
    name: str = ""
    level: int = 0
    exp: int = 0
    last_login: str = ""
    banned: bool = False
    online: bool = False







class PlayerOwnedShipEntry(BaseModel):
    owned_id: int = 0
    ship_id: int = 0
    level: int = 1
    exp: int = 0
    surplus_exp: int = 0
    max_level: int = 70
    intimacy: int = 5000
    is_locked: bool = False
    propose: bool = False
    common_flag: bool = False
    blueprint_flag: bool = False
    proficiency: bool = False
    activity_npc: int = 0
    custom_name: str = ""
    change_name_timestamp: Optional[str] = None
    create_time: Optional[str] = None
    energy: int = 0
    skin_id: int = 0
    is_secretary: bool = False
    secretary_position: Optional[int] = None
    secretary_phantom_id: int = 0
    deleted_at: Optional[str] = None







class PlayerPunishmentCreateRequest(BaseModel):
    punishment_id: int
    reason: str = ""
    expires_at: str = ""







class PlayerPunishmentEntry(BaseModel):
    punishment_id: int = 0
    reason: str = ""
    expires_at: str = ""
    created_at: str = ""







class PlayerPunishmentUpdateRequest(BaseModel):
    reason: Optional[str] = None
    expires_at: Optional[str] = None







class PlayerPunishmentsResponse(BaseModel):
    punishments: list[PlayerPunishmentEntry] = []







class PlayerQueryParams(BaseModel):
    offset: int = 0
    limit: int = 50
    sort: str = ""
    filter: str = ""
    min_level: int = 0
    search: str = ""







class PlayerResourceEntry(BaseModel):
    resource_id: int
    amount: int = 0
    name: str = ""







class PlayerResourceResponse(BaseModel):
    resources: list[PlayerResourceEntry] = []







class PlayerSecretaries(BaseModel):
    secretaries: list[int] = []







class PlayerShipCreateRequest(BaseModel):
    ship_id: int
    level: int = 1
    intimacy: int = 5000
    exp: int = 0
    book_exp: int = 0







class PlayerShipEntry(BaseModel):
    owned_id: int
    ship_id: int
    level: int
    rarity: int
    name: str
    skin_id: int








class PlayerShipEquipmentEntry(BaseModel):
    pos: int = 0
    equip_id: int = 0
    skin_id: int = 0







class PlayerShipEquipmentResponse(BaseModel):
    equipment: list[PlayerShipEquipmentEntry] = []







class PlayerShipEquipmentUpdateRequest(BaseModel):
    equipment: list[PlayerShipEquipmentEntry] = []







class PlayerShipResponse(BaseModel):
    ships: list[PlayerShipEntry]








class PlayerShipUpdateRequest(BaseModel):
    level: Optional[int] = None
    intimacy: Optional[int] = None
    exp: Optional[int] = None
    book_exp: Optional[int] = None
    likes: Optional[int] = None







class PlayerShipsResponse(BaseModel):
    ships: list[PlayerShipEntry] = []









class PlayerShoppingStreetGoodCreateRequest(BaseModel):
    goods_id: int
    goods_type: int = 0







class PlayerShoppingStreetGoodEntry(BaseModel):
    goods_id: int = 0
    goods_type: int = 0
    bought: bool = False







class PlayerShoppingStreetGoodUpdateRequest(BaseModel):
    bought: Optional[bool] = None







class PlayerShoppingStreetGoodsResponse(BaseModel):
    goods: list[PlayerShoppingStreetGoodEntry] = []







class PlayerShoppingStreetResponse(BaseModel):
    refresh_count: int = 0
    refresh_time: str = ""







class PlayerShoppingStreetUpdateRequest(BaseModel):
    refresh_count: Optional[int] = None
    refresh_time: Optional[str] = None







class PlayerSkinEntry(BaseModel):
    skin_id: int = 0
    expires_at: Optional[str] = None







class PlayerSkinResponse(BaseModel):
    skins: list[PlayerSkinEntry] = []







class PlayerSkinUpdateRequest(BaseModel):
    expires_at: Optional[str] = None







class PlayerSummary(BaseModel):
    id: int
    account_id: int
    name: str
    level: int
    last_login: str
    banned: bool
    online: bool








class PlayerListResponse(BaseModel):
    players: list[PlayerSummary]
    meta: PaginationMeta








class PlayerSupportRequisitionResponse(BaseModel):
    count: int = 0
    month: int = 0







class PlayerUpdateRequest(BaseModel):
    account_id: Optional[int] = None
    name: Optional[str] = None
    level: Optional[int] = None
    exp: Optional[int] = None
    last_login: Optional[str] = None
    guide_index: Optional[int] = None
    new_guide_index: Optional[int] = None
    name_change_cooldown: Optional[str] = None
    room_id: Optional[int] = None
    exchange_count: Optional[int] = None
    draw_count1: Optional[int] = None
    draw_count10: Optional[int] = None
    support_requisition_count: Optional[int] = None
    support_requisition_month: Optional[int] = None
    acc_pay_lv: Optional[int] = None
    living_area_cover_id: Optional[int] = None
    selected_icon_frame_id: Optional[int] = None
    selected_chat_frame_id: Optional[int] = None
    selected_battle_ui_id: Optional[int] = None
    display_icon_id: Optional[int] = None
    display_skin_id: Optional[int] = None
    display_icon_theme_id: Optional[int] = None
    random_ship_mode: Optional[int] = None
    random_flag_ship_enabled: Optional[bool] = None
    manifesto: Optional[str] = None
    dorm_name: Optional[str] = None







class PushCompensationResponse(BaseModel):
    pushed: int
    failed: int








class RaritySummary(BaseModel):
    id: int
    name: str








class RarityListResponse(BaseModel):
    rarities: list[RaritySummary]
    meta: PaginationMeta








class RawJSON:
    def __init__(self, value=None):
        self.value = value







class ResourceCreateRequest(BaseModel):
    id: int
    item_id: int
    name: str








class ResourceSummary(BaseModel):
    id: int
    item_id: int
    name: str








class ResourceListResponse(BaseModel):
    resources: list[ResourceSummary]
    meta: PaginationMeta








class ResourceUpdateEntry(BaseModel):
    resource_id: int
    amount: int







class ResourceUpdatePayload(BaseModel):
    item_id: int
    name: str








class ResourceUpdateRequest(BaseModel):
    resources: list[ResourceUpdateEntry] = []







class SendMailAttachmentDTO(BaseModel):
    type: int
    item_id: int
    quantity: int








class SendMailRequest(BaseModel):
    title: str
    body: str
    items: Any = None







class ShipQueryParams(BaseModel):
    offset: int = 0
    limit: int = 50
    name: str = ""
    rarity_id: Optional[int] = None
    type_id: Optional[int] = None
    nationality_id: Optional[int] = None








class ShipSummary(BaseModel):
    id: int
    name: str
    english_name: str
    rarity_id: int
    star: int
    type: int
    nationality: int
    build_time: int
    pools: list[int] = []








class ShipListResponse(BaseModel):
    ships: list[ShipSummary]
    meta: PaginationMeta








class ShipTypeSummary(BaseModel):
    id: int
    name: str








class ShipTypeListResponse(BaseModel):
    ship_types: list[ShipTypeSummary]
    meta: PaginationMeta








class ShopOfferSummary(BaseModel):
    id: int = 0
    effects: list[int] = []
    effect_args: Any = None
    number: int = 0
    resource_number: int = 0
    resource_id: int = 0
    type: int = 0
    genre: int = 0
    discount: int = 0







class ShopOfferListResponse(BaseModel):
    offers: list[ShopOfferSummary] = []
    meta: PaginationMeta = PaginationMeta()







class ShoppingStreetGoodCreateRequest(BaseModel):
    goods_id: int
    discount: int
    buy_count: int








class ShoppingStreetGoodInput(BaseModel):
    goods_id: int
    discount: int
    buy_count: int








class ShoppingStreetGoodPatchRequest(BaseModel):
    discount: Optional[int] = None
    buy_count: Optional[int] = None








class ShoppingStreetGoodsReplaceRequest(BaseModel):
    goods: list[ShoppingStreetGoodInput]








class ShoppingStreetOfferSummary(BaseModel):
    id: int
    resource_num: int
    resource_type: int
    type: int
    num: int
    genre: str
    discount: int
    effect_args: Any








class ShoppingStreetGood(BaseModel):
    goods_id: int
    discount: int
    buy_count: int
    offer: Optional[ShoppingStreetOfferSummary] = None








class ShoppingStreetGoodsResponse(BaseModel):
    goods: list[ShoppingStreetGood]








class ShoppingStreetRefreshRequest(BaseModel):
    goods_count: Optional[int] = None
    next_flash_in_seconds: Optional[int] = None
    set_flash_count: Optional[int] = None
    seed: Optional[int] = None
    goods_ids: list[int] = []
    discount_override: Optional[int] = None
    buy_count: Optional[int] = None








class ShoppingStreetState(BaseModel):
    level: int
    next_flash_time: int
    level_up_time: int
    flash_count: int
    last_refreshed_at: int








class ShoppingStreetResponse(BaseModel):
    state: ShoppingStreetState
    goods: list[ShoppingStreetGood]








class ShoppingStreetUpdateRequest(BaseModel):
    level: Optional[int] = None
    next_flash_time: Optional[int] = None
    level_up_time: Optional[int] = None
    flash_count: Optional[int] = None


class SkinSummary(BaseModel):
    id: int
    name: str
    ship_group: int


class SkinListResponse(BaseModel):
    skins: list[SkinSummary]
    meta: PaginationMeta


class UpdateCompensationRequest(BaseModel):
    title: Optional[str] = None
    text: Optional[str] = None
    send_time: Optional[str] = None
    expires_at: Optional[str] = None
    attach_flag: Optional[bool] = None
    attachments: Optional[list[CompensationAttachmentDTO]] = None
