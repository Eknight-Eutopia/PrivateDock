from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import ARRAY, BigInteger
from sqlalchemy import JSON, TypeDecorator, Boolean, DateTime, String
from sqlalchemy import select, text
from sqlalchemy.orm import Mapped, mapped_column

from src.db import get_default_store
from src.db.session import Base, get_session, get_sync_session


class PortableBigIntegerArray(TypeDecorator):
    """``ARRAY(BigInteger)`` on PostgreSQL, ``JSON`` on SQLite.

    The codebase binds and reads plain Python lists for
    ``loading_pic_id_list_*``; SQLite stores them as JSON text (the
    sqlite_types list adapter serializes on bind), so reads must parse the
    JSON back into a list -- which the JSON type's processor does."""

    impl = ARRAY(BigInteger())
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(ARRAY(BigInteger()))
        return dialect.type_descriptor(JSON())

    def process_bind_param(self, value):
        return value

    def process_result_value(self, value, dialect):
        if dialect.name == "postgresql":
            return value
        # JSON column: SQLite driver may return str (raw) or parsed (ORM)
        if isinstance(value, str):
            import json as _json
            try:
                return _json.loads(value)
            except (ValueError, TypeError):
                return []
        return value
from src.logger.logger import log_event, LOG_LEVEL_INFO, LOG_LEVEL_ERROR
from src.orm import add_item, add_resource
from src.orm.game_data import get_ship_equip_config

DEFAULT_STARTER_SHIPS = [106011]


def create_default_ship_equipments(ownerID: int, ownedShipID: int, shipTemplateID: int):
    slotCount = 5
    defaultEquipIDs = [None] * 3
    try:
        config = get_ship_equip_config(shipTemplateID)
        defaultEquipIDs[0] = config['equip_id_1']
        defaultEquipIDs[1] = config['equip_id_2']
        defaultEquipIDs[2] = config['equip_id_3']

        for pos in range(slotCount):
            equipID = 0
            if (pos+1) <= 3:
                equipID = defaultEquipIDs[pos]
            with get_sync_session() as session:
                session.execute(
                    text(
                        "INSERT INTO owned_ship_equipments (owner_id, ship_id, pos, equip_id, skin_id) VALUES (:owner_id, :ship_id, :pos, :equip_id, 0) ON CONFLICT DO NOTHING"),
                    {"owner_id": ownerID, "ship_id": ownedShipID, "pos": (pos+1), "equip_id": equipID},
                )
                session.commit()
            '''await store.aexecute(
                "INSERT INTO owned_ship_equipments (owner_id, ship_id, pos, equip_id, skin_id) "
                "VALUES ($1, $2, $3, $4, 0) ON CONFLICT DO NOTHING",
                ownerID, ownedShipID, (pos+1), equipID,
            )'''
    except Exception as err:
        log_event("ORM", "commander", f"create_default_ship_equipments error: {err}", LOG_LEVEL_ERROR)
        return None


_ACCOUNT_ID_SEQUENCE = "yostarus_account_id_seq"


async def _next_account_id(store) -> int:
    """Allocate the next free ``yostarus_maps.account_id``.

    On PostgreSQL this keeps using the sequence created by
    ``sql/0184_yostarus_account_id_sequence.sql``. SQLite has no sequences, so the id is
    derived from the current maxima instead -- the caller's insert is retried on
    a unique conflict, which covers the single-writer case this server runs in.
    """
    from src.db.dialect import current_dialect

    dialect = current_dialect()
    if dialect.supports_sequences:
        row = await store.afetchrow(dialect.next_sequence_value_sql(_ACCOUNT_ID_SEQUENCE))
        return int(row[0])

    row = await store.afetchrow(
        "SELECT GREATEST("
        "  COALESCE((SELECT MAX(account_id) FROM yostarus_maps), 0),"
        "  COALESCE((SELECT MAX(commander_id) FROM commanders), 0)"
        ") + 1 AS mx"
    )
    return int(row[0]) if row else 1


async def create_commander(
        _client,
        arg2,
        nickname: str = None,
        extra_ship_ids: list[int] | None = None,
) -> int:
    store = get_default_store()

    account_id = None
    for _ in range(20):
        candidate = await _next_account_id(store)
        try:
            await store.aexecute(
                "INSERT INTO yostarus_maps (arg2, account_id) VALUES ($1, $2)",
                int(arg2), candidate
            )
            account_id = candidate
            break
        except Exception as err:
            from sqlalchemy.exc import IntegrityError
            if isinstance(err, IntegrityError):
                continue
            raise

    if account_id is None:
        raise RuntimeError("failed to allocate a unique account_id for new commander")

    if nickname is None:
        nickname = f"Commander #{account_id}"

    await store.aexecute(
        "INSERT INTO commanders (commander_id, account_id, name, level, exp, guide_index, new_guide_index) "
        "VALUES ($1, $2, $3, 1, 0, 1, 1)",
        account_id, account_id, nickname
    )
    from src.orm.commander_attire import grant_default_attires
    await grant_default_attires(account_id)

    ship_ids = list(extra_ship_ids or []) + DEFAULT_STARTER_SHIPS
    owned_ship_ids = []
    now_dt = datetime.now(timezone.utc)
    # NOTE: starter ships are deliberately NOT created via the generic
    # owned_ship.add_ship path — registration wants its own starter state
    # (is_locked=true). The id allocation below already
    # uses the GLOBAL MAX(id) required by the owned_ships PK.
    for idx, sid in enumerate(ship_ids):
        ship_row = await store.afetchrow(
            # owned_ships.id is a GLOBAL primary key (serial sequence);
            # per-owner MAX(id) would collide for a second commander.
            "SELECT COALESCE(MAX(id), 0) FROM owned_ships"
        )
        next_id = (ship_row[0] or 0) + 1
        await store.aexecute(
            "INSERT INTO owned_ships (id, owner_id, ship_id, level, energy, state, state_info1, "
            "intimacy, exp, surplus_exp, max_level, is_locked, propose, create_time, deleted_at) "
            "VALUES ($1, $2, $3, 1, 100, 1, 0, "
            "5000, 0, 0, 70, true, false, $4, NULL)",
            next_id, account_id, sid, now_dt
        )
        create_default_ship_equipments(account_id, next_id, sid)
        owned_ship_ids.append(next_id)

    add_item(account_id, 20001, 1)
    add_item(account_id, 15003, 10)
    add_resource(account_id, 1, 3000)
    add_resource(account_id, 2, 500)
    add_resource(account_id, 4, 999999)
    """for rid, amt in ((1, 3000), (2, 500), (4, 1000)):
        await store.aexecute(
            "INSERT INTO owned_resources (commander_id, resource_id, amount) VALUES ($1, $2, $3)",
            account_id, rid, amt
        )"""
    if owned_ship_ids:
        await store.aexecute(
            "UPDATE owned_ships SET is_secretary = TRUE, secretary_position = 0 WHERE owner_id = $1 AND id = $2",
            account_id, owned_ship_ids[0]
        )
    await store.aexecute(
        "INSERT INTO fleets (commander_id, game_id, name, ship_list, meowfficer_list) "
        "VALUES ($1, 1, '', $2::jsonb, '[]'::jsonb)",
        account_id, json.dumps(owned_ship_ids)
    )
    await store.aexecute(
        "INSERT INTO fleets (commander_id, game_id, name, ship_list, meowfficer_list) "
        "VALUES ($1, 11, '', '[]'::jsonb, '[]'::jsonb) "
        "ON CONFLICT (commander_id, game_id) DO NOTHING",
        account_id
    )
    if owned_ship_ids:
        # Inserting explicit ids does not advance a PostgreSQL sequence, so the
        # counter has to be pushed up to MAX(id). SQLite derives the next rowid
        # from MAX(rowid)+1 automatically and needs no resync -- the dialect
        # returns an empty statement there.
        from src.db.dialect import current_dialect

        resync = current_dialect().resync_identity_sql("owned_ships", "id")
        if resync:
            await store.aexecute(resync)
    log_event("Client", "CreateCommander", f"created new commander for account {account_id}", LOG_LEVEL_INFO)
    return account_id


async def commander_exists(commander_id: int) -> bool:
    async with get_session() as session:
        result = await session.execute(
            text("SELECT 1 FROM commanders WHERE commander_id = :cid"),
            {"cid": commander_id},
        )
        return result.first() is not None


async def get_commander(commander_id: int) -> Optional[dict]:
    async with get_session() as session:
        result = await session.execute(
            text("SELECT * FROM commanders WHERE commander_id = :cid"),
            {"cid": commander_id},
        )
        row = result.mappings().first()
        return dict(row) if row else None


async def commander_name_exists(name: str, exclude_id: Optional[int] = None) -> bool:
    async with get_session() as session:
        if exclude_id is not None:
            result = await session.execute(
                text("SELECT 1 FROM commanders WHERE name = :nm AND commander_id != :cid"),
                {"nm": name, "cid": exclude_id},
            )
        else:
            result = await session.execute(
                text("SELECT 1 FROM commanders WHERE name = :nm"),
                {"nm": name},
            )
        return result.first() is not None


async def insert_commander(commander_id: int, account_id: int, name: str, level: int = 1, exp: int = 0,
                           **extra) -> None:
    fields = {
        "commander_id": commander_id,
        "account_id": account_id,
        "name": name,
        "level": level,
        "exp": exp,
    }
    fields.update(extra)
    col_names = ", ".join(fields.keys())
    placeholders = ", ".join(f":{k}" for k in fields)
    async with get_session() as session:
        await session.execute(
            text(f"INSERT INTO commanders ({col_names}) VALUES ({placeholders})"),
            fields,
        )
        await session.commit()


async def update_commanders_dynamic(commander_id: int, **fields) -> None:
    if not fields:
        return
    set_clause = ", ".join(f"{k} = :{k}" for k in fields)
    params = {"cid": commander_id}
    params.update(fields)
    async with get_session() as session:
        await session.execute(
            text(f"UPDATE commanders SET {set_clause} WHERE commander_id = :cid"),
            params,
        )
        await session.commit()


async def delete_commander_by_id(commander_id: int) -> None:
    async with get_session() as session:
        await session.execute(
            text("DELETE FROM commanders WHERE commander_id = :cid"),
            {"cid": commander_id},
        )
        await session.commit()


async def count_commanders(where_clause: str = "", params: Optional[dict] = None) -> int:
    async with get_session() as session:
        q = "SELECT COUNT(*) as cnt FROM commanders c"
        if where_clause:
            q += " " + where_clause
        result = await session.execute(text(q), params or {})
        row = result.mappings().first()
        return row["cnt"] if row else 0


async def list_commanders(select_clause: str = "*", where_clause: str = "",
                          order_clause: str = "ORDER BY c.commander_id",
                          params: Optional[dict] = None,
                          offset: int = 0, limit: int = 50) -> list[dict]:
    async with get_session() as session:
        q = f"SELECT {select_clause} FROM commanders c"
        if where_clause:
            q += " " + where_clause
        q += f" {order_clause} OFFSET :ofs LIMIT :lim"
        p = {"ofs": offset, "lim": limit}
        if params:
            p.update(params)
        result = await session.execute(text(q), p)
        return [dict(r) for r in result.mappings().all()]


async def search_commanders(pattern: str, offset: int = 0, limit: int = 50) -> list[dict]:
    async with get_session() as session:
        result = await session.execute(
            text("SELECT commander_id, name, level, account_id, last_login FROM commanders "
                 "WHERE name ILIKE :pat OR CAST(commander_id AS TEXT) ILIKE :pat "
                 "ORDER BY commander_id OFFSET :ofs LIMIT :lim"),
            {"pat": pattern, "ofs": offset, "lim": limit},
        )
        return [dict(r) for r in result.mappings().all()]


async def count_search_commanders(pattern: str) -> int:
    async with get_session() as session:
        result = await session.execute(
            text("SELECT COUNT(*) as cnt FROM commanders WHERE name ILIKE :pat OR CAST(commander_id AS TEXT) ILIKE :pat"),
            {"pat": pattern},
        )
        row = result.mappings().first()
        return row["cnt"] if row else 0

def _sync_check_commander_name_availability(name: str) -> bool:
    with get_sync_session() as session:
        result = session.execute(
            select(Commander).where(Commander.name == name)
        ).scalar_one_or_none()
        return result is None

def _sync_update_commander_guide_indices(commander_id: int, guide_index: int, new_guide_index: int):
    from src.db.session import get_sync_session
    with get_sync_session() as session:
        session.execute(
            text("UPDATE commanders SET guide_index = :gi, new_guide_index = :ngi WHERE commander_id = :cid"),
            {"gi": guide_index, "ngi": new_guide_index, "cid": commander_id}
        )
        session.commit()

def _sync_get_player_registration_date(commander_id: int) -> int | None:
    with get_sync_session() as session:
        result = session.execute(
            select(Commander.create_time).where(Commander.id == commander_id)
        )
        return result.scalar_one_or_none()

def _sync_commit_commander(commander: Commander):
    with get_sync_session() as session:
        session.merge(commander)
        session.commit()

def commander_exists_sync(commander_id: int) -> bool:
    with get_sync_session() as session:
        return session.get(Commander, commander_id) is not None

check_commander_name_availability = _sync_check_commander_name_availability
update_commander_guide_indices = _sync_update_commander_guide_indices
get_player_registration_date = _sync_get_player_registration_date
commit_commander = _sync_commit_commander

class Commander(Base):
    __tablename__ = 'commanders'
    commander_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    account_id: Mapped[int] = mapped_column(BigInteger)
    level: Mapped[int] = mapped_column(BigInteger, default=0)
    exp: Mapped[int] = mapped_column(BigInteger, default=0)
    name: Mapped[str] = mapped_column(String, default='')
    last_login: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    guide_index: Mapped[int] = mapped_column(BigInteger, default=0)
    new_guide_index: Mapped[int] = mapped_column(BigInteger, default=0)
    name_change_cooldown: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    room_id: Mapped[int] = mapped_column(BigInteger, default=0)
    exchange_count: Mapped[int] = mapped_column(BigInteger, default=0)
    draw_count1: Mapped[int] = mapped_column(BigInteger, default=0)
    draw_count10: Mapped[int] = mapped_column(BigInteger, default=0)
    support_requisition_count: Mapped[int] = mapped_column(BigInteger, default=0)
    support_requisition_month: Mapped[int] = mapped_column(BigInteger, default=0)
    collect_attack_count: Mapped[int] = mapped_column(BigInteger, default=0)
    acc_pay_lv: Mapped[int] = mapped_column(BigInteger, default=0)
    living_area_cover_id: Mapped[int] = mapped_column(BigInteger, default=0)
    selected_icon_frame_id: Mapped[int] = mapped_column(BigInteger, default=0)
    selected_chat_frame_id: Mapped[int] = mapped_column(BigInteger, default=0)
    selected_battle_ui_id: Mapped[int] = mapped_column(BigInteger, default=0)
    display_icon_id: Mapped[int] = mapped_column(BigInteger, default=0)
    display_skin_id: Mapped[int] = mapped_column(BigInteger, default=0)
    display_icon_theme_id: Mapped[int] = mapped_column(BigInteger, default=0)
    manifesto: Mapped[str] = mapped_column(String, default='')
    dorm_name: Mapped[str] = mapped_column(String, default='')
    random_ship_mode: Mapped[int] = mapped_column(BigInteger, default=0)
    random_flag_ship_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    child_display: Mapped[int] = mapped_column(BigInteger, default=0)
    mail_storeroom_lv: Mapped[int] = mapped_column(BigInteger, default=0)
    ship_bag_size: Mapped[int] = mapped_column(BigInteger, default=0)
    equip_bag_size: Mapped[int] = mapped_column(BigInteger, default=0)
    commander_bag_size: Mapped[int] = mapped_column(BigInteger, default=0)
    spweapon_bag_size: Mapped[int] = mapped_column(BigInteger, default=0)
    tactical_class_slots: Mapped[int] = mapped_column(BigInteger, default=2)
    loading_pic_open_flag: Mapped[int] = mapped_column(BigInteger, default=0)
    loading_pic_id_list_1: Mapped[list] = mapped_column(PortableBigIntegerArray, default=list)
    loading_pic_id_list_2: Mapped[list] = mapped_column(PortableBigIntegerArray, default=list)

    owned_ships_map: dict = {}
    items_map: dict = {}
    commander_items_map: dict = {}
    misc_items_map: dict = {}
    owned_resources_map: dict = {}
    owned_equipment_map: dict = {}
    owned_sp_weapons: list = []
    owned_sp_weapons_map: dict = {}
    owned_skins_map: dict = {}
    builds: list = []
    ships: list = []

    # -- Cached gameplay flags (per-instance, in self.__dict__) --
    @property
    def is_first_build(self) -> bool:
        """True until the tutorial build's auto-commit task (Guide "Build 1
        ship.", 23003) is submitted. Computed from the DB once per session on
        first access, then cached; the build handler flips it to False as soon
        as the pinned first build is consumed."""
        cached = self.__dict__.get("_is_first_build")
        if cached is None:
            from src.answer.shipbuild.helpers import is_before_first_build_sync
            cached = is_before_first_build_sync(self.commander_id)
            self.__dict__["_is_first_build"] = cached
        return cached

    @is_first_build.setter
    def is_first_build(self, value: bool) -> None:
        self.__dict__["_is_first_build"] = bool(value)

    # -- Delegate methods matching Go Commander methods --
    def has_enough_gold(self, amount):
        from src.orm.resource import has_enough_resource
        return has_enough_resource(self.commander_id, 1, amount)

    def has_enough_item(self, item_id, count):
        from src.orm.item import has_enough_item
        return has_enough_item(self.commander_id, item_id, count)

    def has_enough_resource(self, resource_id, amount):
        from src.orm.resource import has_enough_resource
        return has_enough_resource(self.commander_id, resource_id, amount)

    def add_item(self, item_id, count):
        from src.orm.item import add_item
        return add_item(self.commander_id, item_id, count)

    def add_resource(self, resource_id, amount):
        from src.orm.resource import add_resource
        return add_resource(self.commander_id, resource_id, amount)

    def give_skin(self, skin_id):
        from src.orm.skin import give_skin
        return give_skin(self.commander_id, skin_id)

    def consume_item(self, item_id, count):
        from src.orm.item import consume_item
        return consume_item(self.commander_id, item_id, count)

    def consume_resource(self, resource_id, amount):
        from src.orm.resource import consume_resource
        return consume_resource(self.commander_id, resource_id, amount)

    def add_owned_equipment(self, equip_id, count=1):
        from src.orm.owned_equipment import add_owned_equipment
        return add_owned_equipment(self.commander_id, equip_id, count)

    # Tx variants — ignore connection arg, delegate to non-tx
    def consume_item_tx(self, item_id, count):
        return self.consume_item(item_id, count)

    def consume_resource_tx(self, resource_id, amount):
        return self.consume_resource(resource_id, amount)

    def add_item_tx(self, item_id, count):
        return self.add_item(item_id, count)

    def add_resource_tx(self, resource_id, amount):
        return self.add_resource(resource_id, amount)

    def _cache_new_ship(self, obj):
        """Keep owned_ships_map/ships in sync after a mid-session grant so
        handlers that resolve ships via the cache (e.g. enhance) find it."""
        entry = {
            "id": obj.id,
            "owner_id": self.commander_id,
            "ship_id": obj.ship_id,
            "level": getattr(obj, "level", 1) or 1,
            "energy": getattr(obj, "energy", 150) or 150,
            "state": getattr(obj, "state", 1) or 1,
            "state_info1": getattr(obj, "state_info1", 0) or 0,
            "intimacy": getattr(obj, "intimacy", 0) or 0,
            "exp": getattr(obj, "exp", 0) or 0,
            "surplus_exp": 0,
            "max_level": getattr(obj, "max_level", 100) or 100,
            "is_locked": bool(getattr(obj, "is_locked", False)),
            "propose": bool(getattr(obj, "propose", False)),
            "create_time": getattr(obj, "create_time", None),
        }
        if hasattr(self, "owned_ships_map"):
            self.owned_ships_map[obj.id] = entry
        ships = getattr(self, "ships", None)
        if ships is not None:
            ships.append(obj)

    def add_ship(self, ship_template_id):
        from src.orm.owned_ship import add_ship
        obj = add_ship(self.commander_id, ship_template_id)
        try:
            self._cache_new_ship(obj)
        except Exception:
            pass
        return obj

    def add_ship_tx(self, ship_template_id):
        return self.add_ship(ship_template_id)

    def give_skin_with_expiry(self, skin_id, _expires_at=None):
        return self.give_skin(skin_id)

    def get_item_count(self, item_id):
        from sqlalchemy import text
        from src.db.session import get_sync_session
        with get_sync_session() as session:
            row = session.execute(
                text("SELECT COALESCE(SUM(count), 0) FROM commander_items WHERE commander_id = :cid AND item_id = :iid"),
                {"cid": self.commander_id, "iid": item_id},
            ).scalar()
            return row or 0

    def get_resource_count(self, resource_id):
        from src.orm.resource import dealias_resource
        from sqlalchemy import text
        from src.db.session import get_sync_session
        resource_id = dealias_resource(resource_id)
        with get_sync_session() as session:
            row = session.execute(
                text("SELECT amount FROM owned_resources WHERE commander_id = :cid AND resource_id = :rid"),
                {"cid": self.commander_id, "rid": resource_id},
            ).scalar()
            return row or 0

    def equipment_bag_count(self):
        from src.orm.owned_equipment import count_total_owned_equipment_sync
        return count_total_owned_equipment_sync(self.commander_id)

    def get_owned_equipment(self, equip_id):
        from src.orm.owned_equipment import get_owned_equipment_sync
        return get_owned_equipment_sync(self.commander_id, equip_id)

    def set_resource(self, resource_id, amount):
        from src.orm.resource import upsert_resource_amount
        upsert_resource_amount(self.commander_id, resource_id, amount)

    def increment_reserve_usage(self, count):
        from sqlalchemy import text
        from src.db.session import get_sync_session
        with get_sync_session() as session:
            session.execute(
                text("UPDATE commanders SET draw_count1 = draw_count1 + :cnt WHERE commander_id = :cid"),
                {"cid": self.commander_id, "cnt": count},
            )
            session.commit()

    def remove_owned_equipment(self, equip_id, count=1):
        from src.orm.equipment import remove_owned_equipment as _remove_eq
        return _remove_eq(self.commander_id, equip_id, count)

    def like(self, group_id):
        from sqlalchemy import text
        from src.db.session import get_sync_session
        with get_sync_session() as session:
            session.execute(
                text("INSERT INTO likes (group_id, liker_id) VALUES (:gid, :lid) ON CONFLICT DO NOTHING"),
                {"gid": group_id, "lid": self.commander_id},
            )
            session.commit()

    def commit(self):
        from src.db.session import get_sync_session
        from sqlalchemy import text
        with get_sync_session() as session:
            session.execute(
                text("UPDATE commanders SET name = :name, level = :level, exp = :exp, "
                     "name_change_cooldown = :ncc, manifesto = :manifesto, "
                     "selected_icon_frame_id = :sifi, selected_chat_frame_id = :scfi, "
                     "selected_battle_ui_id = :sbui WHERE commander_id = :cid"),
                {"name": self.name, "level": self.level, "exp": self.exp,
                 "ncc": self.name_change_cooldown, "manifesto": getattr(self, "manifesto", "") or "",
                 "sifi": getattr(self, "selected_icon_frame_id", 0) or 0,
                 "scfi": getattr(self, "selected_chat_frame_id", 0) or 0,
                 "sbui": getattr(self, "selected_battle_ui_id", 0) or 0,
                 "cid": self.commander_id},
            )
            session.commit()

    def save_loading_pic(self):
        from src.db.session import get_sync_session
        from sqlalchemy import text
        with get_sync_session() as session:
            session.execute(
                text("UPDATE commanders SET loading_pic_open_flag = :flag, "
                     "loading_pic_id_list_1 = :l1, loading_pic_id_list_2 = :l2 "
                     "WHERE commander_id = :cid"),
                {"flag": self.loading_pic_open_flag,
                 "l1": self.loading_pic_id_list_1,
                 "l2": self.loading_pic_id_list_2,
                 "cid": self.commander_id},
            )
            session.commit()

    def load(self):
        from src.orm.owned_ship import OwnedShip
        from src.orm.players import get_commander_core_by_id_sync
        from sqlalchemy import select
        reloaded = get_commander_core_by_id_sync(self.commander_id)
        if reloaded is not None:
            for col in self.__table__.columns.keys():
                setattr(self, col, getattr(reloaded, col))
        from src.db.session import get_sync_session
        from sqlalchemy import text
        with get_sync_session() as session:
            self.ships = list(session.execute(
                select(OwnedShip).where(
                    OwnedShip.owner_id == self.commander_id,
                    OwnedShip.deleted_at.is_(None),
                ).order_by(OwnedShip.id)
            ).scalars().all())
            self.owned_ships_map = {}
            for row in session.execute(text("SELECT id, owner_id, ship_id, level, energy, state, state_info1, intimacy, exp, surplus_exp, max_level, is_locked, propose, create_time FROM owned_ships WHERE owner_id = :cid AND deleted_at IS NULL"), {"cid": self.commander_id}).fetchall():
                self.owned_ships_map[row[0]] = {
                    "id": row[0], "owner_id": row[1], "ship_id": row[2],
                    "level": row[3], "energy": row[4], "state": row[5],
                    "state_info1": row[6], "intimacy": row[7], "exp": row[8],
                    "surplus_exp": row[9], "max_level": row[10], "is_locked": row[11],
                    "propose": row[12], "create_time": row[13],
                }
            from src.orm.item import list_commander_items_sync
            self.items_map = {
                r["item_id"]: {"item_id": r["item_id"], "count": r["count"]}
                for r in list_commander_items_sync(self.commander_id)
            }
            self.commander_items_map = self.items_map

            from src.orm.commander_misc_item import list_commander_misc_items_sync
            self.misc_items_map = {
                r["item_id"]: {"item_id": r["item_id"], "data": r["data"]}
                for r in list_commander_misc_items_sync(self.commander_id)
            }

            from src.orm.resource import list_owned_resources_sync
            self.owned_resources_map = {
                r["resource_id"]: {"resource_id": r["resource_id"], "amount": r["amount"]}
                for r in list_owned_resources_sync(self.commander_id)
            }

            from src.orm.owned_equipment import list_owned_equipment_sync
            self.owned_equipment_map = {
                r["equipment_id"]: {"equipment_id": r["equipment_id"], "count": r["count"]}
                for r in list_owned_equipment_sync(self.commander_id)
            }

            from src.orm.spweapon import list_owned_sp_weapons_sync
            self.owned_sp_weapons = list_owned_sp_weapons_sync(self.commander_id)
            self.owned_sp_weapons_map = {
                sp.id: sp for sp in self.owned_sp_weapons
            }
            self.builds = []
            from src.db import sqlite_types as _sqlite_types
            for row in session.execute(text("SELECT id, builder_id, ship_id, pool_id, finishes_at, state FROM builds WHERE builder_id = :cid ORDER BY id"), {"cid": self.commander_id}).fetchall():
                # raw text() reads bypass the SA column types: on SQLite the
                # driver hands finishes_at back as TEXT, while asyncpg returns
                # an aware datetime for timestamptz -- restore the parity here
                # or every consumer of commander.builds trips on str.
                finishes_at = row[4]
                if isinstance(finishes_at, str):
                    parsed = _sqlite_types._convert_timestamp(finishes_at)
                    if parsed is not None:
                        finishes_at = parsed
                self.builds.append({
                    "id": row[0], "builder_id": row[1], "ship_id": row[2],
                    "pool_id": row[3], "finishes_at": finishes_at,
                    "state": (int(row[5]) if row[5] is not None else 1),
                })
            self.owned_skins_map = {}
            for row in session.execute(text("SELECT skin_id FROM owned_skins WHERE commander_id = :cid"), {"cid": self.commander_id}).fetchall():
                self.owned_skins_map[row[0]] = row[0]
            # Keep the live-commander registry in sync so grant helpers can update
            # the in-memory maps immediately after writing to the database.
            try:
                from src.orm.active_commander import register_active_commander
                register_active_commander(self)
            except Exception:
                pass


# --------------------------------------------------------------------------- #
# Build & Exchange Counters
# --------------------------------------------------------------------------- #

def get_commander_build_counts(commander_id: int) -> dict[str, int]:
    store = get_default_store()
    if store is None:
        return {"draw_count1": 0, "draw_count10": 0, "exchange_count": 0}
    row = store.fetchrow(
        "SELECT draw_count1, draw_count10, exchange_count FROM commanders WHERE commander_id = $1",
        commander_id,
    )
    if row:
        return {"draw_count1": row[0], "draw_count10": row[1], "exchange_count": row[2]}
    return {"draw_count1": 0, "draw_count10": 0, "exchange_count": 0}


async def aget_commander_build_counts(commander_id: int) -> dict[str, int]:
    store = get_default_store()
    if store is None:
        return {"draw_count1": 0, "draw_count10": 0, "exchange_count": 0}
    row = await store.afetchrow(
        "SELECT draw_count1, draw_count10, exchange_count FROM commanders WHERE commander_id = $1",
        commander_id,
    )
    if row:
        return {
            "draw_count1": int(row["draw_count1"] or 0),
            "draw_count10": int(row["draw_count10"] or 0),
            "exchange_count": int(row["exchange_count"] or 0),
        }
    return {"draw_count1": 0, "draw_count10": 0, "exchange_count": 0}


def increment_commander_exchange_count(commander_id: int, amount: int) -> None:
    store = get_default_store()
    if store is None:
        return
    store.execute(
        "UPDATE commanders SET exchange_count = exchange_count + $2 WHERE commander_id = $1",
        commander_id, amount,
    )


async def aincrement_commander_exchange_count(commander_id: int, amount: int) -> None:
    store = get_default_store()
    if store is None:
        return
    await store.aexecute(
        "UPDATE commanders SET exchange_count = exchange_count + $2 WHERE commander_id = $1",
        commander_id, amount,
    )


def increment_commander_build_counts(commander_id: int, count: int) -> None:
    store = get_default_store()
    if store is None:
        return
    if count == 1:
        store.execute(
            "UPDATE commanders SET draw_count1 = draw_count1 + 1 WHERE commander_id = $1",
            commander_id,
        )
    elif count == 10:
        store.execute(
            "UPDATE commanders SET draw_count10 = draw_count10 + 1 WHERE commander_id = $1",
            commander_id,
        )
    increment_commander_exchange_count(commander_id, count)


async def aincrement_commander_build_counts(commander_id: int, count: int) -> None:
    store = get_default_store()
    if store is None:
        return
    if count == 1:
        await store.aexecute(
            "UPDATE commanders SET draw_count1 = draw_count1 + 1 WHERE commander_id = $1",
            commander_id,
        )
    elif count == 10:
        await store.aexecute(
            "UPDATE commanders SET draw_count10 = draw_count10 + 1 WHERE commander_id = $1",
            commander_id,
        )
    await aincrement_commander_exchange_count(commander_id, count)


async def atry_decrement_commander_exchange_count(
    commander_id: int, amount: int
) -> Optional[dict[str, Any]]:
    store = get_default_store()
    if store is None:
        return None
    row = await store.afetchrow(
        "UPDATE commanders SET exchange_count = exchange_count - $2 "
        "WHERE commander_id = $1 AND exchange_count >= $2 RETURNING exchange_count",
        commander_id, amount,
    )
    if row is None:
        return None
    return {"exchange_count": row[0]}

