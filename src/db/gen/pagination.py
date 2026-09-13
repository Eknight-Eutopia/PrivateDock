def normalize_pagination(offset: int, limit: int) -> tuple[int, int, bool]:
    if offset < 0:
        offset = 0
    if limit <= 0:
        return offset, 0, True
    return offset, limit, False
