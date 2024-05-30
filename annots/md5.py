import hashlib

from data_model.features import PathWithMd5


def compute_md5(path: str) -> PathWithMd5:
    return PathWithMd5(path, hashlib.md5(open(path, "rb").read()).hexdigest())
