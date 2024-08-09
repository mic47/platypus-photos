import * as React from "react";
import {
    FetchedImagesContext,
    QueryContext,
    RefreshingContext,
} from "@/components/GlobalState";
import { fetchImages } from "@/components/ImageFetcher";
import { useLocalSearchParams } from "expo-router";
import { ImageViewer } from "@/components/ImageViewer";

export default function Page() {
    const query = React.useContext(QueryContext).value;
    const fetchedImages = React.useContext(FetchedImagesContext);
    const refreshing = React.useContext(RefreshingContext);
    const { index } = useLocalSearchParams<{ index: string }>();

    const fetchMore = () =>
        fetchImages({
            reset: false,
            query,
            fetchedImages: fetchedImages.value,
            updateFetchedImages: fetchedImages.update,
            updateRefreshing: refreshing.update,
        });
    return (
        <ImageViewer
            index={parseInt(index) || 0}
            fetchedImages={fetchedImages.value}
            fetchMore={fetchMore}
        />
    );
}
