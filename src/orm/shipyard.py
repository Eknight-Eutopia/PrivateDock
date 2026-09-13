from sqlalchemy import select

from src.db.session import get_sync_session
from src.db.store import NotFoundError
from src.orm.commander_shipyard_blueprint import CommanderShipyardBlueprint
from src.orm.commander_shipyard_state import CommanderShipyardState
from src.orm.config_entry import get_config_entry_sync
from src.orm.shipyard_blueprint_proto import ShipyardBlueprintProto
from src.orm.shipyard_task_template_config import ShipyardTaskTemplateConfig


def get_commander_shipyard_state(commander_id: int) -> dict:
    with get_sync_session() as session:
        result = session.execute(
            select(CommanderShipyardState).where(
                CommanderShipyardState.commander_id == commander_id,
            )
        )
        state = result.scalar_one_or_none()
        if state is None:
            raise NotFoundError
        return {
            "commander_id": state.commander_id,
            "cold_time": state.cold_time,
            "daily_catchup_strengthen": state.daily_catchup_strengthen,
            "daily_catchup_strengthen_ur": state.daily_catchup_strengthen_ur,
        }


def get_or_create_commander_shipyard_state(commander_id: int):
    with get_sync_session() as session:
        result = session.execute(
            select(CommanderShipyardState).where(
                CommanderShipyardState.commander_id == commander_id,
            )
        )
        state = result.scalar_one_or_none()
        if state is None:
            state = CommanderShipyardState(commander_id=commander_id)
            session.add(state)
            session.commit()
        return state


def upsert_commander_shipyard_state(state: CommanderShipyardState):
    with get_sync_session() as session:
        session.add(state)
        session.commit()


def get_shipyard_state_or_default(commander_id: int):
    return get_or_create_commander_shipyard_state(commander_id)


def get_commander_shipyard_blueprint(commander_id: int, blueprint_id: int):
    with get_sync_session() as session:
        result = session.execute(
            select(CommanderShipyardBlueprint).where(
                CommanderShipyardBlueprint.commander_id == commander_id,
                CommanderShipyardBlueprint.blueprint_id == blueprint_id,
            )
        )
        return result.scalar_one_or_none()


def upsert_commander_shipyard_blueprint(blueprint: CommanderShipyardBlueprint):
    with get_sync_session() as session:
        session.add(blueprint)
        session.commit()


def list_commander_shipyard_blueprints(commander_id: int):
    with get_sync_session() as session:
        result = session.execute(
            select(CommanderShipyardBlueprint).where(
                CommanderShipyardBlueprint.commander_id == commander_id,
            )
        )
        return list(result.scalars().all())


def _collect_uint_values(value, out: list[int] | None = None) -> list[int]:
    if out is None:
        out = []
    if isinstance(value, (int, float)):
        if value >= 0:
            out.append(int(value))
    elif isinstance(value, str):
        try:
            parsed = int(value)
            if parsed >= 0:
                out.append(parsed)
        except ValueError:
            pass
    elif isinstance(value, (list, tuple)):
        for item in value:
            _collect_uint_values(item, out)
    elif isinstance(value, dict):
        for item in value.values():
            _collect_uint_values(item, out)
    return out


def get_shipyard_pursue_discounts(ur: bool = False) -> list[int]:
    key = "blueprint_pursue_discount_ur" if ur else "blueprint_pursue_discount_ssr"
    entry = get_config_entry_sync("ShareCfg/gameset.json", key)
    if entry is None or entry.data is None:
        raise NotFoundError
    desc = entry.data.get("description")
    if desc is None:
        raise NotFoundError
    return _collect_uint_values(desc)


def get_shipyard_task_template_config(task_id: int):
    with get_sync_session() as session:
        result = session.execute(
            select(ShipyardTaskTemplateConfig).where(
                ShipyardTaskTemplateConfig.task_id == task_id
            )
        )
        return result.scalar_one_or_none()


def list_shipyard_blueprint_proto():
    with get_sync_session() as session:
        result = session.execute(select(ShipyardBlueprintProto))
        return list(result.scalars().all())
