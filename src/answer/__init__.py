from .helpers import (
    bool_to_uint32,
    tb_info_placeholder,
    tb_permanent_placeholder,
    empty_tb_display,
    merge_drop_list,
)

from .server_ticket import format_server_ticket, parse_server_ticket

from .auth_confirm import handle_auth_confirm
from .auth_confirm_local import handle_local_login
from .join_server import handle_join_server
from .player_info import handle_player_info
from .servers import (
    build_server_info,
    update_server_list,
    handle_cs8239_http,
    SERVER_STATE_ONLINE,
    SERVER_STATE_OFFLINE,
    SERVER_STATE_FULL,
    SERVER_STATE_BUSY,
)

from .fleet_rename import handle_fleet_rename
from .fleet_commit import handle_fleet_commit
from .change_medal_display import handle_change_medal_display
from .set_favorite_ship import handle_set_favorite_ship
from .trophy_claim import handle_claim_trophy
from .evaluate_ship import handle_post_ship_evaluation_comment

from .retire_ship import handle_retire_ship
from .update_ship_like import handle_update_ship_like
from .zan_ship_evaluation import handle_zan_ship_evaluation
from .exchange_ship import handle_exchange_ship
from .propose_exchange_ring import handle_propose_exchange_ring
from .cryptolalia_unlock import handle_cryptolalia_unlock
from .quick_exchange_blueprint import handle_quick_exchange_blueprint

from .mod_ship import handle_mod_ship
from .remould_ship import handle_remould_ship
from .upgrade_star import handle_upgrade_star
from .upgrade_ship_max_level import handle_upgrade_ship_max_level

from .update_ship_equipment_skin import handle_update_ship_equipment_skin
from .collection_award_claim import handle_claim_collection_award

from .activities import handle_activities
from .activity_boss_handlers import handle_activity_boss_page_update, handle_get_boss_4th_info
from .activity_item_list import handle_activity_item_list
from .activity_permanent_start import handle_activity_permanent_start
from .activity_permanent_finish import handle_activity_permanent_finish
from .activity_templates import ActivityTemplate, load_activity_template
from .activity_builders import (
    build_activity_info,
    activity_stop_time,
    _base_activity_info,
    _build_town_activity_info,
    _build_boss_battle_mark_2_activity_info,
    _validate_puzzle_activity,
    _validate_new_server_task_activity,
    _validate_activity_time,
    _validate_task_activity,
    _parse_activity_task_ids,
    _config_entry_exists,
)

from .equip_to_ship import handle_equip_to_ship
from .upgrade_equipment_on_ship import handle_upgrade_equipment_on_ship
from .upgrade_equipment_in_bag import handle_upgrade_equipment_in_bag
from .equiped_special_weapons import list_special_weapons, handle_equiped_special_weapons

from .commander_collection import handle_commander_collection
from .commander_fleet import handle_commander_fleet
from .commander_story_progress import handle_commander_story_progress
from .commander_ids_helpers import normalize_commander_ids

from .mailbox import handle_game_mailbox
from .send_mail_list import handle_send_mail_list
from .get_collection_mail_list import handle_get_collection_mail_list
from .handle_mail_deal_command import handle_mail_deal_command
from .task_handlers import handle_commander_missions, handle_weekly_missions, handle_submit_task, handle_accept_task, handle_update_task_progress, handle_submit_task_batch, handle_submit_quick_task, handle_task_progress_event, emit_task_progress, schedule_emit, handle_submit_weekly_task, handle_submit_weekly_progress
from .survey_request import handle_survey_request
from .survey_state import handle_survey_state
from .shopping_command_answer import handle_shop_purchase

from .activity_fleet import handle_edit_activity_fleet
from .activity_operation import handle_activity_operation
from .activity_store_data import handle_activity_store_data
from .activity_task_helpers import (
    load_activity_task_template,
    load_activity_task_id_set,
    build_award_drop_map,
    activity_drop_map_to_sorted_list,
)
from .activity_task_submit import handle_submit_activity_task
from .atelier_shared import (
    parse_atelier_recipe_config,
    parse_atelier_recipe_allowed_items,
    parse_atelier_item_config,
    atelier_item_buff_tier_count,
    ensure_atelier_activity,
    sorted_atelier_kvdata,
    sorted_atelier_slots,
)
from .atelier_request import handle_atelier_request
from .atelier_composite import handle_atelier_composite
from .atelier_refresh_buff import handle_atelier_refresh_buff
from .backyard_validation import (
    dorm_static_map_size,
    load_furniture_template,
    resolve_furniture_template_id,
    validate_furniture_put_list,
)
from .backyard_theme_template_packets import (
    handle_get_theme_upload_credentials,
    handle_list_custom_theme_templates,
    handle_list_legacy_theme_templates,
    handle_save_custom_theme_template,
    handle_publish_custom_theme_template,
    handle_unpublish_custom_theme_template,
    handle_delete_custom_theme_template,
    handle_list_published_theme_ids,
    handle_list_collected_themes,
    handle_get_theme_preview_md5s,
    handle_get_theme_by_id,
    handle_like_theme,
    handle_collect_theme,
    handle_cancel_theme_collection,
    handle_report_theme,
)
from .commander_guild_data import handle_commander_guild_data
from .commander_guild_chat import handle_commander_guild_chat
from .commander_friend_batch_get import handle_commander_friend_batch_get
from .commander_meow_handlers import (
    handle_commander_build_box_start,
    handle_commander_claim_box,
    handle_commander_fleet_equip,
    handle_commander_upgrade,
    handle_commander_quickly_finish_boxes,
)
from .composite_spweapon import handle_composite_sp_weapon
from .confirm_reforge_spweapon import handle_confirm_reforge_sp_weapon
from .equip_spweapon import handle_equip_sp_weapon
from .reforge_special_weapon import handle_reforge_sp_weapon
from .revert_equipment import handle_revert_equipment
from .equip_code_impeach import handle_equip_code_impeach
from .equip_code_like import handle_equip_code_like
from .equip_code_share import handle_equip_code_share
from .equip_code_share_list_request import handle_equip_code_share_list_request
from .equipped_weapon_skin import handle_equipped_weapon_skin
from .get_meta_ships_points_response import handle_get_meta_ships_points_response
from .get_rival_info import handle_get_rival_info

from .event_collection_info import handle_event_collection_info
from .event_collection_start import handle_event_collection_start, handle_commission_dispatch
from .event_finish import handle_event_finish, handle_commission_collect
from .event_flush import handle_event_flush
from .event_give_up import handle_event_give_up
from .feast_helpers import (
    is_feast_activity_active,
    flatten_uint_set_from_json,
    feast_party_roles_to_proto,
    feast_special_roles_to_proto,
    parse_activity_timer_window,
    parse_activity_timer_point,
    FEAST_FAILURE_RESULT,
)
from .feast_get_data import handle_feast_get_data
from .feast_random_ships import handle_feast_random_ships
from .billboard_rank_list import handle_billboard_rank_list_page, handle_billboard_my_rank
from .challenge_info import handle_challenge_info
from .challenge_initial import handle_challenge_initial
from .challenge_reset import handle_challenge_reset
from .challenge_settle import handle_challenge_settle
from .city_rebuild_handlers import (
    handle_city_rebuild_get_data,
    handle_city_rebuild_end_recruit,
    handle_city_rebuild_building_action,
    handle_city_rebuild_upgrade_buff,
    handle_city_rebuild_result_summary,
    handle_city_rebuild_choose_level,
    handle_city_rebuild_init_time,
)
from .escort_query import handle_escort_query
from .harvest_class_resources import handle_harvest_class_resource
from .lesson_resource_packet_helpers import (
    load_class_resource_item_id,
    load_item_statistics_config,
    parse_usage_arg_exp_value,
    load_ship_exp_book_set,
)
from .limit_challenge_award import handle_limit_challenge_award
from .limit_challenge_info import handle_limit_challenge_info
from .love_letter_handlers import (
    handle_love_letter_get_all_data,
    handle_love_letter_unlock,
    handle_love_letter_claim_rewards,
    handle_love_letter_realize_gift,
    handle_love_letter_level_up,
    handle_love_letter_get_content,
)
from .mail_storeroom_and_love_letter_handlers import (
    handle_extend_mail_storeroom_capacity,
    handle_withdraw_mail_storeroom_resources,
    handle_get_mail_title_list,
    handle_check_love_letter_item_mail,
    handle_repair_love_letter_item_mail,
)
from .meta_pt_award_claim import handle_claim_meta_pt_award
from .meta_quick_tactics_use_books import handle_meta_quick_tactics_use_books
from .month_shop_purchase import handle_month_shop_purchase
from .new_server_shop_get import handle_get_new_server_shop
from .new_server_shop_purchase import handle_new_server_shop_purchase
from .new_server_shop_shared import unmarshal_new_server_shop_data, validate_new_server_shop_request
from .permanent_activity_helpers import is_permanent_activity_open, load_permanent_activity_config
from .reflux_helpers import get_pt_item_id_from_activity, get_chapter_config_id_from_activity, load_reflux_activity_config
from .reflux_pt_award import handle_reflux_pt_award
from .reflux_request_data import handle_reflux_request_data
from .reflux_sign import handle_reflux_sign
from .reject_guild_join_request import handle_reject_guild_join_request
from .submit_guild_report_command_response import handle_submit_guild_report
from .get_guild_requests_command_response import handle_get_guild_requests
from .remaster_active_chapter import handle_remaster_request_active_chapter
from .remaster_set_active_chapter import handle_remaster_set_active_chapter
from .remaster_award_receive import handle_remaster_request_award_receive
from .remaster_config import handle_remaster_request_config
from .remaster_info import handle_remaster_request_info
from .remaster_basic_info import handle_remaster_basic_info
from .remaster_claim import handle_remaster_claim
from .chapter import handle_update_custom_fleet
from .remaster_tickets import handle_remaster_request_tickets
from .report_ship_evaluation_proto import handle_report_ship_evaluation_proto
from .server_status_cache import build_server_status_config, parse_server_status_payload
from .submarine_chapter_info import handle_submarine_chapter_info
from .submarine_expedition import handle_submarine_expedition
from .use_ship_exp_items import handle_use_ship_exp_items
from .world_boss_handlers import handle_world_boss_get_info, handle_world_boss_get_support_info
from .world_core_handlers import handle_world_core_get_data, handle_world_core_open_core
from .world_item_use import handle_world_item_use
from .world_port_and_daily_task_handlers import (
    handle_world_port_get_data,
    handle_world_port_update_daily_task,
    handle_world_port_refresh_daily_task,
)

from .coloring_fetch import handle_coloring_fetch
from .coloring_achieve import handle_coloring_achieve
from .coloring_cell import handle_coloring_cell
from .coloring_clear import handle_coloring_clear
from .compose_equipment import handle_compose_equipment
from .dorm_data import handle_dorm_data, handle_visit_backyard
from .dorm_packets import (
    handle_add_dorm_ship,
    handle_exit_dorm_ship,
    handle_buy_dorm_furniture,
    handle_save_dorm_furniture_layout,
    handle_claim_dorm_intimacy,
    handle_claim_dorm_money,
    handle_poll_dorm_exp_events,
    handle_rename_dorm,
    handle_list_dorm_themes,
    handle_save_dorm_theme,
    handle_delete_dorm_theme,
    handle_get_backyard_visitor,
    handle_get_ship_exp_for_dorm_training,

)
from .exchange_code_redeem import handle_exchange_code_redeem
from .quick_finish_activity_task import handle_quick_finish_activity_task
from .shipyard_blueprint_packets import (
    handle_start_ship_blueprint_development,
    handle_stop_ship_blueprint,
    handle_resume_ship_blueprint,
    handle_finish_ship_blueprint,
    handle_use_tech_speedup_item,
    handle_mod_ship_blueprint,
    handle_pursue_ship_blueprint,
    handle_item_unlock_ship_blueprint,
)
from .special_weapon_sync import handle_special_weapon_sync
from .transform_equipment_in_bag import handle_transform_equipment_in_bag
from .transform_equipment_on_ship import handle_transform_equipment_on_ship
from .update_low_priority_activity_task_progress import handle_update_low_priority_activity_task_progress
from .upgrade_spweapon import handle_upgrade_spweapon

# CS_11001 sub-handler imports (fix: use real implementations, not stubs from handlers.py)
from .playerops import handle_last_login, handle_resources_info, handle_last_online_info
from .miscops import handle_player_buffs, handle_owned_items
from .get_meta_progress import handle_get_meta_progress
from .event_data import handle_event_data
from .meowfficers import handle_meowfficers
from .player_dock import handle_player_dock
from .shipyard_data import handle_shipyard_data
from .shop_data import handle_shop_data
from .commander_friend_list import handle_commander_friend_list
from .activity_task_sync import handle_activity_task_state_sync
from .compensate import handle_compensate_notification

from .technology import handle_technology_refresh_list
from .fleettech import handle_technology_nation_proxy
from .world import handle_world_base_info
from .chapter import handle_chapter_base_sync
from .permanentactivity import handle_permanent_activities
from .auctiongame import handle_auction_game_init
from .shipinfo import handle_send_player_ship_count
from .shipbuild import handle_ongoing_builds
from .fleetmisc import handle_fleet_energy_recover_time
from .gamemisc import handle_game_notices
from .commandermisc import handle_commander_owned_skins, handle_commander_dock, handle_commander_commissions_fleet
