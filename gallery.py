import json
import typing as t
import os
from collections import Counter, defaultdict
import sys
import re

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from tqdm import tqdm

from image_annotation import ImageAnnotations

app = FastAPI()
# TODO: serve these differenty
app.mount("/static", StaticFiles(directory="static/"), name="static")
templates = Jinja2Templates(directory="templates")


IMAGES: t.List[ImageAnnotations] = []
HASH_TO_IMAGE: t.Dict[int, str] = {}

with open("output-all.jsonl") as f:
    for line in tqdm(f, desc="Loading images"):
        j = json.loads(line)
        if (j.get("version") or 0) != ImageAnnotations.current_version():
            continue
        _image = ImageAnnotations.from_dict(j)
        IMAGES.append(_image)
        HASH_TO_IMAGE[hash(_image.image)] = _image.image


@app.get(
    "/img",
    responses={
        200: {"description": "photo", "content": {"image/jpeg": {"example": "No example available."}}}
    },
)
def image_endpoint(hsh: int) -> t.Any:
    file_path = os.path.join(HASH_TO_IMAGE[hsh])
    if os.path.exists(file_path):
        # TODO: fix media type
        return FileResponse(file_path, media_type="image/jpeg", filename=file_path.split("/")[-1])
    return {"error": "File not found!"}


def in_tags(what: str, tags: t.Iterable[str]) -> bool:
    for tag in tags:
        if what in tag:
            return True
    return False


def classify_tag(value: float) -> str:
    if value >= 0.5:
        return ""
    if value >= 0.2:
        return "🤷"
    return "🗑️"


@app.get("/index.html", response_class=HTMLResponse)
@app.get("/", response_class=HTMLResponse)
async def read_item(
    request: Request, tag: str = "", cls: str = "", addr: str = "", page: int = 0, paging: int = 100
) -> HTMLResponse:
    images = []
    tag_cnt: t.Counter[str] = Counter()
    classifications_cnt: t.Counter[str] = Counter()
    address_cnt: t.Counter[str] = Counter()
    for image in IMAGES:
        tags: t.Dict[str, float] = defaultdict(lambda: 0.0)
        for boxes in image.text_classification.boxes:
            confidence = boxes.box.confidence
            for classification in boxes.classifications:
                name = classification.name.replace("_", " ").lower()
                tags[name] += confidence * classification.confidence

        if tag:
            if any(not in_tags(tt, tags.keys()) for tt in tag.split(",") if tt):
                continue
        classifications = ";".join(image.text_classification.captions).lower()
        if cls:
            if re.search(cls, classifications) is None:
                continue

        address_parts = []
        if image.address is not None:
            if image.address.name is not None:
                address_parts.append(image.address.name)
            if image.address.country is not None:
                address_parts.append(image.address.country)

        address = ", ".join(address_parts)
        if addr:
            if re.search(addr.lower(), address.lower()) is None:
                continue

        max_tag = min(1, max(tags.values(), default=1.0))
        images.append(
            {
                "hsh": hash(image.image),
                "classifications": classifications,
                "tags": [(tg, classify_tag(x / max_tag)) for tg, x in sorted(tags.items(), key=lambda x: -x[1])],
                "address": address,
            }
        )
        classifications_cnt.update(x.lower() for x in image.text_classification.captions)
        tag_cnt.update(tags.keys())
        address_cnt.update(address_parts)
    top_tags = sorted(tag_cnt.items(), key=lambda x: -x[1])
    top_cls = sorted(classifications_cnt.items(), key=lambda x: -x[1])
    top_addr = sorted(address_cnt.items(), key=lambda x: -x[1])

    if page * paging >= len(images):
        page = len(images) // paging

    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "id": id,
            "images": images[page * paging : (page + 1) * paging],
            "total": len(images),
            "page": page,
            "paging": paging,
            "input": {
                "tag": tag,
                "cls": cls,
                "addr": addr,
            },
            "inputsep": {
                "tag": add_comma(tag),
                "cls": add_comma(cls),
                "addr": add_comma(addr),
            },
            "top": {
                "tag": top_tags[:15],
                "cls": top_cls[:5],
                "addr": top_addr[:15],
            },
        },
    )


def add_comma(x: str) -> str:
    if x:
        return f"{x},"
    return x
