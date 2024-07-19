import React from "react";

import * as pygallery_service from "./pygallery.generated/services.gen.ts";
import {
    FaceIdentifier,
    FacesResponse,
    FaceWithMeta,
    GalleryPaging,
    IdentitySkipReason,
    ManualIdentityClusterRequest_Input,
    SearchQuery,
    SortParams,
} from "./pygallery.generated";

interface FacesComponentProps {
    query: SearchQuery;
    paging: GalleryPaging;
    sort: SortParams;
}
export function FacesComponent({ query, paging, sort }: FacesComponentProps) {
    const [data, updateData] = React.useState<[SearchQuery, FacesResponse]>([
        query,
        {
            faces: [],
            has_next_page: false,
            top_identities: [],
        },
    ]);
    const [pendingAnnotations, updatePendingAnnotations] = React.useState<{
        [id: string]: IdentityAnnotation;
    }>({});
    React.useEffect(() => {
        let ignore = false;
        const requestBody = {
            query,
            paging,
            sort,
        };
        pygallery_service
            .facesOnPagePost({
                requestBody,
            })
            .then((data) => {
                if (!ignore) {
                    updateData([query, data]);
                    updatePendingAnnotations({});
                }
            });
        return () => {
            ignore = true;
        };
    }, [query, paging, sort]);
    const [settings, updateSettings] = React.useState({
        showHiddenFaces: false,
        hideFacesWithIdentities: false,
    });
    const [slider, updateSlider] = React.useState<number>(280);
    const threshold = slider / 1000;
    const pendingIdentities = new Set(
        Object.values(pendingAnnotations)
            .map((a) => a.identity)
            .filter((id) => id !== null),
    );
    const availableIdentities = [...pendingIdentities];
    data[1].top_identities.forEach((identity) => {
        if (!pendingIdentities.has(identity.identity)) {
            availableIdentities.push(identity.identity);
        }
    });
    console.log(availableIdentities);
    return (
        <div>
            Threshold: {threshold}
            <br />
            <input
                type="range"
                min="1"
                max="1000"
                value={slider}
                onChange={(event) => {
                    updateSlider(parseFloat(event.target.value));
                }}
            />
            <br />
            <input
                type="checkbox"
                checked={settings.showHiddenFaces}
                onChange={(event) => {
                    updateSettings({
                        ...settings,
                        showHiddenFaces: event.target.checked,
                    });
                }}
            />{" "}
            Show hidden faces
            <br />
            <input
                type="checkbox"
                checked={settings.hideFacesWithIdentities}
                onChange={(event) => {
                    updateSettings({
                        ...settings,
                        hideFacesWithIdentities: event.target.checked,
                    });
                }}
            />{" "}
            Hide faces with assigned identities
            <br />
            <FacesView
                threshold={threshold}
                availableIdentities={availableIdentities}
                updatePendingAnnotations={(
                    req: ManualIdentityClusterRequest_Input[],
                ) => {
                    const newAnnotations = req.flatMap((c) =>
                        c.faces.map((f) => {
                            return {
                                id: faceId(f),
                                annotation: {
                                    skip_reason: c.skip_reason,
                                    identity: c.identity,
                                },
                            };
                        }),
                    );
                    if (newAnnotations.length === 0) {
                        return;
                    }
                    const pending = { ...pendingAnnotations };
                    newAnnotations.forEach(({ id, annotation }) => {
                        pending[id] = annotation;
                    });
                    updatePendingAnnotations(pending);
                }}
                data={data[1].faces
                    .map((face) => {
                        const id = faceId(face);
                        const pending = pendingAnnotations[id];
                        if (pending !== undefined && pending !== null) {
                            return {
                                ...face,
                                identity: pending.identity,
                                skip_reason: pending.skip_reason,
                            };
                        }
                        return face;
                    })
                    .filter((face) => {
                        if (
                            !settings.showHiddenFaces &&
                            face.skip_reason !== null
                        ) {
                            return false;
                        }
                        if (
                            settings.hideFacesWithIdentities &&
                            face.identity !== null
                        ) {
                            return false;
                        }
                        return true;
                    })}
            />
        </div>
    );
}
function faceId(face: FaceWithMeta | FaceIdentifier): string {
    return `${face.md5}/${face.position.left},${face.position.top},${face.position.right},${face.position.bottom}`;
}

interface FacesViewProps {
    threshold: number;
    availableIdentities: string[];
    data: FaceWithMeta[];
    updatePendingAnnotations: (
        pending: ManualIdentityClusterRequest_Input[],
    ) => void;
}
function FacesView({
    threshold,
    availableIdentities,
    updatePendingAnnotations,
    data,
}: FacesViewProps) {
    const [clusters, updateClusters] = React.useState<
        Array<{ id: string; faces: FaceWithMeta[] }>
    >([]);
    const [annotations, updateAnnotations] = React.useState<{
        [id: string]: IdentityAnnotation;
    }>({});
    React.useEffect(() => {
        const clusters = doClustering(threshold, data)
            .sort((a, b) => {
                if (a.length < b.length) {
                    return 1;
                } else if (a.length > b.length) {
                    return -1;
                } else {
                    return 0;
                }
            })
            .map((faces) => {
                const posStr = faceId(faces[0]);
                return { id: posStr, faces: faces };
            });
        updateClusters(clusters);
        const ids = new Set(clusters.map((cluster) => cluster.id));
        const deleted = Object.keys(annotations).filter((x) => !ids.has(x));
        if (deleted.length > 0) {
            const annots = { ...annotations };
            deleted.forEach((id) => {
                delete annots[id];
            });
        }
    }, [data, threshold]);
    const submit = () => {
        const req = clusters
            .map(({ id, faces }) => {
                const annotation = annotations[id];
                if (annotation === null || annotation === undefined) {
                    return null;
                }
                return makeClusterRequest(faces, annotation);
            })
            .filter((x) => x !== null);
        submitAnnotationRequest(req);
        updatePendingAnnotations(req);
    };
    const items = clusters.map(({ id, faces }) => {
        return (
            <FaceCluster
                key={id}
                faces={faces}
                availableIdentities={availableIdentities}
                updatePendingAnnotations={updatePendingAnnotations}
                submitAllFaceAnnotations={() => submit()}
                updateAnnotations={(
                    request: ManualIdentityClusterRequest_Input | null,
                ) => {
                    const annots = { ...annotations };
                    if (request === null) {
                        delete annots[id];
                    } else {
                        annots[id] = request;
                    }
                    updateAnnotations(annots);
                }}
            />
        );
    });
    return (
        <div>
            <button onClick={() => submit()}>
                Submit all pending face annotations
            </button>
            {items}
            <button onClick={() => submit()}>
                Submit all pending identity annotations
            </button>
        </div>
    );
}

type IdentityAnnotation = {
    identity: string | null;
    skip_reason: IdentitySkipReason | null;
};

function FaceCluster({
    faces,
    availableIdentities,
    submitAllFaceAnnotations,
    updateAnnotations,
    updatePendingAnnotations,
}: {
    faces: FaceWithMeta[];
    availableIdentities: string[];
    submitAllFaceAnnotations: () => void;
    updateAnnotations: (
        requests: ManualIdentityClusterRequest_Input | null,
    ) => void;
    updatePendingAnnotations: (
        req: ManualIdentityClusterRequest_Input[],
    ) => void;
}) {
    const [request, updateRequest] = React.useState<IdentityAnnotation>({
        identity: null,
        skip_reason: null,
    });
    React.useEffect(() => {
        updateAnnotations(makeClusterRequest(faces, request));
    }, [request, faces]);
    const setSkipReason = (reason: IdentitySkipReason | null) => {
        if (reason === null) {
            updateRequest({ ...request, skip_reason: null });
        } else {
            updateRequest({ ...request, skip_reason: reason, identity: null });
        }
    };
    const setIdentity = (identity: null | string) => {
        if (identity === null || identity.trim() === "") {
            updateRequest({ ...request, identity: null });
        } else {
            updateRequest({
                ...request,
                identity: identity,
                skip_reason: null,
            });
        }
    };
    const clusterItems = faces.map((face) => {
        const posStr = `${face.position.left},${face.position.top},${face.position.right},${face.position.bottom}`;
        return (
            <div key={`${face.md5}/${posStr}`} className="face_container">
                <img
                    loading="lazy"
                    src={`/img/original/${face.md5}.${face.extension}?position=${posStr}`}
                    className="gallery_image"
                    alt={face.identity || "No identity assigned"}
                    title={face.identity || "No identity assigned"}
                />
            </div>
        );
    });
    const identities = [
        ...new Set(
            faces
                .map((face) => face.identity || face.skip_reason)
                .filter((x) => x !== null),
        ),
    ];
    // TODO: warning if there are duplicit identities, or something like that
    return (
        <div className="face_cluster">
            <div>
                <div>
                    Already assigned identities: {identities.join(", ")}
                    <br />
                    <input
                        type="checkbox"
                        checked={request.skip_reason === "not_face"}
                        onChange={(event) =>
                            setSkipReason(
                                event.target.checked ? "not_face" : null,
                            )
                        }
                    />{" "}
                    Not a face <br />
                    <input
                        type="checkbox"
                        checked={request.skip_reason == "not_poi"}
                        onChange={(event) =>
                            setSkipReason(
                                event.target.checked ? "not_poi" : null,
                            )
                        }
                    />{" "}
                    Not interesting person <br />
                    <input
                        type="checkbox"
                        checked={request.identity !== null}
                        disabled={true}
                    />{" "}
                    Identity{" "}
                    <input
                        type="text"
                        value={request.identity || ""}
                        onChange={(event) => setIdentity(event.target.value)}
                    />
                    <select
                        value={
                            request.identity === null
                                ? "__NOIDENTITY__"
                                : request.identity
                        }
                        onChange={(event) => setIdentity(event.target.value)}
                    >
                        <option value="__NOIDENTITY__">
                            Other (use input box)
                        </option>
                        {availableIdentities.map((identity) => {
                            return (
                                <option key={identity} value={identity}>
                                    {identity}
                                </option>
                            );
                        })}
                    </select>
                    <br />
                    <button
                        onClick={() => {
                            const req = makeClusterRequest(faces, request);
                            submitAnnotationRequest([req]);
                            if (req !== null) {
                                updatePendingAnnotations([req]);
                            }
                        }}
                        disabled={
                            request.identity === null &&
                            request.skip_reason === null
                        }
                    >
                        Submit this cluster only
                    </button>
                    <button onClick={() => submitAllFaceAnnotations()}>
                        Submit all pending face annotations
                    </button>
                </div>
            </div>
            {clusterItems}
        </div>
    );
}
function makeClusterRequest(
    faces: FaceWithMeta[],
    request: IdentityAnnotation,
): ManualIdentityClusterRequest_Input | null {
    if (request.identity === null && request.skip_reason === null) {
        return null;
    }
    return {
        identity: request.identity,
        skip_reason: request.skip_reason,
        faces: faces.map((face) => {
            return {
                md5: face.md5,
                extension: face.extension,
                position: face.position,
            };
        }),
    };
}
function submitAnnotationRequest(
    maybe_requests: Array<ManualIdentityClusterRequest_Input | null>,
) {
    const request = maybe_requests.filter((x) => x !== null);
    if (request.length === 0) {
        return;
    }
    pygallery_service.manualIdentityAnnotationEndpointPost({
        requestBody: request,
    });
}

function doClustering(
    threshold: number,
    faces: FaceWithMeta[],
): Array<Array<FaceWithMeta>> {
    const clusters: Array<Array<FaceWithMeta>> = [];
    faces.forEach((face) => {
        const closest = clusters.find((cluster) => {
            const center = cluster[0];
            const dist = distance(center.embedding, face.embedding);
            return dist <= threshold;
        });
        if (closest === undefined) {
            clusters.push([face]);
        } else {
            closest.push(face);
        }
    });
    return clusters;
}

function distance(e1: number[], e2: number[]): number {
    let total = 0.0;
    for (let i = 0; i < Math.max(e1.length, e2.length); i++) {
        const diff = (e1[i] || 0) - (e2[i] || 0);
        total += diff * diff;
    }
    return Math.sqrt(total);
}
