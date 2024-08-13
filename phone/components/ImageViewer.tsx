import * as React from "react";
import { StyleSheet, View, Text } from "react-native";
import Gallery, {
    GalleryRef,
    RenderItemInfo,
} from "react-native-awesome-gallery";
import { Image } from "expo-image";

import { FetchedImages } from "@/components/GlobalState";
import { ImageWithMeta } from "@/components/pygallery.generated/types.gen";
import { OpenAPI } from "./pygallery.generated";

export function ImageViewer({
    index,
    fetchedImages,
    fetchMore,
}: {
    index: number;
    fetchedImages: FetchedImages;
    fetchMore: () => void;
}) {
    const [showDetails, updateShowDetails] = React.useState<boolean>(false);

    const ref = React.useRef<GalleryRef>(null);
    const total = fetchedImages.images.length;
    if (ref.current !== undefined && ref.current !== null) {
        console.log("reset");
        ref.current.reset();
    }
    return (
        <ShowDetailsContext.Provider value={showDetails}>
            <View style={{ flex: 1 }}>
                <Gallery
                    ref={ref}
                    data={fetchedImages.images}
                    keyExtractor={(item) => item.omg.md5}
                    renderItem={RenderedItem}
                    doubleTapScale={1.0}
                    initialIndex={index}
                    numToRender={10}
                    onTap={() => updateShowDetails(showDetails !== true)}
                    onIndexChange={(newIndex) => {
                        if (newIndex + 2 >= total) {
                            fetchMore();
                        }
                    }}
                />
            </View>
        </ShowDetailsContext.Provider>
    );
}

const ShowDetailsContext = React.createContext<boolean>(false);

function RenderedItem({
    item,
    setImageDimensions,
}: RenderItemInfo<ImageWithMeta>) {
    const showDetails = React.useContext(ShowDetailsContext);
    const url = `${OpenAPI.BASE}/img/original/${item.omg.md5}.${item.omg.extension}`;
    const textParts = [];
    if (showDetails) {
        // TODO: add controls to tags & so on
        if (
            item.omg.classifications !== null &&
            item.omg.classifications !== ""
        ) {
            textParts.push(item.omg.classifications);
        }
        if (item.omg.date !== null) {
            textParts.push(item.omg.date.toString());
        }
        if (item.omg.identities.length > 0) {
            textParts.push(`People: ${item.omg.identities.join(", ")}`);
        }
        if (item.omg.address.full !== null && item.omg.address.full !== "") {
            textParts.push(`Location: ${item.omg.address.full}`);
        }
        if (item.omg.tags !== null) {
            // TODO: classify tags
            textParts.push(
                `Tags: ${Object.entries(item.omg.tags)
                    .map(([tag, prob]) => `${tag}: ${prob}`)
                    .join(", ")}`,
            );
        }
        if (item.omg.camera !== null && item.omg.camera !== "") {
            textParts.push(`Camera: ${item.omg.camera}`);
        }
        item.paths.forEach((path) => {
            textParts.push(`${path.dir}/${path.file}`);
        });
    }
    return (
        <View style={{ flex: 1 }}>
            <Image
                source={url}
                style={StyleSheet.absoluteFillObject}
                contentFit="contain"
                onLoad={(e) => {
                    const { width, height } = e.source;
                    setImageDimensions({ width, height });
                }}
            />
            {showDetails ? (
                <Text style={{ backgroundColor: "#FFFFFFaa" }}>
                    {textParts.join("\n")}
                </Text>
            ) : null}
        </View>
    );
}
