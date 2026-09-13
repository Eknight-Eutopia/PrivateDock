def encode_varint(value: int) -> bytes:
    out = bytearray()
    while value > 0x7F:
        out.append((value & 0x7F) | 0x80)
        value >>= 7
    out.append(value & 0x7F)
    return bytes(out)


def read_varint(data: bytes, idx: int) -> tuple[int, int]:
    v = 0
    shift = 0
    while idx < len(data):
        byte = data[idx]
        v |= (byte & 0x7F) << shift
        shift += 7
        idx += 1
        if not (byte & 0x80):
            break
    return v, idx
