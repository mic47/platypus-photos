import * as React from "react";
import { StyleSheet, View } from "react-native";
import Gallery, {
    GalleryRef,
    RenderItemInfo,
} from "react-native-awesome-gallery";
import { Image } from "expo-image";
import {
    FetchedImagesContext,
    QueryContext,
    RefreshingContext,
} from "@/components/GlobalState";
import { fetchImages } from "@/components/ImageFetcher";
import { ImageWithMeta } from "@/components/pygallery.generated/types.gen";
import { useLocalSearchParams } from "expo-router";

export default function Page() {
    const ref = React.useRef<GalleryRef>(null);
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
    const total = fetchedImages.value.images.length;
    if (ref.current !== undefined && ref.current !== null) {
        console.log("reset");
        ref.current.reset();
    }
    return (
        <View style={{ flex: 1 }}>
            <Gallery
                ref={ref}
                data={fetchedImages.value.images}
                keyExtractor={(item) => item.omg.md5}
                renderItem={renderItem}
                doubleTapScale={1.0}
                initialIndex={parseInt(index) || 0}
                numToRender={10}
                onIndexChange={(newIndex) => {
                    if (newIndex + 2 >= total) {
                        fetchMore();
                    }
                }}
            />
        </View>
    );
}

function renderItem({
    item,
    setImageDimensions,
}: RenderItemInfo<ImageWithMeta>) {
    const url = `http://10.0.2.2:8000/img/original/${item.omg.md5}.${item.omg.extension}`;
    return (
        <Image
            source={url}
            style={StyleSheet.absoluteFillObject}
            contentFit="contain"
            onLoad={(e) => {
                const { width, height } = e.source;
                setImageDimensions({ width, height });
            }}
        />
    );
}
