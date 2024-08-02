import datetime
import dataclasses
import io
import tarfile
import typing as t

from pphoto.file_mgmt.paths import resolve_dir, resolve_path, HaveNameAndCountry


@dataclasses.dataclass
class FileToStore:
    og_path: str
    new_path: str


def non_repeating_dirs(
    photos_dir: str,
    paths: t.Iterable[t.Tuple[str, t.Optional[datetime.datetime], t.Optional[HaveNameAndCountry]]],
) -> t.Iterable[FileToStore]:
    last_dir = None
    used_dirs: t.Dict[str, int] = {}
    for path, date, geo in paths:
        directory = resolve_dir(photos_dir, date, geo, flat=True)
        if directory != last_dir:
            index = used_dirs.get(directory)
            if index is not None and geo is not None and (geo.name is not None or geo.country is not None):
                actual_directory = f"{directory}_{index+1:02d}"
                used_dirs[directory] += 1
            else:
                used_dirs[directory] = 0
                actual_directory = directory
        else:
            actual_directory = directory
        last_dir = directory
        final_path = resolve_path(actual_directory, path)
        yield FileToStore(path, final_path)


class ByteStream(io.BytesIO):
    def __init__(self) -> None:
        self._buffer = io.BytesIO()

    def write(self, s: t.Any, /) -> int:
        self._buffer.write(s)
        return len(s)

    def close(self) -> None:
        self._buffer.close()

    def extract_bytes(self) -> bytes:
        s = self._buffer.getvalue()
        self._buffer.close()
        self._buffer = io.BytesIO()
        return s


def tar_stream(paths: t.Iterable[FileToStore]) -> t.Iterable[bytes]:
    # TODO: consider streaming zip library: https://stream-zip.docs.trade.gov.uk/get-started/
    output = ByteStream()
    with tarfile.TarFile.open(None, "w", output) as tar:
        for path in paths:
            tar.add(path.og_path, arcname=path.new_path, recursive=False)
            yield output.extract_bytes()
    yield output.extract_bytes()
