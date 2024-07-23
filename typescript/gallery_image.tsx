import React from "react";
import { isEqual } from "lodash";

import {
    FaceWithMeta,
    GalleryPaging,
    IdentityRowPayload,
    IdentitySkipReason,
    ImageWithMeta,
    ManualIdentityClusterRequest_Input,
    Position,
    PredictedLocation,
    SearchQuery,
    SortParams,
} from "./pygallery.generated";
import {
    append_flag,
    format_seconds_to_duration,
    round,
    time_to_clock,
} from "./utils";
import { MaybeA } from "./jsx/maybea";
import * as pygallery_service from "./pygallery.generated/services.gen.ts";
import {
    IdentityAnnotation,
    makeClusterRequest,
    submitAnnotationRequest,
} from "./faces.tsx";

interface GalleryImageProps {
    image: ImageWithMeta;
    sort: SortParams;
    paging: GalleryPaging;
    previous_timestamp: number | null;
    has_next_page: boolean;
    overlay_index: number | null;
    index: number;
    showLocationIterpolation: boolean;
    callbacks: ImageCallbacks | null;
}

export type ImageCallbacks = {
    update_url: (update: SearchQuery) => void;
    update_url_add_tag: (tag: string) => void;
    update_url_add_identity: (tag: string) => void;
    prev_item: (index: number, paging: GalleryPaging) => void;
    close_overlay: () => void;
    next_item: (
        index: number,
        has_next_page: boolean,
        paging: GalleryPaging,
    ) => void;
    updateOverlayIndex: (index: number | null) => void;
};

type AnnotateFaceBoxRequest = {
    face: { md5: string; extension: string; position: Position };
    ogRequest: IdentityAnnotation;
    newAnnotation: boolean;
    identities: null | string[];
};

function AnnotateFaceBox({
    request: requestParam,
    availableIdentities,
    cancel,
    updatePendingAnnotations,
}: {
    request: AnnotateFaceBoxRequest;
    availableIdentities: string[];
    cancel: () => void;
    updatePendingAnnotations: (
        request: ManualIdentityClusterRequest_Input,
    ) => void;
}) {
    const { face, identities, ogRequest, newAnnotation } = requestParam;
    const [request, updateRequest] =
        React.useState<IdentityAnnotation>(ogRequest);
    const [og, updateOG] = React.useState<AnnotateFaceBoxRequest>(requestParam);
    if (!isEqual(requestParam, og)) {
        // Need to reset defaults, as request changed
        updateRequest(requestParam.ogRequest);
        updateOG(requestParam);
    }

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
    const posStr = `${Math.trunc(face.position.left)},${Math.trunc(face.position.top)},${Math.ceil(face.position.right)},${Math.ceil(face.position.bottom)}`;
    return (
        <div style={{ position: "absolute", background: "#FFFFFFaa" }}>
            <div style={{ display: "flex" }}>
                <div style={{ flex: "10%" }}>
                    <img
                        style={{ width: "7em", height: "7em" }}
                        src={`/img/original/${face.md5}.${face.extension}?position=${posStr}`}
                    />
                </div>
                <div style={{ flex: "90%" }}>
                    {identities === null ? null : (
                        <>
                            Already assigned identities: {identities.join(", ")}
                            <br />
                        </>
                    )}
                    {newAnnotation ? null : (
                        <>
                            <input
                                type="checkbox"
                                checked={request.skip_reason === "not_face"}
                                onChange={(event) =>
                                    setSkipReason(
                                        event.target.checked
                                            ? "not_face"
                                            : null,
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
                        </>
                    )}
                    <input
                        type="checkbox"
                        checked={request !== null && request.identity !== null}
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
                            const req = makeClusterRequest([face], request);
                            submitAnnotationRequest([req]);
                            if (req !== null) {
                                updatePendingAnnotations(req);
                            }
                            cancel();
                        }}
                        disabled={
                            request.identity === null &&
                            request.skip_reason === null
                        }
                    >
                        Submit this cluster only
                    </button>
                    <button onClick={() => cancel()}>Cancel</button>
                </div>
            </div>
        </div>
    );
}

export function AnnotableImage({
    md5,
    extension,
    imgRef,
    children,
}: React.PropsWithChildren<{
    md5: string;
    extension: string;
    imgRef: React.MutableRefObject<HTMLImageElement | null>;
}>) {
    const svgRef = React.useRef<null | SVGSVGElement>(null);
    const [viewBoxStr, updateViewBoxStr] = React.useState<undefined | string>(
        undefined,
    );
    const [, setDimensions] = React.useState({
        height: window.innerHeight,
        width: window.innerWidth,
    });
    const [faceFeatures, updateFaceFeatures] = React.useState<
        null | FaceWithMeta[]
    >(null);
    const [imgDims, updateImgDims] = React.useState<null | ImgDimensions>(null);
    const [selection, updateSelection] = React.useState<
        null | [number, number, number, number]
    >(null);
    const [addOrUpdateAnnotation, updateAddOrUpdateAnnotation] =
        React.useState<null | AnnotateFaceBoxRequest>(null);
    const [pendingRequest, updatePendingRequests] = React.useState<
        ManualIdentityClusterRequest_Input[]
    >([]);
    const [topIdentities, updateTopIdentities] = React.useState<
        IdentityRowPayload[]
    >([]);
    React.useEffect(() => {
        pygallery_service
            .topIdentitiesPost()
            .then((data) => updateTopIdentities(data));
    }, []);
    const availableIdentities = [
        ...pendingRequest.map((x) => x.identity).filter((x) => x !== null),
    ];
    const availableIdentitiesSet = new Set(availableIdentities);
    topIdentities.forEach((ident) => {
        if (ident.identity === null) {
            return;
        }
        if (availableIdentitiesSet.has(ident.identity)) {
            return;
        }
        availableIdentities.push(ident.identity);
    });
    React.useEffect(() => {
        let shouldUpdate = true;
        pygallery_service
            .faceFeaturesForImagePost({
                requestBody: { md5: md5, extension: extension },
            })
            .then((faces) => {
                if (shouldUpdate) updateFaceFeatures(faces);
            });
        return () => {
            shouldUpdate = false;
        };
    }, [md5, extension]);
    React.useEffect(() => {
        function handleResize() {
            setDimensions({
                height: window.innerHeight,
                width: window.innerWidth,
            });
        }
        window.addEventListener("resize", handleResize);
        return () => {
            window.removeEventListener("resize", handleResize);
        };
    });
    React.useEffect(() => {
        const update = () => {
            if (imgRef.current !== null) {
                // TODO: I don't like this solution at all, but currently don't know better. Alternatively I could render IMG inside svg, but I am not sure how the
                // aspect ratio would be kept (maybe it would work like img?)
                const newValue = computeImgDimentions(imgRef.current);
                if (!isEqual(imgDims, newValue)) {
                    updateImgDims(newValue);
                }
            }
        };
        const interval = setInterval(() => update(), 100);
        return () => clearInterval(interval);
    }, [imgRef, imgDims]);
    let featuresSvgContent: Array<JSX.Element> = [];
    if (imgRef.current !== null && imgDims !== null) {
        if (imgRef.current.src.match("/original/") === null) {
            console.log("skipping because loaded old url", imgRef.current.src);
        } else {
            const vbox = computeSvgViewbox(imgDims);
            if (viewBoxStr !== vbox.viewBox) {
                updateViewBoxStr(vbox.viewBox);
            }
            featuresSvgContent = [
                ...(faceFeatures || []),
                ...pendingRequest.flatMap((x) =>
                    x.faces.map((f) => {
                        return {
                            ...f,
                            identity: x.identity,
                            skip_reason: x.skip_reason,
                            stroke: "yellow",
                        };
                    }),
                ),
                addOrUpdateAnnotation === null
                    ? null
                    : {
                          ...addOrUpdateAnnotation.face,
                          ...addOrUpdateAnnotation?.ogRequest,
                          stroke: "cyan",
                      },
            ]
                .filter((x) => x !== null)
                .map((face) => {
                    const { left, top, right, bottom } = scaleAndShiftPosition(
                        face.position,
                        vbox,
                    );
                    return (
                        <>
                            <a
                                href="#"
                                onClick={() => {
                                    if ("stroke" in face) {
                                        return;
                                    }
                                    updateAddOrUpdateAnnotation({
                                        face,
                                        identities:
                                            face.identity === null
                                                ? []
                                                : [face.identity],
                                        newAnnotation: false,
                                        ogRequest: {
                                            skip_reason: face.skip_reason,
                                            identity: face.identity,
                                        },
                                    });
                                }}
                            >
                                <polygon
                                    fill="transparent"
                                    stroke={
                                        "stroke" in face ? face.stroke : "red"
                                    }
                                    strokeDasharray={
                                        face.skip_reason !== null
                                            ? "2 2"
                                            : undefined
                                    }
                                    points={`${left},${top} ${right},${top} ${right},${bottom} ${left},${bottom}`}
                                />
                                <text
                                    x={left + 3}
                                    y={bottom - 3}
                                    className="svgLabelText"
                                >
                                    {face.identity ||
                                        face.skip_reason ||
                                        ("stroke" in face ? " " : null) ||
                                        "Unlabeled"}
                                </text>
                            </a>
                        </>
                    );
                });
        }
    }
    const selElement =
        selection === null ? null : (
            <>
                <polygon
                    fill="none"
                    stroke="red"
                    points={`${selection[0]},${selection[1]} ${selection[2]},${selection[1]} ${selection[2]},${selection[3]} ${selection[0]},${selection[3]}`}
                />
                <polygon
                    fill="none"
                    stroke="#00FFFF"
                    points={`${selection[0] + 1},${selection[1] + 1} ${selection[2] - 1},${selection[1] + 1} ${selection[2] - 1},${selection[3] - 1} ${selection[0] + 1},${selection[3] - 1}`}
                />
            </>
        );
    return (
        <>
            {children}
            <svg
                ref={svgRef}
                className="gallery_feature"
                viewBox={viewBoxStr}
                width={
                    viewBoxStr === undefined
                        ? undefined
                        : viewBoxStr.split(" ")[2]
                }
                height={
                    viewBoxStr === undefined
                        ? undefined
                        : viewBoxStr.split(" ")[3]
                }
                xmlns="http://www.w3.org/2000/svg"
                onMouseDown={(e) => {
                    if (svgRef.current === null) {
                        return;
                    }
                    const r = svgRef.current.getBoundingClientRect();
                    updateSelection([
                        e.clientX - r.x,
                        e.clientY - r.y,
                        e.clientX - r.x,
                        e.clientY - r.y,
                    ]);
                }}
                onMouseMove={(e) => {
                    {
                        if (svgRef.current === null) {
                            return;
                        }
                        const r = svgRef.current.getBoundingClientRect();
                        if (selection !== null) {
                            const dx = selection[0] - (e.clientX - r.x);
                            const dy = selection[1] - (e.clientY - r.y);
                            if (Math.abs(dx) > Math.abs(dy)) {
                                updateSelection([
                                    selection[0],
                                    selection[1],
                                    selection[0] - dx,
                                    selection[1] - sameDirection(dx, dy),
                                ]);
                            } else {
                                updateSelection([
                                    selection[0],
                                    selection[1],
                                    selection[0] - sameDirection(dy, dx),
                                    selection[1] - dy,
                                ]);
                            }
                        }
                    }
                }}
                onMouseUp={() => {
                    if (selection !== null) {
                        if (
                            Math.abs(selection[0] - selection[2]) < 10 ||
                            Math.abs(selection[1] - selection[3]) < 10
                        ) {
                            updateSelection(null);
                            return;
                        }
                        if (imgDims === null) {
                            return;
                        }
                        const vbox = computeSvgViewbox(imgDims);
                        updateAddOrUpdateAnnotation({
                            face: {
                                md5,
                                extension,
                                position: truncCeilPosition(
                                    unScaleAndShiftPosition(
                                        {
                                            left: Math.min(
                                                selection[0],
                                                selection[2],
                                            ),
                                            top: Math.min(
                                                selection[1],
                                                selection[3],
                                            ),
                                            right: Math.max(
                                                selection[0],
                                                selection[2],
                                            ),
                                            bottom: Math.max(
                                                selection[1],
                                                selection[3],
                                            ),
                                        },
                                        vbox,
                                    ),
                                ),
                            },
                            identities: null,
                            newAnnotation: true,
                            ogRequest: {
                                skip_reason: null,
                                identity: null,
                            },
                        });
                    }
                    updateSelection(null);
                }}
            >
                {selElement}
                {featuresSvgContent}
            </svg>
            {addOrUpdateAnnotation === null ? null : (
                <AnnotateFaceBox
                    request={addOrUpdateAnnotation}
                    availableIdentities={availableIdentities}
                    cancel={() => updateAddOrUpdateAnnotation(null)}
                    updatePendingAnnotations={(req) =>
                        updatePendingRequests([...pendingRequest, req])
                    }
                />
            )}
        </>
    );
}

type ImgDimensions = {
    origW: number;
    origH: number;
    imgW: number;
    imgH: number;
};
function computeImgDimentions(img: HTMLImageElement): ImgDimensions {
    const origW = img.naturalWidth;
    const origH = img.naturalHeight;
    const imgRect = img.getBoundingClientRect();
    const imgW = imgRect.width;
    const imgH = imgRect.height;
    return {
        origW,
        origH,
        imgW,
        imgH,
    };
}

function computeSvgViewbox(imgDims: ImgDimensions): {
    ratioW: number;
    ratioH: number;
    offsetW: number;
    offsetH: number;
    viewBox: string;
} {
    const { origW, origH, imgW, imgH } = imgDims;
    const origAspect = origW / origH;
    const imgAspect = imgW / imgH;
    let offsetH = 0;
    let offsetW = 0;
    let renderedW = 0;
    let renderedH = 0;
    if (imgAspect < origAspect) {
        renderedW = imgW;
        renderedH = (1 / origAspect) * renderedW;
        offsetH = (imgH - renderedH) / 2;
    } else {
        renderedH = imgH;
        renderedW = origAspect * renderedH;
        offsetW = (imgW - renderedW) / 2;
    }
    const viewBox = [0, 0, imgW, imgH];
    const viewBoxStr = viewBox.join(" ");

    return {
        offsetH,
        offsetW,
        ratioW: renderedW / origW,
        ratioH: renderedH / origH,
        viewBox: viewBoxStr,
    };
}

function scaleAndShiftPosition(
    position: Position,
    vbox: { ratioW: number; ratioH: number; offsetW: number; offsetH: number },
): Position {
    return {
        left: vbox.offsetW + vbox.ratioW * position.left,
        top: vbox.offsetH + vbox.ratioH * position.top,
        right: vbox.offsetW + vbox.ratioW * position.right,
        bottom: vbox.offsetH + vbox.ratioH * position.bottom,
    };
}
function unScaleAndShiftPosition(
    position: Position,
    vbox: { ratioW: number; ratioH: number; offsetW: number; offsetH: number },
): Position {
    return {
        left: (position.left - vbox.offsetW) / vbox.ratioW,
        top: (position.top - vbox.offsetH) / vbox.ratioH,
        right: (position.right - vbox.offsetW) / vbox.ratioW,
        bottom: (position.bottom - vbox.offsetH) / vbox.ratioH,
    };
}
function truncCeilPosition(p: Position): Position {
    return {
        left: Math.trunc(p.left),
        top: Math.trunc(p.top),
        right: Math.ceil(p.right),
        bottom: Math.ceil(p.bottom),
    };
}

function sameDirection(scale: number, dir: number): number {
    if (Math.sign(scale) === Math.sign(dir)) {
        return scale;
    }
    return -scale;
}

export function GalleryImage({
    image: { omg, predicted_location, paths },
    sort,
    paging,
    previous_timestamp,
    has_next_page,
    overlay_index,
    index,
    showLocationIterpolation,
    callbacks: callbacksOG,
}: GalleryImageProps) {
    const imgRef = React.useRef<null | HTMLImageElement>(null);

    const callbacks = callbacksOG === null ? null : { ...callbacksOG };

    const isOverlay = index === overlay_index;
    const className = isOverlay ? "gallery_item overlay" : "gallery_item";

    const iconsToShow = [];
    if (omg.being_annotated) {
        iconsToShow.push("🏗️");
    }
    const timestamp = omg.date === null ? null : Date.parse(omg.date) / 1000;
    let timeicon = null;
    if (timestamp !== null) {
        timeicon = time_to_clock(timestamp);
    }

    let movementUx = null;
    if (isOverlay && callbacks !== null) {
        const movement = (
            <>
                <a href="#" onClick={() => callbacks.prev_item(index, paging)}>
                    prev
                </a>{" "}
                <a href="#" onClick={() => callbacks.close_overlay()}>
                    close
                </a>{" "}
                <a
                    href="#"
                    onClick={() =>
                        callbacks.next_item(index, has_next_page, paging)
                    }
                >
                    next
                </a>
            </>
        );
        movementUx = <div>{movement}</div>;
    }

    let timeUx = null;
    if (timestamp !== null && !isOverlay && callbacks !== null) {
        let prevLink = null;
        let nextLink = null;
        if (sort.order === "ASC") {
            prevLink = (
                <a
                    href="#"
                    onClick={() =>
                        callbacks.update_url({ tsto: timestamp + 0.01 })
                    }
                >
                    ⬅️ to
                </a>
            );
        } else {
            prevLink = (
                <a
                    href="#"
                    onClick={() =>
                        callbacks.update_url({ tsfrom: timestamp - 0.01 })
                    }
                >
                    ⬅️ from
                </a>
            );
        }
        if (sort.order == "ASC") {
            nextLink = (
                <a
                    href="#"
                    onClick={() =>
                        callbacks.update_url({ tsfrom: timestamp - 0.01 })
                    }
                >
                    from ➡️
                </a>
            );
        } else {
            nextLink = (
                <a
                    href="#"
                    onClick={() =>
                        callbacks.update_url({ tsto: timestamp + 0.01 })
                    }
                >
                    to ➡️
                </a>
            );
        }
        timeUx = (
            <>
                {prevLink} {timeicon}
                {iconsToShow} {nextLink}
            </>
        );
    } else {
        timeUx = <>{iconsToShow}</>;
    }
    let diffDate = null;
    if (previous_timestamp !== null && timestamp !== null) {
        const diff_date = format_seconds_to_duration(
            Math.abs(previous_timestamp - timestamp),
        );
        diffDate = (
            <>
                {timeicon === null ? null : <br />}⏱️{diff_date}
            </>
        );
    }
    let predictedLocation = null;
    if (predicted_location !== null && showLocationIterpolation) {
        let cls = "LocPredView";
        if (
            predicted_location.earlier === null ||
            predicted_location.later === null
        ) {
            cls += "onesided";
        }
        if (
            (predicted_location.earlier?.distance_m || 0) > 1000 ||
            (predicted_location.later?.distance_m || 0) > 1000 ||
            (predicted_location.earlier?.seconds || 0) > 3600 ||
            (predicted_location.later?.seconds || 0) > 3600
        ) {
            cls += "suspicious";
        }
        predictedLocation = (
            <div className={cls}>
                {predicted_location_to_string(predicted_location)}
            </div>
        );
    }

    let dateCrumb = null;
    let timeCrumb = null;
    if (timestamp !== null) {
        const datetime = new Date(timestamp * 1000);
        // TODO: use proper date formatting
        const time = datetime.toLocaleTimeString();
        const date = datetime.toDateString();
        const startOfDay = datetime.setHours(0, 0, 0, 0) / 1000;
        const endOfDay = startOfDay + 86400;
        dateCrumb = (
            <span className="date">
                <MaybeA
                    onClick={
                        callbacks === null
                            ? null
                            : () =>
                                  callbacks.update_url({
                                      tsfrom: startOfDay,
                                      tsto: endOfDay,
                                  })
                    }
                >
                    {date}
                </MaybeA>
            </span>
        );
        timeCrumb = <span className="date">{time}</span>;
    }
    const addressCrumb: JSX.Element[] = [];
    [
        { address: omg.address.name, key: "addr_name" },
        { address: omg.address.country, key: "addr_cou" },
    ].forEach(({ address, key }) => {
        if (address === null) {
            return;
        }
        addressCrumb.push(
            <span className="location" key={key}>
                <MaybeA
                    onClick={
                        callbacks === null
                            ? null
                            : () => callbacks.update_url({ addr: address })
                    }
                >
                    {append_flag(address)}
                </MaybeA>
            </span>,
        );
    });
    const identityCrumbs: JSX.Element[] = [];
    omg.identities.forEach((identity) => {
        identityCrumbs.push(
            <span className="identity" key={identity}>
                <MaybeA
                    onClick={
                        callbacks === null
                            ? null
                            : () => callbacks.update_url_add_identity(identity)
                    }
                >
                    {identity}
                </MaybeA>
            </span>,
        );
    });
    const max_tag = Math.min(
        1,
        Math.max(1.0, ...Object.values(omg.tags || {})),
    );
    const tagsCrumbs: JSX.Element[] = [];
    Object.entries(omg.tags || {}).forEach(([tag, score]) => {
        const tag_class = classifyTag(score / max_tag);
        if (tag_class === null) {
            // this means not rubish
            tagsCrumbs.push(
                <span className="tag" key={tag}>
                    <MaybeA
                        onClick={
                            callbacks === null
                                ? null
                                : () => callbacks.update_url_add_tag(tag)
                        }
                    >
                        {tag}
                    </MaybeA>
                </span>,
            );
        }
    });
    let cameraCrumb = null;
    if (omg.camera !== null) {
        const camera = omg.camera;
        cameraCrumb = (
            <span className="camera">
                <MaybeA
                    onClick={
                        callbacks === null
                            ? null
                            : () => callbacks.update_url({ camera })
                    }
                >
                    {omg.camera}
                </MaybeA>
            </span>
        );
    }

    const extraImageJsx = [];
    if (isOverlay) {
        if (omg.software) {
            extraImageJsx.push(
                <span className="camera" key="software">
                    {omg.software}
                </span>,
            );
        }
        Object.entries(omg.tags || {}).forEach(([tag, score]) => {
            const tag_class = classifyTag(score / max_tag);
            if (tag_class !== null) {
                // this means rubish
                extraImageJsx.push(
                    <span className="tag" key={`tag_${tag}`}>
                        <MaybeA
                            onClick={
                                callbacks === null
                                    ? null
                                    : () => callbacks.update_url_add_tag(tag)
                            }
                        >
                            {tag_class}
                            {tag}
                        </MaybeA>
                    </span>,
                );
            }
        });
        paths.forEach((path) => {
            extraImageJsx.push(
                <span className="dir" key={`dir_${path.dir}`}>
                    <MaybeA
                        onClick={
                            callbacks === null
                                ? null
                                : () =>
                                      callbacks.update_url({
                                          directory: path.dir,
                                      })
                        }
                    >
                        {path.dir}
                    </MaybeA>
                </span>,
            );
        });
        Object.entries(omg).forEach(([key, value]) => {
            extraImageJsx.push(
                <span className="raw" key={`raw_${key}`}>
                    {key}: {JSON.stringify(value)}
                </span>,
            );
        });
    }

    const img = (
        <img
            ref={imgRef}
            loading="lazy"
            src={`/img/${isOverlay ? "original" : "preview"}/${omg.md5}.${omg.extension}`}
            className="gallery_image"
            alt={omg.classifications || ""}
            title={omg.classifications || ""}
        />
    );
    return (
        <div className={className}>
            <span id={`i${index}`}></span>
            {movementUx}
            {timeUx}
            {diffDate}
            {predictedLocation}
            <div
                className="gallery_container"
                onClick={() => {
                    if (callbacks !== null) {
                        callbacks.updateOverlayIndex(index);
                    }
                }}
            >
                {overlay_index === index ? (
                    <AnnotableImage
                        md5={omg.md5}
                        extension={omg.extension}
                        imgRef={imgRef}
                    >
                        {img}
                    </AnnotableImage>
                ) : (
                    img
                )}
            </div>
            <div className="overflow">
                {dateCrumb}
                {timeCrumb}
                {identityCrumbs}
                {addressCrumb}
                {tagsCrumbs}
                {cameraCrumb}
                {extraImageJsx}
            </div>
        </div>
    );
}

function predicted_location_to_string(predicted: PredictedLocation): string {
    const parts: string[] = [];
    if (predicted.earlier !== null) {
        let speed_str = "";
        if (predicted.earlier.seconds > 0.1) {
            const speed =
                ((predicted.earlier.distance_m / predicted.earlier.seconds) *
                    1000) /
                3600;
            speed_str = `, ${round(speed, 1)}km/h`;
        }
        parts.push(
            `e: ${round(predicted.earlier.distance_m, 0)}m, ${format_seconds_to_duration(predicted.earlier.seconds)}${speed_str}`,
        );
    }
    if (predicted.later) {
        let speed_str = "";
        if (predicted.later.seconds > 0.1) {
            const speed =
                ((predicted.later.distance_m / predicted.later.seconds) *
                    1000) /
                3600;
            speed_str = `, ${round(speed, 1)}km/h`;
        }
        parts.push(
            `l: ${round(predicted.later.distance_m)}m, ${format_seconds_to_duration(predicted.later.seconds)}${speed_str}`,
        );
    }
    return parts.join(", ");
}

function classifyTag(value: number): string | null {
    if (value >= 0.5) return null;
    if (value >= 0.2) return "🤷";
    return "🗑️";
}
