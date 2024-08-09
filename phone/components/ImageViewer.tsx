import * as React from "react";
import { StyleSheet, View } from "react-native";
import Gallery, {
    GalleryRef,
    RenderItemInfo,
} from "react-native-awesome-gallery";
import { Image } from "expo-image";

import { FetchedImages } from "@/components/GlobalState";
import { ImageWithMeta } from "@/components/pygallery.generated/types.gen";

export function ImageViewer({
    index,
    fetchedImages,
    fetchMore,
}: {
    index: number;
    fetchedImages: FetchedImages;
    fetchMore: () => void;
}) {
    const ref = React.useRef<GalleryRef>(null);
    const total = fetchedImages.images.length;
    if (ref.current !== undefined && ref.current !== null) {
        console.log("reset");
        ref.current.reset();
    }
    return (
        <View style={{ flex: 1 }}>
            <Gallery
                ref={ref}
                data={fetchedImages.images}
                keyExtractor={(item) => item.omg.md5}
                renderItem={renderItem}
                doubleTapScale={1.0}
                initialIndex={index}
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
