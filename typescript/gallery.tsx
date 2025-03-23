import React from "react";

import {
    GalleryPaging,
    ImageAggregation,
    ImageResponse,
    ManualLocation,
    SearchQuery,
    SortParams,
} from "./pygallery.generated/types.gen.ts";
import { CheckboxesParams, CheckboxSync } from "./state.ts";
import * as pygallery_service from "./pygallery.generated/sdk.gen.ts";
import { GalleryImage, ImageCallbacks } from "./gallery_image.tsx";
import { AggregateInfoView } from "./aggregate_info.tsx";
import { AnnotationOverlayRequest } from "./annotations.tsx";
import { UpdateCallbacks } from "./types";

export type GalleryUrlParams = {
    oi: null | number;
};
export function parse_gallery_url(data: {
    unparsed: { [key: string]: string };
}): GalleryUrlParams {
    const oi = parseInt(data.unparsed["oi"]);
    return { oi: oi === undefined || oi != oi ? null : oi };
}
interface GalleryComponentProps {
    query: SearchQuery;
    queryCallbacks: UpdateCallbacks<SearchQuery>;
    paging: GalleryPaging;
    sort: SortParams;
    galleryUrl: GalleryUrlParams;
    galleryUrlCallbacks: UpdateCallbacks<GalleryUrlParams>;
    submit_annotations: (request: AnnotationOverlayRequest) => void;
    // TODO: remove folllowing 2, they are not done in react way
    checkboxSync: CheckboxSync;
}
export function GalleryComponent({
    query,
    paging,
    sort,
    queryCallbacks,
    galleryUrl,
    galleryUrlCallbacks,
    checkboxSync,
    submit_annotations,
}: GalleryComponentProps) {
    const [data, updateData] = React.useState<GalleryComponentFetchState>({
        query,
        response: {
            omgs: [],
            has_next_page: false,
            some_location: null,
        },
        md5ToIndex: new Map(),
        lastFetchedPage: -1,
    });
    const [pageToFetch, updatePageToFetch] = React.useState<number>(0);
    React.useEffect(() => {
        // If query or paging changes, refetch,
        updatePageToFetch(0);
    }, [query, paging]);
    const handleScroll = () => {
        const bottom =
            Math.ceil(window.innerHeight + window.scrollY) >=
            document.documentElement.scrollHeight - 200;
        if (bottom) {
            if (data.response.has_next_page) {
                updatePageToFetch(data.lastFetchedPage + 1);
            }
        }
    };
    React.useEffect(() => {
        window.addEventListener("scroll", handleScroll);
        return () => {
            window.removeEventListener("scroll", handleScroll);
        };
    }, [query, paging, data.lastFetchedPage, data.response.has_next_page]);
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
            identities: {},
        },
        paging,
    });

    // OI should go outside?
    const [overlayIndex, updateOverlayIndex] = React.useState<null | number>(
        galleryUrl["oi"],
    );
    React.useEffect(() => {
        galleryUrlCallbacks.update({ oi: overlayIndex });
    }, [overlayIndex]);

    const [checkboxes, updateCheckboxes] = React.useState<{
        [name: string]: boolean;
    }>(checkboxSync.get());
    React.useEffect(() => {
        let ignore = false;
        const requestBody = {
            query,
            paging: { paging: paging.paging, page: pageToFetch },
            sort,
        };
        pygallery_service
            .imagePagePost({
                requestBody,
            })
            .then(({ has_next_page, omgs, some_location }) => {
                if (!ignore) {
                    const response =
                        pageToFetch > 0
                            ? { ...data.response }
                            : {
                                  has_next_page,
                                  omgs: [],
                                  some_location,
                              };
                    if (some_location !== null) {
                        response.some_location = some_location;
                    }
                    response.has_next_page = has_next_page;
                    // Images are used as dependency, we need to change it
                    response.omgs = [...response.omgs, ...omgs];
                    // This is ok, as md5ToIndex is not used as dependency for useEffect
                    const md5ToIndex =
                        pageToFetch > 0 ? data.md5ToIndex : new Map();
                    response.omgs.forEach((image, index) => {
                        md5ToIndex.set(image.omg.md5, index);
                    });
                    updateData({
                        query,
                        response,
                        md5ToIndex,
                        lastFetchedPage: pageToFetch,
                    });
                }
            });
        return () => {
            ignore = true;
        };
    }, [query, paging, sort, pageToFetch]);
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
        if (
            overlayIndex !== null &&
            data.response.omgs.length <= overlayIndex
        ) {
            updatePageToFetch(data.lastFetchedPage + 1);
        }
    }, [overlayIndex, data.lastFetchedPage]);
    const md5ToIndex = data.md5ToIndex;
    const callbacks = {
        updateOverlayMd5: (md5: string | null) => {
            if (md5 !== null) {
                const index = md5ToIndex.get(md5);
                if (index !== undefined) {
                    updateOverlayIndex(index);
                    return;
                }
            }
            updateOverlayIndex(null);
        },
        annotation_overlay_interpolated: (location: ManualLocation) => {
            submit_annotations({
                request: {
                    t: "InterpolatedLocation",
                    location,
                },
                query,
            });
        },
        update_checkbox_from_element: (element: HTMLInputElement) => {
            checkboxSync.update_from_element(element);
            updateCheckboxes(checkboxSync.get());
        },
        update_url: (update: SearchQuery) => {
            queryCallbacks.update(update);
        },
        update_url_add_tag: (tag: string) => {
            const old_tag = query["tag"];
            if (old_tag === undefined || old_tag === null) {
                queryCallbacks.update({ tag: tag });
            } else {
                queryCallbacks.update({ tag: `${old_tag},${tag}` });
            }
        },
        update_url_add_identity: (identity: string) => {
            const old_identity = query["identity"];
            if (old_identity === undefined || old_identity === null) {
                queryCallbacks.update({ identity: identity });
            } else {
                queryCallbacks.update({
                    identity: `${old_identity},${identity}`,
                });
            }
        },
    };
    const overlayMovementCallbacks = {
        close_overlay: () => {
            updateOverlayIndex(null);
        },
        prev_item: (index: number) => {
            const newIndex = index - 1;
            if (newIndex >= 0) {
                updateOverlayIndex(newIndex);
            }
        },
        next_item: (index: number, has_next_page: boolean) => {
            const newIndex = index + 1;
            if (newIndex < data.response.omgs.length) {
                updateOverlayIndex(newIndex);
            } else if (has_next_page) {
                updatePageToFetch(data.lastFetchedPage + 1);
                updateOverlayIndex(newIndex);
            }
        },
    };
    return (
        <>
            <AggregateInfoView
                aggr={aggr.aggr}
                show_links={true}
                callbacks={callbacks}
            />
            <GalleryView
                sort={sort}
                data={data.response}
                checkboxes={checkboxes}
                overlay_index={overlayIndex}
                callbacks={callbacks}
                overlayMovementCallbacks={overlayMovementCallbacks}
            />
        </>
    );
}

type GalleryComponentFetchState = {
    query: SearchQuery;
    response: ImageResponse;
    md5ToIndex: Map<string, number>;
    lastFetchedPage: number;
};

interface GalleryViewProps {
    sort: SortParams;
    data: ImageResponse;
    checkboxes: CheckboxesParams;
    overlay_index: number | null;
    callbacks: ImageCallbacks & {
        annotation_overlay_interpolated: (location: ManualLocation) => void;
        update_checkbox_from_element: (element: HTMLInputElement) => void;
    };
    overlayMovementCallbacks: OverlayMovementCallbacks;
}
function GalleryView({
    sort,
    data,
    checkboxes,
    overlay_index,
    callbacks,
    overlayMovementCallbacks,
}: GalleryViewProps) {
    let prev_date: string | null = null;
    const overlayItem =
        overlay_index === null || overlay_index >= data.omgs.length ? null : (
            <GalleryImage
                image={data.omgs[overlay_index]}
                sort={sort}
                previous_timestamp={
                    prev_date === null ? null : Date.parse(prev_date) / 1000
                }
                isOverlay={true}
                showLocationIterpolation={checkboxes["LocPredCheck"] === true}
                showDiffInfo={
                    checkboxes["LocPredCheck"] === true ||
                    checkboxes["ShowDiffCheck"] === true
                }
                showTimeSelection={
                    checkboxes["ShowTimeSelectionCheck"] === true
                }
                showMetadata={checkboxes["ShowMetadataCheck"] === true}
                callbacks={callbacks}
            >
                {callbacks !== null ? (
                    <OverlayMovementUx
                        index={overlay_index}
                        md5={data.omgs[overlay_index].omg.md5}
                        has_next_page={data.has_next_page}
                        callbacks={overlayMovementCallbacks}
                    />
                ) : null}
            </GalleryImage>
        );
    const galleryItems = data.omgs.map((image) => {
        const ret = (
            <GalleryImage
                key={image.omg.md5}
                image={image}
                sort={sort}
                previous_timestamp={
                    prev_date === null ? null : Date.parse(prev_date) / 1000
                }
                isOverlay={false}
                showLocationIterpolation={checkboxes["LocPredCheck"] === true}
                showDiffInfo={
                    checkboxes["LocPredCheck"] === true ||
                    checkboxes["ShowDiffCheck"] === true
                }
                showTimeSelection={
                    checkboxes["ShowTimeSelectionCheck"] === true
                }
                showMetadata={checkboxes["ShowMetadataCheck"] === true}
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
            <input
                type="checkbox"
                id="ShowTimeSelectionCheck"
                checked={checkboxes["ShowTimeSelection"]}
                onClick={(event) =>
                    callbacks.update_checkbox_from_element(event.currentTarget)
                }
            />
            Show Time Selection
            <input
                type="checkbox"
                id="ShowDiffCheck"
                checked={checkboxes["ShowDiffCheck"]}
                onClick={(event) =>
                    callbacks.update_checkbox_from_element(event.currentTarget)
                }
            />
            Show Diff
            <input
                type="checkbox"
                id="ShowMetadataCheck"
                checked={checkboxes["ShowMetadataCheck"]}
                onClick={(event) =>
                    callbacks.update_checkbox_from_element(event.currentTarget)
                }
            />
            Show Metadata
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
            <div>
                {overlayItem} {galleryItems}
            </div>
        </>
    );
}

type OverlayMovementCallbacks = {
    prev_item: (index: number) => void;
    close_overlay: () => void;
    next_item: (index: number, has_next_page: boolean) => void;
};

function OverlayMovementUx({
    index,
    md5,
    has_next_page,
    callbacks,
}: {
    index: number;
    md5: string;
    has_next_page: boolean;
    callbacks: OverlayMovementCallbacks;
}) {
    return (
        <div>
            <a
                href={`#i${md5}`}
                onClick={(event) => {
                    event.preventDefault();
                    callbacks.prev_item(index);
                }}
            >
                prev
            </a>{" "}
            <a href={`#i${md5}`} onClick={() => callbacks.close_overlay()}>
                close
            </a>{" "}
            <a
                href={`#i${md5}`}
                onClick={(event) => {
                    event.preventDefault();
                    callbacks.next_item(index, has_next_page);
                }}
            >
                next
            </a>
        </div>
    );
}
