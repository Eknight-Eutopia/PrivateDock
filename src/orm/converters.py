import json


def to_int64_list(values: list[int]) -> str:
    return json.dumps(values)


def to_uint32_list(json_str: str) -> list[int]:
    if not json_str:
        return []
    return json.loads(json_str)
