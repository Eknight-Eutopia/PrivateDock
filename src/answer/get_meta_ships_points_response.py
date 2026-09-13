from typing import Optional

from src.connection.client import Client
from src.answer.meta.handlers import handle_get_meta_ships_points_response as _real_handle_get_meta_ships_points_response


def handle_get_meta_ships_points_response(buffer: bytes, client: Client) -> tuple[int, int, Optional[Exception]]:
    return _real_handle_get_meta_ships_points_response(buffer, client)
