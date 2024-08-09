import hashlib

from pphoto.data_model.base import PathWithMd5


def compute_md5(path: str) -> PathWithMd5:
    with open(path, "rb") as f:
        md5 = hashlib.md5()
        for x in f:
            md5.update(x)
        return PathWithMd5(path, md5.hexdigest())
