from dataclasses import dataclass
import base64
import io
import json
import os
import sys
import itertools
import traceback
import typing as t

import aiohttp as aioh
from dataclasses_json import DataClassJsonMixin
from PIL import Image, ImageFile
from transformers import pipeline
from ultralytics import YOLO


from data_model.features import (
    ImageClassification,
    BoxClassification,
    Classification,
    Box,
    WithMD5,
    PathWithMd5,
    Error,
)
from db.cache import Cache

ImageFile.LOAD_TRUNCATED_IMAGES = True


def remove_consecutive_words(sentence: str) -> str:
    words = sentence.split(" ")
    out = []
    prev_word = ""
    for word in words:
        if not word:
            continue
        if word == prev_word:
            continue
        prev_word = word
        out.append(word)
    return " ".join(out)


@dataclass
class AnnotateRequest(DataClassJsonMixin):
    path: PathWithMd5
    data_base64: str
    gap_threshold: float
    discard_threshold: float


async def fetch_ann(
    session: aioh.ClientSession, url: str, request: AnnotateRequest
) -> WithMD5[ImageClassification]:
    async with aioh.ClientSession() as session:
        async with session.post(url, json=request.to_dict(), timeout=600) as data:
            dct = json.loads(await data.text())
            error = None
            e = dct.get("e")
            if e is not None:
                error = Error.from_json(e)
            payload = None
            p = dct.get("d")
            if p is not None:
                payload = ImageClassification.from_dict(p)
            return WithMD5(cast(dct["md5"], str), cast(dct["version"], int), payload, error)


T = t.TypeVar("T")


def cast(x: t.Any, type_: t.Type[T]) -> T:
    if not isinstance(x, type_):
        # pylint: disable = broad-exception-raised
        raise Exception(f"Expected value of type '{type_}', got value '{x}'")
    return x


class Models:
    def __init__(self, cache: Cache[ImageClassification], remote: t.Optional[str]) -> None:
        self._cache = cache
        self.predict_model = YOLO("yolov8x.pt")
        self.classify_model = YOLO("yolov8x-cls.pt")
        self.captioner = pipeline("image-to-text", model="Salesforce/blip-image-captioning-base")
        self._version = ImageClassification.current_version()
        self._remote = remote

    async def process_image(
        self: "Models",
        session: aioh.ClientSession,
        path: PathWithMd5,
        gap_threshold: float = 0.2,
        discard_threshold: float = 0.1,
    ) -> WithMD5[ImageClassification]:
        x = self._cache.get(path.md5)
        if x is None or x.payload is None:
            if os.path.getsize(path.path) > 10_000_000:
                for _i in range(5):
                    print(f"Warning large file {path.path}", file=sys.stderr)
            if os.path.getsize(path.path) > 100_000_000:
                for _i in range(5):
                    print(f"ERROR huge file {path.path}", file=sys.stderr)
                return self._cache.add(
                    WithMD5(path.md5, self._version, None, Error("SkippingHugeFile", None, None))
                )
            if self._remote is not None:
                try:
                    with open(path.path, "rb") as f:
                        data = base64.encodebytes(f.read())
                    ret = await fetch_ann(
                        session,
                        self._remote,
                        AnnotateRequest(path, data.decode("utf-8"), gap_threshold, discard_threshold),
                    )
                    return self._cache.add(ret)
                # pylint: disable = bare-except
                except:
                    traceback.print_exc()
        else:
            return x.payload
        for p in self.process_image_batch_impl(((x, None) for x in [path]), gap_threshold, discard_threshold):
            return self._cache.add(p)
        assert False, "Process image batch retruned empty output. This should never happen"

    def process_image_data(
        self,
        request: AnnotateRequest,
    ) -> WithMD5[ImageClassification]:
        return list(
            self.process_image_batch_impl(
                [(request.path, base64.decodebytes(request.data_base64.encode("utf-8")))],
                request.gap_threshold,
                request.discard_threshold,
            )
        )[0]

    def process_image_batch_impl(
        self: "Models",
        paths: t.Iterable[t.Tuple[PathWithMd5, t.Optional[bytes]]],
        gap_threshold: float,
        discard_threshold: float,
    ) -> t.Iterable[WithMD5[ImageClassification]]:
        images = [
            (path, Image.open(path.path) if data is None else Image.open(io.BytesIO(data)))
            for path, data in paths
        ]
        captions = self.captioner([image for (_, image) in images])
        results = self.predict_model([img for (_, img) in images], verbose=False)
        boxes_to_classify = []
        all_input = list(zip(images, results, captions))
        for (path, image), result, caption in all_input:
            names = result.names
            for box_id, box in enumerate(result.boxes):
                classification = names[int(box.cls[0])]
                confidence = float(box.conf[0])
                xyxy = list(float(x) for x in box.xyxy[0])
                boxes_to_classify.append(
                    (
                        path,
                        image,
                        box_id,
                        caption,
                        Box(classification, confidence, xyxy),
                    )
                )

        if boxes_to_classify:
            results = list(
                zip(
                    boxes_to_classify,
                    self.classify_model(
                        [
                            image.crop(
                                (
                                    int(box.xyxy[0]),
                                    int(box.xyxy[1]),
                                    int(box.xyxy[2]),
                                    int(box.xyxy[3]),
                                )
                            )
                            for (_, image, _, _, box) in boxes_to_classify
                        ],
                        verbose=False,
                    ),
                )
            )
        else:
            results = []

        visited = set()
        for path, group in itertools.groupby(results, lambda x: t.cast(PathWithMd5, x[0][0])):
            visited.add(path.path)
            box_class = []
            captions = set()
            for (_, _image, box_id, caption, box), result in group:
                for c in caption:
                    gt = c.get("generated_text")
                    if gt is not None:
                        captions.add(remove_consecutive_words(gt))
                names = result.names
                classifications = []
                prev_conf = 0.0
                for index, conf in zip(result.probs.top5, result.probs.top5conf):
                    if conf < discard_threshold:
                        continue
                    if prev_conf - conf > gap_threshold:
                        break
                    prev_conf = conf
                    classifications.append(Classification(names[index], float(conf)))
                box_class.append(BoxClassification(box, classifications))
            yield WithMD5(path.md5, self._version, ImageClassification(list(captions), box_class), None)
        for (path, image), captions, _ in all_input:
            if path.path in visited:
                continue
            visited.add(path.path)
            captions = set()
            for c in caption:
                gt = c.get("generated_text")
                if gt is not None:
                    captions.add(remove_consecutive_words(gt))
            yield WithMD5(path.md5, self._version, ImageClassification(list(captions), []), None)
