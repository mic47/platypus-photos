import React from "react";
import {
    Button,
    Text,
    TextInput,
    View,
    StyleSheet,
    TouchableWithoutFeedback,
    Dimensions,
    FlatList,
    Image as NativeImage,
} from "react-native";
import Gallery, {
    GalleryRef,
    RenderItemInfo,
} from "react-native-awesome-gallery";
import { Image } from "expo-image";
import { GestureDetector, Gesture } from "react-native-gesture-handler";

import * as pygallery_service from "./pygallery.generated/services.gen";
import { ImageWithMeta, SearchQuery } from "./pygallery.generated/types.gen";
import { runOnJS } from "react-native-reanimated";

const styles = StyleSheet.create({
    textInput: {
        margin: 3,
        borderWidth: 1,
        padding: 3,
        flex: 1,
    },
    inputView: {
        flexDirection: "row",
        justifyContent: "center",
        alignItems: "center",
        flexWrap: "wrap",
    },
});

function InputField({
    prefix,
    suffix,
    control: { value, changeValue },
}: {
    prefix: string;
    suffix: string;
    control: {
        value: string | null;
        changeValue: (text: string) => void;
    };
}) {
    return (
        <View style={styles.inputView}>
            <Button
                title="reset"
                onPress={() => {
                    changeValue("");
                }}
            />
            <Text>{prefix}</Text>
            <TextInput
                style={styles.textInput}
                editable
                onChangeText={(text) => changeValue(text)}
                value={value || ""}
            ></TextInput>
            <Text>{suffix}</Text>
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

export default function Index() {
    const [query, changeQuery] = React.useState<SearchQuery>({});
    const [images, updateImages] = React.useState<{
        page: number;
        images: ImageWithMeta[];
    }>({ page: 0, images: [] });
    const [hasNextPage, updateHasNextPage] = React.useState<boolean>(false);
    const defaultRows = 3;
    const [galleryRows, updateGalleryRows] = React.useState<{
        actual: number;
        gestureStart: number;
        initialIndex: number;
    }>({ actual: defaultRows, gestureStart: defaultRows, initialIndex: 0 });
    const [selectedPhoto, updateSelectedPhoto] = React.useState<null | number>(
        null,
    );
    const [refreshing, updateRefreshing] = React.useState<boolean>(false);
    const [topViewableIndex, updateTopViewableIndex] =
        React.useState<number>(0);
    const ref = React.useRef<GalleryRef>(null);
    const stringField = (
        field: "tag" | "cls" | "addr" | "directory" | "camera" | "identity",
    ) => {
        const f = query[field];
        return {
            value: f === undefined ? null : f,
            changeValue: (value: string) => {
                const ret = { ...query };
                if (value === "") {
                    delete ret[field];
                } else {
                    ret[field] = value;
                }
                changeQuery(ret);
            },
        };
    };
    let fetchingPage: null | number = null;
    const fetchMore = () => {
        const page = images.page;
        if (page === fetchingPage) {
            console.log("Preventing double fetching of page", page);
            return;
        }
        console.log("Fetching page", page, fetchingPage);
        //fetchingPage = page;
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
                    images.page,
                    images.images.length,
                );
                // TODO: is this mutable thing ok?
                updateImages({
                    page: page + 1,
                    images: [...images.images, ...value.omgs],
                });
                updateHasNextPage(value.has_next_page);
                updateRefreshing(false);
            })
            .catch((error) => {
                console.log("ERRR", error);
                updateRefreshing(false);
            })
            .finally(() => {
                fetchingPage = null;
            });
    };

    if (images.page === 0) {
        return (
            <View
                style={{
                    flex: 1,
                    justifyContent: "center",
                    alignItems: "center",
                }}
            >
                <InputField
                    prefix="🏷️"
                    suffix="(tags)"
                    control={stringField("tag")}
                />
                <InputField
                    prefix="📝"
                    suffix="(text)"
                    control={stringField("cls")}
                />
                <InputField
                    prefix="📭"
                    suffix="(address)"
                    control={stringField("addr")}
                />
                <InputField
                    prefix="🤓"
                    suffix="(identity)"
                    control={stringField("identity")}
                />
                <InputField
                    prefix="📁"
                    suffix="(folder)"
                    control={stringField("directory")}
                />
                <InputField
                    prefix="📷"
                    suffix="(camera)"
                    control={stringField("camera")}
                />
                <Button title="Submit" onPress={() => fetchMore()} />
            </View>
        );
    } else if (selectedPhoto === null) {
        const { width } = Dimensions.get("window");
        const omgs: React.JSX.Element[] = [];
        const imageWidth = width / galleryRows.actual;
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
        images.images.forEach((omg) => {
            const url = `http://10.0.2.2:8000/img/preview/${omg.omg.md5}.${omg.omg.extension}`;
            const index = omgs.length;
            omgs.push(
                <TouchableWithoutFeedback
                    key={url}
                    onPress={() => {
                        console.log(index, omgs.length);
                        //updateSelectedPhoto(index)
                    }}
                >
                    <NativeImage source={{ uri: url }} style={styles.image} />
                </TouchableWithoutFeedback>,
            );
        });
        // initialScrollIndex
        // onViewableItemsChanged
        // refreshing
        //
        const pinch = Gesture.Pinch()
            .onStart((e) => {
                console.log("pinch start", galleryRows);
                //runOnJS(updatePinchParams)({ initialWidth: galleryWidth });
            })
            .onUpdate((e) => {
                //console.log(e.scale);
                if (e.scale > 1.1) {
                    const update = Math.floor((e.scale - 1.0) / 0.1);
                    const newWidth = Math.max(
                        1,
                        galleryRows.gestureStart - update,
                    );
                    if (newWidth !== galleryRows.actual) {
                        /*
                        console.log(
                            "Updating width",
                            galleryRows,
                            "->",
                            newWidth,
                        );
                        */
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
                        /*
                        console.log(
                            "Updating width",
                            galleryRows,
                            "->",
                            newWidth,
                        );
                        */
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
        return (
            <GestureDetector gesture={pinch}>
                <View style={{ flex: 1 }}>
                    <FlatList
                        key={galleryRows.actual}
                        data={images.images}
                        keyExtractor={(_omg, index) => index.toString()}
                        getItemLayout={(_, index) => {
                            return {
                                length: imageWidth,
                                offset: index * imageWidth,
                                index,
                            };
                        }}
                        renderItem={({ item: omg, index }) => {
                            const url = `http://10.0.2.2:8000/img/preview/${omg.omg.md5}.${omg.omg.extension}`;
                            return (
                                <TouchableWithoutFeedback
                                    key={url}
                                    onPress={() => {
                                        console.log(index, omgs.length);
                                        updateSelectedPhoto(index);
                                    }}
                                >
                                    <Image source={url} style={styles.image} />
                                </TouchableWithoutFeedback>
                            );
                        }}
                        persistentScrollbar={true}
                        onEndReached={() => fetchMore()}
                        onEndReachedThreshold={5}
                        horizontal={false}
                        numColumns={galleryRows.actual}
                        style={styles.container}
                        initialScrollIndex={Math.ceil(
                            galleryRows.initialIndex / galleryRows.actual,
                        )}
                        onViewableItemsChanged={({
                            changed,
                            viewableItems,
                        }) => {
                            const viewable: number[] = viewableItems
                                .filter((x) => x.isViewable)
                                .map((x) => x.index)
                                .filter((x) => x !== null) as number[];
                            if (viewable.length > 0) {
                                const newTop = Math.min(...viewable);
                                if (topViewableIndex !== newTop) {
                                    console.log("UPDATING WHAT WE SEE", newTop);
                                    updateTopViewableIndex(newTop);
                                    if (
                                        galleryRows.actual ===
                                        galleryRows.gestureStart
                                    ) {
                                        updateGalleryRows({
                                            ...galleryRows,
                                            initialIndex: newTop,
                                        });
                                    }
                                }
                            }
                        }}
                        viewabilityConfig={{
                            itemVisiblePercentThreshold: 20,
                        }}
                        ListFooterComponent={
                            hasNextPage ? (
                                <>
                                    {refreshing ? (
                                        <Text>
                                            Getting More Data. Pls Wait.
                                        </Text>
                                    ) : (
                                        <Text>
                                            There is more data but no request is
                                            in-flight
                                        </Text>
                                    )}
                                    <Button
                                        title="Fetch manually"
                                        onPress={() => fetchMore()}
                                    ></Button>
                                </>
                            ) : null
                        }
                    ></FlatList>
                </View>
            </GestureDetector>
        );
    } else {
        const total = images.images.length;
        if (ref.current !== undefined && ref.current !== null) {
            console.log("reset");
            ref.current.reset();
        }
        return (
            <View style={{ flex: 1 }}>
                <Gallery
                    ref={ref}
                    data={images.images}
                    keyExtractor={(item) => item.omg.md5}
                    renderItem={renderItem}
                    doubleTapScale={0.2}
                    initialIndex={selectedPhoto === null ? 0 : selectedPhoto}
                    numToRender={10}
                    onScaleStart={(scale) => console.log(scale)}
                    onPanStart={() => console.log("pan")}
                    onIndexChange={(newIndex) => {
                        updateSelectedPhoto(newIndex);
                        console.log(newIndex, total);
                        if (newIndex + 2 >= total) {
                            fetchMore();
                        }
                    }}
                />
            </View>
        );
    }
}
