import sys
from tqdm import tqdm
import itertools
import typing as t
from dataclasses_json import dataclass_json
from image_to_text import Models


def batched(l, n):
    for i in range(0, len(l), n):
        yield l[i : i + n]


if __name__ == "__main__":
    models = Models()
    paths = sys.argv[1:]
    bsize = 1
    with open("output.jsonl", "w") as f:
        for b in tqdm(batched(paths, bsize), total=len(paths) // bsize, desc="Image batches"):
            for c in models.process_image_batch(b):
                f.write(c.to_json())
                f.write("\n")
                f.flush()
