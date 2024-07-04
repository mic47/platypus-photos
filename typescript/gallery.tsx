import { createRoot, Root } from "react-dom/client";
import React from "react";

import {
    GalleryPaging,
    ImageAggregation,
    ImageResponse,
    ImageWithMeta,
    ManualLocation,
    PredictedLocation,
    SearchQuery,
    SortParams,
} from "./pygallery.generated/types.gen.ts";
import {
    CheckboxesParams,
    CheckboxSync,
    StateWithHooks,
    UrlSync,
} from "./state.ts";
import * as pygallery_service from "./pygallery.generated/services.gen.ts";
import {
    append_flag,
    format_seconds_to_duration,
    round,
    time_to_clock,
} from "./utils.ts";
import { AnnotationOverlay } from "./photo_map.ts";

export class Gallery {
    private root: Root;
    constructor(
        private div_id: string,
        searchQueryHook: StateWithHooks<SearchQuery>,
        pagingHook: StateWithHooks<GalleryPaging>,
        sortHook: StateWithHooks<SortParams>,
        checkboxSync: CheckboxSync,
    ) {
        const element = document.getElementById(this.div_id);
        if (element === null) {
            throw new Error(`Unable to find element ${this.div_id}`);
        }
        this.root = createRoot(element);
        const galleryUrlSync = new UrlSync(["oi"]);
        this.root.render(
            <React.StrictMode>
                <GalleryComponent
                    searchQueryHook={searchQueryHook}
                    pagingHook={pagingHook}
                    sortHook={sortHook}
                    checkboxSync={checkboxSync}
                    urlSync={galleryUrlSync}
                />
            </React.StrictMode>,
        );
    }
}

interface GalleryComponentProps {
    searchQueryHook: StateWithHooks<SearchQuery>;
    pagingHook: StateWithHooks<GalleryPaging>;
    sortHook: StateWithHooks<SortParams>;
    checkboxSync: CheckboxSync;
    urlSync: UrlSync;
}
function GalleryComponent({
    searchQueryHook,
    pagingHook,
    sortHook,
    checkboxSync,
    urlSync,
}: GalleryComponentProps) {
    const [data, updateData] = React.useState<[SearchQuery, ImageResponse]>([
        {},
        {
            omgs: [],
            has_next_page: false,
            some_location: null,
        },
    ]);
    const [aggr, updateAggr] = React.useState<{
        aggr: ImageAggregation;
        paging: GalleryPaging;
    }>({
        aggr: {
            total: 0,
            address: {},
            tag: {},
            classification: {},
            cameras: {},
        },
        paging: pagingHook.get(),
    });
    const [query, updateQuery] = React.useState<SearchQuery>(
        searchQueryHook.get(),
    );
    const [paging, updatePaging] = React.useState<GalleryPaging>(
        pagingHook.get(),
    );
    const [overlayIndex, updateOverlayIndex] = React.useState<null | number>(
        () => {
            const oi = parseInt(urlSync.get().unparsed["oi"]);
            return oi === undefined || oi != oi ? null : oi;
        },
    );
    React.useEffect(() => {
        urlSync.update({ oi: overlayIndex });
    }, [overlayIndex]);
    const [sort, updateSort] = React.useState<SortParams>(sortHook.get());
    const [checkboxes, updateCheckboxes] = React.useState<{
        [name: string]: boolean;
    }>(checkboxSync.get());
    React.useEffect(() => {
        let ignore = false;
        const requestBody = {
            query,
            paging,
            sort,
        };
        pygallery_service
            .imagePagePost({
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
    React.useEffect(() => {
        let ignore = false;
        const requestBody = {
            query,
        };
        const copiedPaging = { ...paging };
        pygallery_service
            .aggregateImagesPost({
                requestBody,
            })
            .then((data) => {
                if (!ignore) {
                    updateAggr({ aggr: data, paging: copiedPaging });
                }
            });
        return () => {
            ignore = true;
        };
    }, [query, paging]);
    React.useEffect(() => {
        searchQueryHook.register_hook("Gallery", (data) => {
            updateQuery(data);
        });
        return () => searchQueryHook.unregister_hook("Gallery");
    });
    React.useEffect(() => {
        pagingHook.register_hook("Gallery", updatePaging);
        return () => pagingHook.unregister_hook("Gallery");
    });
    React.useEffect(() => {
        sortHook.register_hook("Gallery", updateSort);
        return () => sortHook.unregister_hook("Gallery");
    });
    const callbacks = {
        updateOverlayIndex,
        // TODO
        prev_page: () => {},
        next_page: () => {},
        set_page: () => {},
        annotation_overlay_interpolated: (location: ManualLocation) => {
            const overlay = new AnnotationOverlay("SubmitDataOverlay");
            overlay.fetch({
                request: {
                    t: "InterpolatedLocation",
                    location,
                },
                query: searchQueryHook.get(),
            });
        },
        update_checkbox_from_element: (element: HTMLInputElement) => {
            checkboxSync.update_from_element(element);
            updateCheckboxes(checkboxSync.get());
        },
        update_url: (update: SearchQuery) => {
            searchQueryHook.update(update);
        },
        update_url_add_tag: (tag: string) => {
            const old_tag = searchQueryHook.get()["tag"];
            if (old_tag === undefined || old_tag === null) {
                searchQueryHook.update({ tag: tag });
            } else {
                searchQueryHook.update({ tag: `${old_tag},${tag}` });
            }
        },
        close_overlay: () => {
            updateOverlayIndex(null);
        },
        prev_item: (index: number, paging: GalleryPaging) => {
            const newIndex = index - 1;
            if (newIndex >= 0) {
                updateOverlayIndex(newIndex);
            } else if (paging.page !== undefined && paging.page > 0) {
                const newPage = paging.page - 1;
                const newIndex = (paging.paging || 100) - 1;
                pagingHook.update({ page: newPage });
                updateOverlayIndex(newIndex);
            }
        },
        next_item: (
            index: number,
            has_next_page: boolean,
            paging: GalleryPaging,
        ) => {
            const newIndex = index + 1;
            if (newIndex < (paging.paging || 100)) {
                updateOverlayIndex(newIndex);
            } else if (has_next_page) {
                pagingHook.update({ page: (paging.page || 0) + 1 });
                updateOverlayIndex(0);
            }
        },
    };
    return (
        <>
            <AggregateInfoView
                aggr={aggr.aggr}
                paging={aggr.paging}
                show_links={true}
                callbacks={callbacks}
            />
            <GalleryView
                sort={sort}
                paging={paging}
                data={data[1]}
                checkboxes={checkboxes}
                overlay_index={overlayIndex}
                callbacks={callbacks}
            />
        </>
    );
}

interface GalleryViewProps {
    sort: SortParams;
    paging: GalleryPaging;
    data: ImageResponse;
    checkboxes: CheckboxesParams;
    overlay_index: number | null;
    callbacks: ImageCallbacks & {
        prev_page: () => void;
        next_page: () => void;
        annotation_overlay_interpolated: (location: ManualLocation) => void;
        update_checkbox_from_element: (element: HTMLInputElement) => void;
    };
}
function GalleryView({
    sort,
    paging,
    data,
    checkboxes,
    overlay_index,
    callbacks,
}: GalleryViewProps) {
    let prev_date: string | null = null;
    const galleryItems = data.omgs.map((image, index) => {
        const ret = (
            <GalleryImage
                key={index}
                image={image}
                sort={sort}
                paging={paging}
                previous_timestamp={
                    prev_date === null ? null : Date.parse(prev_date) / 1000
                }
                overlay_index={overlay_index}
                has_next_page={data.has_next_page}
                index={index}
                callbacks={callbacks}
            />
        );
        prev_date = image.omg.date;
        return ret;
    });

    const some_location = data.some_location;
    const locInterpolation =
        some_location === null ? null : (
            <button
                className="LocPredView"
                onClick={() =>
                    callbacks.annotation_overlay_interpolated(some_location)
                }
            >
                Run Location Interpolation
            </button>
        );
    return (
        <>
            <span>
                <a
                    href="#"
                    className="prev-url"
                    onClick={() => callbacks.prev_page()}
                >
                    Prev Page
                </a>{" "}
                <a
                    href="#"
                    className="next-url"
                    onClick={() => callbacks.next_page()}
                >
                    Next Page
                </a>
            </span>
            <input
                type="checkbox"
                id="LocPredCheck"
                checked={checkboxes["LocPredCheck"]}
                onClick={(event) =>
                    callbacks.update_checkbox_from_element(event.currentTarget)
                }
            />
            Show Location Interpolation
            {locInterpolation}
            <div>{galleryItems}</div>
            <br />
            <div
                style={{ float: "left", background: "#CCCCCC", height: "10em" }}
            >
                <a
                    href="#"
                    className="prev-url"
                    onClick={() => callbacks.prev_page()}
                >
                    Prev Page
                </a>{" "}
                <a
                    href="#"
                    className="next-url"
                    onClick={() => callbacks.next_page()}
                >
                    Next Page
                </a>
            </div>
        </>
    );
}

type ImageCallbacks = {
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

interface GalleryImageProps {
    image: ImageWithMeta;
    sort: SortParams;
    paging: GalleryPaging;
    previous_timestamp: number | null;
    has_next_page: boolean;
    overlay_index: number | null;
    index: number;
    callbacks: ImageCallbacks;
}

function GalleryImage({
    image: { omg, predicted_location, paths },
    sort,
    paging,
    previous_timestamp,
    has_next_page,
    overlay_index,
    index,
    callbacks: {
        update_url,
        update_url_add_tag,
        prev_item,
        close_overlay,
        next_item,
        updateOverlayIndex,
    },
}: GalleryImageProps) {
    // GalleryItemFS -> len ak overlay --- mali by sme to len tak renderovat
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
    if (isOverlay) {
        const movement = (
            <>
                <a href="#" onClick={() => prev_item(index, paging)}>
                    prev
                </a>{" "}
                <a href="#" onClick={() => close_overlay()}>
                    close
                </a>{" "}
                <a
                    href="#"
                    onClick={() => next_item(index, has_next_page, paging)}
                >
                    next
                </a>
            </>
        );
        movementUx = <div>{movement}</div>;
    }

    let timeUx = null;
    if (timestamp !== null && !isOverlay) {
        let prevLink = null;
        let nextLink = null;
        if (sort.order === "ASC") {
            prevLink = (
                <a
                    href="#"
                    onClick={() => update_url({ tsto: timestamp + 0.01 })}
                >
                    ⬅️ to
                </a>
            );
        } else {
            prevLink = (
                <a
                    href="#"
                    onClick={() => update_url({ tsfrom: timestamp - 0.01 })}
                >
                    ⬅️ from
                </a>
            );
        }
        if (sort.order == "ASC") {
            nextLink = (
                <a
                    href="#"
                    onClick={() => update_url({ tsfrom: timestamp - 0.01 })}
                >
                    from ➡️
                </a>
            );
        } else {
            nextLink = (
                <a
                    href="#"
                    onClick={() => update_url({ tsto: timestamp + 0.01 })}
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
                <a
                    onClick={() =>
                        update_url({
                            tsfrom: startOfDay,
                            tsto: endOfDay,
                        })
                    }
                    href="#"
                >
                    {date}
                </a>
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
                <a onClick={() => update_url({ addr: address })} href="#">
                    {append_flag(address)}
                </a>
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
                    <a onClick={() => update_url_add_tag(tag)} href="#">
                        {score}
                        {tag}
                    </a>
                </span>,
            );
        }
    });
    let cameraCrumb = null;
    if (omg.camera !== null) {
        const camera = omg.camera;
        cameraCrumb = (
            <span className="camera">
                <a onClick={() => update_url({ camera })} href="#">
                    {omg.camera}
                </a>
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
                        <a onClick={() => update_url_add_tag(tag)} href="#">
                            {tag_class}
                            {tag}
                        </a>
                    </span>,
                );
            }
        });
        paths.forEach((path) => {
            extraImageJsx.push(
                <span className="dir" key={`dir_${path.dir}`}>
                    <a
                        onClick={() => update_url({ directory: path.dir })}
                        href="#"
                    >
                        {path.dir}
                    </a>
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
                onClick={() => updateOverlayIndex(index)}
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

interface AggregateInfoViewProps {
    aggr: ImageAggregation;
    paging: GalleryPaging;
    show_links: boolean;
    callbacks: {
        update_url_add_tag: (tag: string) => void;
        update_url: (update: SearchQuery) => void;
        set_page: (page: number) => void;
    };
}

function AggregateInfoView({
    aggr,
    paging,
    show_links,
    callbacks: { update_url_add_tag, update_url, set_page },
}: AggregateInfoViewProps) {
    const num_pages = Math.ceil(aggr.total / (paging.paging || 100));
    const tags = Object.entries(aggr.tag)
        .sort(([, a], [, b]) => b - a)
        .slice(0, 15)
        .map(([tag, num]) => {
            if (show_links) {
                return (
                    <>
                        <a
                            key={tag}
                            onClick={() => update_url_add_tag(tag)}
                            href="#"
                        >
                            {tag} ({num})
                        </a>{" "}
                    </>
                );
            } else {
                return (
                    <>
                        {tag} ({num}){" "}
                    </>
                );
            }
        });
    const texts = Object.entries(aggr.classification)
        .sort(([, a], [, b]) => b - a)
        .slice(0, 5)
        .map(([text, num]) => {
            if (show_links) {
                return (
                    <>
                        <a
                            key={text}
                            onClick={() => update_url({ cls: text })}
                            href="#"
                        >
                            {text} ({num})
                        </a>{" "}
                    </>
                );
            } else {
                return (
                    <>
                        {text} ({num}){" "}
                    </>
                );
            }
        });
    const locs = Object.entries(aggr.address)
        .sort(([, a], [, b]) => b - a)
        .slice(0, 15)
        .map(([loc, num]) => {
            if (show_links) {
                return (
                    <>
                        <a
                            key={loc}
                            onClick={() => update_url({ addr: loc })}
                            href="#"
                        >
                            {append_flag(loc)} ({num})
                        </a>{" "}
                    </>
                );
            } else {
                return (
                    <>
                        {append_flag(loc)} ({num}){" "}
                    </>
                );
            }
        });
    const cameras = Object.entries(aggr.cameras)
        .sort(([, a], [, b]) => b - a)
        .splice(15)
        .map(([camera, num]) => {
            if (show_links || camera in ["unknown", "other", "distinct"]) {
                return (
                    <>
                        <a
                            key={camera}
                            onClick={() => update_url({ camera: camera })}
                            href="#"
                        >
                            {camera} ({num})
                        </a>{" "}
                    </>
                );
            } else {
                return (
                    <>
                        {append_flag(camera)} ({num}){" "}
                    </>
                );
            }
        });
    const pages = [...Array(num_pages).keys()]
        .filter((page) => page <= 10 || page >= num_pages - 10)
        .map((page) => {
            if (page !== 10) {
                return (
                    <>
                        <a key={page} href="#" onClick={() => set_page(page)}>
                            {page}
                        </a>{" "}
                    </>
                );
            } else {
                return <> ... </>;
            }
        });
    return (
        <div>
            Found {aggr.total} matches.
            <br />
            Top tags: {tags}
            <br />
            Top texts: {texts}
            <br />
            Top locs: {locs}
            <br />
            Cameras: {cameras}
            <br />
            Go to page: {pages}
            <br />
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
