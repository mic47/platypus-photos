import * as React from "react";

import { Gesture, GestureDetector } from "react-native-gesture-handler";
import { runOnJS } from "react-native-reanimated";
import { View } from "react-native";

import { ImageWithMeta } from "@/components/pygallery.generated/types.gen";
import { GalleryBrowser } from "./GalleryBrowser";

export function ZoomableGalleryBrowser({
    width,
    defaultRows,
    hasNextPage,
    refreshing,
    images,
    fetchMore,
    onImageClick,
}: {
    width: number;
    defaultRows: number;
    hasNextPage: boolean;
    refreshing: boolean;
    images: ImageWithMeta[];
    fetchMore: () => void;
    onImageClick: (index: number) => void;
}) {
    const [galleryRows, updateGalleryRows] = React.useState<{
        actual: number;
        gestureStart: number;
        initialIndex: number;
    }>({ actual: defaultRows, gestureStart: defaultRows, initialIndex: 0 });
    const [topViewableIndex, updateTopViewableIndex] =
        React.useState<number>(0);
    const pinch = Gesture.Pinch()
        .onStart(() => {
            console.log("pinch start", galleryRows);
        })
        .onUpdate((e) => {
            //console.log(e.scale);
            if (e.scale > 1.1) {
                const update = Math.floor((e.scale - 1.0) / 0.1);
                const newWidth = Math.max(1, galleryRows.gestureStart - update);
                if (newWidth !== galleryRows.actual) {
                    runOnJS(updateGalleryRows)({
                        actual: newWidth,
                        gestureStart: galleryRows.gestureStart,
                        initialIndex: galleryRows.initialIndex,
                    });
                }
            } else if (e.scale < 0.9) {
                const update = Math.floor(Math.max(0, 1.0 - e.scale) / 0.1);
                const newWidth = galleryRows.gestureStart + update;
                if (newWidth !== galleryRows.actual) {
                    runOnJS(updateGalleryRows)({
                        actual: newWidth,
                        gestureStart: galleryRows.gestureStart,
                        initialIndex: galleryRows.initialIndex,
                    });
                }
            }
        })
        .onEnd(() => {
            console.log("pinch end", galleryRows);
            runOnJS(updateGalleryRows)({
                actual: galleryRows.actual,
                gestureStart: galleryRows.actual,
                initialIndex: topViewableIndex,
            });
        });

    const onViewableImagesChange = (newTop: number) => {
        if (topViewableIndex !== newTop) {
            console.log("UPDATING WHAT WE SEE", newTop);
            updateTopViewableIndex(newTop);
            if (galleryRows.actual === galleryRows.gestureStart) {
                updateGalleryRows({
                    ...galleryRows,
                    initialIndex: newTop,
                });
            }
        }
    };
    return (
        <GestureDetector gesture={pinch}>
            <View style={{ flex: 1 }}>
                <GalleryBrowser
                    width={width}
                    numberOfRows={galleryRows.actual}
                    initialIndexElement={galleryRows.initialIndex}
                    hasNextPage={hasNextPage}
                    refreshing={refreshing}
                    images={images}
                    fetchMore={fetchMore}
                    onImageClick={onImageClick}
                    onViewableImagesChange={onViewableImagesChange}
                />
            </View>
        </GestureDetector>
    );
}
