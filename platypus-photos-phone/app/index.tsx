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
    FlatListProps,
    ViewToken,
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

function InputForm({ submit }: { submit: (query: SearchQuery) => void }) {
    const [query, changeQuery] = React.useState<SearchQuery>({});
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
            <Button title="Submit" onPress={() => submit(query)} />
        </View>
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

export default function Index() {
    const [query, updateQuery] = React.useState<null | SearchQuery>(null);
    const [images, updateImages] = React.useState<{
        page: number;
        images: ImageWithMeta[];
        hasNextPage: boolean;
    }>({ page: 0, images: [], hasNextPage: false });
    const [refreshing, updateRefreshing] = React.useState<boolean>(false);
    const [selectedPhoto, updateSelectedPhoto] = React.useState<null | number>(
        null,
    );
    const ref = React.useRef<GalleryRef>(null);
    const fetchMore = ({ reset }: { reset?: boolean }) => {
        if (query === null) {
            return;
        }
        const page = reset === true ? 0 : images.page;
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
                    images.page,
                    images.images.length,
                );
                // TODO: is this mutable thing ok?
                updateImages({
                    page: page + 1,
                    images:
                        reset === true
                            ? [...value.omgs]
                            : [...images.images, ...value.omgs],
                    hasNextPage: value.has_next_page,
                });
            })
            .catch((error) => {
                console.log("ERRR", error);
            })
            .finally(() => {
                updateRefreshing(false);
            });
    };
    React.useEffect(() => {
        fetchMore({ reset: true });
    }, [query]);

    if (images.page === 0) {
        return <InputForm submit={(query) => updateQuery(query)} />;
    } else if (selectedPhoto === null) {
        const { width } = Dimensions.get("window");
        return (
            <ZoomableGalleryBrowser
                width={width}
                defaultRows={3}
                hasNextPage={images.hasNextPage}
                refreshing={refreshing}
                images={images.images}
                fetchMore={fetchMore}
                onImageClick={updateSelectedPhoto}
            />
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
                            fetchMore({});
                        }
                    }}
                />
            </View>
        );
    }
}
