import asyncio
import ipaddress
import time
from typing import Callable, Optional, Coroutine, Any

from src.connection.client import Client
from src.consts.disconnect_reasons import DR_CONNECTION_TO_SERVER_LOST, DR_SERVER_MAINTENANCE
from src.logger.logger import log_event, with_fields, field_value, LOG_LEVEL_DEBUG, LOG_LEVEL_ERROR, LOG_LEVEL_INFO

ServerDispatcher = Callable[[bytes, Client, int], Coroutine[Any, Any, Any]]

READ_BUFFER_SIZE = 32 << 10  # 32KB
# Largest game frame we will believe.  Real CS_/SC_ frames are a few hundred
# bytes (the biggest observed is SC_10801 at 444 B); 16 KB is already absurdly
# generous.  Anything above this is a peer that is not the game client.
MAX_FRAME_SIZE = 16 << 10
_privatedock_instance: Optional["Server"] = None


def _looks_like_ascii_verb(header: bytes) -> bool:
    """True if a 2-byte frame header is really the start of an HTTP method.

    Asset/CDN requests are the case that matters: "GET " starts with b"GE",
    which as a big-endian u16 is 0x4745 = 18245.  The old code therefore read
    the header, believed the frame was 18245 bytes, and blocked in
    ``readexactly`` waiting for data the client never sent -- the connection
    then died as a silent ``Hello``/``Goodbye`` pair with nothing in the log.
    That is what a CDN hostname being redirected at
    the game port looks like from the server side.  Both bytes being uppercase
    ASCII letters is never a legitimate frame length.
    """
    return (
        len(header) == 2
        and 0x41 <= header[0] <= 0x5A
        and 0x41 <= header[1] <= 0x5A
    )



class Server:
    def __init__(self, bind_address: str, port: int, dispatcher: ServerDispatcher):
        self.bind_address = bind_address
        self.port = port
        self.dispatcher = dispatcher
        self.start_time = 0.0
        self._require_private = True
        self._maintenance = False
        self._clients: dict[int, Client] = {}
        self._rooms: dict[int, list[Client]] = {}
        self._server: Optional[asyncio.AbstractServer] = None
        self._is_accepting_connections = True
        global _privatedock_instance
        _privatedock_instance = self

    @property
    def is_accepting_connections(self) -> bool:
        return self._is_accepting_connections

    @property
    def maintenance_enabled(self) -> bool:
        return self._maintenance

    def set_maintenance(self, enabled: bool):
        self._maintenance = enabled
        if enabled:
            asyncio.create_task(self.disconnect_all(DR_SERVER_MAINTENANCE))

    def set_require_private_clients(self, enabled: bool):
        self._require_private = enabled

    def set_accepting_connections(self, enabled: bool):
        self._is_accepting_connections = enabled
        if not enabled:
            asyncio.create_task(self.disconnect_all(DR_CONNECTION_TO_SERVER_LOST))

    async def _handle_connection(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        peername = writer.get_extra_info("peername")
        remote = f"{peername[0]}:{peername[1]}" if peername else "unknown"

        client = Client(reader, writer, self)

        if self._maintenance:
            log_event("Server", "Run", f"maintenance enabled, rejecting {remote}", LOG_LEVEL_INFO)
            writer.close()
            return

        if not self._allow_client_ip(client.ip):
            with_fields("Server", field_value("remote", remote)).error("client not in private range")
            writer.close()
            return

        if not self._is_accepting_connections:
            log_event("Server", "Reject", f"rejecting {remote} (stopped)", LOG_LEVEL_INFO)
            writer.close()
            return

        self._add_client(client)
        client.start_dispatcher()

        try:
            while not client.is_closed():
                size_header = await reader.readexactly(2)
                size = (size_header[0] << 8) | size_header[1]
                if size < 5 or size > MAX_FRAME_SIZE:
                    # Not a game frame.  Say so loudly: this is how a redirected
                    # asset/CDN host shows up, and without the log it looks like
                    # nothing happened at all (see _looks_like_ascii_verb).
                    hint = " (looks like an HTTP request, not a game client)" if _looks_like_ascii_verb(size_header) else ""
                    log_event(
                        "Server", "Read",
                        f"{remote} sent a non-game frame header {size_header.hex()} -> size {size}{hint}",
                        LOG_LEVEL_ERROR,
                    )
                    break

                payload = await reader.readexactly(size)

                packet_id = (payload[1] << 8) | payload[2]
                log_event("Server", "Packet", f"received CS_{packet_id} size={size}", LOG_LEVEL_INFO)

                packet = bytearray(2 + size)
                packet[0] = size_header[0]
                packet[1] = size_header[1]
                packet[2:] = payload

                await client.enqueue_packet(bytes(packet))
        except asyncio.IncompleteReadError as e:
            # An empty partial is the ordinary "client closed between frames"
            # case.  A non-empty one means the peer sent a truncated frame and
            # left -- typically the tail of an HTTP request after we consumed
            # its first two bytes as a bogus length.  Log it so the payload is
            # recoverable instead of vanishing.
            if e.partial:
                preview = bytes(e.partial[:48])
                log_event(
                    "Server", "Read",
                    f"{remote} closed mid-frame after {len(e.partial)}B: {preview.hex()}",
                    LOG_LEVEL_ERROR,
                )
        except Exception as e:
            log_event("Server", "Read", f"{remote} -> {e}", LOG_LEVEL_ERROR)
        finally:
            self.remove_client(client)

    def _allow_client_ip(self, ip_str: str) -> bool:
        if not self._require_private:
            return True
        try:
            ip = ipaddress.ip_address(ip_str)
            return ip.is_private
        except ValueError:
            return False

    def _add_client(self, client: Client):
        log_event("Server", "Hello", f"new connection from {client.ip}:{client.port}", LOG_LEVEL_DEBUG)
        self._clients[client.hash] = client

    def remove_client(self, client: Client):
        log_event("Server", "Goodbye", f"{client.ip}:{client.port}", LOG_LEVEL_DEBUG)
        for room_clients in self._rooms.values():
            if client in room_clients:
                room_clients.remove(client)
        asyncio.create_task(client.close())
        if client.hash in self._clients:
            del self._clients[client.hash]

    def find_client(self, hash_val: int) -> Optional[Client]:
        return self._clients.get(hash_val)

    def find_client_by_commander(self, commander_id: int) -> Optional[Client]:
        for client in self._clients.values():
            if client.commander and getattr(client.commander, "commander_id", None) == commander_id:
                return client
        return None

    def client_count(self) -> int:
        return len(self._clients)

    def list_clients(self) -> list[Client]:
        return list(self._clients.values())

    async def run(self):
        try:
            self.start_time = time.time()
            log_event("Server", "Run", f"listening on {self.bind_address}:{self.port}", LOG_LEVEL_INFO)
            self._server = await asyncio.start_server(
                self._handle_connection,
                self.bind_address,
                self.port,
            )
            async with self._server:
                await self._server.serve_forever()
        except Exception as e:
            log_event("Answer", "version_check", f"Error: {e}", LOG_LEVEL_ERROR)

    async def disconnect_all(self, reason: int):
        for client in list(self._clients.values()):
            await client.disconnect(reason)
            self.remove_client(client)

    async def disconnect_commander(self, commander_id: int, reason: int, exclude_client: Optional[Client] = None) -> bool:
        for c in list(self._clients.values()):
            if c.commander and getattr(c.commander, "commander_id", None) == commander_id:
                if exclude_client and c is exclude_client:
                    return False
                await c.disconnect(reason)
                await c.flush()
                self.remove_client(c)
                return True
        return False

    # Chat room management
    def join_room(self, room_id: int, client: Client):
        if room_id not in self._rooms:
            self._rooms[room_id] = []
        self._rooms[room_id].append(client)

    def leave_room(self, room_id: int, client: Client):
        if room_id in self._rooms:
            self._rooms[room_id] = [c for c in self._rooms[room_id] if c is not client]

    def change_room(self, old_room_id: int, new_room_id: int, client: Client):
        self.leave_room(old_room_id, client)
        self.join_room(new_room_id, client)
        from src.logger.logger import log_event, LOG_LEVEL_DEBUG
        log_event("Chat", "RoomChange",
                  f"cmd={getattr(getattr(client, 'commander', None), 'commander_id', '?')} "
                  f"{old_room_id} -> {new_room_id} "
                  f"({getattr(client, 'ip', '?')}:{getattr(client, 'port', '?')})",
                  LOG_LEVEL_DEBUG)

    def room_clients(self, room_id: int) -> list:
        return list(self._rooms.get(room_id, []))

    async def broadcast_room(self, room_id: int, packet_id: int, message) -> None:
        """Send a packet to every client in a chat room (including the sender —
        the client renders its own message from this broadcast, SC_50101)."""
        members = self.room_clients(room_id)
        from src.logger.logger import log_event, LOG_LEVEL_DEBUG
        log_event("Chat", "Broadcast",
                  f"room={room_id} SC_{packet_id} members={len(members)} "
                  + "[" + ", ".join(
                      f"{getattr(c, 'ip', '?')}:{getattr(c, 'port', '?')}"
                      f"/cmd{getattr(getattr(c, 'commander', None), 'commander_id', '?')}"
                      f"{' CLOSED' if getattr(c, '_closed', False) else ''}"
                      for c in members) + "]",
                  LOG_LEVEL_DEBUG)
        for c in members:
            try:
                await c.send_message(packet_id, message)
            except Exception:
                pass


def get_instance() -> Optional[Server]:
    return _privatedock_instance


def generate_packet_header(packet_id: int, payload: bytes, packet_index: int = 0) -> bytes:
    payload_size = len(payload) + 5
    header = bytearray(7)
    header[0] = (payload_size >> 8) & 0xFF
    header[1] = payload_size & 0xFF
    header[2] = 0x00
    header[3] = (packet_id >> 8) & 0xFF
    header[4] = packet_id & 0xFF
    header[5] = (packet_index >> 8) & 0xFF
    header[6] = packet_index & 0xFF
    return bytes(header)


def inject_packet_header(packet_id: int, payload: bytearray, packet_index: int = 0):
    header = generate_packet_header(packet_id, bytes(payload), packet_index)
    payload[:0] = bytearray(header)


async def send_proto_message(packet_id: int, client: Client, message) -> tuple[int, int, Optional[Exception]]:
    import json

    try:
        if hasattr(message, "SerializeToString"):
            data = message.SerializeToString()
        elif isinstance(message, dict):
            data = json.dumps(message).encode("utf-8")
        elif isinstance(message, str):
            data = message.encode("utf-8")
        else:
            data = message
    except Exception as e:
        # NEVER fall back to str(message): that puts ASCII debug text on the
        # wire which the client silently drops (chat bug 2026-08-25).
        log_event("Connection", "SerializeError",
                  f"SC_{packet_id} serialization failed, packet NOT sent: {e}", LOG_LEVEL_ERROR)
        return 0, packet_id, e

    if isinstance(data, str):
        data = data.encode("utf-8")
    elif not isinstance(data, bytes):
        data = str(data).encode("utf-8")

    header = generate_packet_header(packet_id, data, client.packet_index)
    client.write_to_buffer(header + data)
    await client.flush()

    log_event("Connection", "SendMessage", f"SC_{packet_id} - {len(data)} bytes sent", LOG_LEVEL_DEBUG)
    return len(data), packet_id, None
