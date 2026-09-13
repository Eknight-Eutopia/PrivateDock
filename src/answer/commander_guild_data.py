import asyncio
from typing import Optional

from src.connection.client import Client
from src.db.store import NotFoundError
from src.orm.guild_core import get_guild_for_commander, list_guild_members
from src.answer.guild.helpers import build_guild_base_info, build_guild_expansion_info, build_guild_member_info
from src.protobuf import protobuf
from src.logger.logger import log_event, LOG_LEVEL_ERROR


def handle_commander_guild_data(_buffer: bytes, client: Client) -> tuple[int, int, Optional[Exception]]:
    packet_id = 60000

    try:
        guild = get_guild_for_commander(client.commander.commander_id)
    except NotFoundError:
        guild = None
    except Exception as e:
        log_event("Answer", "commander_guild_data", f"Error: {e}", LOG_LEVEL_ERROR)
        return 0, packet_id, e

    response = protobuf.SC_60000()
    guild_info = protobuf.GUILD_INFO()
    guild_info.base.CopyFrom(build_guild_base_info(guild))
    guild_info.guild_ex.CopyFrom(build_guild_expansion_info(guild))

    if guild is not None:
        try:
            guild_members = list_guild_members(guild.id)
            for member in guild_members:
                guild_info.member.append(build_guild_member_info(member))
        except Exception as e:
            log_event("Answer", "commander_guild_data", f"guild_members Error: {e}", LOG_LEVEL_ERROR)

    response.guild.CopyFrom(guild_info)
    asyncio.create_task(client.send_message(packet_id, response))
    return 0, packet_id, None
