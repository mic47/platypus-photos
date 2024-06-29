import asyncio

from pphoto.communication.types import (
    SystemStatus,
    RefreshJobs,
    UNIX_CONNECTION_PATH,
    GetSystemStatus,
    image_watcher_encode,
    image_watcher_decode_response,
    ImageWatcherResponses,
    Ok,
)


class UnexpectedResponseFromServer(Exception):
    def __init__(self, reason: str, response: ImageWatcherResponses):
        super().__init__(self, f"Unexpected response from server, beacause {reason}. Response: {response}")


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
        raise UnexpectedResponseFromServer("should receive SystemStatus", response)
    finally:
        writer.close()


async def refresh_jobs(job_id: int) -> Ok:
    reader, writer = await asyncio.open_unix_connection(UNIX_CONNECTION_PATH)
    writer.write(image_watcher_encode(RefreshJobs(job_id)).encode("utf-8"))
    writer.write(b"\n")
    await writer.drain()
    try:
        line = await reader.readline()
        if not line.strip():
            # pylint: disable-next = broad-exception-raised
            raise Exception("Server didn't return anything")
        response = image_watcher_decode_response(line)
        if response.t == "Ok":
            return response
        raise UnexpectedResponseFromServer("should receive Ok", response)
    finally:
        writer.close()
