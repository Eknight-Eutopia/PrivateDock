"""Protocol constants for the client.

Import the submodule that owns the constants::

    from src.consts.drop_types import DROP_TYPE_ITEM
    from src.consts.attire import ATTIRE_TYPE_ICON_FRAME

This package deliberately does NOT re-export them. The flat namespace used to be
assembled with ``from .<module> import *``, which no caller ever used (all
callers import from a submodule) while forcing every ``src.consts.<module>``
import to pull in all the sibling modules.

These values are fixed by the client protocol — never duplicate them locally,
and never "tune" them: the client is the source of truth (client ``const.lua``).
"""
