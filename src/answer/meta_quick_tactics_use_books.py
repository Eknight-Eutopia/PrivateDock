from typing import Optional

from src.connection.client import Client
from src.answer.meta.handlers import handle_meta_quick_tactics_use_books as _real_handle_meta_quick_tactics_use_books


def handle_meta_quick_tactics_use_books(buffer: bytes, client: Client) -> tuple[int, int, Optional[Exception]]:
    return _real_handle_meta_quick_tactics_use_books(buffer, client)
