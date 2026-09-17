from src.packets.handler import register_packet_handler
from src.logger.logger import log_event, LOG_LEVEL_DEBUG
from src.answer.handlers import *
from src.answer import *
from src.answer.world import *
from src.answer.friend import (
    SearchFriend,
    FriendSearchList,
    SendFriendRequest,
    AcceptFriendRequest,
    RejectFriendRequest,
    DeleteFriend,
    AddFriendBlacklist,
    GetFriendBlacklist,
    RelieveFriendBlacklist,
)
from src.answer.guild import (
    guild_apply,
    guild_dissolve,
    guild_fire,
    guild_impeach,
    guild_quit,
    guild_search,
    guild_send_message,
    guild_get_user_info_command,
    get_guild_shop,
    guild_shop_purchase,
    accept_guild_join_request,
    guild_list_refresh,
    modify_guild_info,
    guild_active_event_command_response,
    get_my_assault_fleet_command_response,
    guild_get_activation_event_command_response,
    guild_get_assault_fleet_command_response,
    guild_get_boss_info_command_response,
    guild_get_boss_rank_command_response,
    guild_get_report_rank_command_response,
    guild_get_reports_command_response,
    guild_join_event_command_response,
    guild_join_mission_command_response,
    guild_refresh_assault_recommendations_command_response,
    guild_refresh_mission_command_response,
    guild_update_assault_fleet_command_response,
    guild_update_boss_mission_fleet_command_response,
    guild_update_node_anim_flag_command_response,
    mark_assault_ship_recommend_command_response,
    guild_fetch_boss_command_response,
)
from src.answer.guild.public_tech import (
    handle_public_guild_upgrade_tech,
    handle_public_guild_commit_donate,
    handle_public_guild_refresh_donate,
)
from src.answer.task_handlers import handle_submit_weekly_task_batch
from src.answer.loading_pic import handle_update_loading_pic
from src.answer.chapter_auto.handlers import (
    handle_start_chapter_auto,
    handle_end_chapter_auto,
    handle_add_chapter_auto_time,
)



def register_packets():
    from src.answer.update_packet import handle_gateway_update_check
    register_packet_handler(10800, [handle_gateway_update_check])
    register_packet_handler(10700, [handle_gateway_pack_info])
    register_packet_handler(8239, [handle_write_server_list])
    register_packet_handler(10020, [handle_auth_confirm])
    register_packet_handler(10018, [handle_server_state_check])
    register_packet_handler(10022, [handle_join_server])
    register_packet_handler(10024, [handle_create_new_player])
    register_packet_handler(10026, [handle_player_exist])
    register_packet_handler(11001, [
        handle_last_login,                   # 1  SC_11003
        handle_player_info,                  # 2  SC_11001
        handle_player_buffs,                 # 3  SC_11001
        handle_get_meta_progress,            # 4  SC_70001
        handle_last_online_info,             # 5  SC_11009
        handle_resources_info,               # 6  SC_11005
        handle_event_data,                   # 7  SC_13001
        handle_meowfficers,                  # 8  SC_17003
        handle_commander_collection,         # 9  SC_17005
        handle_ongoing_builds,               # 10 SC_12008
        handle_player_dock,                  # 11 SC_12003
        handle_commander_dock,               # 12 SC_17007
        handle_commander_fleet,              # 13 SC_17009
        handle_commander_owned_skins,        # 14 SC_12010
        handle_technology_refresh_list,      # 15 SC_63001
        handle_shipyard_data,                # 16 SC_63201
        handle_technology_nation_proxy,      # 17 SC_64001
        handle_commander_story_progress,     # 18 SC_11001
        handle_event_collection_info,        # 19 SC_13013
        handle_commander_commissions_fleet,  # 20 SC_62101
        handle_shop_data,                    # 21 SC_22101
        handle_world_base_info,              # 22 SC_33001
        handle_chapter_base_sync,            # 23 SC_11001
        handle_equiped_special_weapons,      # 24 SC_14201
        handle_equipped_weapon_skin,         # 25 SC_12037
        handle_owned_items,                  # 26 SC_11013
        handle_commander_missions,           # 27 SC_20101
        handle_weekly_missions,              # 28 SC_20103
        handle_activity_task_state_sync,     # 29 SC_20201
        handle_dorm_data,                    # 30 SC_28001
        handle_fleet_energy_recover_time,    # 31 SC_11001
        handle_game_mailbox,                 # 32 SC_11001
        handle_compensate_notification,      # 33 SC_30101
        handle_commander_friend_list,        # 34 SC_17011
        handle_activities,                   # 35 SC_11200
        handle_permanent_activities,         # 36 SC_11001
        handle_game_notices,                 # 37 SC_11001
        handle_send_player_ship_count,       # 38 SC_17101
    ])
    register_packet_handler(10100, [handle_send_heartbeat])
    register_packet_handler(10996, [handle_version_check])
    register_packet_handler(10994, [handle_cheater_mark])
    register_packet_handler(10991, [handle_game_tracking])
    register_packet_handler(10992, [handle_new_tracking])
    register_packet_handler(10993, [handle_track_command])

    register_packet_handler(16001, [handle_shop_purchase])
    register_packet_handler(16003, [handle_shop_refresh])
    register_packet_handler(23430, [handle_auction_game_init])
    register_packet_handler(40001, [handle_begin_stage])
    register_packet_handler(40003, [handle_finish_stage])
    register_packet_handler(40005, [handle_quit_battle])
    register_packet_handler(40007, [handle_daily_quick_battle])
    register_packet_handler(12002, [handle_ship_build])
    register_packet_handler(12004, [handle_retire_ship])
    register_packet_handler(12006, [handle_equip_to_ship])
    register_packet_handler(12008, [handle_build_quick_finish])
    register_packet_handler(12011, [handle_remould_ship])
    register_packet_handler(12017, [handle_mod_ship])
    register_packet_handler(12020, [handle_ship_action_validate])
    register_packet_handler(12022, [handle_change_ship_lock_state])
    register_packet_handler(12025, [handle_get_ship])
    register_packet_handler(11800, [handle_get_ship_count])
    register_packet_handler(17101, [handle_get_ship_discuss])
    register_packet_handler(12027, [handle_upgrade_star])
    register_packet_handler(12029, [handle_ship_action_list])
    register_packet_handler(12032, [handle_propose_ship])
    register_packet_handler(12034, [handle_rename_proposed_ship])
    register_packet_handler(12036, [handle_update_ship_equipment_skin])
    register_packet_handler(12038, [handle_upgrade_ship_max_level])
    register_packet_handler(12040, [handle_set_favorite_ship])
    register_packet_handler(12102, [handle_fleet_commit])
    register_packet_handler(12104, [handle_fleet_rename])
    register_packet_handler(17401, [handle_change_medal_display])
    register_packet_handler(17301, [handle_claim_trophy])
    register_packet_handler(17103, [handle_post_ship_evaluation_comment])
    register_packet_handler(17107, [handle_update_ship_like])
    register_packet_handler(17105, [handle_zan_ship_evaluation])
    register_packet_handler(16205, [handle_cryptolalia_unlock])
    register_packet_handler(12043, [handle_build_finish])
    register_packet_handler(12045, [handle_confirm_ship])
    register_packet_handler(12047, [handle_exchange_ship])
    register_packet_handler(15002, [handle_use_item])
    register_packet_handler(15004, [handle_legacy_item_operation])
    register_packet_handler(14002, [handle_upgrade_equipment_on_ship])
    register_packet_handler(14004, [handle_upgrade_equipment_in_bag])
    register_packet_handler(14006, [handle_compose_equipment])
    register_packet_handler(14008, [handle_destroy_equipments])
    register_packet_handler(15006, [handle_compose_item])
    register_packet_handler(15008, [handle_sell_item])
    register_packet_handler(15010, [handle_propose_exchange_ring])
    register_packet_handler(15012, [handle_quick_exchange_blueprint])
    register_packet_handler(11501, [handle_charge_start])
    register_packet_handler(11504, [handle_charge_confirm])
    register_packet_handler(11506, [handle_click_mingshi])
    register_packet_handler(11508, [handle_exchange_code_redeem])
    register_packet_handler(11510, [handle_charge_failure])
    register_packet_handler(11513, [handle_refund_charge_start])
    register_packet_handler(16104, [handle_get_charge_list])
    register_packet_handler(11024, [handle_get_refund_info])
    register_packet_handler(17005, [handle_claim_collection_award])

    register_packet_handler(26031, [handle_activity_boss_page_update])
    register_packet_handler(26081, [handle_get_boss_4th_info])
    register_packet_handler(26106, [handle_activity_item_list])
    register_packet_handler(11206, [handle_activity_permanent_start])
    register_packet_handler(11208, [handle_activity_permanent_finish])

    register_packet_handler(30002, [handle_send_mail_list])
    register_packet_handler(30004, [handle_get_collection_mail_list])
    register_packet_handler(30006, [handle_mail_deal_command])
    register_packet_handler(16001, [handle_shop_purchase])
    register_packet_handler(11025, [handle_survey_request])
    register_packet_handler(11027, [handle_survey_state])

    register_packet_handler(25010, [handle_fetch_commander_candidate_talents])
    register_packet_handler(25012, [handle_learn_commander_talent])
    register_packet_handler(25014, [handle_reset_commander_talents])
    register_packet_handler(25016, [handle_set_commander_lock_state])
    register_packet_handler(25018, [handle_commander_reserve_box])
    register_packet_handler(25020, [handle_rename_commander])
    register_packet_handler(25022, [handle_set_commander_prefab_fleet])
    register_packet_handler(25024, [handle_rename_commander_prefab_fleet])
    register_packet_handler(25028, [handle_commander_cattery_operation])
    register_packet_handler(25030, [handle_commander_cattery_assign])
    register_packet_handler(25032, [handle_commander_cattery_style])
    register_packet_handler(25034, [handle_commander_boxes_refresh])
    register_packet_handler(25036, [handle_commander_cattery_scene_state])

    # Event Collection (NPC collection)
    register_packet_handler(25054, [handle_event_collection_start])
    register_packet_handler(25056, [handle_event_finish])
    register_packet_handler(25058, [handle_event_flush])
    register_packet_handler(13007, [handle_event_give_up])
    # Dock Commission board dispatch/finish (protobuf, client sends these)
    register_packet_handler(13002, [handle_event_collection_info])
    # Some client builds request the commission list with CS_13013 (GetCommissionList)
    # and expect SC_13013; reuse the same handler (it emits SC_13002 which EventProxy
    # listens on). Without this registration the server replies SC_10998 and the client
    # retries in a loop when the commission board opens.
    register_packet_handler(13013, [handle_event_collection_info])
    # CS_13009 = EventFlushCommand (urgent/daily commission refresh, sent when the
    # urgent tab opens). Responds SC_13010(result, collection_list). Without a handler
    # the server replies SC_10998 and the client retries forever, hanging the tab.
    register_packet_handler(13009, [handle_event_flush])
    register_packet_handler(13003, [handle_commission_dispatch])
    register_packet_handler(13005, [handle_commission_collect])

    # Feast (dorm dining)
    register_packet_handler(26156, [handle_feast_get_data])
    register_packet_handler(26158, [handle_feast_random_ships])

    # Billboard rank list
    register_packet_handler(18201, [handle_billboard_rank_list_page])
    register_packet_handler(18203, [handle_billboard_my_rank])

    # Challenge
    register_packet_handler(24002, [handle_challenge_initial])
    register_packet_handler(24004, [handle_challenge_info])
    register_packet_handler(24009, [handle_challenge_settle])
    register_packet_handler(24011, [handle_challenge_reset])

    # City rebuild
    register_packet_handler(26060, [handle_city_rebuild_get_data])
    register_packet_handler(26062, [handle_city_rebuild_end_recruit])
    register_packet_handler(26064, [handle_city_rebuild_building_action])
    register_packet_handler(26066, [handle_city_rebuild_upgrade_buff])
    register_packet_handler(26068, [handle_city_rebuild_result_summary])
    register_packet_handler(26070, [handle_city_rebuild_choose_level])
    register_packet_handler(26072, [handle_city_rebuild_init_time])

    # Escort
    register_packet_handler(13301, [handle_escort_query])

    # Harvest class resources
    register_packet_handler(22001, [handle_resources_info])
    register_packet_handler(22009, [handle_harvest_class_resource])

    # Limit challenge
    register_packet_handler(24020, [handle_limit_challenge_info])
    register_packet_handler(24022, [handle_limit_challenge_award])

    # Love letter
    register_packet_handler(12400, [handle_love_letter_unlock])
    register_packet_handler(12402, [handle_love_letter_claim_rewards])
    register_packet_handler(12404, [handle_love_letter_realize_gift])
    register_packet_handler(12406, [handle_love_letter_get_all_data])
    register_packet_handler(12408, [handle_love_letter_level_up])
    register_packet_handler(12410, [handle_love_letter_get_content])

    # Mail storeroom & love letter mail
    register_packet_handler(30010, [handle_extend_mail_storeroom_capacity])
    register_packet_handler(30012, [handle_withdraw_mail_storeroom_resources])
    register_packet_handler(30014, [handle_get_mail_title_list])
    register_packet_handler(30016, [handle_check_love_letter_item_mail])
    register_packet_handler(30018, [handle_repair_love_letter_item_mail])

    # Meta PT award & quick tactics
    register_packet_handler(34003, [handle_claim_meta_pt_award])
    register_packet_handler(63319, [handle_meta_quick_tactics_use_books])

    # Meta character handlers
    register_packet_handler(63301, [handle_meta_character_repair])
    register_packet_handler(63303, [handle_meta_char_active_energy])
    register_packet_handler(63305, [handle_meta_character_unlock_ship])
    register_packet_handler(63307, [handle_meta_character_tactics_switch])
    register_packet_handler(63309, [handle_meta_character_tactics_level_up])
    register_packet_handler(63311, [handle_meta_character_tactics_unlock])
    register_packet_handler(63313, [handle_meta_character_tactics_request])
    register_packet_handler(63317, [handle_meta_character_tactics_info_request])

    # Legacy meta handlers (older client versions)
    register_packet_handler(70001, [handle_meta_character_repair_legacy])
    register_packet_handler(70003, [handle_meta_char_active_energy_legacy])
    register_packet_handler(70005, [handle_meta_character_unlock_ship_legacy])

    # Month shop
    register_packet_handler(16201, [handle_month_shop_purchase])

    # New server shop
    register_packet_handler(26041, [handle_get_new_server_shop])
    register_packet_handler(26043, [handle_new_server_shop_purchase])

    # Reflux
    register_packet_handler(33039, [handle_reflux_request_data])
    register_packet_handler(33041, [handle_reflux_sign])
    register_packet_handler(33045, [handle_reflux_pt_award])

    # Guild
    register_packet_handler(70059, [handle_reject_guild_join_request])
    register_packet_handler(72030, [handle_submit_guild_report])
    register_packet_handler(70081, [handle_get_guild_requests])
    register_packet_handler(60003, [handle_get_guild_requests])
    register_packet_handler(60005, [guild_apply])
    register_packet_handler(60007, [guild_send_message])
    register_packet_handler(60010, [guild_dissolve])
    register_packet_handler(60014, [guild_fire])
    register_packet_handler(60016, [guild_impeach])
    register_packet_handler(60018, [guild_quit])
    register_packet_handler(60020, [accept_guild_join_request])
    register_packet_handler(60022, [handle_reject_guild_join_request])
    register_packet_handler(60024, [guild_list_refresh])
    register_packet_handler(60026, [modify_guild_info])
    register_packet_handler(60028, [guild_search])
    register_packet_handler(60033, [get_guild_shop])
    register_packet_handler(60035, [guild_shop_purchase])
    register_packet_handler(60102, [guild_get_user_info_command])
    register_packet_handler(62002, [handle_public_guild_commit_donate])
    register_packet_handler(62015, [handle_public_guild_upgrade_tech])
    register_packet_handler(62031, [handle_public_guild_refresh_donate])
    register_packet_handler(61009, [get_my_assault_fleet_command_response])
    register_packet_handler(61011, [guild_get_assault_fleet_command_response])
    register_packet_handler(61003, [guild_update_assault_fleet_command_response])
    register_packet_handler(61013, [guild_update_boss_mission_fleet_command_response])
    register_packet_handler(61033, [mark_assault_ship_recommend_command_response])
    register_packet_handler(61035, [guild_refresh_assault_recommendations_command_response])
    register_packet_handler(61001, [guild_active_event_command_response])
    register_packet_handler(61005, [guild_get_activation_event_command_response])
    register_packet_handler(61015, [guild_fetch_boss_command_response])
    register_packet_handler(61007, [guild_join_mission_command_response])
    register_packet_handler(61017, [guild_get_reports_command_response])
    register_packet_handler(61019, [handle_submit_guild_report])
    register_packet_handler(61023, [guild_refresh_mission_command_response])
    register_packet_handler(61025, [guild_update_node_anim_flag_command_response])
    register_packet_handler(61027, [guild_get_boss_info_command_response])
    register_packet_handler(61029, [guild_get_boss_rank_command_response])
    register_packet_handler(61031, [guild_join_event_command_response])
    register_packet_handler(61037, [guild_get_report_rank_command_response])

    # Remaster
    register_packet_handler(24601, [handle_remaster_request_config])
    register_packet_handler(13501, [handle_remaster_set_active_chapter])
    register_packet_handler(13503, [handle_remaster_basic_info])
    register_packet_handler(13505, [handle_remaster_request_info])
    register_packet_handler(13107, [handle_update_custom_fleet])
    register_packet_handler(13507, [handle_remaster_claim])
    register_packet_handler(24609, [handle_remaster_request_active_chapter])
    register_packet_handler(24611, [handle_remaster_request_tickets])
    register_packet_handler(24615, [handle_remaster_request_award_receive])

    # Report ship evaluation
    register_packet_handler(17109, [handle_report_ship_evaluation_proto])

    # Submarine
    register_packet_handler(26114, [handle_submarine_chapter_info])
    register_packet_handler(26116, [handle_submarine_expedition])

    # Compensate handlers
    register_packet_handler(30101, [handle_compensate_notification])
    register_packet_handler(30102, [handle_get_compensate_list])
    register_packet_handler(30104, [handle_get_compensate_reward])

    # Exercise (arena)
    register_packet_handler(18001, [handle_exercise_enemies])
    register_packet_handler(18003, [handle_exercise_replace_rivals])
    register_packet_handler(18006, [handle_exercise_power_rank_list])
    register_packet_handler(18008, [handle_update_exercise_fleet])

    # Task handlers (submit, accept, progress, batch, quick, event)
    register_packet_handler(20005, [handle_submit_task])
    register_packet_handler(20007, [handle_accept_task])
    register_packet_handler(20009, [handle_update_task_progress])
    register_packet_handler(20011, [handle_submit_task_batch])
    register_packet_handler(20013, [handle_submit_quick_task])
    register_packet_handler(20016, [handle_task_progress_event])

    # Weekly task submit (CS_20106 -> SC_20107), batch Collect All (CS_20108 -> SC_20109),
    # and weekly reward claim (CS_20110 -> SC_20111)
    register_packet_handler(20106, [handle_submit_weekly_task])
    register_packet_handler(20108, [handle_submit_weekly_task_batch])
    register_packet_handler(20110, [handle_submit_weekly_progress])

    # Use ship exp items (CS_22011 -> SC_22012)
    register_packet_handler(22011, [handle_use_ship_exp_items])

    # World
    register_packet_handler(19490, [handle_world_item_use])
    register_packet_handler(19492, [handle_world_boss_get_info])
    register_packet_handler(19494, [handle_world_boss_get_support_info])
    register_packet_handler(19496, [handle_world_port_get_data])
    register_packet_handler(33000, [handle_world_check_info])
    register_packet_handler(33114, [handle_world_base_info])
    register_packet_handler(34501, [handle_world_boss_info])

    register_packet_handler(19506, [handle_world_core_get_data])
    register_packet_handler(19508, [handle_world_core_open_core])
    register_packet_handler(19524, [handle_world_port_update_daily_task])
    register_packet_handler(19526, [handle_world_port_refresh_daily_task])

    # Activity fleet
    register_packet_handler(11204, [handle_edit_activity_fleet])
    # Activity operation
    register_packet_handler(11202, [handle_activity_operation])
    # Activity store data
    register_packet_handler(26160, [handle_activity_store_data])
    # Activity task submit
    register_packet_handler(20205, [handle_submit_activity_task])
    # Atelier
    register_packet_handler(26051, [handle_atelier_request])
    register_packet_handler(26053, [handle_atelier_composite])
    register_packet_handler(26055, [handle_atelier_refresh_buff])
    # Backyard theme templates
    register_packet_handler(19103, [handle_get_theme_upload_credentials])
    register_packet_handler(19105, [handle_list_custom_theme_templates])
    register_packet_handler(19107, [handle_list_legacy_theme_templates])
    register_packet_handler(19109, [handle_save_custom_theme_template])
    register_packet_handler(19111, [handle_publish_custom_theme_template])
    register_packet_handler(19125, [handle_unpublish_custom_theme_template])
    register_packet_handler(19123, [handle_delete_custom_theme_template])
    register_packet_handler(19117, [handle_list_published_theme_ids])
    register_packet_handler(19115, [handle_list_collected_themes])
    register_packet_handler(19131, [handle_get_theme_preview_md5s])
    register_packet_handler(19113, [handle_get_theme_by_id])
    register_packet_handler(19121, [handle_like_theme])
    register_packet_handler(19119, [handle_collect_theme])
    register_packet_handler(19127, [handle_cancel_theme_collection])
    register_packet_handler(19129, [handle_report_theme])
    # Commander guild
    register_packet_handler(60001, [handle_commander_guild_data])
    register_packet_handler(60037, [handle_commander_guild_data])
    register_packet_handler(60100, [handle_commander_guild_chat])
    # Friend handlers (search, requests, blacklist)
    register_packet_handler(50001, [SearchFriend])
    register_packet_handler(50003, [SendFriendRequest])
    register_packet_handler(50006, [AcceptFriendRequest])
    register_packet_handler(50009, [RejectFriendRequest])
    register_packet_handler(50011, [DeleteFriend])
    register_packet_handler(50014, [FriendSearchList])
    register_packet_handler(50016, [GetFriendBlacklist])
    register_packet_handler(50107, [RelieveFriendBlacklist])
    register_packet_handler(50109, [AddFriendBlacklist])

    # Change player name
    register_packet_handler(11007, [handle_change_player_name])

    # Commander friend batch get
    register_packet_handler(50018, [handle_commander_friend_batch_get])
    # Commander meow handlers
    register_packet_handler(25002, [handle_commander_build_box_start])
    register_packet_handler(25004, [handle_commander_claim_box])
    register_packet_handler(25006, [handle_commander_fleet_equip])
    register_packet_handler(25008, [handle_commander_upgrade])
    register_packet_handler(25037, [handle_commander_quickly_finish_boxes])
    # Special weapon handlers
    register_packet_handler(14209, [handle_composite_sp_weapon])
    register_packet_handler(14207, [handle_confirm_reforge_sp_weapon])
    register_packet_handler(14201, [handle_equip_sp_weapon])
    register_packet_handler(14205, [handle_reforge_sp_weapon])
    register_packet_handler(14010, [handle_revert_equipment])
    # Equip code handlers
    register_packet_handler(17607, [handle_equip_code_impeach])
    register_packet_handler(17605, [handle_equip_code_like])
    register_packet_handler(17603, [handle_equip_code_share])
    register_packet_handler(17601, [handle_equip_code_share_list_request])
    # Equipped weapon skin
    register_packet_handler(14100, [handle_equipped_weapon_skin])

    # Commandermisc handlers
    register_packet_handler(12010, [handle_commander_dock])
    register_packet_handler(12201, [handle_commander_owned_skins])
    register_packet_handler(13201, [handle_commander_commissions_fleet])
    register_packet_handler(22300, [handle_commander_manual_info])
    register_packet_handler(22302, [handle_commander_manual_get_task])
    register_packet_handler(22304, [handle_commander_manual_get_pt_award])
    register_packet_handler(62100, [handle_commander_guild_technologies])
    # META ships points
    register_packet_handler(34001, [handle_get_meta_ships_points_response])
    # Rival info
    register_packet_handler(18104, [handle_get_rival_info])

    # Coloring
    register_packet_handler(26008, [handle_coloring_fetch])
    register_packet_handler(26002, [handle_coloring_achieve])
    register_packet_handler(26004, [handle_coloring_cell])
    register_packet_handler(26006, [handle_coloring_clear])

    # Dorm (backyard)
    register_packet_handler(19101, [handle_visit_backyard])
    register_packet_handler(19002, [handle_add_dorm_ship])
    register_packet_handler(19004, [handle_exit_dorm_ship])
    register_packet_handler(19006, [handle_buy_dorm_furniture])
    register_packet_handler(19008, [handle_save_dorm_furniture_layout])
    register_packet_handler(19009, [handle_dorm_food_data])
    register_packet_handler(19011, [handle_claim_dorm_intimacy])
    register_packet_handler(19013, [handle_claim_dorm_money])
    register_packet_handler(19015, [handle_poll_dorm_exp_events])
    register_packet_handler(19016, [handle_rename_dorm])
    register_packet_handler(19018, [handle_list_dorm_themes])
    register_packet_handler(19020, [handle_save_dorm_theme])
    register_packet_handler(19022, [handle_delete_dorm_theme])
    register_packet_handler(19024, [handle_get_backyard_visitor])
    register_packet_handler(19026, [handle_get_ship_exp_for_dorm_training])

    # Quick finish activity task
    register_packet_handler(20207, [handle_quick_finish_activity_task])

    # Shipyard blueprint packets
    register_packet_handler(63200, [handle_start_ship_blueprint_development])
    register_packet_handler(63206, [handle_stop_ship_blueprint])
    register_packet_handler(63208, [handle_resume_ship_blueprint])
    register_packet_handler(63202, [handle_finish_ship_blueprint])
    register_packet_handler(63210, [handle_use_tech_speedup_item])
    register_packet_handler(63204, [handle_mod_ship_blueprint])
    register_packet_handler(63212, [handle_pursue_ship_blueprint])
    register_packet_handler(63214, [handle_item_unlock_ship_blueprint])

    # Transform equipment
    register_packet_handler(14015, [handle_transform_equipment_in_bag])
    register_packet_handler(14013, [handle_transform_equipment_on_ship])

    # Update low priority activity task progress
    register_packet_handler(20209, [handle_update_low_priority_activity_task_progress])

    # Upgrade special weapon
    register_packet_handler(14203, [handle_upgrade_spweapon])

    # Miscops handlers
    register_packet_handler(11013, [handle_give_resources])
    register_packet_handler(11100, [handle_console_command])

    # simpleops handlers
    register_packet_handler(11011, [handle_update_secretaries])
    register_packet_handler(11016, [handle_update_guide_index])
    register_packet_handler(11017, [handle_update_story])
    register_packet_handler(11019, [handle_update_common_flag_command])
    register_packet_handler(11021, [handle_cancel_common_flag_command])
    register_packet_handler(11030, [handle_change_living_area_cover])
    register_packet_handler(11032, [handle_update_story_list])
    register_packet_handler(11034, [handle_update_loading_pic])
    register_packet_handler(11212, [handle_ur_exchange_tracking])
    register_packet_handler(11029, [handle_main_scene_tracking])
    register_packet_handler(28090, [handle_apartment_track_event])
    register_packet_handler(60012, [handle_set_guild_duty])

    # Playerops handlers
    register_packet_handler(11005, [handle_attire_apply])
    register_packet_handler(11009, [handle_change_manifesto])
    register_packet_handler(12202, [handle_change_selected_skin])

    # Juustagram handlers
    register_packet_handler(11701, [handle_juustagram_action])
    register_packet_handler(11703, [handle_juustagram_comment])
    register_packet_handler(11705, [handle_juustagram_message_range])
    register_packet_handler(11710, [handle_juustagram_data])
    register_packet_handler(11720, [handle_juustagram_read_tip])
    register_packet_handler(17509, [handle_mark_manga_read])
    register_packet_handler(17511, [handle_toggle_manga_like])

    # Instagramchat handlers (juustagram chat group operations)
    register_packet_handler(11712, [handle_instagram_chat_reply])
    register_packet_handler(11714, [handle_instagram_chat_set_skin])
    register_packet_handler(11716, [handle_instagram_chat_set_care])
    register_packet_handler(11718, [handle_instagram_chat_set_topic])
    register_packet_handler(11722, [handle_instagram_chat_activate_topic])

    # Randomflag handlers
    register_packet_handler(12204, [handle_toggle_random_flag_ship])
    register_packet_handler(12206, [handle_change_random_flag_ship_mode])
    register_packet_handler(12208, [handle_change_random_flag_ships])

    # Chapter handlers
    register_packet_handler(13012, [handle_start_chapter_auto])
    register_packet_handler(13014, [handle_end_chapter_auto])
    register_packet_handler(13016, [handle_add_chapter_auto_time])
    register_packet_handler(13101, [handle_chapter_tracking])
    register_packet_handler(13103, [handle_chapter_action])
    register_packet_handler(13106, [handle_chapter_battle_result])
    register_packet_handler(13109, [handle_get_chapter_drop_ship_list])
    register_packet_handler(13111, [handle_remove_elite_target_ship])

    # Minigame handlers
    register_packet_handler(26101, [handle_mini_game_hub_data])
    register_packet_handler(26103, [handle_mini_game_operation])
    register_packet_handler(26105, [handle_mini_game_operation_batch])
    register_packet_handler(26110, [handle_mini_game_time_submit])
    register_packet_handler(26111, [handle_mini_game_friend_rank])
    register_packet_handler(26150, [handle_mini_game_shop])
    register_packet_handler(26152, [handle_mini_game_shop_buy])
    register_packet_handler(26154, [handle_mini_game_shop_refresh])

    # Game Room handlers
    register_packet_handler(26122, [handle_game_room_weekly_coin_claim])
    register_packet_handler(26124, [handle_game_room_exchange_coin])
    register_packet_handler(26126, [handle_game_room_success_settlement])
    register_packet_handler(26128, [handle_game_room_first_enter_coin_claim])

    # Secondary password handlers
    register_packet_handler(11603, [handle_fetch_secondary_password])
    register_packet_handler(11605, [handle_set_secondary_password])
    register_packet_handler(11607, [handle_set_secondary_password_settings])
    register_packet_handler(11609, [handle_confirm_secondary_password])

    # Appreciate handlers (gallery & music appreciation)
    register_packet_handler(17501, [handle_appreciate_gallery_unlock])
    register_packet_handler(17503, [handle_appreciate_music_unlock])
    register_packet_handler(17505, [handle_appreciate_gallery_like_toggle])
    register_packet_handler(17507, [handle_appreciate_music_like_toggle])
    register_packet_handler(17513, [handle_appreciate_music_player_settings])

    # Tactics handlers (naval academy skill learning)
    register_packet_handler(22201, [handle_start_learn_tactics])
    register_packet_handler(22014, [handle_quick_finish_learn_tactics])
    register_packet_handler(22203, [handle_cancel_learn_tactics])

    # Legacy educate handlers (CS_270xx -> SC_270xx)
    from src.answer.educate.handlers import (
        EducateRequest, EducateExecutePlans, EducateMapSiteOperate,
        EducateUpgradeFavor, EducateTriggerEnd, EducateGetEndings,
        EducateGetPlans, EducateGetEvents, EducateTriggerEvent,
        EducateSetTarget, EducateSubmitTask, EducateTriggerSpecEvent,
        EducateReset, EducateSetCall, EducateShopping,
        EducateGetTargetAward, EducateAddTaskProgress, EducateAddExtraAttr,
        ChangeEducateCharacter, EducateRequestShopData, EducateRequestOption,
        EducateRefresh,
    )
    register_packet_handler(27000, [EducateRequest])
    register_packet_handler(27002, [EducateExecutePlans])
    register_packet_handler(27004, [EducateMapSiteOperate])
    register_packet_handler(27006, [EducateUpgradeFavor])
    register_packet_handler(27008, [EducateTriggerEnd])
    register_packet_handler(27010, [EducateGetEndings])
    register_packet_handler(27012, [EducateGetPlans])
    register_packet_handler(27014, [EducateGetEvents])
    register_packet_handler(27016, [EducateTriggerEvent])
    register_packet_handler(27019, [EducateSetTarget])
    register_packet_handler(27023, [EducateSubmitTask])
    register_packet_handler(27027, [EducateTriggerSpecEvent])
    register_packet_handler(27029, [EducateReset])
    register_packet_handler(27031, [EducateSetCall])
    register_packet_handler(27033, [EducateShopping])
    register_packet_handler(27035, [EducateGetTargetAward])
    register_packet_handler(27037, [EducateAddTaskProgress])
    register_packet_handler(27039, [EducateAddExtraAttr])
    register_packet_handler(27041, [ChangeEducateCharacter])
    register_packet_handler(27043, [EducateRequestShopData])
    register_packet_handler(27045, [EducateRequestOption])
    register_packet_handler(27047, [EducateRefresh])

    # Neweducate handlers (child2 educate system)
    register_packet_handler(29001, [NewEducateRequest])
    register_packet_handler(29003, [NewEducateGetEndings])
    register_packet_handler(29005, [NewEducateSelectEnding])
    register_packet_handler(29007, [NewEducateReset])
    register_packet_handler(29009, [NewEducateSetCall])
    register_packet_handler(29011, [NewEducateMainEvent])
    register_packet_handler(29013, [NewEducateAssess])
    register_packet_handler(29015, [NewEducateGetTopics])
    register_packet_handler(29017, [NewEducateSelectTopic])
    register_packet_handler(29019, [NewEducateGetTalents])
    register_packet_handler(29021, [NewEducateRefreshTalent])
    register_packet_handler(29023, [NewEducateSelectTalent])
    register_packet_handler(29025, [NewEducateChangePhase])
    register_packet_handler(29027, [NewEducateUpgradeFavor])
    register_packet_handler(29030, [NewEducateTriggerNode])
    register_packet_handler(29032, [NewEducateClearNodeChain])
    register_packet_handler(29040, [NewEducateSchedule])
    register_packet_handler(29042, [NewEducateNextPlan])
    register_packet_handler(29044, [NewEducateUpgradePlan])
    register_packet_handler(29046, [NewEducateScheduleSkip])
    register_packet_handler(29048, [NewEducateGetExtraDrop])
    register_packet_handler(29060, [NewEducateGetMap])
    register_packet_handler(29062, [NewEducateMapNormal])
    register_packet_handler(29064, [NewEducateMapEvent])
    register_packet_handler(29066, [NewEducateShopping])
    register_packet_handler(29068, [NewEducateMapShip])
    register_packet_handler(29070, [NewEducateUpgradeNormalSite])
    register_packet_handler(29090, [NewEducateSelectMind])
    register_packet_handler(29092, [NewEducateRefresh])

    # Medal shop handlers (16106-16109)
    register_packet_handler(16106, [GetMedalShop])
    register_packet_handler(16108, [MedalShopPurchase])

    # Fleet tech handlers (63999-64010)
    register_packet_handler(64001, [handle_start_camp_tech])
    register_packet_handler(64003, [handle_finish_camp_technology])
    register_packet_handler(64005, [handle_claim_fleet_tech_camp_award])
    register_packet_handler(64007, [handle_claim_technology_camp_awards_one_step])
    register_packet_handler(64009, [handle_set_fleet_tech_attr_addition])

    # Chat handlers (11401 room change, 50102 receive message)
    register_packet_handler(11401, [handle_chat_room_change])
    register_packet_handler(50102, [handle_receive_chat_message])

    # Mailbasic handlers (30008 delete archived mail)
    register_packet_handler(30008, [handle_delete_archived_mail])

    # Phantom quest handlers (12210 finish, 12212 get progress)
    register_packet_handler(12210, [handle_finish_phantom_quest])
    register_packet_handler(12212, [handle_get_phantom_quest_progress])

    # Profile handlers
    register_packet_handler(25026, [handle_get_commander_home])
    register_packet_handler(26021, [handle_get_player_summary_info])

    # Technology research handlers (63000-63016)
    register_packet_handler(63000, [handle_technology_refresh_list])
    register_packet_handler(63001, [handle_start_technology_research])
    register_packet_handler(63003, [handle_finish_technology_research])
    register_packet_handler(63005, [handle_stop_technology_research])
    register_packet_handler(63007, [handle_refresh_technology_projects])
    register_packet_handler(63009, [handle_change_refresh_technology_tendency])
    register_packet_handler(63011, [handle_select_technology_catchup_target])
    register_packet_handler(63013, [handle_join_technology_queue])
    register_packet_handler(63015, [handle_finish_queue_technology])

    # Support ship handlers
    register_packet_handler(12301, [handle_request_player_assist_ship])
    register_packet_handler(16100, [handle_support_ship_requisition])

    # Vote handlers
    register_packet_handler(17201, [handle_fetch_vote_ticket_info])
    register_packet_handler(17203, [handle_fetch_vote_info])

    # Arena shop handlers
    register_packet_handler(18100, [handle_get_arena_shop])
    register_packet_handler(18102, [handle_refresh_arena_shop])

    # Emoji info request
    register_packet_handler(11601, [handle_emoji_info_request])

    # Month shop flag
    register_packet_handler(16203, [handle_month_shop_flag])

    # Server interconnection (10802 request -> 10803 response)
    register_packet_handler(10802, [handle_build_server_interconnection_response])

    # Shop street
    register_packet_handler(22101, [handle_get_shop_street])

    # Social misc: friend DM, player report, theme template player info
    register_packet_handler(50105, [handle_send_friend_message])
    register_packet_handler(50111, [handle_report_player])
    register_packet_handler(50113, [handle_get_theme_template_player_info])

    # User auth: register account (gateway packet)
    register_packet_handler(10001, [handle_register_account])

    # Resource check (CS_15300) - no response needed
    register_packet_handler(15300, [lambda _b, _c: (0, 0, None)])

    # CS_12299 - no response needed
    register_packet_handler(12299, [lambda _b, _c: (0, 0, None)])

    log_event("Packets", "Register", f"packet handlers registered", LOG_LEVEL_DEBUG)
