import typing as t
import datetime

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from image_to_text import AnnotateRequest, Models, ImageClassification
from cache import NoCache

MODELS = Models(NoCache(), None)

app = FastAPI()


@app.post(
    "/annotate/image_to_text",
    response_model=ImageClassification,
)
def image_endpoint(image: AnnotateRequest) -> ImageClassification:
    now = datetime.datetime.now()
    ret = MODELS.process_image_data(image)
    after = datetime.datetime.now()
    print(after - now)
    return ret
