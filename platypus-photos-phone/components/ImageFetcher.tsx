import * as React from "react";
import { SearchQuery } from "./pygallery.generated/types.gen";
import * as pygallery_service from "./pygallery.generated/services.gen";
import {
    FetchedImages,
    FetchedImagesContext,
    QueryContext,
    RefreshingContext,
} from "./GlobalState";

export function ImageFetcher() {
    const query = React.useContext(QueryContext).value;
    const fetchedImages = React.useContext(FetchedImagesContext);
    const updateRefreshing = React.useContext(RefreshingContext).update;

    React.useEffect(() => {
        fetchImages({
            reset: true,
            query,
            fetchedImages: fetchedImages.value,
            updateFetchedImages: fetchedImages.update,
            updateRefreshing,
        });
    }, [query]);
    return <></>;
}

export function fetchImages({
    reset,
    query,
    fetchedImages,
    updateFetchedImages,
    updateRefreshing,
}: {
    reset: boolean;
    query: SearchQuery;
    fetchedImages: FetchedImages;
    updateFetchedImages: (data: FetchedImages) => void;
    updateRefreshing: (refreshing: boolean) => void;
}) {
    const page = reset === true ? 0 : fetchedImages.page;
    console.log("Fetching page", page);
    updateRefreshing(true);
    pygallery_service
        .imagePagePost({
            requestBody: {
                query,
                paging: { paging: 1000, page: page },
                sort: {},
            },
        })
        .then((value) => {
            console.log(
                "Received and updating images",
                fetchedImages.page,
                fetchedImages.images.length,
            );
            updateFetchedImages({
                page: page + 1,
                images:
                    reset === true
                        ? [...value.omgs]
                        : [...fetchedImages.images, ...value.omgs],
                hasNextPage: value.has_next_page,
            });
        })
        .catch((error) => {
            console.log("ERRR", error);
        })
        .finally(() => {
            updateRefreshing(false);
        });
}
