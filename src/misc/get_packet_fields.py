from __future__ import annotations

import glob
import re
from dataclasses import dataclass

_field_regex = re.compile(r"(required|repeated|optional)\s+(\w+)\s+(\w+)\s*=\s*(\d+);")


@dataclass
class Field:
    label: str = ""
    name: str = ""
    type: str = ""
    index: int = 0


def _default_err_fields() -> list[Field]:
    return [Field(name="No fields found")]


def parse_file(path: str) -> list[Field]:
    output = []
    try:
        with open(path, "r") as f:
            for line in f:
                m = _field_regex.match(line.strip())
                if m:
                    output.append(Field(
                        label=m.group(1),
                        type=m.group(2),
                        name=m.group(3),
                        index=int(m.group(4)),
                    ))
    except FileNotFoundError:
        return _default_err_fields()
    return output


def get_packet_fields(packet_id: int) -> list[Field]:
    results = glob.glob(f"packets/protobuf_src/*_{packet_id}.proto")
    if not results:
        return _default_err_fields()
    return parse_file(results[0])
