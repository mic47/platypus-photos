import argparse
import asyncio
import multiprocessing
import time
import sys

from pphoto.annots.text import (
    Models,
    image_endpoint as image_endpoint_impl,
)
from pphoto.annots.face import face_embeddings_endpoint
from pphoto.communication.types import (
    RemoteAnnotatorRequest,
    RemoteAnnotatorResponse,
    ActualResponse,
)
from pphoto.communication.client import async_compute_client_loop
from pphoto.db.types import NoCache
from pphoto.utils import Lazy, assert_never, log_error

MODELS = Models(NoCache(), None)


async def check_db_connection() -> None:
    while True:
        Lazy.check_ttl()
        await asyncio.sleep(60)


def annotator_func(request: RemoteAnnotatorRequest) -> ActualResponse:
    start_time = time.time()
    try:
        if request.p.t == "TextAnnotationRequest":
            return ActualResponse(RemoteAnnotatorResponse(image_endpoint_impl(MODELS, request.p)), None)
        if request.p.t == "FaceEmbeddingsRequest":
            return ActualResponse(RemoteAnnotatorResponse(face_embeddings_endpoint(request.p)), None)
        assert_never(request.p.t)
    # pylint: disable-next=broad-exception-caught
    except Exception as e:
        log_error(e, "Unable to process request", request.p.t)
        return ActualResponse.from_exception(e)
    finally:
        print("Remote annotator server request took", request.p.t, time.time() - start_time, file=sys.stderr)


async def worker(_worker_id: int, host: str, port: int) -> None:
    tasks = []
    tasks.append(asyncio.create_task(check_db_connection()))
    tasks.append(
        asyncio.create_task(async_compute_client_loop(annotator_func, RemoteAnnotatorRequest, host, port))
    )
    await asyncio.gather(*tasks, return_exceptions=True)


def worker_run(worker_id: int, host: str, port: int) -> None:
    asyncio.run(worker(worker_id, host, port))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--host", type=str, required=True)
    parser.add_argument("--port", type=int, default=8001)
    args = parser.parse_args()
    processes = []
    try:
        for i in range(args.workers):
            processes.append(multiprocessing.Process(target=worker_run, args=(i, args.host, args.port)))
            processes[-1].start()
        for p in processes:
            p.join()
    finally:
        for p in processes:
            p.kill()


if __name__ == "__main__":
    main()
