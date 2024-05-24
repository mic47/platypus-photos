import itertools
import typing as t
import io
from dataclasses import dataclass
import sys
import traceback
import base64

from PIL import Image
from ultralytics import YOLO
from transformers import pipeline
import requests as rq
from dataclasses_json import DataClassJsonMixin


from cache import Cache
from data_model.features import ImageClassification, BoxClassification, Classification, Box


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
    path: str
    data_base64: bytes
    gap_threshold: float
    discard_threshold: float


def fetch_ann(url: str, request: AnnotateRequest) -> ImageClassification:
    data = rq.post(url, json=request.to_dict(), timeout=60)
    return ImageClassification.from_json(data.content)


class Models:
    def __init__(self, cache: Cache[ImageClassification], remote: t.Optional[str]) -> None:
        self._cache = cache
        self.predict_model = YOLO("yolov8x.pt")
        self.classify_model = YOLO("yolov8x-cls.pt")
        self.captioner = pipeline("image-to-text", model="Salesforce/blip-image-captioning-base")
        self._version = ImageClassification.current_version()
        self._remote = remote

    def process_image_batch(
        self: "Models",
        paths: t.Iterable[str],
        gap_threshold: float = 0.2,
        discard_threshold: float = 0.1,
    ) -> t.Iterable[ImageClassification]:
        not_cached = []
        for path in paths:
            x = self._cache.get(path)
            if x is None:
                if self._remote is not None:
                    try:
                        with open(path, "rb") as f:
                            data = base64.encodebytes(f.read())
                        ret = fetch_ann(
                            self._remote, AnnotateRequest(path, data, gap_threshold, discard_threshold)
                        )
                        if ret.exception is not None:
                            print(ret.exception, file=sys.stderr)
                            print(
                                "There was an exception in remote processing -- storing it anyways.",
                                file=sys.stderr,
                            )
                        self._cache.add(ret)
                        yield ret
                    # pylint: disable = bare-except
                    except:
                        traceback.print_exc()
                        not_cached.append(path)
                else:
                    not_cached.append(path)
            else:
                yield x
        if not_cached:
            for p in self.process_image_batch_impl(
                ((x, None) for x in not_cached), gap_threshold, discard_threshold
            ):
                self._cache.add(p)
                yield p

    def process_image_data(
        self,
        request: AnnotateRequest,
    ) -> ImageClassification:
        return list(
            self.process_image_batch_impl(
                [(request.path, base64.decodebytes(request.data_base64))],
                request.gap_threshold,
                request.discard_threshold,
            )
        )[0]

    def process_image_batch_impl(
        self: "Models",
        paths: t.Iterable[t.Tuple[str, t.Optional[bytes]]],
        gap_threshold: float,
        discard_threshold: float,
    ) -> t.Iterable[ImageClassification]:
        images = [
            (path, Image.open(path) if data is None else Image.open(io.BytesIO(data))) for path, data in paths
        ]
        captions = self.captioner([image for (_, image) in images])
        results = self.predict_model([img for (_, img) in images], verbose=False)
        boxes_to_classify = []
        all_input = list(zip(images, results, captions))
        for ((path, image), result, caption) in all_input:
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
        for (path, group) in itertools.groupby(results, lambda x: t.cast(str, x[0][0])):
            visited.add(path)
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
            yield ImageClassification(path, self._version, list(captions), box_class)
        for ((path, image), captions, _) in all_input:
            if path in visited:
                continue
            visited.add(path)
            captions = set()
            for c in caption:
                gt = c.get("generated_text")
                if gt is not None:
                    captions.add(remove_consecutive_words(gt))
            yield ImageClassification(path, self._version, list(captions), [])
