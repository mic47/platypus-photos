from __future__ import annotations

import asyncio
import base64
import datetime as dt
import io
import multiprocessing
import os
import traceback
import typing as t

from PIL import Image as PILImage, ImageOps
import numpy as np

from pphoto.data_model.base import PathWithMd5, WithMD5, Error
from pphoto.data_model.face import FaceEmbeddings, Face, ImageResolution, Position
from pphoto.db.cache import Cache
from pphoto.communication.server import RemoteExecutorQueue
from pphoto.communication.types import FaceEmbeddingsRequest, FaceEmbeddingsWithMD5, RemoteAnnotatorRequest
from pphoto.utils import Lazy, assert_never, log_error


def _close_pool(pool: "multiprocessing.pool.Pool") -> None:
    pool.close()
    pool.terminate()


def face_embeddings_endpoint(request: FaceEmbeddingsRequest) -> FaceEmbeddingsWithMD5:
    try:
        x = process_image_impl(request.path, base64.decodebytes(request.data_base64.encode("utf-8")))
        return FaceEmbeddingsWithMD5("FaceEmbeddingsWithMD5", x.md5, x.version, x.p, x.e)
    # pylint: disable-next = broad-exception-caught
    except Exception as e:
        log_error(e, "Error finding face embeddings in file", request.path)
        return FaceEmbeddingsWithMD5(
            "FaceEmbeddingsWithMD5",
            request.path.md5,
            FaceEmbeddings.current_version(),
            None,
            Error.from_exception(e),
        )


async def fetch_ann(queue: RemoteExecutorQueue, request: FaceEmbeddingsRequest) -> WithMD5[FaceEmbeddings]:
    annotator = await queue.get()
    response = await annotator(RemoteAnnotatorRequest(request))
    if response.error is not None:
        raise response.error
    if response.response is None:
        # pylint: disable-next = broad-exception-raised
        raise Exception("No error and no payload")
    if response.response.p.t == "FaceEmbeddingsWithMD5":
        return WithMD5(
            response.response.p.md5, response.response.p.version, response.response.p.p, response.response.p.e
        )
    if response.response.p.t == "ImageClassificationWithMD5":
        # pylint: disable-next = broad-exception-raised
        raise Exception(f"Unexpected response from the server {response.response.p.t}")
    assert_never(response.response.p.t)


class FaceEmbeddingsAnnotator:
    def __init__(self, cache: Cache[FaceEmbeddings], remote: t.Optional[RemoteExecutorQueue]) -> None:
        self._cache = cache
        self._version = FaceEmbeddings.current_version()
        ttl = dt.timedelta(seconds=5 * 60)
        self._pool = Lazy(
            # pylint: disable-next = consider-using-with
            lambda: multiprocessing.Pool(processes=1),
            ttl=ttl,
            destructor=_close_pool,
        )
        self._remote = remote
        self._last_remote_request = dt.datetime.now()

    def _remote_can_be_available(self) -> bool:
        if self._remote is None:
            return False
        if not self._remote.empty():
            return True
        if dt.datetime.now() - self._last_remote_request < dt.timedelta(seconds=300):
            return True
        return False

    async def process_image(
        self,
        path: PathWithMd5,
    ) -> WithMD5[FaceEmbeddings]:
        x = self._cache.get(path.md5)
        if x is None or x.payload is None:
            if os.path.getsize(path.path) > 100_000_000:
                return self._cache.add(
                    WithMD5(path.md5, self._version, None, Error("SkippingHugeFile", None, None))
                )
            if self._remote is not None and self._remote_can_be_available():
                try:
                    with open(path.path, "rb") as f:
                        data = base64.encodebytes(f.read())
                    ret = await asyncio.wait_for(
                        fetch_ann(
                            self._remote,
                            FaceEmbeddingsRequest(
                                "FaceEmbeddingsRequest",
                                path,
                                data.decode("utf-8"),
                            ),
                        ),
                        600,
                    )
                    self._last_remote_request = dt.datetime.now()
                    return self._cache.add(ret)
                # pylint: disable-next = bare-except
                except:
                    traceback.print_exc()
        else:
            return x.payload
        p = self._pool.get().apply(process_image_impl, (path, None))
        return self._cache.add(p)


def process_image_impl(
    path: PathWithMd5,
    data: t.Optional[bytes],
) -> WithMD5[FaceEmbeddings]:
    # pylint: disable-next = import-outside-toplevel,import-error
    import face_recognition

    image = PILImage.open(path.path) if data is None else PILImage.open(io.BytesIO(data))
    ImageOps.exif_transpose(image, in_place=True)
    image = image.convert("RGB")
    img = np.array(image)
    (w, h) = image.size
    resolution = ImageResolution(w, h)
    locations = face_recognition.face_locations(img)
    faces = []
    for location, embedding_ndarray in zip(locations, face_recognition.face_encodings(img, locations)):
        (top, right, bottom, left) = t.cast(t.Tuple[int, int, int, int], location)
        faces.append(
            Face(
                Position(left, top, right, bottom),
                t.cast(np.ndarray[t.Literal[128], np.dtype[np.float64]], embedding_ndarray).tolist(),
            )
        )
    return WithMD5(path.md5, FaceEmbeddings.current_version(), FaceEmbeddings(resolution, faces), None)


def process_image_in_pool(path: PathWithMd5) -> WithMD5[FaceEmbeddings]:
    return process_image_impl(path, None)
