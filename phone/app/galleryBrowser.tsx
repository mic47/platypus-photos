import * as React from "react";
import { Dimensions } from "react-native";
import { router } from "expo-router";

import {
    FetchedImagesContext,
    QueryContext,
    RefreshingContext,
} from "@/components/GlobalState";
import { fetchImages } from "@/components/ImageFetcher";
import { ZoomableGalleryBrowser } from "@/components/ZoomableGalleryBrowser";

export default function Page() {
    const { width } = Dimensions.get("window");
    const query = React.useContext(QueryContext).value;
    const fetchedImages = React.useContext(FetchedImagesContext);
    const refreshing = React.useContext(RefreshingContext);
    const fetchMore = () =>
        fetchImages({
            reset: false,
            query,
            fetchedImages: fetchedImages.value,
            updateFetchedImages: fetchedImages.update,
            updateRefreshing: refreshing.update,
        });
    return (
        <ZoomableGalleryBrowser
            width={width}
            defaultRows={3}
            hasNextPage={fetchedImages.value.hasNextPage}
            refreshing={refreshing.value}
            images={fetchedImages.value.images}
            fetchMore={fetchMore}
            onImageClick={(index) => {
                router.push({
                    pathname: "/imageViewer/[index]",
                    params: { index },
                });
            }}
        />
    );
}
