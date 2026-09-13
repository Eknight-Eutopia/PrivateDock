from pydantic import BaseModel

from src.api.types.player import PaginationMeta


class ChapterProgress(BaseModel):
    chapter_id: int
    progress: int
    kill_boss_count: int
    kill_enemy_count: int
    take_box_count: int
    defeat_count: int
    today_defeat_count: int
    pass_count: int
    updated_at: int


class PlayerChapterProgressCreateRequest(BaseModel):
    chapter_id: int
    progress: int = 0


class PlayerChapterProgressEntry(BaseModel):
    chapter_id: int = 0
    progress: int = 0


class PlayerChapterProgressResponse(BaseModel):
    progress: list[PlayerChapterProgressEntry] = []


class PlayerChapterProgressListResponse(BaseModel):
    progress: list[PlayerChapterProgressResponse]
    meta: PaginationMeta


class PlayerChapterProgressUpdateRequest(BaseModel):
    progress: int





