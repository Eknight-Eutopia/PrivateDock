SERVER_TICKET_PREFIX = "=*=*=*=PrivateDock=*=*=*="


def format_server_ticket(arg2: int) -> str:
    if arg2 == 0:
        return SERVER_TICKET_PREFIX
    return f"{SERVER_TICKET_PREFIX}:{arg2}"


def parse_server_ticket(ticket: str) -> int:
    prefix = f"{SERVER_TICKET_PREFIX}:"
    if not ticket.startswith(prefix):
        return 0
    value = ticket[len(prefix):]
    try:
        return int(value)
    except (ValueError, TypeError):
        return 0
