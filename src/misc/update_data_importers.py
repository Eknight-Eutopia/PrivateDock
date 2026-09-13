from __future__ import annotations

import json

from src.db.store import get_default_store
from src.logger.logger import log_event, LOG_LEVEL_INFO, LOG_LEVEL_ERROR
from src.misc.update_data_helpers import (
    get_privatedock_data,
    get_configuration_data,
    list_privatedock_data_files,
    filter_config_files,
    config_entry_key,
    order,
)
from src.orm.config_entry import upsert_config_entry_data

_data_fn_sqlc: dict[str, object] = {}


def _register(name: str):
    def decorator(fn):
        _data_fn_sqlc[name] = fn
        return fn

    return decorator


def update_all_data_sqlc(region: str):
    for key in order:
        fn = _data_fn_sqlc.get(key)
        if fn is None:
            log_event("GameData", "Updating", f"missing importer for {key}", LOG_LEVEL_ERROR)
            continue
        log_event("GameData", "Updating", f"Updating {key} (region={region})", LOG_LEVEL_INFO)
        try:
            fn(region)
        except Exception as e:
            log_event("GameData", "Updating", f"failed to update {key}: {e}", LOG_LEVEL_ERROR)
            raise


def _json_val(data, key, default=None):
    """Safely extract a value from a JSON dict, handling string->int conversion."""
    v = data.get(key, default)
    if v is None:
        return default
    return v


def _int_val(data, key, default=0):
    v = data.get(key, default)
    if v is None or v == "":
        return default
    return int(v)


def _str_val(data, key, default=""):
    v = data.get(key, default)
    if v is None:
        return default
    return str(v)


def _opt_int_val(data, key):
    v = data.get(key)
    if v is None:
        return None
    return int(v)


# ── Items ──────────────────────────────────────────────────────────────


@_register("Items")
def import_items_sqlc(region: str):
    store = get_default_store()
    data = get_privatedock_data(region, "sharecfgdata/item_data_statistics.json")
    for entry in (data.values() if isinstance(data, dict) else data):
        store.execute(
            "INSERT INTO items (id, name, rarity, shop_id, type, virtual_type) "
            "VALUES ($1, $2, $3, $4, $5, $6) "
            "ON CONFLICT (id) DO UPDATE SET "
            "name = EXCLUDED.name, rarity = EXCLUDED.rarity, "
            "shop_id = EXCLUDED.shop_id, type = EXCLUDED.type, "
            "virtual_type = EXCLUDED.virtual_type",
            _int_val(entry, "id"),
            _str_val(entry, "name"),
            _int_val(entry, "rarity"),
            _int_val(entry, "shop_id"),
            _int_val(entry, "type"),
            _int_val(entry, "virtual_type"),
        )
    # Virtual items too. They are NOT part of item_data_statistics; grants that
    # carry a virtual id raw used to lazily stub them into `items` with an
    # empty name (unsearchable). Import the virtual catalog so the table is
    # complete; virtual_type=1 marks catalog virtuals.
    vdata = get_privatedock_data(region, "sharecfgdata/item_virtual_data_statistics.json")
    for entry in (vdata.values() if isinstance(vdata, dict) else vdata):
        store.execute(
            "INSERT INTO items (id, name, rarity, shop_id, type, virtual_type) "
            "VALUES ($1, $2, $3, $4, $5, 1) "
            "ON CONFLICT (id) DO UPDATE SET "
            "name = EXCLUDED.name, rarity = EXCLUDED.rarity, "
            "type = EXCLUDED.type, virtual_type = 1",
            _int_val(entry, "id"),
            _str_val(entry, "name"),
            _int_val(entry, "rarity"),
            _opt_int_val(entry, "shop_id"),
            _int_val(entry, "type"),
        )


# ── Buffs ──────────────────────────────────────────────────────────────


@_register("Buffs")
def import_buffs_sqlc(region: str):
    data = get_privatedock_data(region, "ShareCfg/benefit_buff_template.json")
    store = get_default_store()
    for entry in (data.values() if isinstance(data, dict) else data):
        store.execute(
            "INSERT INTO buffs (id, name, description, max_time, benefit_type) "
            "VALUES ($1, $2, $3, $4, $5) "
            "ON CONFLICT (id) DO UPDATE SET "
            "name = EXCLUDED.name, description = EXCLUDED.description, "
            "max_time = EXCLUDED.max_time, benefit_type = EXCLUDED.benefit_type",
            _int_val(entry, "id"),
            _str_val(entry, "name"),
            _str_val(entry, "description"),
            _int_val(entry, "max_time"),
            _str_val(entry, "benefit_type"),
        )


# ── Ships ──────────────────────────────────────────────────────────────


@_register("Ships")
def import_ships_sqlc(region: str):
    data = get_privatedock_data(region, "sharecfgdata/ship_data_statistics.json")
    store = get_default_store()
    for entry in (data.values() if isinstance(data, dict) else data):
        store.execute(
            "INSERT INTO ships (template_id, name, english_name, rarity_id, star, type, nationality, build_time) "
            "VALUES ($1, $2, $3, $4, $5, $6, $7, $8) "
            "ON CONFLICT (template_id) DO UPDATE SET "
            "name = EXCLUDED.name, english_name = EXCLUDED.english_name, "
            "rarity_id = EXCLUDED.rarity_id, star = EXCLUDED.star, "
            "type = EXCLUDED.type, nationality = EXCLUDED.nationality, "
            "build_time = EXCLUDED.build_time",
            _int_val(entry, "id"),
            _str_val(entry, "name"),
            _str_val(entry, "english_name"),
            _int_val(entry, "rarity"),
            _int_val(entry, "star"),
            _int_val(entry, "type"),
            _int_val(entry, "nationality"),
            _int_val(entry, "build_time"),
        )


# ── Skins ──────────────────────────────────────────────────────────────


@_register("Skins")
def import_skins_sqlc(region: str):
    data = get_privatedock_data(region, "ShareCfg/ship_skin_template.json")
    store = get_default_store()
    for entry in (data.values() if isinstance(data, dict) else data):
        store.execute(
            "INSERT INTO skins ("
            "id, name, ship_group, \"desc\", bg, bg_sp, bgm, painting, prefab, "
            "change_skin, show_skin, skeleton_skin, ship_l2_d_id, l2_d_animations, "
            "l2_d_drag_rate, l2_d_para_range, l2_dse, l2_d_voice_calib, part_scale, "
            "main_ui_fx, spine_offset, spine_profile, tag, time, get_showing, "
            "purchase_offset, shop_offset, rarity_bg, special_effects, "
            "group_index, gyro, hand_id, illustrator, illustrator2, "
            "voice_actor, voice_actor2, double_char, lip_smoothing, lip_sync_gain, "
            "l2_d_ignore_drag, skin_type, shop_id, shop_type_id, shop_dynamic_hx, "
            "spine_action, spine_use_live2_d, live2_d_offset, live2_d_profile, "
            "fx_container, bound_bone, smoke"
            ") VALUES ("
            "$1, $2, $3, $4, $5, $6, $7, $8, $9, "
            "$10, $11, $12, $13, $14, $15, $16, $17, $18, $19, "
            "$20, $21, $22, $23, $24, $25, $26, $27, $28, $29, "
            "$30, $31, $32, $33, $34, $35, $36, $37, $38, $39, "
            "$40, $41, $42, $43, $44, $45, $46, $47, $48, $49, $50, $51"
            ") ON CONFLICT (id) DO UPDATE SET "
            "name = EXCLUDED.name, ship_group = EXCLUDED.ship_group",
            _int_val(entry, "id"),
            _str_val(entry, "name"),
            _int_val(entry, "ship_group"),
            _str_val(entry, "desc"),
            _str_val(entry, "bg"),
            _str_val(entry, "bg_sp"),
            _str_val(entry, "bgm"),
            _str_val(entry, "painting"),
            _str_val(entry, "prefab"),
            json.dumps(entry.get("change_skin", "")),
            _str_val(entry, "show_skin"),
            _str_val(entry, "skeleton_skin"),
            json.dumps(entry.get("ship_l2d_id", "")),
            json.dumps(entry.get("l2d_animations", "")),
            json.dumps(entry.get("l2d_drag_rate", "")),
            json.dumps(entry.get("l2d_para_range", "")),
            json.dumps(entry.get("l2dse", "")),
            json.dumps(entry.get("l2d_voice_calib", "")),
            _str_val(entry, "part_scale"),
            _str_val(entry, "main_ui_fx"),
            json.dumps(entry.get("spine_offset", "")),
            json.dumps(entry.get("spine_profile", "")),
            json.dumps(entry.get("tag", "")),
            json.dumps(entry.get("time", "")),
            json.dumps(entry.get("get_showing", "")),
            json.dumps(entry.get("purchase_offset", "")),
            json.dumps(entry.get("shop_offset", "")),
            _str_val(entry, "rarity_bg"),
            json.dumps(entry.get("special_effects", "")),
            _opt_int_val(entry, "group_index"),
            _opt_int_val(entry, "gyro"),
            _opt_int_val(entry, "hand_id"),
            _opt_int_val(entry, "illustrator"),
            _opt_int_val(entry, "illustrator2"),
            _opt_int_val(entry, "voice_actor"),
            _opt_int_val(entry, "voice_actor2"),
            _opt_int_val(entry, "double_char"),
            _opt_int_val(entry, "lip_smoothing"),
            _opt_int_val(entry, "lip_sync_gain"),
            _opt_int_val(entry, "l2d_ignore_drag"),
            _opt_int_val(entry, "skin_type"),
            _opt_int_val(entry, "shop_id"),
            _opt_int_val(entry, "shop_type_id"),
            _opt_int_val(entry, "shop_dynamic_hx"),
            json.dumps(entry.get("spine_action", "")),
            _opt_int_val(entry, "spine_use_live2d"),
            json.dumps(entry.get("live2d_offset", "")),
            json.dumps(entry.get("live2d_profile", "")),
            json.dumps(entry.get("fx_container", "")),
            json.dumps(entry.get("bound_bone", "")),
            json.dumps(entry.get("smoke", "")),
        )


# ── Resources ──────────────────────────────────────────────────────────


@_register("Resources")
def import_resources_sqlc(region: str):
    data = get_privatedock_data(region, "ShareCfg/player_resource.json")
    store = get_default_store()
    for entry in (data.values() if isinstance(data, dict) else data):
        store.execute(
            "INSERT INTO resources (id, item_id, name) "
            "VALUES ($1, $2, $3) "
            "ON CONFLICT (id) DO UPDATE SET "
            "item_id = EXCLUDED.item_id, name = EXCLUDED.name",
            _int_val(entry, "id"),
            _int_val(entry, "item_id"),
            _str_val(entry, "name"),
        )


# ── Pools (fills build_pool_ships) ────────────────────────────────────────
# build_pools.json is a per-(ship, pool) membership list: a ship may appear in
# several pools (URs and older CAs/CLs are cross-listed, e.g. Heavy+Special or
# Light+Special+Heavy). The draw code reads membership from build_pool_ships;
# ships.pool_id was dropped (migration 0095) — one column cannot represent
# cross-listed ships.


@_register("Pools")
def import_pools_sqlc(region: str):
    data = get_configuration_data("build_pools.json")
    store = get_default_store()
    entries = list(data.values()) if isinstance(data, dict) else list(data)
    store.execute("DELETE FROM build_pool_ships")
    for entry in entries:
        pool_id = _int_val(entry, "pool")
        template_id = _int_val(entry, "id")
        if not template_id:
            continue
        store.execute(
            "INSERT INTO build_pool_ships (pool_id, template_id) VALUES ($1, $2) "
            "ON CONFLICT DO NOTHING",
            pool_id, template_id,
        )
        if store.fetchrow("SELECT 1 FROM ships WHERE template_id = $1", template_id) is None:
            log_event("GameData", "Pools", f"ship not found for template_id={template_id}", LOG_LEVEL_ERROR)


# ── Requisition Ships ──────────────────────────────────────────────────


@_register("Requisition")
def import_requisition_ships_sqlc(region: str):
    ship_ids = get_configuration_data("requisition_ships.json")
    store = get_default_store()
    if isinstance(ship_ids, dict):
        ship_ids = list(ship_ids.keys())
    for ship_id in ship_ids:
        store.execute(
            "INSERT INTO requisition_ships (ship_id) VALUES ($1) ON CONFLICT DO NOTHING",
            int(ship_id),
        )


# ── Build Times (updates ships table) ──────────────────────────────────


@_register("BuildTimes")
def import_build_times_sqlc(region: str):
    build_times = get_configuration_data("build_times.json")
    store = get_default_store()
    if isinstance(build_times, list):
        for entry in build_times:
            if isinstance(entry, dict):
                rc = store.execute(
                    "UPDATE ships SET build_time = $1 WHERE template_id = $2",
                    _int_val(entry, "build_time"),
                    _int_val(entry, "id"),
                )
                if rc == 0:
                    log_event("GameData", "BuildTimes", f"ship not found for template_id={entry.get('id')}", LOG_LEVEL_ERROR)
    else:
        for str_id, time_val in build_times.items():
            rc = store.execute(
                "UPDATE ships SET build_time = $1 WHERE template_id = $2",
                int(time_val),
                int(str_id),
            )
            if rc == 0:
                log_event("GameData", "BuildTimes", f"ship not found for template_id={str_id}", LOG_LEVEL_ERROR)


# ── Shop Offers ────────────────────────────────────────────────────────


@_register("ShopOffers")
def import_shop_offers_sqlc(region: str):
    data = get_privatedock_data(region, "sharecfgdata/shop_template.json")
    store = get_default_store()
    for entry in (data.values() if isinstance(data, dict) else data):
        effect_args = entry.get("effect_args", [])
        if isinstance(effect_args, list):
            effects = json.dumps([int(x) for x in effect_args])
        else:
            effects = json.dumps(effect_args)
        store.execute(
            "INSERT INTO shop_offers (id, effects, effect_args, number, resource_number, resource_id, type, genre, discount) "
            "VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9) "
            "ON CONFLICT (id) DO UPDATE SET "
            "effects = EXCLUDED.effects, effect_args = EXCLUDED.effect_args, "
            "number = EXCLUDED.number, resource_number = EXCLUDED.resource_number, "
            "resource_id = EXCLUDED.resource_id, type = EXCLUDED.type, "
            "genre = EXCLUDED.genre, discount = EXCLUDED.discount",
            _int_val(entry, "id"),
            effects,
            json.dumps(effect_args),
            int(entry.get("num", 0)),
            int(entry.get("resource_num", 0)),
            int(entry.get("resource_type", 0)),
            _int_val(entry, "type"),
            _str_val(entry, "genre"),
            _int_val(entry, "discount"),
        )

    # Regenerate the Charge-shop limit JSONs (gift packages + gem shop) from
    # the same template data and refresh the live server-side dicts — keeps
    # SC_16105.normal_list and the purchase gate in sync with the client.
    from src.misc.offer_limits import write_offer_limits
    write_offer_limits(region, template_data=data)


# ── Weapons ────────────────────────────────────────────────────────────


@_register("Weapons")
def import_weapons_sqlc(region: str):
    data = get_privatedock_data(region, "sharecfgdata/weapon_property.json")
    store = get_default_store()
    for entry in (data.values() if isinstance(data, dict) else data):
        store.execute(
            "INSERT INTO weapons ("
            "id, action_index, aim_type, angle, attack_attribute, attack_attribute_ratio, "
            "auto_aftercast, axis_angle, barrage_id, bullet_id, charge_param, corrected, "
            "damage, effect_move, expose, fire_fx, fire_fx_loop_type, fire_sfx, "
            "initial_over_heat, min_range, oxy_type, precast_param, queue, range, "
            "recover_time, reload_max, search_condition, search_type, shake_screen, "
            "spawn_bound, suppress, torpedo_ammo, type"
            ") VALUES ("
            "$1, $2, $3, $4, $5, $6, $7, $8, $9, $10, "
            "$11, $12, $13, $14, $15, $16, $17, $18, $19, $20, "
            "$21, $22, $23, $24, $25, $26, $27, $28, $29, $30, $31, $32, $33"
            ") ON CONFLICT (id) DO UPDATE SET "
            "damage = EXCLUDED.damage, type = EXCLUDED.type",
            _int_val(entry, "id"),
            _str_val(entry, "action_index"),
            _int_val(entry, "aim_type"),
            _int_val(entry, "angle"),
            _int_val(entry, "attack_attribute"),
            _int_val(entry, "attack_attribute_ratio"),
            json.dumps(entry.get("auto_aftercast", "")),
            _int_val(entry, "axis_angle"),
            json.dumps(entry.get("barrage_id", "")),
            json.dumps(entry.get("bullet_id", "")),
            json.dumps(entry.get("charge_param", "")),
            _int_val(entry, "corrected"),
            _int_val(entry, "damage"),
            _int_val(entry, "effect_move"),
            _int_val(entry, "expose"),
            _str_val(entry, "fire_fx"),
            _int_val(entry, "fire_fx_loop_type"),
            _str_val(entry, "fire_sfx"),
            _int_val(entry, "initial_over_heat"),
            _int_val(entry, "min_range"),
            json.dumps(entry.get("oxy_type", "")),
            json.dumps(entry.get("precast_param", "")),
            _int_val(entry, "queue"),
            _int_val(entry, "range"),
            json.dumps(entry.get("recover_time", 0)),
            _int_val(entry, "reload_max"),
            json.dumps(entry.get("search_condition", "")),
            _int_val(entry, "search_type"),
            _int_val(entry, "shake_screen"),
            json.dumps(entry.get("spawn_bound", "")),
            _int_val(entry, "suppress"),
            _int_val(entry, "torpedo_ammo"),
            _int_val(entry, "type"),
        )


# ── Equipments ─────────────────────────────────────────────────────────


@_register("Equipments")
def import_equipments_sqlc(region: str):
    data = get_privatedock_data(region, "sharecfgdata/equip_data_template.json")
    store = get_default_store()
    for entry in (data.values() if isinstance(data, dict) else data):
        store.execute(
            'INSERT INTO equipments ('
            'id, base, destroy_gold, destroy_item, equip_limit, "group", important, '
            'level, next, prev, restore_gold, restore_item, ship_type_forbidden, '
            'trans_use_gold, trans_use_item, type, upgrade_formula_id'
            ") VALUES ("
            "$1, $2, $3, $4, $5, $6, $7, $8, $9, $10, "
            "$11, $12, $13, $14, $15, $16, $17"
            ") ON CONFLICT (id) DO UPDATE SET "
            "type = EXCLUDED.type, level = EXCLUDED.level, "
            "destroy_gold = EXCLUDED.destroy_gold, destroy_item = EXCLUDED.destroy_item",
            _int_val(entry, "id"),
            _opt_int_val(entry, "base"),
            _int_val(entry, "destory_gold"),
            json.dumps(entry.get("destory_item", "")),
            _int_val(entry, "equip_limit"),
            _int_val(entry, "group"),
            _int_val(entry, "important"),
            _int_val(entry, "level"),
            _int_val(entry, "next"),
            _int_val(entry, "prev"),
            _int_val(entry, "restore_gold"),
            json.dumps(entry.get("restore_item", "")),
            json.dumps(entry.get("ship_type_forbidden", "")),
            _int_val(entry, "trans_use_gold"),
            json.dumps(entry.get("trans_use_item", "")),
            _int_val(entry, "type"),
            json.dumps(entry.get("upgrade_formula_id", "")),
        )


# ── Skills ─────────────────────────────────────────────────────────────


@_register("Skills")
def import_skills_sqlc(region: str):
    data = get_privatedock_data(region, "GameCfg/skill.json")
    store = get_default_store()
    if isinstance(data, dict):
        entries = data.values()
    else:
        entries = data
    for entry in entries:
        store.execute(
            'INSERT INTO skills (id, name, "desc", cd, painting, picture, ani_effect, ui_effect, effect_list) '
            "VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9) "
            'ON CONFLICT (id) DO UPDATE SET '
            'name = EXCLUDED.name, "desc" = EXCLUDED."desc", '
            "cd = EXCLUDED.cd, painting = EXCLUDED.painting, "
            "picture = EXCLUDED.picture, ani_effect = EXCLUDED.ani_effect, "
            "ui_effect = EXCLUDED.ui_effect, effect_list = EXCLUDED.effect_list",
            _int_val(entry, "id"),
            _str_val(entry, "name"),
            _str_val(entry, "desc"),
            _int_val(entry, "cd"),
            json.dumps(entry.get("painting", "")),
            _str_val(entry, "picture"),
            json.dumps(entry.get("ani_effect", "")),
            _str_val(entry, "ui_effect"),
            json.dumps(entry.get("effect_list", [])),
        )


# ── Config Entries ─────────────────────────────────────────────────────


@_register("Configs")
def import_config_entries_sqlc(region: str):
    share_cfg_files = list_privatedock_data_files(region, "ShareCfg")
    game_cfg_files = list_privatedock_data_files(region, "GameCfg")

    share_cfg_files = filter_config_files(
        share_cfg_files,
        [
            "activity_",
            "child_",
            "child2_",
            "dorm_",
            "dorm3d_",
            # fleet_tech_* (group / template / ship_template / ship_class) backs the
            # Fleet Tech camp (CS_64002/64005/64009) and the shipyard devdock tech
            # bar (shipyard_blueprint_helpers reads fleet_tech_ship_template).
            # It was in the old EXCLUDE list, then dropped when that list became
            # this allowlist -- so a full re-import silently stopped loading it and
            # load_fleet_tech_configs() returned empty. Keep it here.
            "fleet_tech_",
            "furniture_",
            "guild_",
            "mini_game_",
            "constellation_",
            "lover_",
            "loveletter_",
            "navalacademy_",
            "spweapon_",
            "equip_skin_",
            "ship_meta_",
            "technology_",
            "shop_",
        ],
        [
            "ShareCfg/tutorial_handbook.json",
            "ShareCfg/tutorial_handbook_task.json",
            "ShareCfg/game_room_template.json",
            "ShareCfg/gameroom_shop_template.json",
            "ShareCfg/backyard_theme_template.json",
            "ShareCfg/gameset.json",
            "ShareCfg/benefit_buff_template.json",
            "sharecfgdata/item_data_statistics.json",
            "sharecfgdata/item_virtual_data_statistics.json",
            "sharecfgdata/chapter_template.json",
            "sharecfgdata/chapter_template_loop.json",
            "sharecfgdata/ship_data_template.json",
            "sharecfgdata/ship_data_breakout.json",
            "sharecfgdata/ship_data_statistics.json",
            "sharecfgdata/equip_data_statistics.json",
            "ShareCfg/item_data_frame.json",
            "ShareCfg/item_data_chat.json",
            "ShareCfg/item_data_battleui.json",
            "ShareCfg/drop_data_restore.json",
            "ShareCfg/livingarea_cover.json",
            "ShareCfg/oilfield_template.json",
            "ShareCfg/tradingport_template.json",
            "ShareCfg/class_upgrade_template.json",
            "ShareCfg/ship_data_blueprint.json",
            # exchange_ship.py reads this to resolve the exchange ship id for the
            # regular build pool.  It has a hardcoded fallback, but the config is
            # the real source -- without it the fallback silently masks data drift.
            "ShareCfg/ship_data_create_exchange.json",
            "ShareCfg/ship_data_strengthen.json",
            "ShareCfg/ship_strengthen_blueprint.json",
            "ShareCfg/ship_strengthen_meta.json",
            "ShareCfg/transform_data_template.json",
            "ShareCfg/compose_data_template.json",
            "ShareCfg/equip_upgrade_data.json",
            "ShareCfg/month_shop_template.json",
            "ShareCfg/medal_template.json",
            "ShareCfg/newserver_shop_template.json",
            "ShareCfg/blackfriday_shop_template.json",
            "ShareCfg/guild_store.json",
            "ShareCfg/guildset.json",
            "ShareCfg/shop_template.json",
            "ShareCfg/quota_shop_template.json",
            "ShareCfg/recommend_shop.json",
            "ShareCfg/re_map_template.json",
            "ShareCfg/escort_template.json",
            "ShareCfg/escort_map_template.json",
            "ShareCfg/shop_banner_template.json",
            "ShareCfg/pay_data_display.json",
            "ShareCfg/shop_discount_coupon_template.json",
            "ShareCfg/emoji_template.json",
            "ShareCfg/strategy_data_template.json",
            "ShareCfg/box_data_template.json",
            "sharecfgdata/expedition_data_template.json",
            "ShareCfg/expedition_daily_template.json",
            "ShareCfg/expedition_data_by_map.json",
            "sharecfgdata/task_data_template.json",
            "ShareCfg/skill_data_template.json",
            "ShareCfg/ship_level.json",
            "ShareCfg/user_level.json",
            "ShareCfg/collection_template.json",
            "ShareCfg/soundstory_template.json",
            "ShareCfg/storeup_data_template.json",
            "ShareCfg/commander_data_template.json",
            "ShareCfg/commander_home_style.json",
            "ShareCfg/intimacy_template.json",
            "ShareCfg/weekly_task_template.json",
            "ShareCfg/arena_data_shop.json",
            "ShareCfg/honormedal_goods_list.json",
            "ShareCfg/chapter_auto_statistics.json",
        ],
    )
    game_cfg_files = filter_config_files(game_cfg_files, None, [
        "GameCfg/dorm.json",
    ])

    all_files = share_cfg_files + game_cfg_files
    for file_path in all_files:
        _import_config_entries_from_file(region, file_path)


def _import_config_entries_from_file(region: str, file_path: str):
    data = get_privatedock_data(region, file_path)
    if isinstance(data, list):
        for index, entry in enumerate(data):
            upsert_config_entry_data(file_path, config_entry_key(entry, index), entry)
    elif isinstance(data, dict):
        for key, value in data.items():
            upsert_config_entry_data(file_path, key, value)


# ── Juustagram Templates ───────────────────────────────────────────────


@_register("JuustagramTemplates")
def import_juustagram_templates_sqlc(region: str):
    data = get_privatedock_data(region, "ShareCfg/activity_ins_template.json")
    store = get_default_store()
    for entry in (data.values() if isinstance(data, dict) else data):
        npc_discuss_persist = json.dumps(entry.get("npc_discuss_persist", []), ensure_ascii=False)
        time_val = json.dumps(entry.get("time", []), ensure_ascii=False)
        time_persist = json.dumps(entry.get("time_persist", []), ensure_ascii=False)
        store.execute(
            "INSERT INTO juustagram_templates ("
            "id, group_id, ship_group, name, sculpture, picture_persist, "
            "message_persist, is_active, npc_discuss_persist, time, time_persist, oalist_pic_persist"
            ") VALUES ("
            "$1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12"
            ") ON CONFLICT (id) DO UPDATE SET "
            "name = EXCLUDED.name, ship_group = EXCLUDED.ship_group, "
            "sculpture = EXCLUDED.sculpture, picture_persist = EXCLUDED.picture_persist, "
            "message_persist = EXCLUDED.message_persist, is_active = EXCLUDED.is_active, "
            "npc_discuss_persist = EXCLUDED.npc_discuss_persist, "
            "time = EXCLUDED.time, time_persist = EXCLUDED.time_persist, "
            "oalist_pic_persist = EXCLUDED.oalist_pic_persist",
            _int_val(entry, "id"),
            _int_val(entry, "group_id"),
            _int_val(entry, "ship_group"),
            _str_val(entry, "name"),
            _str_val(entry, "sculpture"),
            _str_val(entry, "picture_persist"),
            _str_val(entry, "message_persist"),
            _int_val(entry, "is_active"),
            npc_discuss_persist,
            time_val,
            time_persist,
            _str_val(entry, "oalist_pic_persist"),
        )


# ── Juustagram NPC Templates ───────────────────────────────────────────


@_register("JuustagramNpcTemplates")
def import_juustagram_npc_templates_sqlc(region: str):
    data = get_privatedock_data(region, "ShareCfg/activity_ins_npc_template.json")
    store = get_default_store()
    for entry in (data.values() if isinstance(data, dict) else data):
        npc_reply_persist = json.dumps(entry.get("npc_reply_persist", []), ensure_ascii=False)
        time_persist = json.dumps(entry.get("time_persist", []), ensure_ascii=False)
        store.execute(
            "INSERT INTO juustagram_npc_templates ("
            "id, ship_group, message_persist, npc_reply_persist, time_persist"
            ") VALUES ("
            "$1, $2, $3, $4, $5"
            ") ON CONFLICT (id) DO UPDATE SET "
            "ship_group = EXCLUDED.ship_group, message_persist = EXCLUDED.message_persist, "
            "npc_reply_persist = EXCLUDED.npc_reply_persist, time_persist = EXCLUDED.time_persist",
            _int_val(entry, "id"),
            _int_val(entry, "ship_group"),
            _str_val(entry, "message_persist"),
            npc_reply_persist,
            time_persist,
        )


# ── Juustagram Language ────────────────────────────────────────────────


@_register("JuustagramLanguage")
def import_juustagram_language_sqlc(region: str):
    data = get_privatedock_data(region, "ShareCfg/activity_ins_language.json")
    store = get_default_store()
    if isinstance(data, dict):
        for key, entry in data.items():
            value = entry.get("value", "") if isinstance(entry, dict) else str(entry)
            store.execute(
                "INSERT INTO juustagram_languages (key, value) "
                "VALUES ($1, $2) "
                "ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value",
                key, value,
            )


# ── Juustagram Ship Groups ─────────────────────────────────────────────


@_register("JuustagramShipGroups")
def import_juustagram_ship_groups_sqlc(region: str):
    data = get_privatedock_data(region, "ShareCfg/activity_ins_ship_group_template.json")
    store = get_default_store()
    for entry in (data.values() if isinstance(data, dict) else data):
        store.execute(
            "INSERT INTO juustagram_ship_group_templates ("
            "ship_group, name, background, sculpture, sculpture_ii, nationality, type"
            ") VALUES ("
            "$1, $2, $3, $4, $5, $6, $7"
            ") ON CONFLICT (ship_group) DO UPDATE SET "
            "name = EXCLUDED.name, background = EXCLUDED.background, "
            "sculpture = EXCLUDED.sculpture, sculpture_ii = EXCLUDED.sculpture_ii, "
            "nationality = EXCLUDED.nationality, type = EXCLUDED.type",
            _int_val(entry, "ship_group"),
            _str_val(entry, "name"),
            _str_val(entry, "background"),
            _str_val(entry, "sculpture"),
            _str_val(entry, "sculpture_ii"),
            _int_val(entry, "nationality"),
            _int_val(entry, "type"),
        )


# ── ServerCfg (activity allowlist, etc.) ──────────────────────────────


@_register("ServerCfg")
def import_server_cfg_sqlc(region: str):
    store = get_default_store()
    # 7 = Military Exercise (activity_template type 7). The client gates the
    # Exercise menu on this activity being present and active; handle_activities
    # forces an open-ended window for it. Without 7 here every reseed hides
    # Exercise again ("This event has not yet started or has already ended").
    # NOTE: 1 (BUILDSHIP_1 / Wishing Well) is deliberately ABSENT: the current
    # EN client bundle has activity_template[1].config_id = 4, but
    # ship_data_create_exchange[4] does not exist -> the build menu crashes
    # whenever any BUILDSHIP_1 activity is active. Re-add 1 only after the
    # client data gains a matching exchange entry.
    default_allowlist = [4, 2, 3, 6, 9, 7]  # Always-active visible activities
    upsert_config_entry_data("ServerCfg/activities.json", "allowlist", default_allowlist)


# ── ServerActivities (operational registry) ─────────────────────────────


def _timer_unix(point) -> int:
    if not isinstance(point, list) or len(point) != 2:
        return 0
    date, clock = point[0], point[1]
    if not (isinstance(date, list) and isinstance(clock, list)
            and len(date) == 3 and len(clock) == 3):
        return 0
    try:
        from datetime import datetime, timezone
        return int(datetime(
            int(date[0]), int(date[1]), int(date[2]),
            int(clock[0]), int(clock[1]), int(clock[2]),
            tzinfo=timezone.utc,
        ).timestamp())
    except (ValueError, TypeError):
        return 0


def plan_server_activities(entries, enabled_ids) -> list[dict]:
    """Classify ShareCfg activity templates into server_activities rows.

    Every entry becomes a row (so toggling `enabled` later is a one-line
    UPDATE); ``enabled_ids`` decides which start being served. ``time`` is
    ``"always"`` -> permanent, ``["timer", ...]`` -> start/end unix bounds.
    """
    rows = []
    seen = set()
    for e in entries:
        if not isinstance(e, dict):
            continue
        try:
            aid = int(e.get("id", 0))
        except (TypeError, ValueError):
            continue
        if not aid or aid in seen:
            continue
        seen.add(aid)
        t = e.get("time")
        is_permanent = t == "always"
        start_time, end_time = 0, 0
        if isinstance(t, list) and t and t[0] == "timer" and len(t) >= 3:
            start_time = _timer_unix(t[1])
            end_time = _timer_unix(t[2])
        rows.append({
            "activity_id": aid,
            "enabled": aid in enabled_ids,
            "is_permanent": is_permanent,
            "start_time": start_time,
            "end_time": end_time,
            "sort_order": aid,  # stable order = numeric id
            "note": e.get("title_res_tag", "") or "",
        })
    return rows


@_register("ServerActivities")
def import_server_activities_sqlc(region: str):
    store = get_default_store()
    data = get_privatedock_data(region, "ShareCfg/activity_template.json")
    entries = data if isinstance(data, list) else list(data.values())

    # Operator baseline: whatever the legacy ServerCfg allowlist already had.
    enabled_ids = set()
    try:
        from src.orm.config_entry import get_config_entry
        raw = get_config_entry("ServerCfg/activities.json", "allowlist")
        if raw is not None:
            val = raw.data if hasattr(raw, "data") else raw
            if isinstance(val, list):
                enabled_ids = {int(x) for x in val}
    except Exception as e:
        log_event("GameData", "ServerActivities",
                  f"failed to read legacy allowlist: {e}", LOG_LEVEL_ERROR)

    # Default: serve the full official permanent set (time == "always") plus
    # the legacy choices. Temporaries (timer-windowed events) are seeded
    # disabled - flip `enabled` per event once the server backs it.
    permanent_ids = {
        int(e["id"]) for e in entries
        if isinstance(e, dict) and e.get("time") == "always"
    }
    enabled_ids |= permanent_ids

    rows = plan_server_activities(entries, enabled_ids)
    for r in rows:
        store.execute(
            "INSERT INTO server_activities "
            "(activity_id, enabled, is_permanent, start_time, end_time, sort_order, note) "
            "VALUES ($1, $2, $3, $4, $5, $6, $7) "
            "ON CONFLICT (activity_id) DO UPDATE SET "
            "enabled = EXCLUDED.enabled, is_permanent = EXCLUDED.is_permanent, "
            "start_time = EXCLUDED.start_time, end_time = EXCLUDED.end_time, "
            "sort_order = EXCLUDED.sort_order, note = EXCLUDED.note, "
            "updated_at = now()",
            r["activity_id"], r["enabled"], r["is_permanent"],
            r["start_time"], r["end_time"], r["sort_order"], r["note"],
        )
    log_event("GameData", "ServerActivities",
              f"seeded {len(rows)} activities "
              f"({len(enabled_ids & permanent_ids)} permanent + "
              f"{len(enabled_ids - permanent_ids)} legacy) from activity_template.json",
              LOG_LEVEL_INFO)
