import dataclasses as dc
import typing as t

import av
from PIL import Image


@dc.dataclass
class VideoFrame:
    image: Image.Image
    pts: int


def get_video_frame(filename: str, frame_position: t.Optional[int]) -> VideoFrame | None:
    with av.open(filename) as video:
        stream = video.streams.best("video")
        if stream is None:
            return None
        video.seek(frame_position or 0, stream=stream)
        for frame in video.decode(stream):
            if not isinstance(frame, av.VideoFrame):
                continue
            image = frame.to_image()
            if frame_position is not None and frame.pts != frame_position:
                raise Exception(  # pylint: disable=broad-exception-raised
                    f"Unable to seek to frame {frame_position} in file {filename}"
                )
            return VideoFrame(image, frame.pts)
    return None


def get_video_frames(
    filename: str,
    frame_each_seconds: float | None,
    number_of_frames: int | None,
) -> t.Iterable[VideoFrame]:

    with av.open(filename) as video:
        stream = video.streams.best("video")
        if stream is None:
            return
        stream.codec_context.skip_frame = "NONKEY"  # noqa: F841
        duration = stream.duration  # in time_base units
        time_base = stream.time_base
        if duration is not None and time_base is not None and frame_each_seconds is not None:
            # In this case, the number of frames is used as minimum number of frames to extract
            if number_of_frames is None:
                number_of_frames = 3
            number_of_frames = max(
                number_of_frames, int(1 + float(duration * time_base) / frame_each_seconds)
            )
        if duration is not None and number_of_frames is not None:
            seeks = [duration * i // (number_of_frames - 1) for i in range(number_of_frames)]
        else:
            # We don't know how long it is, let's just do single image
            seeks = [0]
        for frame in video.decode(stream):
            if not isinstance(frame, av.VideoFrame):
                continue
            image = frame.to_image()
            yield VideoFrame(image, frame.pts)

            if not seeks:
                break
            seek = seeks.pop(0)
            video.seek(seek, stream=stream)
