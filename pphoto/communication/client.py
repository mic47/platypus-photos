import asyncio

from pphoto.communication.types import (
    SystemStatus,
    UNIX_CONNECTION_PATH,
    GetSystemStatus,
    image_watcher_encode,
    image_watcher_decode_response,
)
from pphoto.utils import assert_never


async def get_system_status() -> SystemStatus:
    reader, writer = await asyncio.open_unix_connection(UNIX_CONNECTION_PATH)
    writer.write(image_watcher_encode(GetSystemStatus()).encode("utf-8"))
    writer.write(b"\n")
    await writer.drain()
    try:
        line = await reader.readline()
        if not line.strip():
            # pylint: disable-next = broad-exception-raised
            raise Exception("Server didn't return anything")
        response = image_watcher_decode_response(line)
        if response.t == "SystemStatus":
            return response
        assert_never(response.t)
    finally:
        writer.close()
