import json
import typing as t
from collections import Counter
import sys
import re

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from image_annotation import ImageAnnotations

app = FastAPI()
# TODO: serve these differenty
app.mount("/static", StaticFiles(directory="/"), name="static")
templates = Jinja2Templates(directory="templates")


IMAGES: t.List[ImageAnnotations] = []
with open("output-all.jsonl") as f:
    for line in f:
        j = json.loads(line)
        if (j.get("version") or 0) != ImageAnnotations.current_version():
            continue
        IMAGES.append(ImageAnnotations.from_dict(j))


@app.get("/index.html", response_class=HTMLResponse)
async def read_item(request: Request, tag: str = "", cls: str = "", addr: str = ""):
    images = []
    tag_cnt = Counter()
    classifications_cnt = Counter()
    address_cnt = Counter()
    for image in IMAGES:
        tags = sorted(
            list(
                set(
                    classification.name.replace("_", " ").lower()
                    for boxes in image.text_classification.boxes
                    for classification in boxes.classifications
                )
            )
        )
        if tag:
            if any(tt not in tags for tt in tag.split(",") if tt):
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
            if re.search(addr, address) is None:
                continue

        images.append(
            {
                "path": image.image,
                "classifications": classifications,
                "tags": tags,
                "address": address,
            }
        )
        classifications_cnt.update(x.lower() for x in image.text_classification.captions)
        tag_cnt.update(tags)
        address_cnt.update(address_parts)
    top_tags = sorted(tag_cnt.items(), key=lambda x: -x[1])
    top_cls = sorted(classifications_cnt.items(), key=lambda x: -x[1])
    top_addr = sorted(address_cnt.items(), key=lambda x: -x[1])

    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "id": id,
            "images": images,
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
                "tag": top_tags[:5],
                "cls": top_cls[:5],
                "addr": top_addr[:5],
            },
        },
    )


def add_comma(x: str) -> str:
    if x:
        return f"{x},"
    return x
