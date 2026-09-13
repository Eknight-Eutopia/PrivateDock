HEADER_SIZE = 7

UPDATE_CHECK_PACKET = 10800
HTTP_GET_SERVERS = 8239
AUTH_PACKET = 10021

"""
Packet body:
  - 2 bytes (uint16) : packet size
  - 1 byte (uint8)   : 0x00
  - 2 bytes (uint16) : packet id
  - 2 bytes (uint16) : packet index (0x0000 or 0x0001 if frame has >1 packet)
  - rest    : content
"""


def get_packet_id(offset: int, buffer: bytes) -> int:
    return (buffer[3 + offset] << 8) | buffer[4 + offset]


def get_packet_size(offset: int, buffer: bytes) -> int:
    return (buffer[0 + offset] << 8) | buffer[1 + offset]


def get_packet_index(offset: int, buffer: bytes) -> int:
    return (buffer[5 + offset] << 8) | buffer[6 + offset]
