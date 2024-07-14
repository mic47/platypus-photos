import asyncio
import typing as t
import sys

# pylint: disable-next = unused-import
from dataclasses_json import DataClassJsonMixin

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
    ActualResponse,
)
from pphoto.utils import log_error


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
    writer.write_eof()
    await writer.drain()
    try:
        line = await reader.read()
        if not line.strip():
            # pylint: disable-next = broad-exception-raised
            raise Exception("Server didn't return anything")
        response = image_watcher_decode_response(line)
        if isinstance(response, expected_type):
            return t.cast(R, response)
        raise UnexpectedResponseFromServer(f"should receive {expected_type.__name__}", response)
    finally:
        writer.close()


Request = t.TypeVar("Request", bound="DataClassJsonMixin")
Response = t.TypeVar("Response", bound="DataClassJsonMixin")


async def async_compute_client_loop(
    func: t.Callable[[Request], ActualResponse],
    request_parser: t.Type[Request],
    host: str,
    port: int,
) -> None:
    unable_to_connect_sleep = 1
    while True:
        try:
            try:
                print("Connecting", file=sys.stderr)
                reader, writer = await asyncio.open_connection(host, port)
                print("Connected", file=sys.stderr)
                unable_to_connect_sleep = 1
            # pylint: disable-next=broad-exception-caught
            except Exception as e:
                log_error(e, "Unable to connect to", host, port)
                print("Sleeping for", unable_to_connect_sleep, file=sys.stderr)
                await asyncio.sleep(unable_to_connect_sleep)
                unable_to_connect_sleep *= 2
                unable_to_connect_sleep = min(unable_to_connect_sleep, 120)
                continue
            try:
                line = await reader.read()
                if not line.strip():
                    # pylint: disable-next = broad-exception-raised
                    raise Exception("Empty request")
                request = request_parser.from_json(line)
                response = func(request)
                writer.write(response.to_json().encode("utf-8"))
                writer.write_eof()
                await writer.drain()
            # pylint: disable-next = broad-exception-caught
            except Exception as e:
                log_error(e, "Error while processing request")
                writer.write(ActualResponse.from_exception(e).to_json().encode("utf-8"))
                writer.write_eof()
                await writer.drain()
            finally:
                writer.close()
        # pylint: disable-next = broad-exception-caught
        except Exception as e:
            log_error(e, "Unexpected Error while processing request")
