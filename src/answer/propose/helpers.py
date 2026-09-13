import time
from typing import Optional

from src.db.store import get_default_store
from src.db.session import get_sync_session
from src.logger.logger import log_event, LOG_LEVEL_ERROR, LOG_LEVEL_INFO
from sqlalchemy import select
from src.orm.skin import Skin, give_skin
from src.orm.game_data import get_ship_template_config
from src.orm.owned_ship import count_married_ships

PROMISE_RING_ITEM_ID = 15006


def check_and_consume_ring(commander_id: int) -> bool:
    from src.orm.item import has_enough_item, consume_item
    if not has_enough_item(commander_id, PROMISE_RING_ITEM_ID, 1):
        log_event("Propose", "Ring", f"uid={commander_id} does not have a promise ring", LOG_LEVEL_ERROR)
        return False
    consume_item(commander_id, PROMISE_RING_ITEM_ID, 1)
    return True


def propose_ship_db(commander_id: int, ship_id: int) -> tuple[bool, str]:
    store = get_default_store()
    row = store.fetchrow(
        "SELECT id, propose FROM owned_ships WHERE id = $1 AND owner_id = $2 AND deleted_at IS NULL",
        ship_id, commander_id,
    )
    if row is None:
        return False, "ship not found"
    if row["propose"]:
        return False, "already proposed"
    if not check_and_consume_ring(commander_id):
        return False, "missing promise ring"
    store.execute(
        "UPDATE owned_ships SET propose = true WHERE id = $1 AND owner_id = $2",
        ship_id, commander_id,
    )
    log_event("Dock", "Propose", f"uid={commander_id} proposed ship id={ship_id} successfully", LOG_LEVEL_INFO)
    # Grant the ship's OATH (wedding) skin so the marriage ceremony and manual
    # skin application (CS_12202) succeed. The OATH skin is the ship_skin_template
    # entry for the ship's group_type with skin_type == 1 (SKIN_TYPE_PROPOSE).
    row = store.fetchrow(
        "SELECT ship_id FROM owned_ships WHERE id = $1 AND owner_id = $2 AND deleted_at IS NULL",
        ship_id, commander_id,
    )
    if row is not None:
        granted = grant_oath_skin_for_ship(commander_id, int(row["ship_id"] or 0))
        if granted is not None:
            log_event("Dock", "Propose", f"uid={commander_id} granted OATH skin {granted} for ship {ship_id}", LOG_LEVEL_INFO)
    return True, ""


MARRIAGE_FURNITURE = [
    (3, 12102),  # Married x3 -> Kimono Hanger
    (5, 12103),  # Married x5 -> Shrine
    (7, 12002),  # Married x7 -> Maple Leaf Wallpaper
]




def grant_marriage_furniture(commander_id: int) -> list[int]:
    """Grant the wedding furniture earned for the current marriage count.

    Wiki: after marrying N different shipgirls you are gifted one wedding
    furniture piece at N == 3, 5, 7. Grant every due piece not yet owned so
    skipping an OATH ceremony still awards all earned furniture.
    """
    from src.orm.commander_furniture import add_commander_furniture

    count = count_married_ships(commander_id)
    granted = []
    now = int(time.time())
    store = get_default_store()
    for threshold, furniture_id in MARRIAGE_FURNITURE:
        if count < threshold:
            continue
        existing = store.fetchrow(
            "SELECT 1 FROM commander_furnitures WHERE commander_id = $1 AND furniture_id = $2",
            commander_id, furniture_id,
        )
        if existing is None:
            add_commander_furniture(commander_id, furniture_id, 1, now)
            granted.append(furniture_id)
    return granted


def get_group_oath_skin_id(group_type: int) -> Optional[int]:
    with get_sync_session() as session:
        return session.execute(
            select(Skin.id).where(Skin.ship_group == group_type, Skin.skin_type == 1)
        ).scalar_one_or_none()


def grant_oath_skin_for_ship(commander_id: int, ship_template_id: int) -> Optional[int]:
    tpl = get_ship_template_config(ship_template_id)
    if not isinstance(tpl, dict):
        return None
    group_type = tpl.get("group_type")
    if not group_type:
        return None
    oath_skin = get_group_oath_skin_id(int(group_type))
    if oath_skin is None:
        return None
    give_skin(commander_id, oath_skin)
    return oath_skin
