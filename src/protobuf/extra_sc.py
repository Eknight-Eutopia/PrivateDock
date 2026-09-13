from __future__ import annotations

from google.protobuf import descriptor_pb2 as _descriptor_pb2
from google.protobuf import descriptor_pool as _descriptor_pool
from google.protobuf import message_factory as _message_factory

pool = _descriptor_pool.Default()


def _make_simple_sc(packet_id: int, fields: list[tuple[str, int, int]]):
    """
    Build a FileDescriptorProto with a single SC_{packet_id} message.
    Each field = (name, type_enum, label) where:
      type_enum: TYPE_* constants from descriptor.proto
      label: 1=optional, 2=required, 3=repeated
    """
    msg_name = f"SC_{packet_id}"
    fdp = _descriptor_pb2.FileDescriptorProto()
    fdp.name = f"{msg_name}.proto"
    fdp.package = "src"

    msg = fdp.message_type.add()
    msg.name = msg_name
    for i, (name, ftype, flabel) in enumerate(fields, start=1):
        field = msg.field.add()
        field.name = name
        field.number = i
        field.type = ftype
        field.label = flabel
        if ftype == TYPE_MESSAGE:
            dummy = fdp.message_type.add()
            dummy.name = f"_{msg_name}_{name}"
            field.type_name = f"src._{msg_name}_{name}"

    # Add to pool and create class
    fdp_bytes = fdp.SerializeToString()
    try:
        pool.AddSerializedFile(fdp_bytes)
    except Exception:
        pass  # already added or collision

    try:
        desc = pool.FindMessageTypeByName(f"src.{msg_name}")
    except KeyError:
        return None
    cls = _message_factory.GetMessageClass(desc)
    return cls


# Type constants (from descriptor.proto)
TYPE_UINT32 = 13
TYPE_INT32 = 5
TYPE_STRING = 9
TYPE_BOOL = 8
TYPE_MESSAGE = 11
TYPE_BYTES = 12

LABEL_OPTIONAL = 1
LABEL_REQUIRED = 2
LABEL_REPEATED = 3


# Register all missing SC types for remaining 22 files
_SC_TYPES: dict[int, list[tuple[str, int, int]]] = {
    70082: [("result", TYPE_UINT32, LABEL_REQUIRED),
            ("member_count", TYPE_UINT32, LABEL_OPTIONAL),
            ("join_requests", TYPE_MESSAGE, LABEL_REPEATED)],
    33046: [("result", TYPE_UINT32, LABEL_REQUIRED),
            ("awards", TYPE_MESSAGE, LABEL_REPEATED)],
    33040: [("result", TYPE_UINT32, LABEL_REQUIRED),
            ("activity_id", TYPE_UINT32, LABEL_OPTIONAL),
            ("today_task_complete_flag", TYPE_UINT32, LABEL_REPEATED),
            ("task_daily_progress", TYPE_UINT32, LABEL_REPEATED),
            ("task_unlock_activity_preview_flag", TYPE_UINT32, LABEL_REPEATED),
            ("task_fetch_list", TYPE_UINT32, LABEL_REPEATED),
            ("sign_in_time", TYPE_INT32, LABEL_OPTIONAL),
            ("sign_data", TYPE_MESSAGE, LABEL_REPEATED),
            ("elite_fleet_list", TYPE_MESSAGE, LABEL_REPEATED),
            ("ethernet_core", TYPE_UINT32, LABEL_OPTIONAL),
            ("ethernet_support", TYPE_STRING, LABEL_OPTIONAL)],
    33042: [("result", TYPE_UINT32, LABEL_REQUIRED),
            ("sign_data", TYPE_MESSAGE, LABEL_REPEATED)],
    70060: [("result", TYPE_UINT32, LABEL_REQUIRED)],
    24610: [("result", TYPE_UINT32, LABEL_REQUIRED),
            ("chapter_list", TYPE_MESSAGE, LABEL_REPEATED)],
    24616: [("result", TYPE_UINT32, LABEL_REQUIRED),
            ("drop_list", TYPE_MESSAGE, LABEL_REPEATED)],
    24602: [("result", TYPE_UINT32, LABEL_REQUIRED),
            ("config", TYPE_MESSAGE, LABEL_REPEATED)],
    24604: [("result", TYPE_UINT32, LABEL_REQUIRED),
            ("info", TYPE_MESSAGE, LABEL_REPEATED)],
    24612: [("result", TYPE_UINT32, LABEL_REQUIRED),
            ("ticket", TYPE_MESSAGE, LABEL_REPEATED)],
    24071: [("result", TYPE_UINT32, LABEL_REQUIRED)],
    26115: [("result", TYPE_UINT32, LABEL_REQUIRED),
            ("chapter_list", TYPE_MESSAGE, LABEL_REPEATED)],
    26117: [("result", TYPE_UINT32, LABEL_REQUIRED),
            ("expeditions", TYPE_MESSAGE, LABEL_REPEATED)],
    72031: [("result", TYPE_UINT32, LABEL_REQUIRED),
            ("report_event", TYPE_UINT32, LABEL_REPEATED),
            ("report_drop_list", TYPE_MESSAGE, LABEL_REPEATED),
            ("score", TYPE_UINT32, LABEL_OPTIONAL),
            ("award_list", TYPE_MESSAGE, LABEL_REPEATED),
            ("event_list", TYPE_MESSAGE, LABEL_REPEATED)],
    63330: [("ret", TYPE_UINT32, LABEL_REQUIRED),
            ("level", TYPE_UINT32, LABEL_OPTIONAL),
            ("exp", TYPE_UINT32, LABEL_OPTIONAL)],
    19493: [("info", TYPE_MESSAGE, LABEL_REPEATED),
            ("group_list", TYPE_MESSAGE, LABEL_REPEATED),
            ("rank_list", TYPE_MESSAGE, LABEL_REPEATED),
            ("military_reward_info", TYPE_MESSAGE, LABEL_REPEATED)],
    19495: [("support_info", TYPE_MESSAGE, LABEL_REPEATED)],
    19509: [("result", TYPE_UINT32, LABEL_REQUIRED),
            ("data", TYPE_MESSAGE, LABEL_REPEATED)],
    19507: [("result", TYPE_UINT32, LABEL_REQUIRED)],
    19491: [("result", TYPE_UINT32, LABEL_REQUIRED)],
    19497: [("result", TYPE_UINT32, LABEL_REQUIRED),
            ("port_list", TYPE_MESSAGE, LABEL_REPEATED),
            ("daily_task_list", TYPE_MESSAGE, LABEL_REPEATED),
            ("left_refresh_count", TYPE_UINT32, LABEL_OPTIONAL),
            ("purchase_list", TYPE_MESSAGE, LABEL_REPEATED)],
    19525: [("result", TYPE_UINT32, LABEL_REQUIRED),
            ("daily_task_list", TYPE_MESSAGE, LABEL_REPEATED)],
    19527: [("result", TYPE_UINT32, LABEL_REQUIRED)],
    23431: [("gold", TYPE_UINT32, LABEL_REQUIRED),
            ("buy_num", TYPE_UINT32, LABEL_REQUIRED),
            ("max_profit", TYPE_UINT32, LABEL_REQUIRED),
            ("acc_profit", TYPE_INT32, LABEL_REQUIRED),
            ("item_list", TYPE_UINT32, LABEL_REPEATED),
            ("acc_buy_price", TYPE_UINT32, LABEL_REQUIRED),
            ("pre_buy_state", TYPE_UINT32, LABEL_REQUIRED),
            ("pre_timestamp", TYPE_UINT32, LABEL_REQUIRED),
            ("match_time", TYPE_UINT32, LABEL_REQUIRED),
            ("is_forbidden", TYPE_UINT32, LABEL_REQUIRED),
            ("game_num", TYPE_UINT32, LABEL_REQUIRED),
            ("inactive_num", TYPE_UINT32, LABEL_REQUIRED),
            ("inactive_state", TYPE_UINT32, LABEL_REQUIRED),
            ("back_forbidden", TYPE_UINT32, LABEL_REQUIRED),
            ("acc_item_price", TYPE_UINT32, LABEL_REQUIRED),
            ("get_relief_num", TYPE_UINT32, LABEL_REQUIRED)],
}


def _register_all():
    for pid, fields in _SC_TYPES.items():
        cls = _make_simple_sc(pid, fields)
        if cls is None:
            continue
        # Register into the protobuf module
        import src.protobuf.protobuf as _pb_mod
        setattr(_pb_mod, f"SC_{pid}", cls)


_register_all()
