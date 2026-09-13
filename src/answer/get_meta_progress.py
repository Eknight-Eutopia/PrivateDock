from typing import Optional

from src.connection.client import Client
from src.answer.meta.handlers import handle_get_meta_progress as _handler


def handle_get_meta_progress(buffer: bytes, client: Client) -> tuple[int, int, Optional[Exception]]:
    return _handler(buffer, client)
