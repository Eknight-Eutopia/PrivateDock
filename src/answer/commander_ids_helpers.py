def normalize_commander_ids(ids: list, exclude: int = 0) -> list:
    if not ids:
        return []
    seen = set()
    normalized = []
    for cid in ids:
        cid = int(cid)
        if cid == 0 or cid == exclude:
            continue
        if cid in seen:
            continue
        seen.add(cid)
        normalized.append(cid)
    return normalized
