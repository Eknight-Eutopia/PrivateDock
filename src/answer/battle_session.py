import asyncio
import json
import math
import os
import random
import re
from typing import Optional

from src.connection.client import Client
from src.logger.logger import log_event, LOG_LEVEL_INFO, LOG_LEVEL_ERROR
from src.protobuf import protobuf

_battle_session_key: int = 0

BATTLE_SYSTEM_SCENARIO = 1
BATTLE_SYSTEM_ROUTINE = 2
BATTLE_SYSTEM_DUEL = 3
BATTLE_SYSTEM_SUB = 11
BATTLE_SYSTEM_WORLD = 51

# Ship type ids that count as submarines (client model/const/shiptype.lua:
# SubShipType = { QianTing=8, QianMu=17, FengFanS=14 }). Called-in submarines
# take no per-battle morale penalty — except sinking (-10) and the Supply
# Line Disruption daily (normal penalty), see _compute_morale_delta.
SUBMARINE_SHIP_TYPE_IDS = (8, 14, 17)

RANK_SCORE_S = 4
# BattleScore rating thresholds (client battleconst.lua): D=0, C=1, B=2,
# A=3, S=4. "at least an A-rating" means score >= 3.
RANK_SCORE_A = 3

# Main-game Hard Mode chapters (chapter_template type 2) use chapter ids
# 10101..11404 (1-1H..14-4H). The stage id the client sends on a battle is the
# EXPEDITION id, not the chapter id: for hard-mode chapters it is the chapter
# id * 1000 (e.g. H1-1 boss = 10101000, H3-4 boss = 10304000), so derive the
# chapter id from the stage id before the range check. Emitting (182, 10101)
# on a hard-mode clear advances every "Sortie and clear X Hard Mode Stages"
# task (they all target 10101).
_HARD_MODE_CHAPTER_MIN = 10101
_HARD_MODE_CHAPTER_MAX = 11404

_DAILY_CHALLENGE_STAGE_IDS = None


def _daily_challenge_stage_ids() -> set:
    """Stage ids that count as "Daily Challenge" clears (sub_type 26). Built
    from ShareCfg/expedition_daily_template.json's expedition_and_lv_limit_list."""
    global _DAILY_CHALLENGE_STAGE_IDS
    if _DAILY_CHALLENGE_STAGE_IDS is not None:
        return _DAILY_CHALLENGE_STAGE_IDS
    ids = set()
    try:
        from src.orm.config_entry import list_config_entries_sync
        for e in list_config_entries_sync("ShareCfg/expedition_daily_template.json"):
            data = e.data if isinstance(e.data, dict) else json.loads(e.data)
            lst = data.get("expedition_and_lv_limit_list")
            if isinstance(lst, list):
                for entry in lst:
                    if isinstance(entry, list) and len(entry) >= 1:
                        try:
                            ids.add(int(entry[0]))
                        except (TypeError, ValueError):
                            pass
    except Exception:
        pass
    _DAILY_CHALLENGE_STAGE_IDS = ids
    return ids


def _is_hard_mode_stage(stage_id: int) -> bool:
    chapter_id = stage_id // 1000
    return _HARD_MODE_CHAPTER_MIN <= chapter_id <= _HARD_MODE_CHAPTER_MAX


def _is_daily_challenge_stage(stage_id: int) -> bool:
    return stage_id in _daily_challenge_stage_ids()


def _battle_enemy_kill_count(payload) -> int:
    """Number of enemy ships sunk in a battle, for "Defeat N enemies" tasks
    (sub_type 11). Prefers kill_id_list (the client's explicit killed-enemy
    ids) and falls back to enemy_info (one entry per enemy ship in the fight).
    On a victory every enemy is defeated, so either count is the kill total."""
    if payload is not None and getattr(payload, "kill_id_list", None):
        return len(payload.kill_id_list)
    if payload is not None and getattr(payload, "enemy_info", None):
        return len(payload.enemy_info)
    return 0


COMMANDER_XP_TABLE_A = [0, 0, 20, 27, 35, 42, 49, 57, 65, 72]
COMMANDER_XP_TABLE_S = [0, 0, 24, 32, 42, 51, 59, 69, 78, 87]

EXP_BONUS_AMAZON_RATE = 0.18
EXP_BONUS_YUUBARI_RATE = 0.15
EXP_BONUS_HOUSHOU_RATE = 0.15
EXP_BONUS_LANGLEY_RATE = 0.15
EXP_BONUS_ARGUS_RATE = 0.10
EXP_BONUS_NURN_RATE = 0.10


def _next_battle_session_key() -> int:
    global _battle_session_key
    _battle_session_key += 1
    return _battle_session_key


def handle_begin_stage(
    buffer: bytes,
    client: Client,
) -> tuple[int, int, Optional[Exception]]:
    payload = protobuf.CS_40001()
    payload.ParseFromString(buffer)

    key = _next_battle_session_key()
    session_data = {
        "commander_id": client.commander.commander_id,
        "system": payload.system,
        "stage_id": payload.data,
        "ship_ids": list(payload.ship_id_list),
    }

    from src.orm.battle_session import upsert_battle_session_sync
    try:
        upsert_battle_session_sync(client.commander.commander_id, key, session_data)
    except Exception as e:
        return 0, 40002, e

    # Per-battle fleet oil, part 1: the entering fleet's START cost at battle
    # entrance (client battlegatescenario.Entrance consumes the same amount
    # after SC_40002). The END cost is charged in handle_finish_stage.
    try:
        from src.answer.battle_oil import OIL_COST_SYSTEMS, charge_battle_oil_start
        if payload.system in OIL_COST_SYSTEMS:
            charge_battle_oil_start(
                client, payload.system, int(payload.data), list(payload.ship_id_list),
            )
    except Exception as e:
        log_event("Battle", "OilStartCharge",
                  f"failed: {e} system={payload.system} stage={payload.data}",
                  LOG_LEVEL_ERROR)

    response = protobuf.SC_40002(result=0, key=key)
    asyncio.create_task(client.send_message(40002, response))
    return 0, 40002, None


def handle_finish_stage(
    buffer: bytes,
    client: Client,
) -> tuple[int, int, Optional[Exception]]:
    payload = protobuf.CS_40003()
    payload.ParseFromString(buffer)
    log_event("Server", "40003", f"payload={payload}", LOG_LEVEL_INFO)

    from src.orm.battle_session import get_battle_session_sync, delete_battle_session_sync

    try:
        session = get_battle_session_sync(client.commander.commander_id)
    except Exception as e:
        return 0, 40004, e

    # High-Efficiency Combat Logistics Plan: doubled oil/morale cost and
    # doubled rewards (exp, affinity) + a second independent drop roll for
    # every battle of the sortie tracked with the plan.
    plan_active = (
        session is not None
        and _chapter_plan_active(client.commander.commander_id, session.stage_id)
    )
    if plan_active:
        log_event(
            "Battle", "PlanActive",
            f"commander={client.commander.commander_id} stage={session.stage_id}",
            LOG_LEVEL_INFO,
        )

    owned_ships_map = getattr(client.commander, "owned_ships_map", None)
    if owned_ships_map is None and hasattr(client.commander, "load"):
        try:
            client.commander.load()
        except Exception as e:
            return 0, 40004, e

    ship_ids = []
    if session is not None:
        raw = session.ship_ids
        if isinstance(raw, list):
            ship_ids = raw
        elif isinstance(raw, str):
            ship_ids = json.loads(raw)

    stats_by_ship = _build_statistics_map(payload.statistics)
    mvp = _resolve_mvp_ship(ship_ids, stats_by_ship)

    # Units that fought but were NOT part of the CS_40001 fleet list: the
    # submarine group is called into a chapter battle mid-fight as support, so
    # its ships only appear in the CS_40003 statistics. Recover them by
    # matching statistics uids against the commander's own ships (NPC allies
    # and enemies are not owned, so they stay excluded).
    _owned_all = getattr(client.commander, "owned_ships_map", None) or {}
    extra_participants = _extra_participant_ids(stats_by_ship, ship_ids, _owned_all)

    # Per-battle fleet oil, part 2: the fleet's END cost (sunk ships included)
    # plus the called-in submarines' end cost at battle exit (client
    # battlegatescenario.Exit). The START cost was charged in
    # handle_begin_stage. Skipped when there is no begin-stage session (the
    # fleet composition is then unknown).
    if session is not None:
        try:
            from src.answer.battle_oil import OIL_COST_SYSTEMS, charge_battle_oil_end
            if payload.system in OIL_COST_SYSTEMS:
                charge_battle_oil_end(
                    client, payload.system, int(payload.data),
                    ship_ids, extra_participants,
                )
        except Exception as e:
            log_event("Battle", "OilEndCharge",
                      f"failed: {e} system={payload.system} stage={payload.data}",
                      LOG_LEVEL_ERROR)

    base_expedition = _load_expedition_config(payload.data)
    apply_morale = _battle_uses_morale(payload.system)
    is_rank_s = payload.score >= RANK_SCORE_S
    # Win/lose: the battle rating is 0 (BattleScore.D) on a defeat and >= 1
    # (C or better) on a victory. boss_hp is not a reliable signal (it is 0 on
    # both win and loss in chapter battles), so the score field is authoritative.
    won = payload.score > 0
    if payload.system == BATTLE_SYSTEM_DUEL:
        # Military Exercise (PvP / Mock Battles): ship XP follows the Azur Lane
        # wiki formula  BaseExperience = floor(1.5 * sum(enemy levels)) + 171.
        # Our NPC rivals all use EXERCISE_RIVAL_LEVEL, so the sum is simply
        # level * ships-per-rival. Defeat halves the experience (wiki). Morale
        # and S-rank modifiers do NOT apply in Exercises, but the MVP (x2) and
        # flagship (x1.5) multipliers are still applied by
        # _compute_ship_exp_gain below.
        from src.answer.exercise.helpers import (
            EXERCISE_RIVAL_LEVEL, EXERCISE_SHIPS_PER_RIVAL,
        )
        enemy_total_level = EXERCISE_RIVAL_LEVEL * EXERCISE_SHIPS_PER_RIVAL
        base_ship_exp = math.floor(1.5 * enemy_total_level) + 171
        if not won:
            base_ship_exp //= 2
        is_rank_s = False
    else:
        base_ship_exp = base_expedition.get("exp", 0) if base_expedition else 0

    ship_exp_gains = {}
    ship_energy_updates = {}
    ship_intimacy_updates = {}
    ship_exp_list = []

    if (won or payload.system == BATTLE_SYSTEM_DUEL) and ship_ids:
        fleet_ships = []
        owned_ships_map = client.commander.owned_ships_map or {}
        for ship_id in ship_ids:
            if ship_id in owned_ships_map:
                fleet_ships.append(owned_ships_map[ship_id])

        for ship_id in ship_ids:
            owned = owned_ships_map.get(ship_id) if hasattr(owned_ships_map, "get") else None
            if owned is None:
                entry = protobuf.SHIP_EXP()
                entry.ship_id = ship_id
                entry.exp = 0
                entry.intimacy = 10000
                entry.energy = 0
                ship_exp_list.append(entry)
                continue

            ship_stat = stats_by_ship.get(ship_id)
            ship_exp = _compute_ship_exp_gain(
                base_ship_exp, owned, fleet_ships,

                ship_ids[0], mvp, is_rank_s, apply_morale,
            )
            # Plan buff 48 (chapter_up +100%): Commander EXP, Ship EXP,
            # Affection and Mood are doubled for the whole sortie.
            if plan_active:
                ship_exp *= 2
            ship_exp_gains[ship_id] = ship_exp

            energy_delta = _compute_morale_delta(
                owned, ship_stat, apply_morale,
                stage_id=session.stage_id if session is not None else 0,
            )
            # Plan: the per-fight morale COST doubles (wiki), so only the loss
            # is deepened; a non-negative delta stays untouched.
            if plan_active and energy_delta < 0:
                energy_delta *= 2
            new_energy = _clamp_uint32(owned["energy"] + energy_delta, 0, 150)
            ship_energy_updates[ship_id] = new_energy

            intimacy_delta = _compute_intimacy_delta(new_energy, apply_morale, ship_id == mvp)
            if plan_active:
                intimacy_delta *= 2
            new_intimacy = _clamp_uint32(owned["intimacy"] + intimacy_delta, 0, 2**32 - 1)
            ship_intimacy_updates[ship_id] = new_intimacy

            energy_loss = max(-energy_delta, 0) if energy_delta < 0 else 0
            entry = protobuf.SHIP_EXP()
            entry.ship_id = ship_id
            entry.exp = ship_exp
            entry.intimacy = 10000 + intimacy_delta
            entry.energy = energy_loss
            ship_exp_list.append(entry)

        # Mid-battle joiners (submarine support) earn ship exp like the sortied
        # fleet, but take no morale/affinity change for being called in. Their
        # entries go into SC_40004 so the client's submarine result panel shows
        # the real gain instead of +0.
        for ship_id in extra_participants:
            owned = owned_ships_map.get(ship_id)
            if owned is None:
                continue
            ship_stat = stats_by_ship.get(ship_id)
            ship_exp = _compute_ship_exp_gain(
                base_ship_exp, owned, fleet_ships,

                ship_ids[0], mvp, is_rank_s, apply_morale,
            )
            if plan_active:
                ship_exp *= 2
            ship_exp_gains[ship_id] = ship_exp
            entry = protobuf.SHIP_EXP()
            entry.ship_id = ship_id
            entry.exp = ship_exp
            entry.intimacy = 10000
            entry.energy = 0
            ship_exp_list.append(entry)

    drop_list = []
    extra_drop_list = []
    if session is not None:
        try:
            if getattr(session, "system", 0) == 1 and getattr(session, "created_at", None) is not None:
                import time as _b_time
                from src.misc.safe_ts import safe_ts
                from src.answer.chapter.sortie_tracker import record_battle_overhead
                battle_start = safe_ts(session.created_at, default=int(_b_time.time()))
                combat_dur = int(getattr(payload, "total_time", 0))
                record_battle_overhead(client.commander.commander_id, battle_start, combat_dur)
        except Exception as _e:
            log_event("Chapter/SortieTracker", "RecordBattleOverheadError", f"err={_e}", LOG_LEVEL_ERROR)

        # Include the mid-battle joiners in the writeback participant set so a
        # submarine group that actually fought consumes its ammo (and its ships'
        # HP is persisted) just like the surface fleet.
        participant_ids = ship_ids + extra_participants
        update = _update_chapter_state_after_battle(
            client.commander.commander_id, session.stage_id,
            stats_by_ship=stats_by_ship, ship_ids=participant_ids,
            won=won,
        )
        if update is not None:
            err = _update_chapter_progress_after_battle(
                client.commander.commander_id, update, payload.score,
            )
            if err is not None:
                return 0, 40004, err

            if update.get("defeated"):
                _tpl = update.get("template") or {}
                _chapter_id = update["current"].id
                _boss_defeated = update["expedition_id"] in _tpl.get("boss_expedition_id", [])
                # Boss Fleet defeat (task sub_type 21, e.g. Mini-Event Gallery
                # 6002 tasks 35027-35033 "Sortie and defeat 3 Boss Fleets" and
                # Jigsaw task 10057). Defeating the boss node's fleet counts
                # once per battle regardless of how many ships died.
                if _boss_defeated and won:
                    try:
                        from src.answer.task_handlers import schedule_emit as _se
                        _se(client, 21, int(_chapter_id), 1)
                    except Exception:
                        pass
                drops = _build_chapter_award_drops(
                    _tpl, _chapter_id, _boss_defeated, payload.score,
                    update["expedition_id"],
                )
                if drops:
                    try:
                        _apply_drop_list(client, drops)
                    except Exception as e:
                        return 0, 40004, e
                    drop_list = list(drops.values())
                    # Plan buff 8 (extra_drop): RNG drops are rolled TWICE
                    # (not doubled outright, per the wiki).
                    # The second roll is placed into SC_40004.extra_drop_info
                    # so the client marks each bonus item with riraty = true
                    # (via finishstagecommand -> battlegatescenario -> newbattleresultdisplayawardpage)
                    # and renders the "Bonus" frame badge (icon_bg/bonus) in AwardInfoLayer.
                    if plan_active:
                        extra_drops = _build_chapter_award_drops(
                            _tpl, _chapter_id, _boss_defeated, payload.score,
                            update["expedition_id"],
                        )
                        if extra_drops:
                            try:
                                _apply_drop_list(client, extra_drops)
                            except Exception as e:
                                return 0, 40004, e
                            extra_drop_list = list(extra_drops.values())

                # Official one-time stage rewards are the chapter missions (the
                # scenario "Clear X-Y" tasks, sub_type 1020, and the branch
                # "Get 3 stars" tasks, sub_type 1021). The first boss defeat of
                # a stage completes its Clear mission and lighting the last star
                # completes the 3-Star mission; the player claims them from the
                # Missions screen. Never join these into drop_info (that put
                # them in the same popup list as the node's own loot). Campaign
                # chapter ids are small; event chapters (21xxxxx) are excluded
                # (they have their own activity-task path).
                try:
                    if int(_chapter_id) < 1000000:
                        from src.answer.task_handlers import schedule_emit
                        if update.get("clear_first_complete"):
                            schedule_emit(client, 1020, _chapter_id, 1)
                        if update.get("star_first_complete"):
                            schedule_emit(client, 1021, _chapter_id, 1)
                except Exception:
                    pass

    if not drop_list and won and session is not None:
        # Daily / event (ROUTINE/SUB) stages aren't chapters, so they don't use
        # the chapter-award path above. Grant the stage expedition's award_display
        # drops (with per-stage overrides for guaranteed box mechanics).
        if payload.system in (BATTLE_SYSTEM_ROUTINE, BATTLE_SYSTEM_SUB):
            try:
                daily_drops = _build_daily_award_drops(session.stage_id)
            except Exception:
                daily_drops = {}
            if daily_drops:
                try:
                    _apply_drop_list(client, daily_drops)
                except Exception as e:
                    return 0, 40004, e
                drop_list = list(daily_drops.values())

    # The client keeps the cached dock roster from the login chain. A battle
    # only delivers drop_info (type/number) in SC_40004, which has no full
    # SHIPINFO, so a freshly granted ship never appears in the dock until the
    # next re-login. Re-push the dock (SC_12001 first 101 ships, SC_12010 the
    # rest) so the new ship shows immediately after the battle.
    #
    # Player info (SC_11003) must NOT be pushed here: the client applies battle
    # drops (resources/items) to its own resource cache and then subtracts the
    # battle's end oil in the SC_40004 exit callback. A PLAYERINFO push that
    # lands BEFORE SC_40004 sets the cache to server truth first, and the local
    # subtraction then runs on top of it — the displayed oil loses the end cost
    # a second time. This never pushes 11003 mid-session (login only); the
    # client's local prediction stays exact because the server charges the same
    # start/end formulas (src/answer/battle_oil.py).
    if drop_list:
        from src.consts.drop_types import DROP_TYPE_SHIP
        _ship_granted = any(d.get("type") == DROP_TYPE_SHIP for d in drop_list)
        if _ship_granted:
            try:
                from src.answer.player_dock import handle_player_dock
                handle_player_dock(b"", client)
            except Exception:
                pass
            try:
                from src.answer.commandermisc.handlers import handle_commander_dock
                handle_commander_dock(b"", client)
            except Exception:
                pass

    if won or payload.system == BATTLE_SYSTEM_DUEL:
        try:
            _apply_battle_ship_updates(client, ship_exp_gains, ship_energy_updates, ship_intimacy_updates)
        except Exception as e:
            return 0, 40004, e

    player_exp = 0
    if won:
        system = payload.system
        if system in (BATTLE_SYSTEM_SCENARIO, BATTLE_SYSTEM_ROUTINE, BATTLE_SYSTEM_SUB):
            player_exp = _compute_commander_exp_gain(len(ship_ids), is_rank_s)
            player_exp = _apply_commander_exp_reduction(
                player_exp, client.commander.level, base_expedition, system,
            )
            # Plan buff 48: Commander EXP doubled for the whole sortie.
            if plan_active:
                player_exp *= 2
        try:
            old_level = client.commander.level
            _apply_commander_exp_gain(client, player_exp)
            if client.commander.level != old_level:
                # Commander leveled up: sub_type 1011 tasks ("Reach Commander
                # Level N") are state-based -- the possession sync records them.
                try:
                    from src.answer.task_handlers import schedule_possession_sync
                    schedule_possession_sync(client)
                except Exception:
                    pass
        except Exception as e:
            return 0, 40004, e

    if session is not None:
        try:
            _save_limit_challenge_clear(
                client, session.stage_id,
                payload.total_time, payload.score,
            )
        except Exception:
            pass

    try:
        delete_battle_session_sync(client.commander.commander_id)
    except Exception as e:
        return 0, 40004, e

    try:
        if payload.system in (BATTLE_SYSTEM_ROUTINE, BATTLE_SYSTEM_SUB) and payload.score >= 2 and session is not None:
            from src.orm.daily_level import apply_daily_level_battle, add_daily_quick_stage
            daily_level_id = apply_daily_level_battle(client.commander.commander_id, session.stage_id)
            if daily_level_id is not None and is_rank_s:
                add_daily_quick_stage(client.commander.commander_id, session.stage_id)
    except Exception:
        pass

    # Server-authoritative task progress: a battle victory advances any task whose
    # sub_type matches a "win battle" / "sortie victory" event. (1020, stage_id)
    # covers chapter-clear tasks; (20, 0) covers generic sortie-victory tasks.
    if won:
        try:
            from src.answer.task_handlers import schedule_emit
            stage_id = session.stage_id if session is not None else 0
            schedule_emit(client, 1020, stage_id, 1)
            schedule_emit(client, 20, 0, 1)
            # (11, 0) covers "Defeat N enemies" weekly/daily tasks. Count the
            # actual enemy ships sunk in this battle, not one per battle.
            enemy_kills = _battle_enemy_kill_count(payload)
            if enemy_kills > 0:
                schedule_emit(client, 11, 0, enemy_kills)
            # (23, 0) covers "Sortie and obtain X victories with at least an
            # A-rating" — one victory per winning battle rated A or above.
            if payload.score >= RANK_SCORE_A:
                schedule_emit(client, 23, 0, 1)
            # Daily Challenge clears (sub_type 26) and Hard Mode stage clears
            # (sub_type 182, target 10101) are server-authoritative too.
            if _is_daily_challenge_stage(stage_id):
                schedule_emit(client, 26, stage_id, 1)
            if _is_hard_mode_stage(stage_id):
                schedule_emit(client, 182, 10101, 1)
        except Exception:
            pass

    # Urgent Commissions (wiki): "When finishing a Campaign battle, there is a
    # chance for one of these Commissions to appear." Only a victory rolls; the
    # spawn is pushed to the client as SC_13011 so the Urgent tab updates
    # without reopening the commission board.
    if won and session is not None:
        try:
            from src.answer.event_collection_spawn import maybe_spawn_urgent_after_battle_sync
            maybe_spawn_urgent_after_battle_sync(client, session.stage_id)
        except Exception as e:
            log_event("Commission", "UrgentSpawnError",
                      f"failed after stage {session.stage_id}: {e}", LOG_LEVEL_ERROR)

    # Dev Dock (ShipBluePrint) chain missions: exp battles advance the running
    # development's "Combat Data Collection" stages (task sub_type 1041, e.g.
    # "accumulate 1M exp with Royal Navy vanguard ships"). Uses the raw per-ship
    # gain (capped ships still count, per the wiki) and only for the systems
    # the wiki lists as supported -- Exercise (duel), dorm and commissions do
    # NOT count.
    if ship_exp_gains:
        try:
            from src.answer.shipyard_blueprint_helpers import schedule_shipyard_combat_data
            schedule_shipyard_combat_data(client, ship_exp_gains, payload.system)
        except Exception:
            pass

    # Military Exercise (PvP / Mock Battles): a duel result (system == 3)
    # updates the player's seasonal score, Merit and attempt count. Both wins
    # and losses grant something; losses grant the smaller amounts.
    if payload.system == BATTLE_SYSTEM_DUEL and client.commander is not None:
        result = {}
        try:
            from src.answer.exercise.helpers import (
                apply_exercise_result,
                EXERCISE_MERIT_RESOURCE_ID,
            )
            from src.consts.drop_types import DROP_TYPE_RESOURCE
            result = apply_exercise_result(client.commander.commander_id, won)
            merit_gain = result.get("merit_gain", 0)
            if merit_gain:
                # apply_exercise_result already granted the Merit as resource id 3
                # (DB write + in-memory owned_resources_map bump via _bump_amount_map).
                # Do NOT call client.commander.add_resource here -- it delegates to the
                # same DB-writing add_resource, which would double the grant.
                # Show it as loot in the result screen via drop_info; the client applies
                # that drop to its own resource cache, so we must NOT also re-push
                # SC_11003 (that would set the cache to the granted total and then the
                # drop would be added on top, doubling the displayed amount).
                drop_list.append({
                    "type": DROP_TYPE_RESOURCE,
                    "id": EXERCISE_MERIT_RESOURCE_ID,
                    "number": merit_gain,
                })
        except Exception:
            pass

        # The rank-up promotion reward is delivered as an in-game mail. Re-push
        # SC_30001 (unread/total) so the mailbox badge appears and the client's
        # cached mail total updates - otherwise the "All" tab never fetches it.
        try:
            if result.get("rank_reward_mailed"):
                from src.answer.mailbox import push_mail_count_sync
                push_mail_count_sync(client)
        except Exception:
            pass

        # After a duel the rivals must change (the defeated opponent should not
        # remain beatable with the same fleet). apply_exercise_result above
        # already bumped state.score, so build_exercise_rival_target_list now
        # reseeds from the new score and yields a fresh rival set. Push SC_18005
        # so the client's MilitaryExerciseProxy on(18005) stores the new rivals
        # in its seasonInfo; the next open of the Exercise menu renders them.
        # This is safe here: a duel can only be started (and thus finished) from
        # the Exercise menu, so getSeasonInfo() is non-nil and the 18005 handler
        # will not crash.
        try:
            from src.answer.exercise.helpers import build_exercise_season_push_update
            push = build_exercise_season_push_update(client.commander.commander_id)
            asyncio.create_task(client.send_message(18005, push))
        except Exception as e:
            log_event("Exercise", "SeasonPushError",
                      f"failed to push SC_18005 after duel: {e}", LOG_LEVEL_ERROR)

        # (27, 0) advances every "Win X Exercises" / "Conduct X Exercises"
        # task (sub_type 27) on a duel victory.
        if won:
            try:
                from src.answer.task_handlers import schedule_emit
                schedule_emit(client, 27, 0, 1)
            except Exception:
                pass
        # NOTE on SC_18005: we DO push SC_18005 here (see the block above) to
        # refresh the rival list after the battle. The earlier concern was that
        # pushing SC_18005 before the Exercise menu is ever opened crashes the
        # client (MilitaryExerciseProxy.on(18005) indexes getSeasonInfo(), which
        # is nil until CS_18001 -> SC_18002 -> addSeasonInfo). But a duel can
        # only be started from the Exercise menu, so getSeasonInfo() is already
        # populated by the time we finish the duel, and the push is safe. Without
        # it the client keeps the cached (pre-battle) rivals because the Exercise
        # mediator does not re-request CS_18001 on return from battle.

    response = protobuf.SC_40004(result=0, player_exp=player_exp, mvp=mvp)
    for item in drop_list:
        entry = protobuf.DROPINFO()
        entry.type, entry.id, entry.number = _wire_drop(item)
        response.drop_info.append(entry)
    for item in extra_drop_list:
        entry = protobuf.DROPINFO()
        entry.type, entry.id, entry.number = _wire_drop(item)
        response.extra_drop_info.append(entry)
    for entry in ship_exp_list:
        response.ship_exp_list.append(entry)
    asyncio.create_task(client.send_message(40004, response))
    return 0, 40004, None


def handle_quit_battle(
    _buffer: bytes,
    client: Client,
) -> tuple[int, int, Optional[Exception]]:
    from src.orm.battle_session import delete_battle_session_sync
    try:
        delete_battle_session_sync(client.commander.commander_id)
    except Exception as e:
        return 0, 40006, e
    response = protobuf.SC_40006(result=0)
    asyncio.create_task(client.send_message(40006, response))
    return 0, 40006, None


def handle_daily_quick_battle(
    buffer: bytes,
    client: Client,
) -> tuple[int, int, Optional[Exception]]:
    payload = protobuf.CS_40007()
    payload.ParseFromString(buffer)
    reward_count = int(payload.cnt)
    response = protobuf.SC_40008(result=0)

    daily_drops = {}
    try:
        if payload.system == BATTLE_SYSTEM_ROUTINE and reward_count > 0:
            from src.orm.daily_level import daily_level_for_stage, increment_daily_level_count
            daily_level_id = daily_level_for_stage(int(payload.id))
            if daily_level_id is not None:
                increment_daily_level_count(client.commander.commander_id, daily_level_id, reward_count)
            daily_drops = _build_daily_award_drops(int(payload.id))
            if daily_drops:
                _apply_drop_list(client, daily_drops)
    except Exception as e:
        return 0, 40008, e

    for _ in range(reward_count):
        reward = protobuf.QUICK_REWARD()
        for d in daily_drops.values():
            di = reward.drop_list.add()
            di.type, di.id, di.number = _wire_drop(d)
            response.reward_list.append(reward)

    # A quick (repeat) battle replays a previously-cleared stage, so it must
    # advance the same task-progress events as a normal stage finish. Without
    # this, weekly/daily tasks like "Sortie and obtain N victories" (sub_type 20)
    # and chapter-clear tasks (1020) never advance when the player uses the
    # quick-battle / repeat-stage feature instead of a full sortie.
    if payload.system == BATTLE_SYSTEM_ROUTINE and reward_count > 0:
        try:
            from src.answer.task_handlers import schedule_emit
            schedule_emit(client, 20, 0, reward_count)
            schedule_emit(client, 1020, int(payload.id), reward_count)
            if _is_daily_challenge_stage(int(payload.id)):
                schedule_emit(client, 26, int(payload.id), reward_count)
            if _is_hard_mode_stage(int(payload.id)):
                schedule_emit(client, 182, 10101, reward_count)
        except Exception:
            pass

    # Refresh the dock so any ship granted by the quick battle shows without a
    # re-login (see handle_finish_stage for rationale). SC_11003 is deliberately
    # NOT pushed: the client applies quick-battle drops and oil costs locally,
    # and a PLAYERINFO push landing before SC_40008 would be double-counted by
    # the client's own local resource bookkeeping.
    if daily_drops:
        from src.consts.drop_types import DROP_TYPE_SHIP
        _ship_granted = any(d.get("type") == DROP_TYPE_SHIP for d in daily_drops.values())
        if _ship_granted:
            try:
                from src.answer.player_dock import handle_player_dock
                handle_player_dock(b"", client)
            except Exception:
                pass
            try:
                from src.answer.commandermisc.handlers import handle_commander_dock
                handle_commander_dock(b"", client)
            except Exception:
                pass

    asyncio.create_task(client.send_message(40008, response))
    return 0, 40008, None


# --- Helper functions ---

from src.orm.config_entry import entry_data as _entry_data


def _load_expedition_config(expedition_id: int) -> Optional[dict]:
    if expedition_id == 0:
        return None
    from src.orm.config_entry import get_config_entry
    from src.db.store import NotFoundError
    try:
        entry = get_config_entry("sharecfgdata/expedition_data_template.json", str(expedition_id))
        return _entry_data(entry)
    except (NotFoundError, Exception):
        return None


def _load_ship_level_config(level: int) -> Optional[dict]:
    if level == 0:
        return None
    from src.orm.config_entry import get_config_entry
    from src.db.store import NotFoundError
    try:
        entry = get_config_entry("ShareCfg/ship_level.json", str(level))
        return _entry_data(entry)
    except (NotFoundError, Exception):
        return None


def _load_user_level_config(level: int) -> Optional[dict]:
    if level == 0:
        return None
    from src.orm.config_entry import get_config_entry
    from src.db.store import NotFoundError
    try:
        entry = get_config_entry("ShareCfg/user_level.json", str(level))
        return _entry_data(entry)
    except (NotFoundError, Exception):
        return None


def _load_virtual_item_config(item_id: int) -> Optional[dict]:
    from src.orm.config_entry import get_config_entry
    from src.db.store import NotFoundError
    try:
        entry = get_config_entry("sharecfgdata/item_virtual_data_statistics.json", str(item_id))
        return _entry_data(entry)
    except (NotFoundError, Exception):
        return None


def _build_statistics_map(stats) -> dict:
    result = {}
    for entry in stats:
        if entry is None:
            continue
        ship_id = entry.ship_id
        if ship_id == 0:
            continue
        result[ship_id] = entry
    return result


def _resolve_mvp_ship(ship_ids: list, stats: dict) -> int:
    if not ship_ids:
        return 0
    mvp = ship_ids[0]
    max_damage = 0
    for ship_id in ship_ids:
        entry = stats.get(ship_id)
        if entry is None:
            continue
        damage = entry.damage_caused
        if damage > max_damage:
            max_damage = damage
            mvp = ship_id
    return mvp


def _extra_participant_ids(stats_by_ship: dict, ship_ids: list, owned_ships_map: dict) -> list:
    """Owned ships that fought (present in the CS_40003 statistics) but were
    NOT in the CS_40001 begin-stage fleet list -- e.g. the submarine group
    called into a chapter battle as mid-fight support. Sorted for determinism;
    only player-owned uids qualify (NPC allies / enemies are never owned)."""
    if not stats_by_ship:
        return []
    session = set(ship_ids or [])
    owned = owned_ships_map or {}
    return [uid for uid in sorted(stats_by_ship) if uid not in session and uid in owned]


def _battle_uses_morale(system: int) -> bool:
    return system not in (BATTLE_SYSTEM_DUEL, BATTLE_SYSTEM_WORLD)


def _operation_buff_is_special_operation(buff_id: int) -> bool:
    """True for the High-Efficiency Combat Logistics Plan marker buff. The
    tracking handler stores the plan's benefit_buff_template "desc" entry
    (id 47, benefit_condition = the plan item id 61001) into
    CURRENTCHAPTERINFO.operation_buff; only special-operation tickets have a
    "desc" buff with a non-empty condition."""
    if buff_id == 0:
        return False
    try:
        from src.orm.config_entry import get_config_entry
        entry = _entry_data(get_config_entry("ShareCfg/benefit_buff_template.json", str(buff_id)))
    except Exception:
        return False
    if not isinstance(entry, dict):
        return False
    if entry.get("benefit_type") != "desc":
        return False
    condition = str(entry.get("benefit_condition") or "").strip()
    return condition.isdigit() and int(condition) != 0


def _chapter_plan_active(commander_id: int, expedition_id: int) -> bool:
    """True when the current battle is fought under a High-Efficiency Combat
    Logistics Plan. The plan is attached at CS_13101 tracking time (one item
    per sortie) and covers EVERY battle of that sortie, so the flag lives in
    the persisted chapter state, not in the per-battle session. A battle only
    counts when its expedition id is one of the tracked chapter's own cells
    (the same test the chapter writeback uses) — that keeps daily/event/duel
    stages fought afterwards from inheriting a stale plan."""
    if expedition_id == 0:
        return False
    try:
        from src.orm.chapter import get_chapter_state_sync
        state = get_chapter_state_sync(commander_id)
    except Exception:
        return False
    if state is None or not state.state:
        return False
    try:
        current = protobuf.CURRENTCHAPTERINFO()
        current.ParseFromString(bytes(state.state))
    except Exception:
        return False
    if not any(_operation_buff_is_special_operation(b) for b in current.operation_buff):
        return False
    return _is_chapter_battle(current, expedition_id)


def _compute_ship_exp_gain(
    base_exp: int, owned, fleet_ships: list,

    flagship_id: int, mvp: int, is_rank_s: bool, apply_morale: bool,
) -> int:
    if base_exp == 0 or owned is None:
        return 0
    if owned["level"] >= owned["max_level"] and owned["max_level"] < 100:
        return 0

    multiplier = 1.0
    if is_rank_s:
        multiplier *= 1.2
    if owned["id"] == flagship_id:
        multiplier *= 1.5
    if owned["id"] == mvp:
        multiplier *= 2.0
    if apply_morale:
        if owned["energy"] >= 120:
            multiplier *= 1.2
        elif owned["energy"] == 0:
            multiplier *= 0.5

    base_gain = int(math.floor(base_exp * multiplier + 1e-6))
    bonus_rate = _compute_exp_skill_bonus_rate(owned, fleet_ships)
    bonus_gain = int(math.floor(base_exp * bonus_rate))
    return base_gain + bonus_gain


def _is_submarine_ship(owned) -> bool:
    if owned is None:
        return False
    ship = owned.get("ship") if isinstance(owned, dict) else getattr(owned, "ship", None)
    if not ship:
        return False
    stype = ship.get("type") if isinstance(ship, dict) else getattr(ship, "type", 0)
    return int(stype or 0) in SUBMARINE_SHIP_TYPE_IDS


# Supply Line Disruption daily raid (expedition_daily_template id 501): the
# ONE stage where submarines take the normal per-battle morale penalty
# (wiki "Morale": the no-penalty exception for called-in submarines does not
# apply to the Supply Line Disruption daily challenge). Stage ids 1000-1005.
_SUPPLY_LINE_DISRUPTION_STAGE_IDS = frozenset(range(1000, 1006))


def _compute_morale_delta(owned, stats, apply_morale: bool, stage_id: int = 0) -> int:
    if owned is None:
        return 0
    if not apply_morale:
        return 0
    # Submarines take no morale penalty for being CALLED into battle, but a
    # sunk submarine still loses morale (-10), and on Supply Line Disruption
    # they take the normal penalty just like surface ships.
    if _is_submarine_ship(owned):
        if stats is not None and stats.hp_rest == 0:
            return -10
        if stage_id in _SUPPLY_LINE_DISRUPTION_STAGE_IDS:
            return -2
        return 0
    if stats is not None and stats.hp_rest == 0:
        return -10
    return -2


def _compute_intimacy_delta(energy: int, apply_morale: bool, is_mvp: bool) -> int:
    # Affinity (intimacy) is stored as an integer where 100 DB points = 1 client
    # point. Wiki: a normal battle raises affinity by ~0.0625 client points
    # (0.125 if MVP) => +6 / +12 DB points. Exercises/Operation Siren
    # (apply_morale == False) grant none. A Sad ship (energy 0) loses affinity;
    # a Neutral ship (1-30) gains none.
    if not apply_morale:
        return 0
    if energy == 0:
        return -100
    if energy <= 30:
        return 0
    return 12 if is_mvp else 6


def _compute_exp_skill_bonus_rate(target, fleet_ships: list) -> float:
    if target is None:
        return 0.0
    bonus_rate = 0.0
    if hasattr(target, "ship") and target.ship.get("type") == 1:
        bonus_rate += _exp_skill_bonus_amazon(fleet_ships)
    if hasattr(target, "ship") and target.ship.get("type") in (2, 3):
        bonus_rate += _exp_skill_bonus_yuubari(fleet_ships)
    if hasattr(target, "ship") and target.ship.get("type") in (6, 7):
        bonus_rate += _exp_skill_bonus_carrier(fleet_ships)
    if hasattr(target, "ship") and target.ship.get("type") == 6:
        bonus_rate += _exp_skill_bonus_argus(fleet_ships)
    if hasattr(target, "ship") and target.ship.get("type") in (8, 17):
        bonus_rate += _exp_skill_bonus_nurnberg(fleet_ships)
    return bonus_rate


def _exp_bonus_if_present(fleet_ships: list, english_name: str, rate: float, stackable: bool) -> float:
    if rate == 0:
        return 0.0
    count = 0
    for ship in fleet_ships:
        if ship is None:
            continue
        if hasattr(ship, "ship") and ship.ship.get("english_name") == english_name:
            count += 1
            if not stackable:
                break
    if count == 0:
        return 0.0
    return float(count) * rate if stackable else rate


def _exp_skill_bonus_amazon(fleet_ships: list) -> float:
    return _exp_bonus_if_present(fleet_ships, "HMS Amazon", EXP_BONUS_AMAZON_RATE, False)


def _exp_skill_bonus_yuubari(fleet_ships: list) -> float:
    return _exp_bonus_if_present(fleet_ships, "IJN Yūbari", EXP_BONUS_YUUBARI_RATE, False)


def _exp_skill_bonus_carrier(fleet_ships: list) -> float:
    bonus = _exp_bonus_if_present(fleet_ships, "IJN Hōshō", EXP_BONUS_HOUSHOU_RATE, False)
    bonus += _exp_bonus_if_present(fleet_ships, "USS Langley", EXP_BONUS_LANGLEY_RATE, False)
    return bonus


def _exp_skill_bonus_argus(fleet_ships: list) -> float:
    return _exp_bonus_if_present(fleet_ships, "HMS Argus", EXP_BONUS_ARGUS_RATE, True)


def _exp_skill_bonus_nurnberg(fleet_ships: list) -> float:
    return _exp_bonus_if_present(fleet_ships, "KMS Nürnberg", EXP_BONUS_NURN_RATE, False)


def _compute_commander_exp_gain(fleet_size: int, is_rank_s: bool) -> int:
    if fleet_size < 0:
        return 0
    if fleet_size > 9:
        fleet_size = 9
    return COMMANDER_XP_TABLE_S[fleet_size] if is_rank_s else COMMANDER_XP_TABLE_A[fleet_size]


def _apply_commander_exp_reduction(
    exp: int, commander_level: int, expedition: Optional[dict], system: int,
) -> int:
    if exp == 0 or expedition is None:
        return exp
    level_gap = commander_level - int(expedition.get("level", 0))
    if level_gap <= 0:
        return exp
    threshold_half = 21
    threshold_severe = 41
    if system == BATTLE_SYSTEM_WORLD:
        threshold_half = 31
        threshold_severe = 61
    if level_gap >= threshold_severe:
        return exp // 10
    if level_gap >= threshold_half:
        return exp // 2
    return exp


def _apply_commander_exp_gain(client: Client, exp: int) -> None:
    if exp == 0 or client.commander.level >= 200:
        return
    remaining = exp
    while remaining > 0 and client.commander.level < 200:
        config = _load_user_level_config(client.commander.level)
        if config is None or config.get("exp", 0) == 0:
            client.commander.exp += remaining
            client.commander.commit()
            return
        needed = int(config["exp"]) - client.commander.exp
        if needed <= 0:
            client.commander.level += 1
            client.commander.exp = 0
            continue
        if remaining < needed:
            client.commander.exp += remaining
            remaining = 0
            break
        remaining -= needed
        client.commander.level += 1
        client.commander.exp = 0
    if client.commander.level >= 200:
        client.commander.level = 200
        client.commander.exp = 0
    client.commander.commit()


def _apply_battle_ship_updates(
    client: Client,
    exp_gains: dict,
    energy_updates: dict,
    intimacy_updates: dict,
) -> None:
    if not exp_gains and not energy_updates and not intimacy_updates:
        return
    owned_ships_map = getattr(client.commander, "owned_ships_map", {}) or {}
    modified = set()
    for ship_id, gain in exp_gains.items():
        owned = owned_ships_map.get(ship_id)
        if owned is None:
            continue
        if gain > 0:
            if owned["level"] >= owned["max_level"]:
                if owned["max_level"] >= 100:
                    owned["surplus_exp"] = _add_surplus_exp(owned["surplus_exp"], gain)
                    gain = 0
            else:
                new_exp = owned["exp"] + gain
                level = owned["level"]
                while level < owned["max_level"]:
                    config = _load_ship_level_config(level)
                    if config is None:
                        break
                    ship_dict = owned.get("ship")
                    required = config.get("exp_ur", config.get("exp", 0)) if ship_dict and ship_dict.get("rarity_id") == 6 else config.get("exp", 0)
                    if required == 0 or new_exp < required:
                        break
                    new_exp -= required
                    level += 1
                owned["exp"] = new_exp
                owned["level"] = level
                if owned["level"] >= owned["max_level"] and owned["max_level"] >= 100 and owned["exp"] > 0:
                    owned["surplus_exp"] = _add_surplus_exp(owned["surplus_exp"], owned["exp"])
                    owned["exp"] = 0
        if ship_id in energy_updates:
            owned["energy"] = energy_updates[ship_id]
        if ship_id in intimacy_updates:
            owned["intimacy"] = intimacy_updates[ship_id]
        modified.add(ship_id)
    from src.orm.owned_ship import sync_update_owned_ship_fields
    import time as _time
    _now_ts = int(_time.time())
    for owned_id in modified:
        owned = owned_ships_map[owned_id]
        sync_update_owned_ship_fields(
            client.commander.commander_id, owned_id,
            exp=owned["exp"], level=owned["level"],
            energy=owned["energy"], intimacy=owned["intimacy"],
            surplus_exp=owned.get("surplus_exp", 0),
            # Anchor the morale-recovery clock to the moment energy changed, so
            # a freshly-consumed ship does not instantly "recover" from a stale
            # anchor on the next dock sync.
            state_info1=_now_ts,
        )


def _add_surplus_exp(current: int, gain: int) -> int:
    SURPLUS_CAP = 3000000
    if current >= SURPLUS_CAP:
        return current
    new_value = current + gain
    return min(new_value, SURPLUS_CAP)


def _clamp_uint32(value: int, min_val: int, max_val: int) -> int:
    if value < min_val:
        return min_val
    if value > max_val:
        return max_val
    return value


def _wire_drop(item: dict) -> tuple[int, int, int]:
    """Convert a drops-dict entry into the DROPINFO shape the client credits.

    Resource-proxy virtuals (Coins 59001, Oil 59002, ...) are internal bookkeeping
    only: original SC_40004 sends gold as {type:1, id:1} (resource), and a type-2
    entry for 59001 makes the CLIENT file the "Coins" item into its local depot --
    the inventory contamination the server DB never has. Server-side granting is
    unaffected: _apply_drop_list already routes them through the add_item guard.
    """
    d_type = item.get("type", 0)
    d_id = item.get("id", 0)
    d_count = item.get("number", 0)
    if d_type == 2:
        from src.consts.drop_types import DROP_TYPE_RESOURCE
        from src.orm.item import RESOURCE_VIRTUAL_ITEMS
        if d_id in RESOURCE_VIRTUAL_ITEMS:
            return DROP_TYPE_RESOURCE, RESOURCE_VIRTUAL_ITEMS[d_id], d_count
    return d_type, d_id, d_count


def _apply_drop_list(client: Client, drops: dict) -> None:
    if not drops:
        return
    c = client.commander
    for drop in drops.values():
        drop_type = drop.get("type", 0)
        drop_id = drop.get("id", 0)
        drop_count = drop.get("number", 0)
        if drop_type == 1:
            c.add_resource(drop_id, drop_count)
        elif drop_type == 2:
            c.add_item(drop_id, drop_count)
        elif drop_type == 4:
            for _ in range(drop_count):
                c.add_ship(drop_id)
        elif drop_type == 7:
            for _ in range(drop_count):
                c.give_skin(drop_id)
        elif drop_type in (14, 15, 31):
            from src.orm.commander_attire import grant_commander_attire_drop_sync
            grant_commander_attire_drop_sync(c.commander_id, drop_type, drop_id, drop_count)


def _build_chapter_award_drops(
    template, chapter_id: int = 0, boss_defeated: bool = False, score: int = 0,
    expedition_id: int = 0,
) -> dict:
    drops = {}
    # Per-fleet drop table: the client shows each enemy fleet its own
    # expedition_data_template[expedition].award_display before battle, so that
    # is what must roll. Falls back to the chapter-wide awards when the
    # expedition has no display config.
    entries = _fleet_award_entries(template, expedition_id)
    from src.answer.chapter import drop_rates

    # Resolve fleet size and role (Small/Medium/Large/Boss/Elite; Recon/Main/Aviation/Cargo)
    fleet_size, fleet_role = drop_rates.resolve_fleet_profile(expedition_id, boss_defeated)

    # 1. Roll gear plates independently (T1, T2, T3 tiered for mobs; 2..4 T3 for boss)
    plates = drop_rates.roll_gear_plates(fleet_size, fleet_role, chapter_id, boss_defeated)
    for p in plates:
        key = f"{p['type']}_{p['id']}"
        drops[key] = {"type": p["type"], "id": p["id"], "number": p["number"]}

    # Boss drops use the separate boss config; both configs still apply the
    # S-rank ship-chance and current-chapter tier modifiers.
    by_category: dict = {}
    coin_seen = False
    display_coin_desc = None
    for entry in entries:
        if len(entry) < 2:
            continue
        drop_type = entry[0]
        for i in range(1, len(entry)):
            drop_id = entry[i]
            # Ignore non-id elements (e.g. a "desc" third slot in award_display
            # entries) - this path only rolls per-category drop tables.
            if not isinstance(drop_id, int) or drop_id == 0:
                continue
            # Gear plates (17xxx) are already handled above by the authentic tiered roller
            if drop_rates.is_plate_item(drop_id):
                continue
            # The coin marker rolls below (every fleet grants gold); only its
            # amount descriptor ([2, 59001, 'Few'|'1'|'10~20'] - the next entry
            # slot) is captured here.
            if drop_id == 59001:
                if not coin_seen:
                    coin_seen = True
                    for extra in entry[i + 1:]:
                        if isinstance(extra, str):
                            display_coin_desc = extra
                            break
                continue
            # Core Data (virtual item 59900) is a hard-mode-only drop granted as
            # itself; its per-stage amount comes from chapter_core_data_drops.json.
            # Keep it as 59900 (do NOT resolve it into its display_icon contents).
            if drop_id == 59900:
                from src.answer.chapter import core_data_drops
                amt = core_data_drops.get_core_data_amount(chapter_id) or 1
                key = "2_59900"
                if key in drops:
                    drops[key]["number"] = drops[key].get("number", 0) + amt
                else:
                    drops[key] = {"type": 2, "id": 59900, "number": amt}
                continue
            category = drop_rates.classify_category(drop_id)
            by_category.setdefault(category, []).append((drop_type, drop_id))
    # Originally grants gold from EVERY enemy fleet even when the fleet's
    # award_display omits 59001. A word-marked coin entry rolls the word
    # amount (4-4 boss 'Numerous': originally ~ 1091/1246); an unmarked
    # one rolls the per-fleet-size coin_range from drop_rates_campaign.json
    # via the category machinery below.
    if coin_seen and display_coin_desc is not None:
        amt = _parse_award_display_desc(display_coin_desc, 2, 59001)
        if amt:
            drops["2_59001"] = {"type": 2, "id": 59001, "number": int(amt)}
    else:
        by_category.setdefault("coin", []).append((2, 59001))

    if not by_category:
        return drops
    tier_weights = drop_rates.effective_tier_weights(chapter_id, boss_defeated)
    for category, pool in by_category.items():
        # Mechanics 1 + 3: per-category drop chance (scaled by fleet size: Small/Medium/Large/Boss)
        chance = drop_rates.effective_category_chance(
            category, score, boss_defeated, fleet_size, fleet_role
        )
        try:
            attempts = drop_rates.get_attempts(category, boss_defeated, fleet_size)
        except TypeError:
            attempts = drop_rates.get_attempts(category, boss_defeated)
        for _ in range(attempts):
            if random.random() > chance:
                continue
            drop_type, drop_id = random.choice(pool)
            if category == "ship":
                # Most Mystery Ship virtuals (event maps) carry an explicit
                # display_icon ship list - roll inside it. The handful of
                # opaque campaign items (56000/56500/...) have no client
                # data at all: those roll from the stage's droppable pool
                # (derived from the chapter's own 56xxx award item),
                # capped by the mystery's rarity tier.
                inline = (_load_virtual_item_config(drop_id) or {}).get("display_icon") or []
                if inline:
                    resolved = _resolve_chapter_award_drop(drop_type, drop_id, tier_weights or None)
                    if resolved is None:
                        continue
                    resolved_type, resolved_id, resolved_count = resolved
                else:
                    rolled = _roll_mystery_ship(chapter_id, drop_id, tier_weights or None)
                    if rolled is None:
                        continue
                    resolved_type, resolved_id, resolved_count = 4, rolled, 1
            else:
                # Mechanic 2: within a category, rarer tiers drop less often
                # (the current-chapter ramp makes rare tiers more likely on
                # late chapters).
                resolved = _resolve_chapter_award_drop(drop_type, drop_id, tier_weights or None)
                if resolved is None:
                    continue
                resolved_type, resolved_id, resolved_count = resolved
            # Coins (virtual item 59001) get a randomized amount from the
            # fleet size coin config (separate normal/boss min-max ranges).
            if resolved_type == 2 and resolved_id == 59001:
                lo, hi = drop_rates.get_fleet_coin_range(fleet_size, boss_defeated)
                if hi > 0:
                    resolved_count = random.randint(lo, hi) if hi > lo else lo
            # A fleet shows at most one Mystery Ship icon - never more than
            # one ship per battle, even if several entries could resolve.
            if resolved_type == 4:
                if any(d.get("type") == 4 for d in drops.values()):
                    continue
            key = f"{resolved_type}_{resolved_id}"
            if key in drops:
                drops[key]["number"] = drops[key].get("number", 0) + resolved_count
            else:
                drops[key] = {"type": resolved_type, "id": resolved_id, "number": resolved_count}
    if drops:
        from src.logger.logger import LOG_LEVEL_INFO as _ILI
        log_event(
            "Battle", "Drops",
            f"chapter={chapter_id} expedition={expedition_id} boss={boss_defeated} "
            f"score={score} -> "
            + ", ".join(f"t{d['type']}:{d['id']}x{d['number']}" for d in drops.values()),
            _ILI,
        )
    return drops


_STAGE_SHIP_POOL_CACHE: dict = {}


def _stage_ship_pool(chapter_id: int) -> list:
    """Everything that CAN drop as a ship on this stage, derived from client
    data: the chapter's own "Mystery Ship" award item(s) (56xxx) carry an
    explicit display_icon ship list - that IS the level's droppable pool
    (e.g. 56012 for 3-4 lists Akagi/Kaga plus the commons; hardmode reuses
    the normal chapter's item). Returns [(template_id, rarity_id)]."""
    if not chapter_id:
        return []
    cached = _STAGE_SHIP_POOL_CACHE.get(chapter_id)
    if cached is not None:
        return cached
    ids: set[int] = set()
    try:
        from src.orm.config_entry import get_config_entry
        for category_key in (
            "sharecfgdata/chapter_template.json",
            "sharecfgdata/chapter_template_loop.json",
        ):
            data = _entry_data(get_config_entry(category_key, str(chapter_id))) or {}
            if not isinstance(data, dict):
                continue
            for award in (data.get("awards") or []):
                if not (isinstance(award, (list, tuple)) and len(award) >= 2):
                    continue
                try:
                    award_id = int(award[1])
                except Exception:
                    continue
                config = _load_virtual_item_config(award_id) or {}
                for sub in (config.get("display_icon") or []):
                    if isinstance(sub, (list, tuple)) and len(sub) >= 2 and int(sub[0]) == 4:
                        if int(sub[1]):
                            ids.add(int(sub[1]))
    except Exception:
        pass
    pool: list[tuple[int, int]] = []
    if ids:
        from src.db.store import get_default_store
        store = get_default_store()
        if store is not None:
            try:
                rows = store.fetch(
                    "SELECT template_id, rarity_id FROM ships WHERE template_id = ANY($1)",
                    sorted(ids),
                )
                pool = [(int(r["template_id"]), int(r["rarity_id"])) for r in rows]
            except Exception:
                pool = []
        if not pool:
            # Fallback when store is unavailable (e.g. offline unit test): resolve via config
            from src.orm.config_entry import get_config_entry
            for sid in sorted(ids):
                try:
                    scfg = get_config_entry("sharecfgdata/ship_data_statistics.json", str(sid))
                    sdata = scfg.data if hasattr(scfg, "data") else (scfg if isinstance(scfg, dict) else None)
                    s_rarity = sdata.get("rarity", 1) if sdata else 1
                except Exception:
                    s_rarity = 1
                pool.append((sid, s_rarity))
    _STAGE_SHIP_POOL_CACHE[chapter_id] = pool
    return pool


def _roll_mystery_ship(chapter_id: int, virtual_item_id: int, tier_weights: dict = None) -> Optional[int]:
    """Roll a ship for one of the opaque campaign Mystery Ship tiers
    (56000/56500/56501/... - the only ones without client data).

    The pool is the level's own droppable list (its 56xxx award item's
    display_icon). The mystery's displayed rarity is a CAP, not an exact match:
    "Mystery Ship (Elite)" rolls Elite and below, "(SR)" - the whole pool. The
    item rarity scale is one below the ship table's (item 2=Rare/3=Elite/4=SR
    vs ship 3/4/5), so SR uniques are out of reach for mob fleets.

    Within the pool, ships are picked by rarity tier_weights from
    chapter/boss_drop_rates.json (same weights as inline display_icon rolls),
    including the current-chapter tier ramp."""
    config = _load_virtual_item_config(virtual_item_id) or {}
    try:
        tier_cap = int(config.get("rarity", 0) or 0) + 1
    except Exception:
        tier_cap = 0
    candidates = [
        (template_id, rarity)
        for template_id, rarity in _stage_ship_pool(chapter_id)
        if rarity <= tier_cap
    ]
    if not candidates:
        return None
    if tier_weights:
        kept_ids = []
        weights = []
        for template_id, rarity in candidates:
            try:
                w = int(tier_weights.get(str(rarity), 1))
            except Exception:
                w = 1
            # a base weight of 0 means "never drop this tier"
            if w > 0:
                kept_ids.append(template_id)
                weights.append(w)
        if not kept_ids:
            return None
        return random.choices(kept_ids, weights=weights)[0]
    return random.choice([template_id for template_id, _rarity in candidates])


def _fleet_award_entries(template, expedition_id: int) -> list:
    entries = None
    if expedition_id:
        try:
            from src.orm.config_entry import get_config_entry
            exp_cfg = get_config_entry("sharecfgdata/expedition_data_template.json", str(expedition_id))
            entries = (_entry_data(exp_cfg) or {}).get("award_display")
        except Exception:
            entries = None
    if not entries:
        if template is None:
            return []
        if isinstance(template, dict):
            entries = template.get("awards")
        else:
            entries = getattr(template, "awards", None)
    return list(entries or [])


_RARITY_CACHE: dict = {}


def _resolve_chapter_award_drop(drop_type: int, drop_id: int, tier_weights: dict = None):
    from src.consts.drop_types import DROP_TYPE_ITEM
    if drop_type != DROP_TYPE_ITEM:
        return drop_type, drop_id, 1
    config = _load_virtual_item_config(drop_id)
    if config is None or not config.get("display_icon"):
        return drop_type, drop_id, 1
    display_icon = config["display_icon"]
    if tier_weights:
        entry = _weighted_pick(display_icon, tier_weights)
    else:
        entry = random.choice(display_icon)
    if len(entry) < 2:
        return drop_type, drop_id, 1
    count = 1
    if len(entry) > 2 and entry[2] > 0:
        count = entry[2]
    return entry[0], entry[1], count


def _weighted_pick(display_icon: list, tier_weights: dict) -> list:
    weights = []
    for sub in display_icon:
        if len(sub) < 2:
            weights.append(1)
            continue
        rarity = _drop_rarity(sub[0], sub[1])
        w = tier_weights.get(str(rarity))
        if w is None:
            w = tier_weights.get(rarity, 1)
        weights.append(max(int(w), 0))
    total = sum(weights)
    if total <= 0:
        return random.choice(display_icon)
    roll = random.uniform(0, total)
    upto = 0
    for sub, w in zip(display_icon, weights):
        upto += w
        if roll <= upto:
            return sub
    return display_icon[-1]


def _drop_rarity(drop_type: int, drop_id: int) -> int:
    from src.orm.config_entry import get_config_entry
    if drop_type == 4:
        key = ("ship", drop_id)
        category = "sharecfgdata/ship_data_statistics.json"
    elif drop_type == 2:
        key = ("item", drop_id)
        category = "sharecfgdata/item_data_statistics.json"
    else:
        return 1
    cached = _RARITY_CACHE.get(key)
    if cached is not None:
        return cached
    try:
        entry = get_config_entry(category, str(drop_id))
        rarity = entry.data.get("rarity", 1) if entry else 1
    except Exception:
        rarity = 1
    _RARITY_CACHE[key] = rarity
    return rarity


# --- Daily / event raid award_display parsing & per-stage overrides ---
#
# Azur Lane expedition `award_display` entries are [type, id, desc] where desc
# encodes either a drop CHANCE ("40%chance"), a fixed/range AMOUNT ("1", "0~1"),
# or a coin-amount word ("Few"/"Some"/"Normal"/"Many"/"Numerous").
#
# The word -> gold range table lives in configurations/coin_override.json
# (`coin_word_amounts`) and is read through src.config.coin_override, so it can
# be tuned without touching code.

_COIN_WORD_FALLBACK_AMOUNT = 300


def _coin_word_amount(word: str) -> int:
    from src.config.coin_override import get_coin_word_range

    rng = get_coin_word_range(word)
    if rng is None:
        return _COIN_WORD_FALLBACK_AMOUNT
    return random.randint(rng[0], rng[1])


def _parse_award_display_desc(desc, drop_type, drop_id) -> Optional[int]:
    s = str(desc).strip()
    if not s:
        return 1
    if s.lower().endswith("chance"):
        m = re.match(r"(\d+)", s)
        if not m:
            return 0
        p = int(m.group(1)) / 100.0
        return 1 if random.random() < p else 0
    if "~" in s:
        try:
            lo, hi = s.split("~", 1)
            return random.randint(int(lo), int(hi))
        except (ValueError, TypeError):
            return None
    if s.isdigit():
        return int(s)
    # Non-numeric word: coins get a word-mapped amount, everything else defaults to 1.
    if drop_type == 2 and drop_id == 59001:
        return _coin_word_amount(s)
    return 1


_DAILY_OVERRIDE_CACHE = None

_TECH_BOX_IDS = {54032, 54033, 54034}


def _daily_override_path() -> str:
    here = os.path.dirname(os.path.abspath(__file__))
    cur = here
    for _ in range(8):
        cand = os.path.join(cur, "configurations", "daily_raid_overrides.json")
        if os.path.exists(cand):
            return cand
        parent = os.path.dirname(cur)
        if parent == cur:
            break
        cur = parent
    return os.path.join("configurations", "daily_raid_overrides.json")


def load_daily_overrides() -> dict:
    global _DAILY_OVERRIDE_CACHE
    if _DAILY_OVERRIDE_CACHE is None:
        try:
            with open(_daily_override_path(), "r", encoding="utf-8") as f:
                _DAILY_OVERRIDE_CACHE = json.load(f) or {}
        except (json.JSONDecodeError, OSError):
            _DAILY_OVERRIDE_CACHE = {}
    return _DAILY_OVERRIDE_CACHE


def reload_daily_overrides() -> None:
    global _DAILY_OVERRIDE_CACHE
    _DAILY_OVERRIDE_CACHE = None
    load_daily_overrides()


def get_daily_override(stage_id: int) -> Optional[dict]:
    return load_daily_overrides().get(str(stage_id))


def _pick_weighted_tier(tiers) -> Optional[int]:
    if not tiers:
        return None
    total = sum(w for _, w in tiers)
    if total <= 0:
        return tiers[0][0]
    r = random.random() * total
    acc = 0.0
    for tid, w in tiers:
        acc += w
        if r < acc:
            return tid
    return tiers[-1][0]


def _roll_item_award(drop_id: int, count: int) -> list:
    """Resolve a type-2 (item) award entry into concrete drops.

    Expedition award tables reference *virtual markers* that are never shipped
    as physical items -- the server must roll them at grant time:
      * 59001/59002/... resource proxies ("Coins" / "Oil")  -> resource drop;
      * type-99 "Random ..." boxes with an official display_icon pool;
      * type-98 OPAQUE boxes (54004-54007 "Mystery Skill Book", 54032 Tech
        Pack, ...) whose pool is derived from the real same-tier items.
    Real items (present in item_data_statistics, e.g. skill books 1600x / META
    books 16031) pass through unchanged. ``count`` = number of independent box
    rolls for mystery entries, but a plain quantity for concrete items and
    resource proxies.
    """
    from src.orm.item import resolve_virtual_item_drops
    if _load_virtual_item_config(drop_id) is None:
        from src.consts.drop_types import DROP_TYPE_ITEM
        return [(DROP_TYPE_ITEM, drop_id, count)]
    return resolve_virtual_item_drops(drop_id, count)


def _merge_drop(drops: dict, d_type: int, d_id: int, count: int) -> None:
    if count <= 0:
        return
    key = f"{d_type}_{d_id}"
    if key in drops:
        drops[key]["number"] = drops[key].get("number", 0) + count
    else:
        drops[key] = {"type": d_type, "id": d_id, "number": count}


def _build_daily_award_drops(stage_id: int) -> dict:
    # Daily / event (ROUTINE/SUB) stages aren't chapters, so they never go through
    # the chapter-award path. Their drops come from the stage expedition's
    # `award_display` list, which is the canonical Azur Lane drop table, with an
    # optional per-stage override for stages whose table can't express the real
    # "guaranteed N boxes, each tier-rolled" mechanic (Fierce Assault, Escort,
    # Advance Mission, ...).
    expedition = _load_expedition_config(stage_id)
    if expedition is None:
        return {}
    award_display = expedition.get("award_display") or []
    override = get_daily_override(stage_id)
    skip_ids = set()
    if override:
        skip_ids.update(override.get("skip_ids", []))
        if override.get("tech_box_count"):
            skip_ids.update(_TECH_BOX_IDS)

    drops = {}
    for entry in award_display:
        if len(entry) < 2:
            continue
        d_type = entry[0]
        d_id = entry[1]
        if d_id in skip_ids:
            continue
        d_desc = entry[2] if len(entry) > 2 else ""
        count = _parse_award_display_desc(d_desc, d_type, d_id)
        if not count or count <= 0:
            continue
        if d_type == 2:
            # Virtual marker / resource proxy / real item -> roll it to content.
            for r_type, r_id, r_count in _roll_item_award(d_id, count):
                _merge_drop(drops, int(r_type), int(r_id), int(r_count))
        else:
            _merge_drop(drops, int(d_type), int(d_id), count)

    if override:
        # Guaranteed rolled boxes (Fierce uses tech_box_*; others may use box_count/tiers).
        tiers = override.get("tiers") or override.get("tech_box_tiers")
        if tiers:
            bc = int(override.get("box_count", override.get("tech_box_count", 0)))
            for _ in range(bc):
                tid = _pick_weighted_tier(tiers)
                if not tid:
                    continue
                # Each mystery box is an independent roll into concrete content.
                for r_type, r_id, r_count in _roll_item_award(int(tid), 1):
                    _merge_drop(drops, int(r_type), int(r_id), int(r_count))
        # Extra forced drops on top of the rolled boxes (e.g. T4 / META at lv95).
        for forced in override.get("forced", []):
            if len(forced) < 3:
                continue
            f_type, f_id, f_count = forced[0], forced[1], forced[2]
            if int(f_type) == 2:
                for r_type, r_id, r_count in _roll_item_award(int(f_id), int(f_count)):
                    _merge_drop(drops, int(r_type), int(r_id), int(r_count))
            else:
                _merge_drop(drops, int(f_type), int(f_id), int(f_count))
    return drops


def _find_main_fleet_pos(current):
    if current.main_group_list:
        g = current.main_group_list[0]
        if g.pos is not None:
            return g.pos.row, g.pos.column
    if current.submarine_group_list:
        g = current.submarine_group_list[0]
        if g.pos is not None:
            return g.pos.row, g.pos.column
    return None


def _find_fighting_group_pos(current, ship_ids):
    """Position of the fleet that actually fought this battle, identified by the
    ship ids the battle session recorded. The client sends the stage id of the
    enemy cell under THIS fleet (getStageId(fleet.line.row, fleet.line.column)),
    so the cell to disable is the one at this group's position - not at
    main_group_list[0]'s position (a different fleet that did not fight)."""
    if not ship_ids:
        return None
    ship_ids_set = set(ship_ids)
    for group in _iter_chapter_groups(current):
        group_ids = {s.id for s in group.ship_list}
        if group_ids & ship_ids_set:
            if group.pos is not None:
                return group.pos.row, group.pos.column
    return None


def _disable_chapter_cell_by_expedition_proto(current, expedition_id: int, ship_ids=None):
    fleet_pos = _find_fighting_group_pos(current, ship_ids)
    if fleet_pos is None:
        fleet_pos = _find_main_fleet_pos(current)
    if fleet_pos is not None:
        from src.answer.chapter.helpers import find_chapter_cell_at
        from src.answer.chapter.helpers import ChapterPos
        idx, cell = find_chapter_cell_at(current, ChapterPos(row=fleet_pos[0], column=fleet_pos[1]))
        if cell is not None and cell.item_id == expedition_id and _is_enemy_attachment(cell.item_type) and cell.item_flag != 1:
            cell.item_flag = 1
            return True, cell.item_type
    for cell in current.cell_list:
        if cell.item_id != expedition_id:
            continue
        if not _is_enemy_attachment(cell.item_type):
            continue
        if cell.item_flag == 1:
            continue
        cell.item_flag = 1
        return True, cell.item_type
    return False, 0


def _update_chapter_state_after_battle(commander_id: int, expedition_id: int, stats_by_ship=None, ship_ids=None, won=True):
    if expedition_id == 0:
        return None
    from src.orm.chapter import get_chapter_state_sync, upsert_chapter_state_sync

    try:
        state = get_chapter_state_sync(commander_id)
    except Exception:
        return None
    if state is None:
        return None

    current = protobuf.CURRENTCHAPTERINFO()
    current.ParseFromString(bytes(state.state))
    chapter_id = current.id
    loop_flag = current.loop_flag
    template = _load_chapter_template(chapter_id, loop_flag)
    update = {
        "current": current, "expedition_id": expedition_id,
        "template": template,
    }
    changed, attachment = (False, 0)
    if won:
        changed, attachment = _disable_chapter_cell_by_expedition_proto(current, expedition_id, ship_ids)
    update["defeated"] = changed
    update["defeated_attachment"] = attachment

    on_chapter_battle = _is_chapter_battle(current, expedition_id)
    writeback_changed = False
    if on_chapter_battle:
        writeback_changed = _apply_chapter_battle_writeback(current, stats_by_ship, ship_ids)

    # Server-driven reinforcement wave: spawn the next enemy/boss squad only
    # after a REAL victory (won = score > 0). This mirrors original behaviour
    # where reinforcements appear AFTER the player wins, not when the fleet
    # merely steps onto an enemy cell (act 8 / OpEnemyRound). On a defeat
    # (won=False) we neither disable the beaten cell nor grant any reward/exp.
    if won and on_chapter_battle and changed:
        from src.answer.chapter.helpers import (
            load_chapter_template as _load_dc_template,
            parse_chapter_grids,
            spawn_wave_cells,
        )
        dt = _load_dc_template(chapter_id, loop_flag)
        if dt is not None and dt.enemy_refresh:
            grids = parse_chapter_grids(dt.grids)
            current.kill_count = (current.kill_count or 0) + 1
            new_cells = spawn_wave_cells(current, dt, grids, current.kill_count)
            if new_cells:
                current.cell_list.extend(new_cells)
                writeback_changed = True

    if not changed and not writeback_changed:
        return update
    new_state_bytes = current.SerializeToString()
    try:
        upsert_chapter_state_sync(commander_id, chapter_id, new_state_bytes)
    except Exception:
        return None
    return update


def _is_chapter_battle(current, expedition_id: int) -> bool:
    for cell in current.cell_list:
        if cell.item_id == expedition_id:
            return True
    return False


def _apply_chapter_battle_writeback(current, stats_by_ship, ship_ids) -> bool:
    """Mirror the client's ChapterLevelData.writeBack:
    write ship HP (hp_rant = statistics hp_rest) and consume 1 ammo per
    group that participated, persisting into the chapter state so a re-login
    (SC_13000) returns the damaged fleets instead of full HP / max ammo."""
    if not stats_by_ship:
        return False
    changed = False
    ship_ids_set = set(ship_ids or [])
    for group in _iter_chapter_groups(current):
        group_ids_set = {s.id for s in group.ship_list}
        participated = bool(group_ids_set & ship_ids_set) if ship_ids_set else False
        for ship in group.ship_list:
            stat = stats_by_ship.get(ship.id)
            if stat is not None and stat.hp_rest is not None:
                if ship.hp_rant != stat.hp_rest:
                    ship.hp_rant = stat.hp_rest
                    changed = True
        if participated and group.bullet is not None and group.bullet > 0:
            group.bullet = group.bullet - 1
            changed = True
    return changed


def _iter_chapter_groups(current):
    yield from current.main_group_list
    yield from current.submarine_group_list
    yield from current.support_group_list


def _is_enemy_attachment(attachment: int) -> bool:
    return attachment in (4, 5, 6, 7, 8, 12, 24)


def _is_enemy_count_attachment(attachment: int) -> bool:
    return attachment in (4, 6, 12)


def _load_chapter_template(chapter_id: int, loop_flag: int):
    from src.orm.config_entry import get_config_entry
    try:
        base = _entry_data(get_config_entry("sharecfgdata/chapter_template.json", str(chapter_id)))
        if loop_flag == 0:
            return base
        loop = _entry_data(get_config_entry("sharecfgdata/chapter_template_loop.json", str(chapter_id)))
        if loop is None:
            return base
        merged = dict(base) if isinstance(base, dict) else {}
        if isinstance(loop, dict):
            for key, value in loop.items():
                if value is not None:
                    merged[key] = value
        return merged
    except Exception:
        return None


def _update_chapter_progress_after_battle(commander_id: int, update: dict, score: int):
    if update.get("template") is None or update.get("current") is None:
        return None
    if not update.get("defeated"):
        return None
    from src.orm.chapter import get_chapter_progress_sync, upsert_chapter_progress_sync
    from src.orm.chapter_progress import ChapterProgress

    chapter_id = update["current"].id
    try:
        progress = get_chapter_progress_sync(commander_id, chapter_id)
    except Exception as e:
        return e
    if progress is None:
        progress = ChapterProgress(
            commander_id=commander_id, chapter_id=chapter_id,
            progress=0, kill_boss_count=0, kill_enemy_count=0,
            take_box_count=0, defeat_count=0, today_defeat_count=0,
            pass_count=0, star_rewarded=0, clear_rewarded=0, updated_at=0,
        )

    chapter_cleared = _is_chapter_cleared(update["current"])
    boss_defeated = (
        update["defeated_attachment"] == 1 or
        update["expedition_id"] in update["template"].get("boss_expedition_id", [])
    )
    first_clear = False
    template = update["template"]
    if boss_defeated:
        new_progress = min(progress.progress + template.get("progress_boss", 0), 100)
        first_clear = progress.pass_count == 0 and new_progress == 100
        if new_progress == 100:
            progress.pass_count += 1
        progress.progress = new_progress
        progress.defeat_count += 1
        progress.today_defeat_count += 1

    current = update["current"]
    init_ship_count = current.init_ship_count
    _apply_star_slot(
        template.get("star_require_1", 0), template.get("num_1", 0),
        chapter_cleared, boss_defeated, update["defeated_attachment"],
        update["defeated"], score, init_ship_count,
        progress, "kill_boss_count",
    )
    _apply_star_slot(
        template.get("star_require_2", 0), template.get("num_2", 0),
        chapter_cleared, boss_defeated, update["defeated_attachment"],
        update["defeated"], score, init_ship_count,
        progress, "kill_enemy_count",
    )
    _apply_star_slot(
        template.get("star_require_3", 0), template.get("num_3", 0),
        chapter_cleared, boss_defeated, update["defeated_attachment"],
        update["defeated"], score, init_ship_count,
        progress, "take_box_count",
    )
    # Original one-time stage rewards are the chapter missions themselves: the
    # scenario "Clear X-Y" tasks (sub_type 1020, ids 4-67) and the branch
    # "Get 3 stars in stage X-Y" tasks (sub_type 1021, ids 3001+, target
    # chapter id). The player claims them from the Missions screen, so nothing
    # is granted inline here (the old custom star/clear grant joined those
    # rewards into SC_40004.drop_info, mixing them with the node's own loot).
    # Track the state so those missions can be prefilled/seeded from past runs
    # and the battle path can emit the completion event exactly once.
    if not progress.star_rewarded and _all_star_objectives_complete(progress, template):
        progress.star_rewarded = 1
        update["star_first_complete"] = True

    if first_clear:
        progress.clear_rewarded = 1
        update["clear_first_complete"] = True

    try:
        upsert_chapter_progress_sync(progress)
    except Exception as e:
        return e

    try:
        from src.orm.daily_expedition import (
            get_chapter_map_type,
            increment_elite_expedition_count,
            increment_chapter_defeat_count,
            chapter_tries_limit,
            MAP_TYPE_ELITE,
        )
        map_type = get_chapter_map_type(chapter_id, update["current"].loop_flag)
        if boss_defeated:
            if map_type == MAP_TYPE_ELITE:
                increment_elite_expedition_count(commander_id)
            if chapter_tries_limit(chapter_id):
                increment_chapter_defeat_count(commander_id, chapter_id)
    except Exception:
        pass
    return None


def _apply_star_slot(
    star_type: int, config: int, chapter_cleared: bool,
    boss_defeated: bool, attachment: int, defeated: bool,
    score: int, init_ship_count: int, progress, count_key: str,
):
    if config == 0:
        return
    if isinstance(progress, dict):
        cur = progress.get(count_key, 0)
        if cur >= config:
            return
        if star_type == 1:
            if boss_defeated and defeated:
                progress[count_key] = cur + 1
        elif star_type == 2:
            if defeated and _is_enemy_count_attachment(attachment):
                progress[count_key] = cur + 1
        elif star_type == 3:
            if chapter_cleared:
                progress[count_key] = cur + 1
        elif star_type == 4:
            if boss_defeated and init_ship_count <= config:
                progress[count_key] = cur + 1
        elif star_type == 6:
            if boss_defeated and score == 4:
                progress[count_key] = cur + 1
    else:
        cur = getattr(progress, count_key, 0)
        if cur >= config:
            return
        if star_type == 1:
            if boss_defeated and defeated:
                setattr(progress, count_key, cur + 1)
        elif star_type == 2:
            if defeated and _is_enemy_count_attachment(attachment):
                setattr(progress, count_key, cur + 1)
        elif star_type == 3:
            if chapter_cleared:
                setattr(progress, count_key, cur + 1)
        elif star_type == 4:
            if boss_defeated and init_ship_count <= config:
                setattr(progress, count_key, cur + 1)
        elif star_type == 6:
            if boss_defeated and score == 4:
                setattr(progress, count_key, cur + 1)


def _is_chapter_cleared(current) -> bool:
    for cell in current.cell_list:
        if not _is_enemy_attachment(cell.item_type):
            continue
        if cell.item_flag != 1:
            return False
    return True


def _all_star_objectives_complete(progress, template) -> bool:
    """True when EVERY star objective of the chapter is complete.

    Mirrors the client's ChapterConst.IsAchieved (model/const/chapterconst.lua):
    the achieves list is built from star_require_i / num_i with counts
    (kill_boss_count, kill_enemy_count, take_box_count) per slot, and an
    objective is achieved when config <= count (types 4/5 are satisfied by a
    single clear: count >= 1). Only objectives with star_require_i > 0 count."""
    if template is None or not isinstance(template, dict):
        return False
    if isinstance(progress, dict):
        counters = [
            progress.get("kill_boss_count", 0),
            progress.get("kill_enemy_count", 0),
            progress.get("take_box_count", 0),
        ]
    else:
        counters = [
            getattr(progress, "kill_boss_count", 0),
            getattr(progress, "kill_enemy_count", 0),
            getattr(progress, "take_box_count", 0),
        ]
    for i, count in enumerate(counters):
        star_type = template.get("star_require_%d" % (i + 1), 0) or 0
        if not star_type:
            continue
        config = template.get("num_%d" % (i + 1), 0) or 0
        if star_type in (4, 5):
            achieved = count >= 1
        else:
            achieved = count >= config
        if not achieved:
            return False
    return True


def _save_limit_challenge_clear(client, stage_id: int, total_time: int, score: int):
    if stage_id == 0 or score == 0:
        return
    from datetime import datetime, timezone
    from src.orm.config_entry import get_config_entry, list_config_entries
    month_config = None
    month_id = datetime.now(timezone.utc).month
    raw = get_config_entry("ShareCfg/constellation_challenge_month.json", str(month_id))
    if raw is not None:
        data = _entry_data(raw)
        if isinstance(data, dict) and data.get("id") == month_id:
            month_config = data
    if month_config is None:
        for entry in list_config_entries("ShareCfg/constellation_challenge_month.json"):
            data = _entry_data(entry)
            if isinstance(data, dict) and data.get("id") == month_id:
                month_config = data
                break
    if month_config is None:
        return
    challenge_ids = month_config.get("stage", [])
    challenge_id = None
    for cid in challenge_ids:
        template = _entry_data(get_config_entry("ShareCfg/expedition_constellation_challenge_template.json", str(cid)))
        if template and template.get("dungeon_id") == stage_id:
            challenge_id = cid
            break
    if challenge_id is None:
        return
    from src.orm.limit_challenge import load_limit_challenge_state, save_limit_challenge_state
    state = load_limit_challenge_state(client.commander.commander_id)
    best = state["best_times"].get(challenge_id, 0)
    if best == 0 or (total_time > 0 and total_time < best):
        state["best_times"][challenge_id] = total_time
    if challenge_id not in state["pass_ids"]:
        state["pass_ids"].append(challenge_id)
        state["pass_ids"].sort()
    save_limit_challenge_state(
        state["commander_id"],
        state["month_bucket"],
        state["best_times"],
        state["awarded"],
        state["pass_ids"],
    )
