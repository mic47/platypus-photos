import argparse
import typing as t

import av
import PIL.Image as Image


def video_to_frames(filename: str, number_of_frames: int = 11) -> t.Iterable[t.Tuple[Image.Image, int]]:
    with av.open(filename) as video:
        stream = video.streams.best("video")
        if stream is None:
            return
        stream.codec_context.skip_frame = "NONKEY"
        duration = stream.duration  # in time_base units
        time_base = stream.time_base
        frames = stream.frames
        if duration is not None and number_of_frames > 1:
            seeks = [duration * i // (number_of_frames - 1) for i in range(number_of_frames)]
        else:
            # We don't know how long it is, let's just do single image
            seeks = [0]
        for frame in video.decode(stream):
            if not isinstance(frame, av.VideoFrame):
                continue
            if not seeks:
                break
            seek = seeks.pop(0)
            video.seek(seek, stream=stream)
            image = frame.to_image()
            yield (image, frame.pts)
            image.save(
                f"tmp/testing-video-extraction.{frame.pts:04d}.jpg",
                quality=80,
            )

        print(filename, duration, time_base, frames, stream.start_time)
        print(filename, video.duration, video.start_time, video.size)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("filename")
    args = parser.parse_args()
    filename = args.filename
    list(video_to_frames(filename))


if __name__ == "__main__":
    main()
