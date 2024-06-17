import asyncio
import datetime
import time
import typing as t
import sys

from fastapi import FastAPI, Request, Response

from pphoto.annots.text import (
    AnnotateRequest,
    Models,
    ImageClassificationWithMD5,
    image_endpoint as image_endpoint_impl,
)
from pphoto.db.cache import NoCache
from pphoto.utils import Lazy

MODELS = Models(NoCache(), None)
# Load models because of undiagnosed memory leak
MODELS.load()

app = FastAPI()


@app.on_event("startup")
async def on_startup() -> None:
    asyncio.create_task(check_db_connection())


async def check_db_connection() -> None:
    while True:
        Lazy.check_ttl()
        await asyncio.sleep(60)


@app.middleware("http")
async def log_metadata(request: Request, func: t.Callable[[Request], t.Awaitable[Response]]) -> Response:
    start_time = time.time()
    response = await func(request)
    print("Remote annotator server request took", request.url, time.time() - start_time, file=sys.stderr)
    return response


@app.post(
    "/annotate/image_to_text",
    response_model=ImageClassificationWithMD5,
)
def image_endpoint(image: AnnotateRequest) -> ImageClassificationWithMD5:
    now = datetime.datetime.now()
    ret = image_endpoint_impl(MODELS, image)
    after = datetime.datetime.now()
    print(after - now)
    return ret
