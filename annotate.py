from PIL import Image
from pprint import pprint
import sys
from tqdm import tqdm
import itertools
from ultralytics import YOLO
from dataclasses import dataclass
import typing as t
from dataclasses_json import dataclass_json
from transformers import pipeline

predict_model = YOLO("yolov8x.pt")
classify_model = YOLO("yolov8x-cls.pt")

captioner = pipeline("image-to-text", model="Salesforce/blip-image-captioning-base")


@dataclass_json
@dataclass
class Box:
    classification: str
    confidence: float
    xyxy: t.List[float]


@dataclass_json
@dataclass
class Classification:
    name: str
    confidence: float


@dataclass_json
@dataclass
class BoxClassification:
    box: Box
    classifications: t.List[Classification]


@dataclass_json
@dataclass
class ImageClassification:
    image: str
    captions: t.List[str]
    boxes: t.List[BoxClassification]

    def print(self):
        print(self.image)
        for caption in self.captions:
            print(" ", caption)
        for box in self.boxes:
            print(" ", box.box.classification, box.box.confidence)
            for c in box.classifications:
                print("   ", c.name, c.confidence)


def process_image_batch(
    paths: t.Iterable[str], gap_threshold: float = 0.2, discard_threshold: float = 0.1
) -> t.Iterable[ImageClassification]:
    global captioner
    global predict_model
    global classify_model
    images = [(path, Image.open(path)) for path in paths]
    captions = captioner([image for (_, image) in images])
    results = predict_model([img for (_, img) in images], verbose=False)
    boxes_to_classify = []
    all_input = list(zip(images, results, captions))
    for ((path, image), result, caption) in all_input:
        names = result.names
        for box_id, box in enumerate(result.boxes):
            classification = names[int(box.cls[0])]
            confidence = float(box.conf[0])
            xyxy = list(float(x) for x in box.xyxy[0])
            boxes_to_classify.append((path, image, box_id, caption, Box(classification, confidence, xyxy)))

    if boxes_to_classify:
        results = list(
            zip(
                boxes_to_classify,
                classify_model(
                    [
                        image.crop((int(box.xyxy[0]), int(box.xyxy[1]), int(box.xyxy[2]), int(box.xyxy[3])))
                        for (_, image, _, _, box) in boxes_to_classify
                    ],
                    verbose=False,
                ),
            )
        )
    else:
        results = []

    visited = set()
    for (path, group) in itertools.groupby(results, lambda x: (x[0][0])):
        visited.add(path)
        box_class = []
        captions = set()
        for (_, _image, box_id, caption, box), result in group:
            for c in caption:
                t = c.get("generated_text")
                if t is not None:
                    captions.add(remove_consecutive_words(t))
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
        yield ImageClassification(path, list(captions), box_class)
    for ((path, image), captions, _) in all_input:
        if path in visited:
            continue
        visited.add(path)
        captions = set()
        for c in caption:
            t = c.get("generated_text")
            if t is not None:
                captions.add(remove_consecutive_words(t))
        yield ImageClassification(path, list(captions), [])


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


def batched(l, n):
    for i in range(0, len(l), n):
        yield l[i : i + n]


if __name__ == "__main__":
    paths = sys.argv[1:]
    bsize = 1
    with open("output.jsonl", "w") as f:
        for b in tqdm(batched(paths, bsize), total=len(paths) // bsize, desc="Image batches"):
            for c in process_image_batch(b):
                f.write(c.to_json())
                f.write("\n")
                f.flush()
