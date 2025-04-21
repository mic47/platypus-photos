import React from "react";

import {
    GalleryPaging,
    ImageResponse,
    ManualLocation,
    SearchQuery,
    SortParams,
} from "./pygallery.generated/types.gen.ts";
import * as pygallery_service from "./pygallery.generated/sdk.gen.ts";
import { GalleryImage, ImageCallbacks } from "./gallery_image.tsx";
import { AnnotationOverlayRequest } from "./annotations.tsx";
import { UpdateCallbacks, QueryCallbacks } from "./types";

type ValidCheckboxes =
    | "LocPredCheck"
    | "ShowDiffCheck"
    | "ShowTimeSelectionCheck"
    | "ShowFaceMetadata"
    | "ShowMetadataCheck";

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
    queryCallbacks: QueryCallbacks;
    paging: GalleryPaging;
    sort: SortParams;
    galleryUrl: GalleryUrlParams;
    galleryUrlCallbacks: UpdateCallbacks<GalleryUrlParams>;
    submit_annotations: (request: AnnotationOverlayRequest) => void;
    checkboxes: Record<ValidCheckboxes, boolean>;
}
export function GalleryComponent({
    children,
    query,
    paging,
    sort,
    queryCallbacks,
    galleryUrl,
    galleryUrlCallbacks,
    checkboxes,
    submit_annotations,
}: React.PropsWithChildren<GalleryComponentProps>) {
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

    // OI should go outside?
    const [overlayIndex, updateOverlayIndex] = React.useState<null | number>(
        galleryUrl["oi"],
    );
    React.useEffect(() => {
        galleryUrlCallbacks.update({ oi: overlayIndex });
    }, [overlayIndex]);

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
        if (
            overlayIndex !== null &&
            data.response.omgs.length <= overlayIndex
        ) {
            updatePageToFetch(data.lastFetchedPage + 1);
        }
    }, [overlayIndex, data.lastFetchedPage]);
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
    React.useEffect(() => {
        if (overlayIndex === null) {
            return () => {};
        }
        const handleKeyPress = (e: KeyboardEvent) => {
            if (overlayIndex === null) {
                return;
            }
            if (e.key == "Escape") {
                overlayMovementCallbacks.close_overlay();
            } else if (e.key == "ArrowRight" || e.key == " ") {
                overlayMovementCallbacks.next_item(
                    overlayIndex,
                    data.response.has_next_page,
                );
            } else if (e.key == "ArrowLeft" || e.key == "Backspace") {
                overlayMovementCallbacks.prev_item(overlayIndex);
            }
        };

        document.addEventListener("keydown", handleKeyPress);
        return () => document.removeEventListener("keydown", handleKeyPress);
    }, [overlayIndex, data.response.has_next_page]);
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
        ...queryCallbacks,
    };
    return (
        <GalleryView
            sort={sort}
            data={data.response}
            checkboxes={checkboxes}
            overlay_index={overlayIndex}
            callbacks={callbacks}
            overlayMovementCallbacks={overlayMovementCallbacks}
        >
            {children}
        </GalleryView>
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
    checkboxes: Record<ValidCheckboxes, boolean>;
    overlay_index: number | null;
    callbacks: ImageCallbacks & {
        annotation_overlay_interpolated: (location: ManualLocation) => void;
    };
    overlayMovementCallbacks: OverlayMovementCallbacks;
}
function GalleryView({
    children,
    sort,
    data,
    checkboxes,
    overlay_index,
    callbacks,
    overlayMovementCallbacks,
}: React.PropsWithChildren<GalleryViewProps>) {
    if (overlay_index !== null) {
        if (overlay_index < data.omgs.length) {
            return (
                <GalleryImage
                    image={data.omgs[overlay_index]}
                    sort={sort}
                    previous_timestamp={null}
                    isOverlay={true}
                    showLocationIterpolation={
                        checkboxes["LocPredCheck"] === true
                    }
                    showDiffInfo={
                        checkboxes["LocPredCheck"] === true ||
                        checkboxes["ShowDiffCheck"] === true
                    }
                    showTimeSelection={
                        checkboxes["ShowTimeSelectionCheck"] === true
                    }
                    showMetadata={checkboxes["ShowMetadataCheck"] === true}
                    showFaces={checkboxes["ShowFaceMetadata"] === true}
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
        } else {
            return <div>Please wait while data is loading...</div>;
        }
    }
    let prev_date: string | null = null;
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
            {children}
            {locInterpolation}
            <div>{galleryItems}</div>
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
