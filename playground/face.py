from __future__ import annotations

import argparse
import dataclasses as dc
import itertools
import math
import os
import pickle
import random
import sys
import typing as t

import dataclasses_json as dj
import numpy as np
import face_recognition
from PIL import Image as PILImage, UnidentifiedImageError
from sklearn.linear_model import LinearRegression

import tqdm

from pphoto.annots.md5 import compute_md5, PathWithMd5
from pphoto.data_model.config import Config
from pphoto.utils.files import get_paths


@dc.dataclass
class Face(dj.DataClassJsonMixin):
    loc: t.Tuple[int, int, int, int]
    image_file: str
    encoding: t.List[float]


@dc.dataclass
class ImageFaces(dj.DataClassJsonMixin):
    path: PathWithMd5
    faces: t.List[Face]
    version: int

    @staticmethod
    def current_version() -> int:
        return 0


@dc.dataclass
class PairAnnotation(dj.DataClassJsonMixin):
    face1: str
    face2: str
    same_person: bool | None


@dc.dataclass
class Identity(dj.DataClassJsonMixin):
    name: str


@dc.dataclass(order=True)
class FaceClusterMember(dj.DataClassJsonMixin):
    face_image_file: str
    source_image_md5: str


Embedding = np.ndarray[t.Literal[128], np.dtype[np.float64]]


@dc.dataclass
class FaceCluster(dj.DataClassJsonMixin):
    center: Embedding
    radius: float
    members: t.List[FaceClusterMember]


# Clustering
## From annotation and negatives you take min(distance / 2) and get max cluster size
## Cluster based on this
## Union find on clusters on positives
## Sample largest distances from same identity
## Sample from bordering regions

T = t.TypeVar("T")


def remove_element_from_list(l: t.List[T], index: int) -> T:
    removed = l[index]
    l[index] = l[-1]
    l.pop()
    return removed


def cluster_centers_random(
    faces: t.Dict[str, t.Tuple[Face, ImageFaces, Embedding]],
    distances: t.Dict[str, t.Dict[str, t.Tuple[bool, float]]],
    distance: float,
) -> t.List[FaceCluster]:
    all_faces = list(faces.keys())
    in_cluster: t.Set[str] = set()
    centers = []
    while all_faces:
        index = random.randrange(len(all_faces))
        first_center_key = remove_element_from_list(all_faces, index)
        face = faces[first_center_key]
        members = [
            FaceClusterMember(face[0].image_file, face[1].path.md5),
            *(
                FaceClusterMember(faces[k][0].image_file, faces[k][1].path.md5)
                for k, x in distances[first_center_key].items()
                if k not in in_cluster and x[1] <= distance
            ),
        ]
        center = np.mean([faces[k.face_image_file][2] for k in members], axis=0)
        fc = FaceCluster(
            center,
            distance,
            members=members,
        )
        centers.append(fc)
        in_cluster = in_cluster.union(x.face_image_file for x in fc.members)
        all_faces = [x for x in all_faces if x not in in_cluster]
    centers.sort(key=lambda x: len(x.members))
    # for center in centers:
    #    print(center.center, len(center.members), center.members[:5])
    return centers


def cluster_distance_min(
    distances: t.Dict[str, t.Dict[str, t.Tuple[bool, float]]],
    c1: t.Iterable[FaceClusterMember],
    c2: t.Iterable[FaceClusterMember],
) -> t.Tuple[float, FaceClusterMember | None, FaceClusterMember | None]:
    return min(
        (
            (distances[m1.face_image_file][m2.face_image_file][1], m1, m2)
            for m1 in c1
            for m2 in c2
            if m1 != m2
        ),
        default=(10000000, None, None),
    )


def cluster_distance_max(
    distances: t.Dict[str, t.Dict[str, t.Tuple[bool, float]]],
    c1: t.Iterable[FaceClusterMember],
    c2: t.Iterable[FaceClusterMember],
) -> t.Tuple[float, FaceClusterMember | None, FaceClusterMember | None]:
    return max(
        (
            (distances[m1.face_image_file][m2.face_image_file][1], m1, m2)
            for m1 in c1
            for m2 in c2
            if m1 != m2
        ),
        default=(0.0, None, None),
    )


@dc.dataclass
class IgnoreAnnotation(dj.DataClassJsonMixin):
    face_image_file: str


class IgnoreAnnotations:
    def __init__(self, file: str = "data/face-ignore-annotations.jsonl") -> None:
        self._annotations = []
        if os.path.exists(file):
            with open(file, encoding="utf-8") as f:
                for line in f:
                    self._annotations.append(IgnoreAnnotation.from_json(line))
        self._out = open(file, "a", encoding="utf-8")

    def get(self) -> t.List[IgnoreAnnotation]:
        return self._annotations

    def add(self, a: IgnoreAnnotation) -> None:
        self._annotations.append(a)
        self._out.write(a.to_json())
        self._out.write("\n")
        self._out.flush()


class Annotations:
    def __init__(self, file: str = "data/face-pair-annotations.jsonl") -> None:
        self._annotations = []
        if os.path.exists(file):
            with open(file, encoding="utf-8") as f:
                for line in f:
                    self._annotations.append(PairAnnotation.from_json(line))
        self._out = open(file, "a", encoding="utf-8")

    def get(self) -> t.List[PairAnnotation]:
        return self._annotations

    def add(self, a: PairAnnotation) -> None:
        self._annotations.append(a)
        self._out.write(a.to_json())
        self._out.write("\n")
        self._out.flush()


def iterative_clustering(
    faces: t.Dict[str, t.Tuple[Face, ImageFaces, Embedding]],
    distances: t.Dict[str, t.Dict[str, t.Tuple[bool, float]]],
    annotations: t.List[PairAnnotation],
    model: None | LinearRegression,
) -> t.Iterable[t.Tuple[str, str, float, str]]:
    print(f"Using {len(annotations)} annotations")
    if annotations:
        # TODO: can fail if there is missing annotaiton of either side
        distance_neg = min(distances[x.face1][x.face2][1] for x in annotations if x.same_person is False) / 2
        distance_pos = max(distances[x.face1][x.face2][1] for x in annotations if x.same_person is True)
        num_neg = len([x for x in annotations if x.same_person is False]) * 3 * 100
        num_pos = len([x for x in annotations if x.same_person is True])
        total = num_neg + num_pos
        if distance_pos > distance_neg:
            distance = (num_neg / total) * distance_neg + (num_pos / total) * distance_pos
        else:
            distance = distance_neg
    else:
        distance = max(vv[1] for v in distances.values() for vv in v.values()) / 2
    print("Using distance:", distance)
    centers = cluster_centers_random(faces, distances, distance)
    print(f"Found {len(centers)} clusters")

    # TODO: union find for annotations
    uf: UnionFind[str] = UnionFind()
    f2c = {
        member.face_image_file: center.members[0].face_image_file
        for center in centers
        for member in center.members
    }
    for center in centers:
        uf.add(center.members[0].face_image_file)
    for annotation in annotations:
        if annotation.same_person == True:
            uf.union(f2c[annotation.face1], f2c[annotation.face2])

    identities: t.Dict[str, t.List[FaceCluster]] = {}
    for center in centers:
        parent = uf.parent(center.members[0].face_image_file)
        identities.setdefault(parent, []).append(center)
    print(f"Found {len(identities)} identities")
    pretty_identities(faces, identities, annotations, model)

    min_center_pairs = []
    max_pairs_in_center = []
    vals = list(identities.values())
    for index1, id1 in enumerate(vals):
        max_pairs_in_center.append(
            cluster_distance_max(
                distances,
                itertools.chain.from_iterable(c.members for c in id1),
                itertools.chain.from_iterable(c.members for c in id1),
            ),
        )
        for index2, id2 in enumerate(vals):
            if index1 == index2:
                continue
            min_center_pairs.append(
                cluster_distance_min(
                    distances,
                    itertools.chain.from_iterable(c.members for c in id1),
                    itertools.chain.from_iterable(c.members for c in id2),
                ),
            )
    min_center_pairs.sort(key=lambda x: x[0])
    max_pairs_in_center.sort(key=lambda x: x[0], reverse=True)

    done_pairs = set()
    done_individuals = set()
    for a in annotations:
        done_individuals.add(f2c[a.face1])
        done_individuals.add(f2c[a.face2])
        done_pairs.add((f2c[a.face1], f2c[a.face2]))
        done_pairs.add((f2c[a.face2], f2c[a.face1]))

    to_yield = 1
    for p in max_pairs_in_center:
        if to_yield <= 0:
            break
        if p[0] <= distance:
            continue
        if p[1] is None or p[2] is None:
            continue
        if f2c[p[1].face_image_file] in done_individuals:
            continue
        if f2c[p[2].face_image_file] in done_individuals:
            continue
        yield p[1].face_image_file, p[2].face_image_file, p[0], "Same identity"
        done_individuals.add(f2c[p[1].face_image_file])
        done_individuals.add(f2c[p[2].face_image_file])
        done_pairs.add((f2c[p[1].face_image_file], f2c[p[2].face_image_file]))
        done_pairs.add((f2c[p[2].face_image_file], f2c[p[1].face_image_file]))
        to_yield -= 1
    for p in max_pairs_in_center:
        if to_yield <= 0:
            break
        if p[0] <= distance:
            continue
        if p[1] is None or p[2] is None:
            continue
        key = (f2c[p[1].face_image_file], f2c[p[2].face_image_file])
        if key in done_pairs:
            continue
        yield p[1].face_image_file, p[2].face_image_file, p[0], "Same identity"
        done_individuals.add(f2c[p[1].face_image_file])
        done_individuals.add(f2c[p[2].face_image_file])
        done_pairs.add((f2c[p[1].face_image_file], f2c[p[2].face_image_file]))
        done_pairs.add((f2c[p[2].face_image_file], f2c[p[1].face_image_file]))
        to_yield -= 1
    to_yield += 5
    for p in min_center_pairs:
        if to_yield <= 0:
            break
        if p[1] is None or p[2] is None:
            continue
        if f2c[p[1].face_image_file] in done_individuals:
            continue
        if f2c[p[2].face_image_file] in done_individuals:
            continue
        yield p[1].face_image_file, p[2].face_image_file, p[0], "Close identities"
        done_individuals.add(f2c[p[1].face_image_file])
        done_individuals.add(f2c[p[2].face_image_file])
        done_pairs.add((f2c[p[1].face_image_file], f2c[p[2].face_image_file]))
        done_pairs.add((f2c[p[2].face_image_file], f2c[p[1].face_image_file]))
        to_yield -= 1
    for p in min_center_pairs:
        if to_yield <= 0:
            break
        if p[1] is None or p[2] is None:
            continue
        key = (f2c[p[1].face_image_file], f2c[p[2].face_image_file])
        if key in done_pairs:
            continue
        yield p[1].face_image_file, p[2].face_image_file, p[0], "Close identities"
        done_individuals.add(f2c[p[1].face_image_file])
        done_individuals.add(f2c[p[2].face_image_file])
        done_pairs.add((f2c[p[1].face_image_file], f2c[p[2].face_image_file]))
        done_pairs.add((f2c[p[2].face_image_file], f2c[p[1].face_image_file]))
        to_yield -= 1


K = t.TypeVar("K")


class UnionFind(t.Generic[K]):
    def __init__(self) -> None:
        self._parents: t.Dict[K, K] = {}
        self._sizes: t.Dict[K, int] = {}

    def add(self, k: K) -> UnionFind[K]:
        self._sizes.setdefault(k, -1)
        self._parents.setdefault(k, k)
        return self

    def parent(self, k: K) -> K:
        if self._parents[k] == k:
            return k
        p = self.parent(self._parents[k])
        self._parents[k] = p
        return p

    def union(self, k1: K, k2: K) -> UnionFind[K]:
        p1 = self.parent(k1)
        p2 = self.parent(k2)
        if self._sizes[p1] > self._sizes[p2]:
            self._sizes[p2] += self._sizes[p1]
            self._parents[p1] = p2
        else:
            self._sizes[p1] += self._sizes[p2]
            self._parents[p2] = p1
        return self


def uf_clusters(
    faces: t.Dict[str, t.Tuple[Face, ImageFaces, Embedding]],
    distances: t.Dict[str, t.Dict[str, t.Tuple[bool, float]]],
    pairs: t.List[t.Tuple[str, str]],
) -> None:
    uf: UnionFind[str] = UnionFind()
    for x in faces:
        uf.add(x)
    for x, y in tqdm.tqdm(pairs, desc="Clustering"):
        if distances[x][y][0]:
            uf.union(x, y)
    par: t.Dict[str, t.List[t.Tuple[Face, ImageFaces, Embedding]]] = {}
    for x in faces:
        par.setdefault(uf.parent(x), []).append(faces[x])
    print(len(par))
    for p, fs in par.items():
        if len(fs) > 1:
            print(p, len(fs))
            for ff in fs[:5]:
                d = distances[p].get(ff[0].image_file)
                print(" ", ff[0].image_file, d)
    print(len(faces))


def fit_annotations(
    faces: t.Dict[str, t.Tuple[Face, ImageFaces, Embedding]],
    annotations: t.List[PairAnnotation],
    positive: bool,
    fit_intercept: bool,
    previous_model: None | LinearRegression,
) -> LinearRegression:
    lr = LinearRegression(fit_intercept=fit_intercept, positive=positive)
    x = []
    y = []
    positives = 0
    negatives = 0
    for annotation in annotations:
        if annotation.same_person is None:
            continue
        a = faces[annotation.face1][2]
        b = faces[annotation.face2][2]
        coefs = np.square(a - b)
        x.append(coefs)
        if annotation.same_person:
            y.append(-5.0)
            positives += 1
        else:
            y.append(5.0)
            negatives += 1
    print("Size of trainint data", len(x), "positives", positives, "negatives", negatives)
    model = lr.fit(x, y)
    print("intercept", model.intercept_)
    print(np.mean(model.coef_), np.max(model.coef_), np.min(model.coef_))
    if previous_model is not None:
        coef_diff = np.sqrt(np.sum(np.square(previous_model.coef_ - model.coef_)))
        inter_diff = previous_model.intercept_ - model.intercept_
        print("Difference from used model: ", coef_diff, inter_diff)
    return model


def compute_distance(face1: Embedding, face2: Embedding, model: None | LinearRegression) -> float:
    def sigmoid(x: float) -> float:
        return t.cast(float, 1.0 / (1.0 + np.exp(-x)))

    if model is None:
        return t.cast(float, face_recognition.face_distance([face1], face2)[0])
    return sigmoid(float(model.predict([np.square(face1 - face2)])[0]))


def compute_distances(
    faces: t.Dict[str, t.Tuple[Face, ImageFaces, Embedding]],
    model: None | LinearRegression,
) -> t.Dict[str, t.Dict[str, t.Tuple[bool, float]]]:
    distances: t.Dict[str, t.Dict[str, t.Tuple[bool, float]]] = {}
    pairs = []
    for x in faces:
        for y in faces:
            if x == y:
                continue
            pairs.append((x, y))
    for x, y in tqdm.tqdm(pairs, desc="Processing square matrix"):
        encX = faces[x][2]
        encY = faces[y][2]
        same = face_recognition.compare_faces([encX], encY, tolerance=0.5)[0]
        distances.setdefault(x, {})[y] = (
            same,
            compute_distance(encX, encY, model),
        )
    return distances


def pretty_identities(
    faces: t.Dict[str, t.Tuple[Face, ImageFaces, Embedding]],
    identities: t.Dict[str, t.List[FaceCluster]],
    annotations: t.List[PairAnnotation],
    model: None | LinearRegression,
) -> None:
    with open("identities.html", "w", encoding="utf-8") as f:
        print(
            """<html>
<head>
<style>
img {
  max-width: 100px;
  max-hegith: 100px;
}
</style>
</head>
                <body>""",
            file=f,
        )

        print(f"Num identities {len(identities)}", file=f)
        for rep, clusters in sorted(identities.items(), key=lambda x: len(x[1]), reverse=True):
            print(f'<h2>Identity: <img src="{rep}"/> {rep}</h2>', file=f)
            print(f"Num Clusters: {len(clusters)}<br/>", file=f)
            f2c = {
                member.face_image_file: cluster.members[0].face_image_file
                for cluster in clusters
                for member in cluster.members
            }
            print(f"<h3>Inter cluster annotations</h3>", file=f)
            for ann in annotations:
                c1 = f2c.get(ann.face1)
                c2 = f2c.get(ann.face2)
                if ann.same_person is not True:
                    continue
                if c1 is None or c2 is None or c1 == c2:
                    continue
                print(f'<img src="{ann.face1}" title="{ann.face1}"/>', file=f)
                print(f'<img src="{ann.face2}" title="{ann.face2}"/>', file=f)
                print(ann.same_person, file=f)
                print("<br/>", file=f)

            for cluster in sorted(clusters, key=lambda x: len(x.members), reverse=True):
                print(f"<h3>Cluster of size {len(cluster.members)}</h3>", file=f)
                print("<h4>annotations</h4>", file=f)
                members = set(c.face_image_file for c in cluster.members)
                for ann in annotations:
                    if ann.face1 not in members or ann.face2 not in members:
                        continue
                    print(f'<img src="{ann.face1}" title="{ann.face1}"/>', file=f)
                    print(f'<img src="{ann.face2}" title="{ann.face2}"/>', file=f)
                    print(ann.same_person, file=f)
                    print("<br/>", file=f)
                print("<h4>members</h4>", file=f)
                for member in cluster.members:
                    dist = compute_distance(cluster.center, faces[member.face_image_file][2], model)
                    print(
                        f'<img src="{member.face_image_file}" title="{dist} {member.face_image_file}"/>',
                        file=f,
                    )

        print("</body></html>", file=f)


def cluster(data: t.Dict[str, ImageFaces]) -> None:
    ignores = IgnoreAnnotations()
    to_skip = set(x.face_image_file for x in ignores.get())
    faces: t.Dict[str, t.Tuple[Face, ImageFaces, Embedding]] = {
        face.image_file: (face, image, np.array(face.encoding))
        for image in data.values()
        for face in image.faces
        if face.image_file not in to_skip
    }
    model: None | LinearRegression = None
    used_model: None | LinearRegression = None
    if not os.path.exists("data/face-distances.pickle"):
        distances = compute_distances(faces, model)
        with open("data/face-distances.pickle", "wb") as f:
            pickle.dump([used_model, distances], f)
    else:
        with open("data/face-distances.pickle", "rb") as f:
            [used_model, distances] = pickle.load(f)
            distances = {
                k: {kk: vv for kk, vv in v.items() if kk not in to_skip}
                for k, v in distances.items()
                if k not in to_skip
            }
    annotations = Annotations()
    random.seed()
    while True:
        filtered_annotations = [
            ann for ann in annotations.get() if ann.face1 not in to_skip and ann.face2 not in to_skip
        ]
        model = fit_annotations(faces, filtered_annotations, False, True, used_model)
        distances = {
            k: {kk: vv for kk, vv in v.items() if kk not in to_skip}
            for k, v in distances.items()
            if k not in to_skip
        }
        for a, b, distance, reason in iterative_clustering(
            faces, distances, filtered_annotations, used_model
        ):
            if a in to_skip or b in to_skip:
                print("This faces were already kicked out")
                continue
            base_width = 500
            new = PILImage.new("RGB", ((2 * base_width, 2 * base_width)))
            ai = PILImage.open(a)
            aii = PILImage.open(faces[a][1].path.path)
            bi = PILImage.open(b)
            bii = PILImage.open(faces[b][1].path.path)
            ai.thumbnail((base_width, base_width))
            aii.thumbnail((base_width, base_width))
            new.paste(ai, (0, 0))
            new.paste(aii, (0, base_width))
            bi.thumbnail((base_width, base_width))
            bii.thumbnail((base_width, base_width))
            new.paste(bi, (base_width, 0))
            new.paste(bii, (base_width, base_width))
            print("to annotatate", reason, a, b, "distance:", distance)
            same_person = None
            skip = False
            while True:
                print(
                    "Is it same person? (Y)es/(N)o/(U)nable to tell/(S)kip/(R)ecompute model/kick (left/right/both) (face/faces/image/images)"
                )
                new.show()
                result = sys.stdin.readline().lower().strip()
                if result in ["y", "yes"]:
                    same_person = True
                    break
                elif result in ["n", "no"]:
                    same_person = False
                    break
                elif result in ["u", "unable", "unable to tell"]:
                    same_person = None
                    break
                elif result in ["s", "skip"]:
                    skip = True
                    break
                elif result in ["r", "recompute", "recompute model"]:
                    skip = True
                    distances = compute_distances(faces, model)
                    used_model = model
                    with open("data/face-distances.pickle", "wb") as f:
                        pickle.dump([used_model, distances], f)
                    break
                elif result in ["klf", "kick left face"]:
                    # TODO: save these
                    if a in faces:
                        ignores.add(IgnoreAnnotation(a))
                        to_skip.add(a)
                        del faces[a]
                    break
                elif result in ["krf", "kick right face"]:
                    if b in faces:
                        ignores.add(IgnoreAnnotation(b))
                        to_skip.add(b)
                        del faces[b]
                    break
                elif result in ["kbf", "kick both faces"]:
                    if a in faces:
                        ignores.add(IgnoreAnnotation(a))
                        to_skip.add(a)
                        del faces[a]
                    if b in faces:
                        ignores.add(IgnoreAnnotation(b))
                        to_skip.add(b)
                        del faces[b]
                    break
                elif result in ["kli", "kick left image"]:
                    if a in faces:
                        image = faces[a][1]
                        for x in image.faces:
                            if x.image_file in faces:
                                ignores.add(IgnoreAnnotation(x.image_file))
                                to_skip.add(x.image_file)
                                del faces[x.image_file]
                    break
                elif result in ["kri", "kick right image"]:
                    if b in faces:
                        image = faces[b][1]
                        for x in image.faces:
                            if x.image_file in faces:
                                ignores.add(IgnoreAnnotation(x.image_file))
                                to_skip.add(x.image_file)
                                del faces[x.image_file]
                    break
                elif result in ["kbi", "kick both images"]:
                    if a in faces:
                        image = faces[a][1]
                        for x in image.faces:
                            if x.image_file in faces:
                                ignores.add(IgnoreAnnotation(x.image_file))
                                to_skip.add(x.image_file)
                                del faces[x.image_file]
                    if b in faces:
                        image = faces[b][1]
                        for x in image.faces:
                            if x.image_file in faces:
                                ignores.add(IgnoreAnnotation(x.image_file))
                                to_skip.add(x.image_file)
                                del faces[x.image_file]
                    break
                else:
                    print("I don't understand")

            if not skip:
                annotations.add(PairAnnotation(a, b, same_person))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", default="process_images", choices=["process_images", "cluster"])
    parser.add_argument("--db-file", default="data/faces.jsonl")
    args = parser.parse_args()
    output_file = args.db_file
    cache = {}
    if os.path.exists(output_file):
        with open(output_file, encoding="utf-8") as f:
            for line in f:
                face = ImageFaces.from_json(line)
                cache[face.path.path] = face

    if args.command == "cluster":
        cluster(cache)
    elif args.command == "process_images":
        config = Config.load("config.yaml")

        all_paths = [x for x in get_paths(config.input_patterns, config.input_directories) if x not in cache]
        with open(output_file, "a", encoding="utf-8") as f:
            faces_progress = tqdm.tqdm(None, desc="Found faces", position=1)
            for path in tqdm.tqdm(all_paths, desc="Processing paths", total=len(all_paths), position=0):
                if path in cache:
                    continue
                try:
                    wmd5 = compute_md5(path)
                    img = face_recognition.load_image_file(path)

                    image = PILImage.open(path)
                    image = image.convert("RGB")
                    img = np.array(image)
                    locations = face_recognition.face_locations(img)
                    faces_progress.update(len(locations))
                    faces = []
                    for index, (location, encoding) in enumerate(
                        zip(locations, face_recognition.face_encodings(img, locations))
                    ):
                        (top, right, bottom, left) = location
                        cropped = image.crop((left, top, right, bottom))
                        extension = wmd5.path.split(".")[-1]
                        directory = f"data/faces/{wmd5.md5[0]}/{wmd5.md5[1]}/{wmd5.md5[2]}/{wmd5.md5[3]}/"
                        if not os.path.exists(directory):
                            os.makedirs(directory, exist_ok=True)
                        filename = f"{directory}/{wmd5.md5}_{index}.{extension}"
                        cropped.save(filename, format=image.format)
                        faces.append(Face((left, top, right, bottom), filename, encoding.tolist()))
                    # face_recognition.face_distance([encodings[0]], encodings[1])
                    # face_recognition.compare_faces([encodings[0]], encodings[1])
                    out = ImageFaces(wmd5, faces, ImageFaces.current_version())
                    f.write(out.to_json())
                    f.write("\n")
                    f.flush()
                except UnidentifiedImageError:
                    pass


if __name__ == "__main__":
    main()
