import asyncio
import time
from typing import Callable, Optional, Union, Coroutine, Any

from src.connection.client import Client
from src.connection.server import send_proto_message
from src.logger.logger import log_event, with_fields, field_value, LOG_LEVEL_DEBUG, LOG_LEVEL_ERROR, LOG_LEVEL_WARN
from src.packets.magic import get_packet_id, get_packet_size, get_packet_index, HEADER_SIZE

PacketHandler = Callable[[bytes, "Client"], Union[tuple[int, int, Optional[Exception]], Coroutine[Any, Any, tuple[int, int, Optional[Exception]]]]]

_packet_decision_fn: dict[int, list[PacketHandler]] = {}
MISSING_PACKET_RESULT = 1


def register_packet_handler(packet_id: int, handlers: list[PacketHandler]):
    log_event("Handler", "Added", f"CS_{packet_id}", LOG_LEVEL_DEBUG)
    _packet_decision_fn[packet_id] = handlers


def get_packet_handler(packet_id: int) -> Optional[list[PacketHandler]]:
    return _packet_decision_fn.get(packet_id)


def has_packet_handler(packet_id: int) -> bool:
    return packet_id in _packet_decision_fn


async def dispatch(buffer: bytes, client: Client, n: int):
    try:
        offset = 0
        while offset < n:
            packet_id = get_packet_id(offset, buffer)
            packet_size = get_packet_size(offset, buffer) + 2
            client.packet_index = get_packet_index(offset, buffer)
            handlers = _packet_decision_fn.get(packet_id)

            with_fields(
                "Handler",
                field_value("remote", f"{client.ip}:{client.port}"),
                field_value("packet", packet_id),
                field_value("size", packet_size),
                field_value("has_handler", handlers is not None),
            ).debug(f"received packet")

            # TEMP DEBUG: always-visible log of every received packet id so we
            # can identify the commission board request packet. Remove after.
            log_event("Handler", "RecvPacket", f"CS_{packet_id} has_handler={handlers is not None}", LOG_LEVEL_WARN)

            headerless_buffer = buffer[offset + HEADER_SIZE:offset + packet_size]
            if headerless_buffer == b"\x00":
                headerless_buffer = b""

            if client.commander is not None:
                from src.answer.task_handlers import maybe_reset_daily_weekly
                try:
                    await maybe_reset_daily_weekly(client)
                except Exception:
                    pass

            if handlers is None:
                log_event("Handler", "Missing", f"CS_{packet_id}", LOG_LEVEL_DEBUG)
                from src.protobuf import protobuf
                await send_proto_message(10998, client, protobuf.SC_10998(
                    cmd=packet_id,
                    result=MISSING_PACKET_RESULT,
                ))
            else:
                for handler in handlers:
                    start = time.monotonic()
                    try:
                        result = handler(headerless_buffer, client)
                        if asyncio.iscoroutine(result):
                            n_sent, resp_packet_id, err = await result
                        else:
                            n_sent, resp_packet_id, err = result
                    except Exception as e:
                        log_event("Handler", "Exception", f"CS_{packet_id} handler raised: {e}", LOG_LEVEL_ERROR)
                        import traceback
                        log_event("Handler", "Exception", traceback.format_exc(), LOG_LEVEL_ERROR)
                        client.record_handler_error()
                        await client.close_with_error()
                        return
                    elapsed = time.monotonic() - start
                    handler_name = getattr(handler, "__name__", type(handler).__name__)
                    ms = elapsed * 1000.0
                    if ms >= 500:
                        log_event("Metrics", "HandlerMs",
                                  f"CS_{packet_id}/{handler_name} -> {ms:.0f}ms SLOW", LOG_LEVEL_WARN)
                    else:
                        log_event("Metrics", "HandlerMs",
                                  f"CS_{packet_id}/{handler_name} -> {ms:.2f}ms", LOG_LEVEL_DEBUG)
                    if err:
                        client.record_handler_error()
                        log_event("Handler", "Error", f"SC_{resp_packet_id} - {err}", LOG_LEVEL_ERROR)
                        await client.close_with_error()
                        return

            offset += packet_size

        buf_len = len(client._buffer)
        log_event("Handler", "FlushStart", f"buffer={buf_len}B for {client.ip}:{client.port}", LOG_LEVEL_WARN)
        await client.flush()
        log_event("Handler", "FlushDone", f"flushed {buf_len}B for {client.ip}:{client.port}", LOG_LEVEL_WARN)
    except Exception as e:
        log_event("Handler", "FlushDone", f"Error:{e}", LOG_LEVEL_ERROR)
