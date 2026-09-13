from .activities import handle_activities
from .activity_permanent_start import handle_activity_permanent_start
from .activity_permanent_finish import handle_activity_permanent_finish
from .activity_item_list import handle_activity_item_list
from .activity_boss_handlers import handle_activity_boss_page_update, handle_get_boss_4th_info

# Ported handler implementations override the stubs above
from .auth_confirm import handle_auth_confirm
from .join_server import handle_join_server
from .player_info import handle_player_info
from .battle_session import (
    handle_begin_stage,
    handle_finish_stage,
    handle_quit_battle,
    handle_daily_quick_battle,
)
from .shop_data import handle_shop_data
from .fleet_rename import handle_fleet_rename
from .fleet_commit import handle_fleet_commit
from .change_player_name import handle_change_player_name
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
from .use_item import handle_use_item
from .mod_ship import handle_mod_ship
from .remould_ship import handle_remould_ship
from .upgrade_star import handle_upgrade_star
from .upgrade_ship_max_level import handle_upgrade_ship_max_level
from .update_ship_equipment_skin import handle_update_ship_equipment_skin
from .collection_award_claim import handle_claim_collection_award
from .compose_item import handle_compose_item
from .destroy_equipments import handle_destroy_equipments
from .equip_to_ship import handle_equip_to_ship
from .upgrade_equipment_on_ship import handle_upgrade_equipment_on_ship
from .upgrade_equipment_in_bag import handle_upgrade_equipment_in_bag
from .commander_collection import handle_commander_collection
from .commander_fleet import handle_commander_fleet
from .commander_story_progress import handle_commander_story_progress
from .commander_packet_handlers import (
    handle_fetch_commander_candidate_talents,
    handle_learn_commander_talent,
    handle_reset_commander_talents,
    handle_set_commander_lock_state,
    handle_rename_commander,
    handle_set_commander_prefab_fleet,
    handle_rename_commander_prefab_fleet,
)
from .commander_reserve_box import handle_commander_reserve_box
from .commander_cattery_handlers import (
    handle_commander_cattery_operation,
    handle_commander_cattery_assign,
    handle_commander_cattery_style,
    handle_commander_boxes_refresh,
    handle_commander_cattery_scene_state,
)
from .mailbox import handle_game_mailbox
from .send_mail_list import handle_send_mail_list
from .get_collection_mail_list import handle_get_collection_mail_list
from .handle_mail_deal_command import handle_mail_deal_command
from .task_handlers import handle_commander_missions, handle_weekly_missions, handle_submit_task, handle_accept_task, handle_update_task_progress, handle_submit_task_batch, handle_submit_quick_task, handle_task_progress_event, emit_task_progress
from .survey_request import handle_survey_request
from .survey_state import handle_survey_state
from .shopping_command_answer import handle_shop_purchase
from .shop_refresh import handle_shop_refresh
from .event_collection_info import handle_event_collection_info
from .event_collection_start import handle_event_collection_start
from .event_finish import handle_event_finish
from .event_flush import handle_event_flush
from .event_give_up import handle_event_give_up
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
from .reflux_pt_award import handle_reflux_pt_award
from .reflux_request_data import handle_reflux_request_data
from .reflux_sign import handle_reflux_sign
from .reject_guild_join_request import handle_reject_guild_join_request
from .submit_guild_report_command_response import handle_submit_guild_report
from .get_guild_requests_command_response import handle_get_guild_requests
from .remaster_active_chapter import handle_remaster_request_active_chapter
from .remaster_award_receive import handle_remaster_request_award_receive
from .remaster_config import handle_remaster_request_config
from .remaster_info import handle_remaster_request_info
from .remaster_basic_info import handle_remaster_basic_info
from .remaster_set_active_chapter import handle_remaster_set_active_chapter
from .remaster_claim import handle_remaster_claim
from .remaster_chapter_info import handle_remaster_chapter_info
from .remaster_tickets import handle_remaster_request_tickets
from .report_ship_evaluation_proto import handle_report_ship_evaluation_proto
from .submarine_chapter_info import handle_submarine_chapter_info
from .submarine_expedition import handle_submarine_expedition
from .use_ship_exp_items import handle_use_ship_exp_items
from .world_boss_handlers import handle_world_boss_get_info, handle_world_boss_get_support_info
from .world_core_handlers import handle_world_core_get_data, handle_world_core_open_core
from .world.handlers import (
    handle_world_check_info,
    handle_world_base_info,
    handle_world_boss_info,
)
from .world_item_use import handle_world_item_use
from .world_port_and_daily_task_handlers import (
    handle_world_port_get_data,
    handle_world_port_update_daily_task,
    handle_world_port_refresh_daily_task,
)

# New handler implementations override the stubs above
from .activity_fleet import handle_edit_activity_fleet
from .activity_operation import handle_activity_operation
from .activity_store_data import handle_activity_store_data
from .activity_task_submit import handle_submit_activity_task
from .activity_task_sync import handle_activity_task_state_sync
from .atelier_request import handle_atelier_request
from .atelier_composite import handle_atelier_composite
from .atelier_refresh_buff import handle_atelier_refresh_buff
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
from .commander_friend_list import handle_commander_friend_list
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
from .equiped_special_weapons import handle_equiped_special_weapons
from .equipped_weapon_skin import handle_equipped_weapon_skin
from .get_meta_progress import handle_get_meta_progress
from .get_meta_ships_points_response import handle_get_meta_ships_points_response
from .get_rival_info import handle_get_rival_info

# New handler implementations override the stubs above
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
    handle_dorm_food_data,
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

# Handler stubs that were not overridden - now wired to real implementations
from .update_packet import handle_update_check
from .gateway_pack_info import handle_gateway_pack_info
from .servers import handle_write_server_list
from .server_state_checker import handle_server_state_check
from .version_check import handle_version_check

from .meta.handlers import (
    handle_meta_character_repair,
    handle_meta_char_active_energy,
    handle_meta_character_unlock_ship,
    handle_meta_character_tactics_info_request,
    handle_meta_character_tactics_request,
    handle_meta_character_tactics_switch,
    handle_meta_character_tactics_level_up,
    handle_meta_character_tactics_unlock,
    handle_meta_character_repair_legacy,
    handle_meta_char_active_energy_legacy,
    handle_meta_character_unlock_ship_legacy,
)

from .simpleops.handlers import (
    handle_cancel_common_flag_command,
    handle_change_living_area_cover,
    handle_update_common_flag_command,
    handle_update_guide_index,
    handle_update_secretaries,
    handle_update_story_list,
    handle_update_story,
    handle_set_guild_duty,
    handle_legacy_item_operation,
    handle_new_tracking,
    handle_main_scene_tracking,
    handle_track_command,
    handle_ur_exchange_tracking,
    handle_apartment_track_event,
)

# Playerops handlers override the stubs above
from .playerops.handlers import (
    handle_send_heartbeat,
    handle_resources_info,
    handle_player_exist,
    handle_last_online_info,
    handle_last_login,
    handle_change_ship_lock_state,
    handle_change_selected_skin,
    handle_change_manifesto,
    handle_attire_apply,
)

# Shipbuild handlers override the stubs above
from .shipbuild.handlers import (
    handle_ship_build,
    handle_ongoing_builds,
    handle_build_quick_finish,
    handle_build_finish,
)

# Chapter handlers override the stubs above
from .chapter.handlers import (
    handle_chapter_base_sync,
    handle_chapter_tracking,
    handle_chapter_action,
    handle_chapter_battle_result,
    handle_get_chapter_drop_ship_list,
    handle_remove_elite_target_ship,
)

# Propose handlers override the stubs above
from .propose.handlers import (
    handle_propose_ship,
    handle_rename_proposed_ship,
    handle_confirm_ship,
)

# Shipinfo handlers override the stubs above
from .shipinfo.handlers import (
    handle_send_player_ship_count,
    handle_get_ship_count,
    handle_get_ship_discuss,
    handle_get_ship,
)

# Randomflag handlers override the stubs above
from .randomflag.handlers import (
    handle_toggle_random_flag_ship,
    handle_change_random_flag_ship_mode,
    handle_change_random_flag_ships,
)

# Compensate handlers override the stub above
from .compensate.handlers import (
    handle_compensate_notification,
    handle_get_compensate_list,
    handle_get_compensate_reward,
)

# Juustagram handlers override the stubs above
from .juustagram.handlers import (
    handle_juustagram_action,
    handle_juustagram_comment,
    handle_juustagram_message_range,
    handle_juustagram_data,
    handle_juustagram_read_tip,
    handle_mark_manga_read,
    handle_toggle_manga_like,
)

# Exercise handlers override the stubs above
from .exercise.handlers import (
    handle_exercise_enemies,
    handle_exercise_replace_rivals,
    handle_exercise_power_rank_list,
    handle_update_exercise_fleet,
)

# Minigame handlers override the stubs above
from .minigame.handlers import (
    handle_mini_game_hub_data,
    handle_mini_game_operation,
    handle_mini_game_operation_batch,
    handle_mini_game_time_submit,
    handle_mini_game_friend_rank,
    handle_mini_game_shop,
    handle_mini_game_shop_buy,
    handle_mini_game_shop_refresh,
)

# Miscops handlers override the stubs above
from .miscops.handlers import (
    handle_cheater_mark,
    handle_give_item,
    handle_give_resources,
    handle_click_mingshi,
    handle_owned_items,
    handle_player_buffs,
    handle_sell_item,
    handle_console_command,
)

# Commandermisc handlers override the stubs above
from .commandermisc.handlers import (
    handle_commander_owned_skins,
    handle_commander_manual_info,
    handle_commander_manual_get_task,
    handle_commander_manual_get_pt_award,
    handle_commander_guild_technologies,
    handle_commander_dock,
    handle_commander_commissions_fleet,
)

# Instagram chat handlers (juustagram chat group operations)
from .instagramchat.handlers import (
    handle_instagram_chat_activate_topic,
    handle_instagram_chat_reply,
    handle_instagram_chat_set_care,
    handle_instagram_chat_set_skin,
    handle_instagram_chat_set_topic,
)

# Gameroom handlers override the stubs above
from .gameroom.handlers import (
    handle_game_room_weekly_coin_claim,
    handle_game_room_exchange_coin,
    handle_game_room_success_settlement,
    handle_game_room_first_enter_coin_claim,
)

# Charge handlers override the stubs above
from .charge.handlers import (
    handle_charge_start,
    handle_charge_confirm,
    handle_charge_failure,
    handle_refund_charge_start,
    handle_get_charge_list,
    handle_get_refund_info,
)

# Secondary password handlers override the stubs above
from .secondarypwd.handlers import (
    handle_fetch_secondary_password,
    handle_set_secondary_password,
    handle_set_secondary_password_settings,
    handle_confirm_secondary_password,
)

# Appreciate handlers override the stubs above
from .appreciate.handlers import (
    handle_appreciate_gallery_unlock,
    handle_appreciate_gallery_like_toggle,
    handle_appreciate_music_unlock,
    handle_appreciate_music_like_toggle,
    handle_appreciate_music_player_settings,
)

# Tactics handlers override the stubs above
from .tactics.handlers import (
    handle_start_learn_tactics,
    handle_quick_finish_learn_tactics,
    handle_cancel_learn_tactics,
)

# Neweducate handlers
from .neweducate.handlers import (
    NewEducateRequest,
    NewEducateGetEndings,
    NewEducateSelectEnding,
    NewEducateReset,
    NewEducateSetCall,
    NewEducateMainEvent,
    NewEducateAssess,
    NewEducateGetTopics,
    NewEducateSelectTopic,
    NewEducateGetTalents,
    NewEducateRefreshTalent,
    NewEducateSelectTalent,
    NewEducateChangePhase,
    NewEducateUpgradeFavor,
    NewEducateTriggerNode,
    NewEducateClearNodeChain,
    NewEducateSchedule,
    NewEducateNextPlan,
    NewEducateUpgradePlan,
    NewEducateScheduleSkip,
    NewEducateGetExtraDrop,
    NewEducateGetMap,
    NewEducateMapNormal,
    NewEducateMapEvent,
    NewEducateShopping,
    NewEducateMapShip,
    NewEducateUpgradeNormalSite,
    NewEducateSelectMind,
    NewEducateRefresh,
)

# Medal handlers
from .medal.handlers import (
    GetMedalShop,
    MedalShopPurchase,
)

# Fleet tech handlers override the stub above
from .fleettech.handlers import (
    handle_technology_nation_proxy,
    handle_start_camp_tech,
    handle_finish_camp_technology,
    handle_claim_fleet_tech_camp_award,
    handle_claim_technology_camp_awards_one_step,
    handle_set_fleet_tech_attr_addition,
)

# Arena handlers override the stubs above
from .arena.handlers import (
    handle_get_arena_shop,
    handle_refresh_arena_shop,
)

# Emoji handler overrides the stub above
from .emoji.handlers import (
    handle_emoji_info_request,
)

# Fleetmisc handler overrides the stub above
from .fleetmisc.handlers import (
    handle_fleet_energy_recover_time,
)

# Monthshopflag handler overrides the stub above
from .monthshopflag.handlers import (
    handle_month_shop_flag,
)

# Onboarding handler overrides the stub above
from .onboarding.handlers import (
    handle_create_new_player,
)

# Permanentactivity handler overrides the stub above
from .permanentactivity.handlers import (
    handle_permanent_activities,
)

# Serverlink handler overrides the stub above
from .serverlink.handlers import (
    handle_build_server_interconnection_response,
)

# Shopstreet handler overrides the stub above
from .shopstreet.handlers import (
    handle_get_shop_street,
)

# Socialmisc handlers override the stubs above
from .socialmisc.handlers import (
    handle_send_friend_message,
    handle_report_player,
    handle_get_theme_template_player_info,
)

# Userauth handler overrides the stub above
from .userauth.handlers import (
    handle_register_account,
)

# Profile handlers override the stubs above
from .profile.handlers import (
    handle_get_commander_home,
    handle_get_player_summary_info,
)

# Shipaction handlers override the stubs above
from .shipaction.handlers import (
    handle_ship_action_list,
    handle_ship_action_validate,
)

# Supportship handlers override the stubs above
from .supportship.handlers import (
    handle_request_player_assist_ship,
    handle_support_ship_requisition,
)

# Technology handlers override the stubs above
from .technology.handlers import (
    handle_technology_refresh_list,
    handle_start_technology_research,
    handle_finish_technology_research,
    handle_stop_technology_research,
    handle_refresh_technology_projects,
    handle_change_refresh_technology_tendency,
    handle_select_technology_catchup_target,
    handle_join_technology_queue,
    handle_finish_queue_technology,
)

# Vote handlers override the stubs above
from .vote.handlers import (
    handle_fetch_vote_info,
    handle_fetch_vote_ticket_info,
)

# Chat handlers override the stubs above
from .chat.handlers import (
    handle_chat_room_change,
    handle_receive_chat_message,
)

# Gamemisc handlers override the stubs above
from .gamemisc.handlers import (
    handle_game_notices,
    handle_game_tracking,
)

# Mailbasic handlers override the stubs above
from .mailbasic.handlers import (
    handle_ask_mail_body,
    handle_delete_archived_mail,
)

# Phantomquest handlers override the stubs above
from .phantomquest.handlers import (
    handle_finish_phantom_quest,
    handle_get_phantom_quest_progress,
)
