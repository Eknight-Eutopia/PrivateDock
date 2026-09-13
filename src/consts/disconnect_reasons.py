DR_LOGGED_IN_ON_ANOTHER_DEVICE = 1
DR_SERVER_MAINTENANCE = 2
DR_GAME_UPDATE = 3
DR_OFFLINE_TOO_LONG = 4
DR_CONNECTION_LOST = 5
DR_CONNECTION_TO_SERVER_LOST = 6
DR_DATA_VALIDATION_FAILED = 7
DR_LOGIN_DATA_EXPIRED = 199

_REASON_MAP = {
    DR_LOGGED_IN_ON_ANOTHER_DEVICE: "logged in on another device",
    DR_SERVER_MAINTENANCE: "server maintenance",
    DR_GAME_UPDATE: "game update",
    DR_OFFLINE_TOO_LONG: "offline too long",
    DR_CONNECTION_LOST: "connection lost",
    DR_CONNECTION_TO_SERVER_LOST: "connection to server lost",
    DR_DATA_VALIDATION_FAILED: "data validation failed",
    DR_LOGIN_DATA_EXPIRED: "login data expired",
}


def resolve_reason(reason: int) -> str:
    return _REASON_MAP.get(reason, f"unknown reason {reason}")
