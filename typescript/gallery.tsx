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
import * as pygallery_service from "./pygallery.generated/services.gen.ts";
import { GalleryImage, ImageCallbacks } from "./gallery_image.tsx";
import { AggregateInfoView } from "./aggregate_info.tsx";
import { AnnotationOverlayRequest } from "./annotations.tsx";
import { SortFormView } from "./sort_form.tsx";
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
    pagingCallbacks: UpdateCallbacks<GalleryPaging>;
    sort: SortParams;
    sortCallbacks: UpdateCallbacks<SortParams>;
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
    pagingCallbacks,
    sortCallbacks,
    galleryUrl,
    galleryUrlCallbacks,
    checkboxSync,
    submit_annotations,
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
    const callbacks = {
        updateOverlayIndex,
        prev_page: (paging: GalleryPaging) => {
            if (paging.page !== undefined && paging.page > 0) {
                pagingCallbacks.update({ page: paging.page - 1 });
            }
        },
        next_page: (paging: GalleryPaging, has_next_page: boolean) => {
            if (has_next_page) {
                pagingCallbacks.update({ page: (paging.page || 0) + 1 });
            }
        },
        set_page: (page: number) => {
            pagingCallbacks.update({ page });
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
                pagingCallbacks.update({ page: newPage });
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
                pagingCallbacks.update({ page: (paging.page || 0) + 1 });
                updateOverlayIndex(0);
            }
        },
    };
    return (
        <>
            <SortFormView
                sort={sort}
                update_sort={(update) => sortCallbacks.update(update)}
            />
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
        prev_page: (paging: GalleryPaging) => void;
        next_page: (paging: GalleryPaging, has_next_page: boolean) => void;
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
                key={image.omg.md5}
                image={image}
                sort={sort}
                paging={paging}
                previous_timestamp={
                    prev_date === null ? null : Date.parse(prev_date) / 1000
                }
                overlay_index={overlay_index}
                has_next_page={data.has_next_page}
                index={index}
                showLocationIterpolation={checkboxes["LocPredCheck"] === true}
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
                    onClick={() => callbacks.prev_page(paging)}
                >
                    Prev Page
                </a>{" "}
                <a
                    href="#"
                    className="next-url"
                    onClick={() =>
                        callbacks.next_page(paging, data.has_next_page)
                    }
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
                    onClick={() => callbacks.prev_page(paging)}
                >
                    Prev Page
                </a>{" "}
                <a
                    href="#"
                    className="next-url"
                    onClick={() =>
                        callbacks.next_page(paging, data.has_next_page)
                    }
                >
                    Next Page
                </a>
            </div>
        </>
    );
}
