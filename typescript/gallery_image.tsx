import React from "react";

import {
    ImageWithMeta,
    PredictedLocation,
    SearchQuery,
    SortParams,
    Image,
    PathSplit,
} from "./pygallery.generated";
import {
    append_flag,
    format_seconds_to_duration,
    round,
    time_to_clock,
} from "./utils";
import { MaybeA } from "./jsx/maybea";
import { AnnotableImage } from "./annotable_image";
import ReactPlayer from "react-player";

interface GalleryImageProps {
    image: ImageWithMeta;
    sort: SortParams;
    previous_timestamp: number | null;
    isOverlay: boolean;
    showLocationIterpolation: boolean;
    callbacks: ImageCallbacks | null;
}

export type ImageCallbacks = {
    update_url: (update: SearchQuery) => void;
    update_url_add_tag: (tag: string) => void;
    update_url_add_identity: (tag: string) => void;
    updateOverlayMd5: (md5: string | null) => void;
};

export type GalleryImageFeatures = {
    showDiffInfo?: boolean;
    showMetadata?: boolean;
    showFaces?: boolean;
    showTimeSelection?: boolean;
};

export function GalleryImage({
    image: { omg, media_class, predicted_location, paths },
    sort,
    previous_timestamp,
    isOverlay,
    showLocationIterpolation,
    callbacks: callbacksOG,
    showDiffInfo,
    showMetadata,
    showTimeSelection,
    showFaces,
    children,
}: React.PropsWithChildren<GalleryImageProps & GalleryImageFeatures>) {
    const imgRef = React.useRef<null | HTMLImageElement>(null);

    const callbacks = callbacksOG === null ? null : { ...callbacksOG };

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

    const width_em =
        omg.dimension == null
            ? 15
            : Math.round((15 / omg.dimension.height) * omg.dimension.width) / 1;
    const gallery_item_width = isOverlay ? "100%" : `${width_em}em`;
    const height_em =
        15 +
        (showTimeSelection === true ? 1 : 0) +
        (showDiffInfo === true ? 2 : 0) +
        (showMetadata === true ? 7 : 0);
    const gallery_item_height = isOverlay ? "100%" : `${height_em}em`;

    const gallery_container_width = isOverlay ? "initial" : `${width_em}em`;
    const gallery_container_height = isOverlay
        ? showMetadata === true
            ? "90%"
            : "100%"
        : "15em";

    const img =
        media_class === "VIDEO" && isOverlay ? (
            <div className="gallery_video">
                <ReactPlayer
                    url={`/video/${omg.md5}.${omg.extension}`}
                    playing={true}
                    controls={true}
                    width="100%"
                    height="100%"
                />
            </div>
        ) : (
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
        <div
            className={className}
            style={{ width: gallery_item_width, height: gallery_item_height }}
        >
            <span id={`i${omg.md5}`}></span>
            {children}
            {showTimeSelection &&
            timestamp !== null &&
            !isOverlay &&
            callbacks !== null ? (
                <TimeUx
                    timestamp={timestamp}
                    timeicon={timeicon}
                    iconsToShow={iconsToShow}
                    sort={sort}
                    callbacks={callbacks}
                />
            ) : (
                <>{iconsToShow}</>
            )}
            {showDiffInfo === true ? (
                <DiffInfo
                    timestamp={timestamp}
                    previous_timestamp={previous_timestamp}
                    predicted_location={predicted_location}
                    showLocationInterpolation={showLocationIterpolation}
                    timeicon={timeicon}
                />
            ) : null}
            <div
                className="gallery_container"
                style={{
                    width: gallery_container_width,
                    height: gallery_container_height,
                }}
                onClick={() => {
                    if (callbacks !== null) {
                        callbacks.updateOverlayMd5(omg.md5);
                    }
                }}
            >
                {isOverlay && showFaces ? (
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
            {showMetadata ? (
                <MetadataInfo
                    omg={omg}
                    paths={paths}
                    isOverlay={isOverlay}
                    timestamp={timestamp}
                    callbacks={callbacks}
                />
            ) : null}
        </div>
    );
}

function MetadataInfo({
    omg,
    paths,
    isOverlay,
    timestamp,
    callbacks,
}: {
    omg: Image;
    paths: PathSplit[];
    isOverlay: boolean;
    timestamp: number | null;
    callbacks: ImageCallbacks | null;
}) {
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
    const addressCrumb: React.JSX.Element[] = [];
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
    const identityCrumbs: React.JSX.Element[] = [];
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
    const tagsCrumbs: React.JSX.Element[] = [];
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
    return (
        <div className="overflow">
            {dateCrumb}
            {timeCrumb}
            {identityCrumbs}
            {addressCrumb}
            {tagsCrumbs}
            {cameraCrumb}
            {extraImageJsx}
        </div>
    );
}

function DiffInfo({
    timestamp,
    previous_timestamp,
    predicted_location,
    showLocationInterpolation,
    timeicon,
}: {
    timestamp: number | null;
    previous_timestamp: number | null;
    predicted_location: PredictedLocation | null;
    showLocationInterpolation: boolean;
    timeicon: string | null;
}) {
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
    if (predicted_location !== null && showLocationInterpolation) {
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
    return (
        <>
            {diffDate} {predictedLocation}
        </>
    );
}
function TimeUx({
    timestamp,
    timeicon,
    iconsToShow,
    sort,
    callbacks,
}: {
    timestamp: number;
    timeicon: string | null;
    iconsToShow: string[];
    sort: SortParams;
    callbacks: ImageCallbacks;
}) {
    let prevLink = null;
    let nextLink = null;
    if (sort.order === "ASC") {
        prevLink = (
            <a
                href="#"
                onClick={() => callbacks.update_url({ tsto: timestamp + 0.01 })}
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
                onClick={() => callbacks.update_url({ tsto: timestamp + 0.01 })}
            >
                to ➡️
            </a>
        );
    }
    return (
        <>
            {prevLink} {timeicon}
            {iconsToShow} {nextLink}
        </>
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
