from typing import Optional

from pydantic import BaseModel

from src.api.types.player import PaginationMeta


class ChapterCellPos(BaseModel):
    row: int
    column: int


class ChapterCellFlag(BaseModel):
    pos: ChapterCellPos
    flag_list: list[int]


class ChapterCellInfo(BaseModel):
    pos: ChapterCellPos
    item_type: int
    item_id: Optional[int] = None
    item_flag: Optional[int] = None
    item_data: Optional[int] = None
    extra_id: list[int]


class ChapterCommander(BaseModel):
    pos: int
    id: int


class ChapterFleetDuty(BaseModel):
    key: int
    value: int


class ChapterShip(BaseModel):
    id: int
    hp_rant: int


class ChapterStrategy(BaseModel):
    id: int
    count: int


class ChapterGroup(BaseModel):
    id: int
    ship_list: list[ChapterShip]
    pos: ChapterCellPos
    step_count: int
    box_strategy_list: list[ChapterStrategy]
    ship_strategy_list: list[ChapterStrategy]
    strategy_ids: list[int]
    bullet: int
    start_pos: ChapterCellPos
    commander_list: list[ChapterCommander]
    move_step_down: int
    kill_count: int
    fleet_id: int
    vision_lv: int


class ChapterState(BaseModel):
    id: int
    time: int
    cell_list: list[ChapterCellInfo]
    main_group_list: list[ChapterGroup]
    ai_list: list[ChapterCellInfo]
    escort_list: list[ChapterCellInfo]
    round: int
    is_submarine_auto_attack: int
    operation_buff: list[int]
    model_act_count: int
    buff_list: list[int]
    loop_flag: int
    extra_flag_list: list[int]
    cell_flag_list: list[ChapterCellFlag]
    chapter_hp: int
    chapter_strategy_list: list[ChapterStrategy]
    kill_count: int
    init_ship_count: int
    continuous_kill_count: int
    battle_statistics: list[ChapterStrategy]
    fleet_duties: list[ChapterFleetDuty]
    move_step_count: int
    submarine_group_list: list[ChapterGroup]
    support_group_list: list[ChapterGroup]


class PlayerChapterStateCreateRequest(BaseModel):
    chapter_id: int
    state: int = 0


class PlayerChapterStateDeleteRequest(BaseModel):
    chapter_id: int


class PlayerChapterStateEntry(BaseModel):
    chapter_id: int = 0
    state: int = 0


class PlayerChapterStateResponse(BaseModel):
    states: list[PlayerChapterStateEntry] = []


class PlayerChapterStateListResponse(BaseModel):
    states: list[PlayerChapterStateResponse]
    meta: PaginationMeta


class PlayerChapterStateUpdateRequest(BaseModel):
    chapter_id: int
    state: int
