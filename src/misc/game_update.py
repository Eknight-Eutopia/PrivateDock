from src.logger.logger import log_event, LOG_LEVEL_INFO
from src.misc.update_data_helpers import update_all_data as _update_all_data


def update_all_data(region: str):
    log_event("GameUpdate", "Data", f"updating game data for region {region}", LOG_LEVEL_INFO)
    _update_all_data(region)
