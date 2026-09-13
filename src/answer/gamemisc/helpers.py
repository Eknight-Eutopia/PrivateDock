
from src.db.store import get_default_store


def list_notices(limit: int = 10) -> list[dict]:
    store = get_default_store()
    if store is None:
        return []
    rows = store.fetch(
        "SELECT id, version, btn_title, title, title_image, time_desc, content, tag_type, icon, track "
        "FROM notices ORDER BY id DESC LIMIT $1",
        limit
    )
    result = []
    for row in rows:
        result.append({
            "id": row["id"],
            "version": row["version"],
            "btn_title": row["btn_title"],
            "title": row["title"],
            "title_image": row["title_image"],
            "time_desc": row["time_desc"],
            "content": row["content"],
            "tag_type": row["tag_type"],
            "icon": row["icon"],
            "track": row["track"],
        })
    return result
