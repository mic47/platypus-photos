import asyncio
import typing as t

from pphoto.communication.types import (
    SystemStatus,
    RefreshJobs,
    UNIX_CONNECTION_PATH,
    GetSystemStatus,
    image_watcher_encode,
    image_watcher_decode_response,
    ImageWatcherResponses,
    ImageWatcherCommands,
    Ok,
)


class UnexpectedResponseFromServer(Exception):
    def __init__(self, reason: str, response: ImageWatcherResponses):
        super().__init__(self, f"Unexpected response from server, beacause {reason}. Response: {response}")


R = t.TypeVar("R")


async def get_system_status() -> SystemStatus:
    return await request_response(GetSystemStatus(), SystemStatus)


async def refresh_jobs(job_id: int) -> Ok:
    return await request_response(RefreshJobs(job_id), Ok)


async def request_response(request: ImageWatcherCommands, expected_type: t.Type[R]) -> R:
    reader, writer = await asyncio.open_unix_connection(UNIX_CONNECTION_PATH)
    writer.write(image_watcher_encode(request).encode("utf-8"))
    writer.write(b"\n")
    await writer.drain()
    try:
        line = await reader.readline()
        if not line.strip():
            # pylint: disable-next = broad-exception-raised
            raise Exception("Server didn't return anything")
        response = image_watcher_decode_response(line)
        if isinstance(response, expected_type):
            return t.cast(R, response)
        raise UnexpectedResponseFromServer(f"should receive {expected_type.__name__}", response)
    finally:
        writer.close()
