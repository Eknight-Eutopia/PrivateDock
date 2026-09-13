from typing import Optional

from src.connection.client import Client
from src.connection.server import generate_packet_header
from src.orm.mail import get_mailbox_counts
from src.protobuf import protobuf


def handle_game_mailbox(_buffer: bytes, client: Client) -> tuple[int, int, Optional[Exception]]:
    total, unread = get_mailbox_counts(client.commander.commander_id)

    response = protobuf.SC_30001()
    response.unread_number = unread
    response.total_number = total
    data = response.SerializeToString()
    header = generate_packet_header(30001, data, client.packet_index)
    client.write_to_buffer(header + data)
    return 0, 30001, None


def push_mail_count_sync(client: Client):
    """Re-send SC_30001 (unread/total) to a live client after a mail is created.

    Without this the client keeps the login-time mailbox totals, so a mail
    delivered mid-session shows no badge and the "All" tab never fetches it
    (the client skips the list request while its cached total is 0).
    """
    handle_game_mailbox(b"", client)
    import asyncio

    asyncio.create_task(client.flush())
