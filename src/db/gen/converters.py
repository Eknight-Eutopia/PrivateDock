

class Int64List(list):
    pass


def to_int64_list(values: list[int]) -> Int64List:
    if not values:
        return Int64List()
    return Int64List(int(v) for v in values)


def to_uint32_list(values: list[int]) -> list[int]:
    if not values:
        return []
    return [int(v) for v in values]


class StringList(list):
    pass
