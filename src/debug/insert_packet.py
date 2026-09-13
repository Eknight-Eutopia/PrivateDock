from src.db.store import get_default_store
from src.logger.logger import log_event, LOG_LEVEL_ERROR

SKIPPED_PACKET_IDS = {8239}


def insert_packet(packet_id: int, payload: bytes) -> None:
    if packet_id in SKIPPED_PACKET_IDS:
        return
    store = get_default_store()
    try:
        store.execute(
            "INSERT INTO debugs (packet_id, data, packet_size) VALUES ($1, $2, $3)",
            packet_id, payload, len(payload),
        )
    except Exception as e:
        log_event("Debug", "InsertPacket", f"Failed to insert packet {packet_id}", LOG_LEVEL_ERROR)
        log_event("Debug", "InsertPacket", str(e), LOG_LEVEL_ERROR)
