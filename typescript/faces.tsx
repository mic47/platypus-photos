import React from "react";

import * as pygallery_service from "./pygallery.generated/services.gen.ts";
import {
    FacesResponse,
    FaceWithMeta,
    GalleryPaging,
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
        },
    ]);
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
                }
            });
        return () => {
            ignore = true;
        };
    }, [query, paging, sort]);
    const [slider, updateSlider] = React.useState<number>(280);
    const threshold = slider / 1000;
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
            <input type="checkbox" /> Show hidden faces
            <br />
            <input type="checkbox" /> Hide faces with assigned identities
            <br />
            <FacesView
                threshold={threshold}
                availableIdentities={["RandomIdentity", "Other Test identity"]}
                data={data[1]}
            />
        </div>
    );
}
interface FacesViewProps {
    threshold: number;
    availableIdentities: string[];
    data: FacesResponse;
}
function FacesView({ threshold, availableIdentities, data }: FacesViewProps) {
    const items = doClustering(threshold, data.faces)
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
            const clusterItems = faces.map((face) => {
                const posStr = `${face.position.left},${face.position.top},${face.position.right},${face.position.bottom}`;
                return (
                    <div
                        key={`${face.md5}/${posStr}`}
                        className="face_container"
                    >
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
            const posStr = `${faces[0].md5}/${faces[0].position.left},${faces[0].position.top},${faces[0].position.right},${faces[0].position.bottom}`;
            const identities = [
                ...new Set(
                    faces
                        .map((face) => face.identity)
                        .filter((x) => x !== null),
                ),
            ];
            // TODO: warning if there are duplicit identities
            return (
                <div key={posStr} className="face_cluster">
                    <div>
                        <div>
                            Already assigned identities :{" "}
                            {identities.join(", ")}
                            <br />
                            <input type="checkbox" /> Not a face <br />
                            <input type="checkbox" /> Not interesting person{" "}
                            <br />
                            <input type="checkbox" /> New identity{" "}
                            <input type="text" />
                            <br />
                            <select
                                defaultValue={
                                    identities.length > 0
                                        ? identities[0]
                                        : "__NOIDENTITY__}"
                                }
                            >
                                <option value="__NOIDENTITY__">
                                    No identity
                                </option>
                                {availableIdentities.map((identity) => {
                                    return (
                                        <option key={identity} value={identity}>
                                            {identity}
                                        </option>
                                    );
                                })}
                            </select>
                            <button>Submit this cluster only</button>
                            <button>Submit all pending face annotations</button>
                        </div>
                    </div>
                    {clusterItems}
                </div>
            );
        });
    return (
        <div>
            <button>Submit pending face annotations</button>
            {items}
            <button>Submit pending identity annotations</button>
        </div>
    );
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
