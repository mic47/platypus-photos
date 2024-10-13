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
from pphoto.data_model.manual import ManualIdentity
from pphoto.db.cache import Cache
from pphoto.communication.server import RemoteExecutorQueue
from pphoto.communication.types import FaceEmbeddingsRequest, FaceEmbeddingsWithMD5, RemoteAnnotatorRequest
from pphoto.utils import Lazy, assert_never, log_error
from pphoto.utils.files import supported_media_class, SupportedMediaClass
from pphoto.utils.video import get_video_frames, VideoFrame


def _close_pool(pool: "multiprocessing.pool.Pool") -> None:
    pool.close()
    pool.terminate()


def face_embeddings_endpoint(request: FaceEmbeddingsRequest) -> FaceEmbeddingsWithMD5:
    try:
        x = _process_image_impl(
            request.path,
            base64.decodebytes(request.data_base64.encode("utf-8")),
            request.pts,
            request.for_positions,
        )
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

    async def add_faces(
        self, path: PathWithMd5, identities: t.List[ManualIdentity]
    ) -> WithMD5[FaceEmbeddings]:
        # TODO: resolve this for video, or make it not possible for video
        existing = self._cache.get(path.md5)
        if existing is None or existing.payload is None or existing.payload.p is None:
            to_compute = identities
        else:
            existing_positions = set(x.position for x in existing.payload.p.faces)
            to_compute = [identity for identity in identities if identity.position not in existing_positions]
            if not to_compute:
                return existing.payload

        if os.path.getsize(path.path) > 100_000_000:
            if existing is not None and existing.payload is not None:
                return existing.payload
            return self._cache.add(
                WithMD5(path.md5, self._version, None, Error("SkippingHugeFile", None, None))
            )
        to_return = None
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
                            [x.position for x in to_compute],
                            data.decode("utf-8"),
                            None,  # TODO: is this correct?
                        ),
                    ),
                    600,
                )
                self._last_remote_request = dt.datetime.now()
                to_return = self._cache.add(ret)
            # pylint: disable-next = bare-except
            except:
                traceback.print_exc()
        if to_return is None:
            to_return = self._pool.get().apply(
                _process_image_impl, (path, None, [x.position for x in to_compute])
            )

        if existing is None or existing.payload is None or existing.payload.p is None:
            return self._cache.add(to_return)

        if to_return.p is not None:
            existing.payload.p.faces.extend(to_return.p.faces)
        return self._cache.add(existing.payload)

    async def process_file(
        self,
        path: PathWithMd5,
        frame_each_seconds: int = 3,
        number_of_frames: int = 10,
    ) -> WithMD5[FaceEmbeddings]:
        # TODO: extract image previews with pts
        # TODO: extract iamge previews for gallery
        x = self._cache.get(path.md5)
        if x is not None and x.payload is not None:
            return x.payload
        media_class = supported_media_class(path.path)
        if media_class == SupportedMediaClass.IMAGE:
            return self._cache.add(await self._process_image(path, None, None))
        if media_class == SupportedMediaClass.VIDEO:
            return self._cache.add(await self._process_video(path, frame_each_seconds, number_of_frames))
        if media_class is None:
            return self._cache.add(
                WithMD5(path.md5, self._version, None, Error("UnsupportedMediaFile", None, None))
            )
        assert_never(media_class)

    async def _process_video(
        self, path: PathWithMd5, frame_each_seconds: int, number_of_frames: int
    ) -> WithMD5[FaceEmbeddings]:
        async def process_frame(frame: VideoFrame) -> WithMD5[FaceEmbeddings]:
            buffer = io.BytesIO(b"")
            frame.image.save(buffer, format="jpeg")
            data = buffer.getvalue()
            return await self._process_image(path, data, frame.pts)

        annotations = await asyncio.gather(
            *[
                process_frame(frame)
                for frame in get_video_frames(
                    path.path,
                    frame_each_seconds=frame_each_seconds,
                    number_of_frames=number_of_frames,
                )
            ]
        )
        processed = []
        errors = []
        for annotated in annotations:
            if annotated.e is not None:
                errors.append(annotated.e)
            if annotated.p is None:
                continue
            processed.append(annotated.p)
        if processed:
            return WithMD5(path.md5, self._version, _merge_face_embeddings_for_video(processed), None)
        if errors:
            return WithMD5(path.md5, self._version, None, errors[0])
        return WithMD5(
            path.md5,
            self._version,
            None,
            Error("NothingErrorOrSuccessWhileProcessingVideo", None, None),
        )

    async def _process_image(
        self, path: PathWithMd5, data: t.Optional[bytes], pts: t.Optional[int]
    ) -> WithMD5[FaceEmbeddings]:
        if data is None and os.path.getsize(path.path) > 100_000_000:
            return WithMD5(path.md5, self._version, None, Error("SkippingHugeFile", None, None))
        if self._remote is not None and self._remote_can_be_available():
            try:
                if data is None:
                    with open(path.path, "rb") as f:
                        data = base64.encodebytes(f.read())
                else:
                    data = base64.encodebytes(data)
                ret = await asyncio.wait_for(
                    fetch_ann(
                        self._remote,
                        FaceEmbeddingsRequest(
                            "FaceEmbeddingsRequest",
                            path,
                            None,
                            data.decode("utf-8"),
                            pts,
                        ),
                    ),
                    600,
                )
                self._last_remote_request = dt.datetime.now()
                return ret
            # pylint: disable-next = bare-except
            except:
                traceback.print_exc()
        p = self._pool.get().apply(_process_image_impl, (path, data, pts, None))
        return p


def _process_image_impl(
    path: PathWithMd5, data: t.Optional[bytes], pts: t.Optional[int], positions: t.Optional[t.List[Position]]
) -> WithMD5[FaceEmbeddings]:
    # pylint: disable-next = import-outside-toplevel,import-error
    import face_recognition

    image = PILImage.open(path.path) if data is None else PILImage.open(io.BytesIO(data))
    ImageOps.exif_transpose(image, in_place=True)
    image = image.convert("RGB")
    img = np.array(image)
    (w, h) = image.size
    resolution = ImageResolution(w, h)
    if positions is None:
        positions = [
            Position(left, top, right, bottom, pts)
            for (top, right, bottom, left) in t.cast(
                t.List[t.Tuple[int, int, int, int]], face_recognition.face_locations(img)
            )
        ]
    faces = []
    for position, embedding_ndarray in zip(
        positions,
        face_recognition.face_encodings(img, [[p.top, p.right, p.bottom, p.left] for p in positions]),
    ):
        faces.append(
            Face(
                position,
                t.cast(np.ndarray[t.Literal[128], np.dtype[np.float64]], embedding_ndarray).tolist(),
            )
        )
    return WithMD5(path.md5, FaceEmbeddings.current_version(), FaceEmbeddings(resolution, faces), None)


def _merge_face_embeddings_for_video(embeddings: t.Sequence[FaceEmbeddings]) -> FaceEmbeddings:
    return FaceEmbeddings(embeddings[0].resolution, [face for emb in embeddings for face in emb.faces])
