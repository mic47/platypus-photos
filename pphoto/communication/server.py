import asyncio
import typing as t

# pylint: disable-next = unused-import
from dataclasses_json import DataClassJsonMixin

from pphoto.communication.types import (
    SystemStatus,
    RefreshJobs,
    ImportDirectory,
    Ok,
    UNIX_CONNECTION_PATH,
    image_watcher_encode,
    image_watcher_decode_command,
    ActualResponse,
    RemoteAnnotatorRequest,
)
from pphoto.utils import assert_never
from pphoto.utils.alive import get_state
from pphoto.utils.progress_bar import get_bars


async def _image_watcher_server_loop(
    reader: asyncio.StreamReader,
    writer: asyncio.StreamWriter,
    refresh_jobs_queue: asyncio.Queue[RefreshJobs],
    import_directory_queue: asyncio.Queue[ImportDirectory],
) -> None:
    try:
        while True:
            data = await reader.readline()
            if not data.strip():
                return
            decoded = image_watcher_decode_command(data)
            if decoded.t == "GetSystemStatus":
                state = get_state()
                writer.write(image_watcher_encode(SystemStatus(get_bars(), state)).encode("utf-8"))
                writer.write(b"\n")
            elif decoded.t == "RefreshJobs":
                refresh_jobs_queue.put_nowait(decoded)
                writer.write(image_watcher_encode(Ok()).encode("utf-8"))
                writer.write(b"\n")
            elif decoded.t == "ImportDirectory":
                import_directory_queue.put_nowait(decoded)
                writer.write(image_watcher_encode(Ok()).encode("utf-8"))
                writer.write(b"\n")
            else:
                assert_never(decoded.t)
            await writer.drain()
    finally:
        writer.close()


async def start_image_server_loop(
    refresh_jobs_queue: asyncio.Queue[RefreshJobs],
    import_directory_queue: asyncio.Queue[ImportDirectory],
    path: str = UNIX_CONNECTION_PATH,
) -> None:
    await asyncio.start_unix_server(
        lambda a, b: _image_watcher_server_loop(a, b, refresh_jobs_queue, import_directory_queue), path
    )


Request = t.TypeVar("Request", bound="DataClassJsonMixin")


class ConnectedComputeResouce(t.Generic[Request]):
    def __init__(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
    ) -> None:
        self._reader = reader
        self._writer = writer

    async def __call__(self, request: Request) -> ActualResponse:
        try:
            self._writer.write(request.to_json().encode("utf-8"))
            self._writer.write_eof()
            await self._writer.drain()
            line = await self._reader.read()
            if not line.strip():
                # pylint: disable-next = broad-exception-raised
                raise Exception("Empty response")
            return ActualResponse.from_json(line)
        # pylint: disable-next=broad-exception-caught
        except Exception as e:
            return ActualResponse.from_exception(e)
        finally:
            self._writer.close()


RemoteExecutorQueue = asyncio.Queue[ConnectedComputeResouce[RemoteAnnotatorRequest]]


async def start_annotation_remote_worker_loop(
    worker_queue: asyncio.Queue[ConnectedComputeResouce[Request]],
    port: int,
) -> None:
    await asyncio.start_server(
        lambda a, b: worker_queue.put_nowait(ConnectedComputeResouce(a, b)), "0.0.0.0", port
    )
