from __future__ import annotations

import asyncio
import typing as t
import sys
import time

from PIL import ImageFile

from fastapi import FastAPI, Request, Response
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from pphoto.utils import Lazy

from .common import custom_generate_unique_id, DB

from .annotations import router as annotations_router
from .export import router as export_router
from .geo import router as geo_router
from .media import router as media_router
from .web import router as web_router

ImageFile.LOAD_TRUNCATED_IMAGES = True

app = FastAPI(generate_unique_id_function=custom_generate_unique_id)
app.mount("/static", StaticFiles(directory="static/"), name="static")
app.mount("/css", StaticFiles(directory="css/"), name="static")

app.include_router(annotations_router)
app.include_router(export_router)
app.include_router(geo_router)
app.include_router(media_router)
app.include_router(web_router)


@app.on_event("startup")
async def on_startup() -> None:
    asyncio.create_task(check_db_connection())


async def check_db_connection() -> None:
    await asyncio.sleep(1)
    while True:
        DB.get().check_unused()
        Lazy.check_ttl()
        await asyncio.sleep(10)


@app.middleware("http")
async def log_metadata(request: Request, func: t.Callable[[Request], t.Awaitable[Response]]) -> Response:
    start_time = time.time()
    response = await func(request)
    took = time.time() - start_time
    print("Request took ", request.url, took, file=sys.stderr)
    return response


@app.get("/index.html")
@app.get("/")
async def read_index() -> FileResponse:
    return FileResponse("static/index.html")
