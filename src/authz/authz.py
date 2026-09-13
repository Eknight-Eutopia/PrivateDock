from enum import Enum
from typing import Optional

from src.authz.keys import known_permissions


class Operation(str, Enum):
    ReadSelf = "read_self"
    ReadAny = "read_any"
    WriteSelf = "write_self"
    WriteAny = "write_any"


class Capability:
    def __init__(self, read_self: bool = False, read_any: bool = False, write_self: bool = False, write_any: bool = False):
        self.read_self = read_self
        self.read_any = read_any
        self.write_self = write_self
        self.write_any = write_any

    def allowed(self, op: Operation) -> bool:
        if op == Operation.ReadSelf:
            return self.read_self or self.read_any
        elif op == Operation.ReadAny:
            return self.read_any
        elif op == Operation.WriteSelf:
            return self.write_self or self.write_any
        elif op == Operation.WriteAny:
            return self.write_any
        return False

    @staticmethod
    def all() -> "Capability":
        return Capability(read_self=True, read_any=True, write_self=True, write_any=True)

    @staticmethod
    def none() -> "Capability":
        return Capability()

    def __repr__(self):
        return f"Capability(rs={self.read_self},ra={self.read_any},ws={self.write_self},wa={self.write_any})"


def merge_capabilities(current: Capability, next_: Capability) -> Capability:
    return Capability(
        read_self=current.read_self or next_.read_self,
        read_any=current.read_any or next_.read_any,
        write_self=current.write_self or next_.write_self,
        write_any=current.write_any or next_.write_any,
    )


def operation_for_method(method: str, read_op: Operation, write_op: Operation) -> Operation:
    if method in ("GET", "HEAD"):
        return read_op
    return write_op


class Permission:
    def __init__(self, resource: str, action: str):
        self.resource = resource
        self.action = action

    def __key(self):
        return (self.resource, self.action)

    def __hash__(self):
        return hash(self.__key())

    def __eq__(self, other):
        return isinstance(other, Permission) and self.__key() == other.__key()


class Role:
    def __init__(self, name: str, permissions: Optional[set[Permission]] = None):
        self.name = name
        self.permissions = permissions or set()


_default_permissions: dict[str, list[str]] = {}


def register_default(resource: str, action: str):
    if resource not in _default_permissions:
        _default_permissions[resource] = []
    _default_permissions[resource].append(action)


def get_default_permissions() -> dict[str, list[str]]:
    return dict(_default_permissions)
