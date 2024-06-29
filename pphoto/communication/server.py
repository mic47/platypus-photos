import asyncio

from pphoto.communication.types import (
    SystemStatus,
    RefreshJobs,
    ImportDirectory,
    Ok,
    UNIX_CONNECTION_PATH,
    image_watcher_encode,
    image_watcher_decode_command,
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
