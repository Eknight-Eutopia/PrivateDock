from src.answer.educate.helpers import educate_flag_id, has_educate_flag


async def EducateFlagID(base: int, flag_id: int) -> int:
    return educate_flag_id(base, flag_id)


async def HasEducateFlag(commander_id: int, flag_id: int) -> bool:
    return await has_educate_flag(commander_id, flag_id)
