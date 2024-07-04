import React from "react";

import {
    GalleryPaging,
    ImageWithMeta,
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

interface GalleryImageProps {
    image: ImageWithMeta;
    sort: SortParams;
    paging: GalleryPaging;
    previous_timestamp: number | null;
    has_next_page: boolean;
    overlay_index: number | null;
    index: number;
    callbacks: ImageCallbacks | null;
}

export type ImageCallbacks = {
    update_url: (update: SearchQuery) => void;
    update_url_add_tag: (tag: string) => void;
    prev_item: (index: number, paging: GalleryPaging) => void;
    close_overlay: () => void;
    next_item: (
        index: number,
        has_next_page: boolean,
        paging: GalleryPaging,
    ) => void;
    updateOverlayIndex: (index: number | null) => void;
};

export function GalleryImage({
    image: { omg, predicted_location, paths },
    sort,
    paging,
    previous_timestamp,
    has_next_page,
    overlay_index,
    index,
    callbacks: callbacksOG,
}: GalleryImageProps) {
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
    if (predicted_location !== null) {
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
                        {score}
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
                <img
                    loading="lazy"
                    src={`/img?hsh=${omg.md5}&size=${isOverlay ? "original" : "preview"}`}
                    className="gallery_image"
                    alt={omg.classifications || ""}
                    title={omg.classifications || ""}
                />
            </div>
            <div className="overflow">
                {dateCrumb}
                {timeCrumb}
                {addressCrumb}
                {tagsCrumbs}
                {cameraCrumb}
                {extraImageJsx}
            </div>
        </div>
    );
}

function MaybeA({
    onClick,
    children,
}: React.PropsWithChildren<{ onClick: null | (() => void) }>) {
    if (onClick === null) {
        return <>{children}</>;
    } else {
        return (
            <a href="#" onClick={onClick}>
                {children}
            </a>
        );
    }
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
