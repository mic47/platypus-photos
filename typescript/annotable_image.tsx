import React from "react";
import { isEqual } from "lodash";

import {
    FaceWithMeta,
    IdentityRowPayload,
    IdentitySkipReason,
    ManualIdentityClusterRequest_Input,
    Position,
} from "./pygallery.generated";
import * as pygallery_service from "./pygallery.generated/sdk.gen.ts";
import {
    IdentityAnnotation,
    makeClusterRequest,
    submitAnnotationRequest,
} from "./faces.tsx";
import { position_to_str } from "./utils.ts";

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
    const [selection, updateSelection] = React.useState<null | Selection>(null);
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
    let featuresSvgContent: Array<React.JSX.Element> = [];
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
                    points={selectionToPointStr(selection)}
                />
                <polygon
                    fill="none"
                    stroke="#00FFFF"
                    points={selectionToPointStr(shrinkSelection(selection))}
                />
            </>
        );
    const squareSelector = new SquareSelector(
        svgRef.current,
        imgDims,
        selection,
        updateSelection,
        (position) => {
            updateAddOrUpdateAnnotation({
                face: {
                    md5,
                    extension,
                    position,
                },
                identities: null,
                newAnnotation: true,
                ogRequest: {
                    skip_reason: null,
                    identity: null,
                },
            });
        },
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
                onMouseDown={(e) => squareSelector.onMouseDown(e)}
                onMouseMove={(e) => squareSelector.onMouseMove(e)}
                onMouseUp={() => squareSelector.onMouseUp()}
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

class SquareSelector {
    private readonly vbox: VBox | null;
    constructor(
        private readonly svg: SVGSVGElement | null,
        private readonly imgDims: ImgDimensions | null,
        private readonly selection: Selection | null,
        private readonly updateSelection: (selection: Selection | null) => void,
        private readonly doAction: (position: Position) => void,
    ) {
        // WARNING: this class should not have any internal state
        if (this.imgDims === null) {
            this.vbox = null;
        } else {
            this.vbox = computeSvgViewbox(this.imgDims);
        }
    }
    private validateShiftedPoint(point: Point): boolean {
        if (this.vbox === null || this.imgDims === null) {
            return false;
        }
        const unscaled = unscaleAndShiftPoint(point, this.vbox);
        if (
            unscaled.x < 0 ||
            unscaled.y < 0 ||
            unscaled.x >= this.imgDims.origW ||
            unscaled.y >= this.imgDims.origH
        ) {
            console.log("outside bound");
            return false;
        }
        return true;
    }
    onMouseDown(e: React.MouseEvent<SVGSVGElement, MouseEvent>) {
        if (this.svg === null) {
            return;
        }
        const r = this.svg.getBoundingClientRect();
        const point = {
            x: e.clientX - r.x,
            y: e.clientY - r.y,
        };
        if (!this.validateShiftedPoint(point)) {
            return;
        }
        this.updateSelection({ start: { ...point }, end: { ...point } });
    }
    onMouseMove(e: React.MouseEvent<SVGSVGElement, MouseEvent>) {
        if (this.svg === null) {
            return;
        }
        const r = this.svg.getBoundingClientRect();
        if (this.selection !== null) {
            const dx = this.selection.start.x - (e.clientX - r.x);
            const dy = this.selection.start.y - (e.clientY - r.y);
            let point = {
                x: this.selection.start.x - sameDirection(dy, dx),
                y: this.selection.start.y - dy,
            };
            if (Math.abs(dx) > Math.abs(dy)) {
                point = {
                    x: this.selection.start.x - dx,
                    y: this.selection.start.y - sameDirection(dx, dy),
                };
            }
            if (!this.validateShiftedPoint(point)) {
                return;
            }
            this.updateSelection({
                start: { ...this.selection.start },
                end: point,
            });
        }
    }
    onMouseUp() {
        if (this.selection !== null) {
            if (
                Math.abs(this.selection.start.x - this.selection.end.x) < 10 ||
                Math.abs(this.selection.start.y - this.selection.end.y) < 10
            ) {
                this.updateSelection(null);
                return;
            }
            if (this.imgDims === null || this.vbox === null) {
                return;
            }
            this.doAction(
                truncCeilPosition(
                    unScaleAndShiftPosition(
                        {
                            left: Math.min(
                                this.selection.start.x,
                                this.selection.end.x,
                            ),
                            top: Math.min(
                                this.selection.start.y,
                                this.selection.end.y,
                            ),
                            right: Math.max(
                                this.selection.start.x,
                                this.selection.end.x,
                            ),
                            bottom: Math.max(
                                this.selection.start.y,
                                this.selection.end.y,
                            ),
                            pts: null,
                        },
                        this.vbox,
                    ),
                ),
            );
        }
        this.updateSelection(null);
    }
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

function computeSvgViewbox(imgDims: ImgDimensions): VBox & {
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

type Selection = {
    start: Point;
    end: Point;
};
function selectionToPointStr(s: Selection): string {
    return `${s.start.x},${s.start.y} ${s.end.x},${s.start.y} ${s.end.x},${s.end.y} ${s.start.x},${s.end.y}`;
}
function shrinkSelection(s: Selection): Selection {
    const out = { start: { ...s.start }, end: { ...s.end } };
    if (out.start.x < out.end.x) {
        out.start.x += 1;
        out.end.x -= 1;
    } else {
        out.end.x += 1;
        out.start.x -= 1;
    }
    if (out.start.y < out.end.y) {
        out.start.y += 1;
        out.end.y -= 1;
    } else {
        out.end.y += 1;
        out.start.y -= 1;
    }
    return out;
}
function scaleAndShiftPosition(position: Position, vbox: VBox): Position {
    return {
        left: vbox.offsetW + vbox.ratioW * position.left,
        top: vbox.offsetH + vbox.ratioH * position.top,
        right: vbox.offsetW + vbox.ratioW * position.right,
        bottom: vbox.offsetH + vbox.ratioH * position.bottom,
        pts: position.pts,
    };
}
type Point = {
    x: number;
    y: number;
};
type VBox = {
    ratioW: number;
    ratioH: number;
    offsetW: number;
    offsetH: number;
};
function unscaleAndShiftPoint(point: Point, vbox: VBox): Point {
    return {
        x: (point.x - vbox.offsetW) / vbox.ratioW,
        y: (point.y - vbox.offsetH) / vbox.ratioH,
    };
}
function unScaleAndShiftPosition(position: Position, vbox: VBox): Position {
    return {
        left: (position.left - vbox.offsetW) / vbox.ratioW,
        top: (position.top - vbox.offsetH) / vbox.ratioH,
        right: (position.right - vbox.offsetW) / vbox.ratioW,
        bottom: (position.bottom - vbox.offsetH) / vbox.ratioH,
        pts: position.pts,
    };
}
function truncCeilPosition(p: Position): Position {
    return {
        left: Math.trunc(p.left),
        top: Math.trunc(p.top),
        right: Math.ceil(p.right),
        bottom: Math.ceil(p.bottom),
        pts: p.pts,
    };
}

function sameDirection(scale: number, dir: number): number {
    if (Math.sign(scale) === Math.sign(dir)) {
        return scale;
    }
    return -scale;
}

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
    const posStr = position_to_str(face.position);
    return (
        <div style={{ position: "absolute", background: "#FFFFFFaa" }}>
            <div style={{ display: "flex" }}>
                <div style={{ flex: "10%" }}>
                    <img
                        style={{ width: "7em", height: "7em" }}
                        src={`/img/original/${face.md5}.${face.extension}?${posStr}`}
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
