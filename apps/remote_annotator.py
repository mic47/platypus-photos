import asyncio
import dataclasses
import datetime
import sys
import traceback
import typing as t

from fastapi import FastAPI

from annots.text import AnnotateRequest, Models, ImageClassification
from data_model.features import Error
from db.cache import NoCache
from utils import Lazy

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


@dataclasses.dataclass
class ImageClassificationWithMD5:
    md5: str
    version: int
    p: t.Optional[ImageClassification]
    e: t.Optional[Error]
    # TODO: make test that make sure it's same as WithMD5[ImageClassification]


@app.post(
    "/annotate/image_to_text",
    response_model=ImageClassificationWithMD5,
)
def image_endpoint(image: AnnotateRequest) -> ImageClassificationWithMD5:
    now = datetime.datetime.now()
    try:
        x = MODELS.process_image_data(image)
        ret = ImageClassificationWithMD5(x.md5, x.version, x.p, x.e)
    # pylint: disable = broad-exception-caught
    except Exception as e:
        ret = ImageClassificationWithMD5(
            image.path.md5,
            ImageClassification.current_version(),
            None,
            Error.from_exception(e),
        )
        traceback.print_exc()
        print("Error processing file:", image.path, file=sys.stderr)
    after = datetime.datetime.now()
    print(after - now)
    return ret
