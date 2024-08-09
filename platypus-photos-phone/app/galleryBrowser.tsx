import * as React from "react";

import { Image } from "expo-image";
import { Gesture, GestureDetector } from "react-native-gesture-handler";
import { runOnJS } from "react-native-reanimated";
import {
    Button,
    Dimensions,
    FlatList,
    StyleSheet,
    Text,
    TouchableWithoutFeedback,
    View,
    ViewToken,
} from "react-native";

import {
    FetchedImagesContext,
    QueryContext,
    RefreshingContext,
} from "@/components/GlobalState";
import { ImageWithMeta } from "@/components/pygallery.generated/types.gen";
import { fetchImages } from "@/components/ImageFetcher";
import { router } from "expo-router";

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

function ZoomableGalleryBrowser({
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
    fetchMore: ({}) => void;
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

function GalleryBrowser({
    width,
    numberOfRows,
    initialIndexElement,
    hasNextPage,
    refreshing,
    images,
    fetchMore,
    onImageClick,
    onViewableImagesChange,
}: {
    width: number;
    numberOfRows: number;
    initialIndexElement: number;
    hasNextPage: boolean;
    refreshing: boolean;
    images: ImageWithMeta[];
    fetchMore: ({}) => void;
    onImageClick: (index: number) => void;
    onViewableImagesChange: (index: number) => void;
}) {
    const imageWidth = width / numberOfRows;
    const styles = StyleSheet.create({
        container: {
            flex: 1,
            flexDirection: "row",
            flexWrap: "wrap",
        },
        image: {
            width: imageWidth,
            height: imageWidth,
        },
    });
    const getItemLayout = (_: any, index: number) => {
        return {
            length: imageWidth,
            offset: index * imageWidth,
            index,
        };
    };
    const keyExtractor = (_: any, index: number) => index.toString();
    const renderItem = ({
        item: omg,
        index,
    }: {
        item: ImageWithMeta;
        index: number;
    }) => {
        const url = `http://10.0.2.2:8000/img/preview/${omg.omg.md5}.${omg.omg.extension}`;
        return (
            <TouchableWithoutFeedback
                key={url}
                onPress={() => {
                    console.log(index, images.length);
                    onImageClick(index);
                }}
            >
                <Image source={url} style={styles.image} />
            </TouchableWithoutFeedback>
        );
    };
    const onViewableItemsChanged = ({
        viewableItems,
    }: {
        viewableItems: ViewToken<ImageWithMeta>[];
    }) => {
        const viewable: number[] = viewableItems
            .filter((x) => x.isViewable)
            .map((x) => x.index)
            .filter((x) => x !== null) as number[];
        if (viewable.length > 0) {
            const newTop = Math.min(...viewable);
            onViewableImagesChange(newTop);
        }
    };
    return (
        <FlatList
            key={numberOfRows}
            data={images}
            keyExtractor={keyExtractor}
            getItemLayout={getItemLayout}
            renderItem={renderItem}
            persistentScrollbar={true}
            onEndReached={() => fetchMore({})}
            onEndReachedThreshold={5}
            horizontal={false}
            numColumns={numberOfRows}
            style={styles.container}
            initialScrollIndex={Math.ceil(initialIndexElement / numberOfRows)}
            onViewableItemsChanged={onViewableItemsChanged}
            viewabilityConfig={{
                itemVisiblePercentThreshold: 20,
            }}
            ListFooterComponent={
                hasNextPage ? (
                    <>
                        {refreshing ? (
                            <Text>Getting More Data. Pls Wait.</Text>
                        ) : (
                            <Text>
                                There is more data but no request is in-flight
                            </Text>
                        )}
                        <Button
                            title="Fetch manually"
                            onPress={() => fetchMore({})}
                        ></Button>
                    </>
                ) : null
            }
        ></FlatList>
    );
}
