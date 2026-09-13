from typing import Optional

from src.connection.client import Client
from src.answer.meta.handlers import handle_claim_meta_pt_award as _real_handle_claim_meta_pt_award


def handle_claim_meta_pt_award(buffer: bytes, client: Client) -> tuple[int, int, Optional[Exception]]:
    return _real_handle_claim_meta_pt_award(buffer, client)
