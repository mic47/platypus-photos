from __future__ import annotations

import asyncio
import base64
import datetime
import io
import os
import itertools
import multiprocessing
import sys
import traceback
import typing as t

from PIL import Image, ImageFile


from pphoto.data_model.base import (
    WithMD5,
    PathWithMd5,
)
from pphoto.data_model.text import (
    ImageClassification,
    BoxClassification,
    Classification,
    Box,
)
from pphoto.db.types import Cache, NoCache
from pphoto.communication.types import (
    TextAnnotationRequest,
    ImageClassificationWithMD5,
    Error,
    RemoteAnnotatorRequest,
)
from pphoto.communication.server import RemoteExecutorQueue
from pphoto.utils import Lazy, assert_never

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


def image_endpoint(models: Models, image: TextAnnotationRequest) -> ImageClassificationWithMD5:
    try:
        x = models.process_image_data(image)
        return ImageClassificationWithMD5("ImageClassificationWithMD5", x.md5, x.version, x.p, x.e)
    # pylint: disable-next = broad-exception-caught
    except Exception as e:
        traceback.print_exc()
        print("Error processing file:", image.path, file=sys.stderr)
        return ImageClassificationWithMD5(
            "ImageClassificationWithMD5",
            image.path.md5,
            ImageClassification.current_version(),
            None,
            Error.from_exception(e),
        )


async def fetch_ann(
    queue: RemoteExecutorQueue, request: TextAnnotationRequest
) -> WithMD5[ImageClassification]:
    annotator = await queue.get()
    response = await annotator(RemoteAnnotatorRequest(request))
    if response.error is not None:
        raise response.error
    if response.response is None:
        # pylint: disable-next = broad-exception-raised
        raise Exception("No error and no payload")
    if response.response.p.t == "ImageClassificationWithMD5":
        return WithMD5(
            response.response.p.md5, response.response.p.version, response.response.p.p, response.response.p.e
        )
    if response.response.p.t == "FaceEmbeddingsWithMD5":
        # pylint: disable-next = broad-exception-raised
        raise Exception(f"Unexpected response from the server {response.response.p.t}")
    assert_never(response.response.p.t)


T = t.TypeVar("T")


class YoloProtocol(t.Protocol):
    def __call__(self, source: t.List[Image.Image], verbose: bool) -> t.Any: ...  # noqa: F841


class PipelineProtocol(t.Protocol):
    def __call__(self, source: t.List[Image.Image]) -> t.Any: ...  # noqa: F841


def cast(x: t.Any, type_: t.Type[T]) -> T:
    if not isinstance(x, type_):
        # pylint: disable-next = broad-exception-raised
        raise Exception(f"Expected value of type '{type_}', got value '{x}'")
    return x


def yolo_model(model: str) -> YoloProtocol:
    # pylint: disable-next = import-outside-toplevel,import-error
    import ultralytics

    ret = ultralytics.YOLO(model)
    return t.cast(YoloProtocol, ret)


def image_to_text_model() -> PipelineProtocol:
    # pylint: disable-next = import-outside-toplevel,import-error,unused-import
    import transformers  # noqa: F401

    # pylint: disable-next = import-outside-toplevel,import-error
    from transformers import pipeline

    ret = pipeline("image-to-text", model="Salesforce/blip-image-captioning-base")
    return t.cast(PipelineProtocol, ret)


def _close_pool(pool: "multiprocessing.pool.Pool") -> None:
    pool.close()
    pool.terminate()


_POOL_MODELS = Lazy(lambda: Models(NoCache(), remote=None))


def _process_image_in_pool(
    path: PathWithMd5, data: t.Optional[bytes], gap_threshold: float, discard_threshold: float
) -> WithMD5[ImageClassification]:
    return list(
        _POOL_MODELS.get().process_image_batch_impl(
            ((x, data) for x in [path]), gap_threshold, discard_threshold
        )
    )[0]


class Models:
    def __init__(self, cache: Cache[ImageClassification], remote: t.Optional[RemoteExecutorQueue]) -> None:
        self._cache = cache
        self._predict_model = Lazy(lambda: yolo_model("yolov8x.pt"))
        self._classify_model = Lazy(lambda: yolo_model("yolov8x-cls.pt"))
        self._captioner = Lazy(image_to_text_model)
        self._version = ImageClassification.current_version()
        ttl = datetime.timedelta(seconds=5 * 60)
        self._pool = Lazy(
            # pylint: disable-next = consider-using-with
            lambda: multiprocessing.Pool(processes=1),
            ttl=ttl,
            destructor=_close_pool,
        )
        self._remote = remote
        self._last_remote_request = datetime.datetime.now()

    def load(self) -> None:
        image = [Image.new(mode="RGB", size=(200, 200))]
        self._predict_model.get()(image, verbose=False)
        self._classify_model.get()(image, verbose=False)
        self._captioner.get()(image)

    def _remote_can_be_available(self) -> bool:
        if self._remote is None:
            return False
        if not self._remote.empty():
            return True
        if datetime.datetime.now() - self._last_remote_request < datetime.timedelta(seconds=300):
            return True
        return False

    async def process_file(
        self: "Models",
        path: PathWithMd5,
        gap_threshold: float = 0.2,
        discard_threshold: float = 0.1,
    ) -> WithMD5[ImageClassification]:
        """
        Used externally to process file
        """
        x = self._cache.get(path.md5)
        if x is not None and x.payload is not None:
            return x.payload
        return self._cache.add(await self._process_image(path, None, gap_threshold, discard_threshold))

    async def _process_image(
        self: "Models",
        path: PathWithMd5,
        data: t.Optional[bytes],
        gap_threshold: float,
        discard_threshold: float,
    ) -> WithMD5[ImageClassification]:
        if data is None and os.path.getsize(path.path) > 100_000_000:
            return WithMD5(path.md5, self._version, None, Error("SkippingHugeFile", None, None))
        if self._remote is not None and self._remote_can_be_available():
            try:
                if data is None:
                    with open(path.path, "rb") as f:
                        data = base64.encodebytes(f.read())
                ret = await asyncio.wait_for(
                    fetch_ann(
                        self._remote,
                        TextAnnotationRequest(
                            "TextAnnotationRequest",
                            path,
                            data.decode("utf-8"),
                            gap_threshold,
                            discard_threshold,
                        ),
                    ),
                    600,
                )
                self._last_remote_request = datetime.datetime.now()
                return ret
            # pylint: disable-next = bare-except
            except:
                traceback.print_exc()
        p = self._pool.get().apply(_process_image_in_pool, (path, data, gap_threshold, discard_threshold))
        return p

    def process_image_data(
        self,
        request: TextAnnotationRequest,
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
        captions = self._captioner.get()([image for (_, image) in images])
        results = self._predict_model.get()([img for (_, img) in images], verbose=False)
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
                    self._classify_model.get()(
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
