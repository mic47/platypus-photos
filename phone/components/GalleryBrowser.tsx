import * as React from "react";
import { Image } from "expo-image";
import {
    Button,
    FlatList,
    StyleSheet,
    Text,
    TouchableWithoutFeedback,
    ViewToken,
} from "react-native";

import { ImageWithMeta } from "@/components/pygallery.generated/types.gen";

export function GalleryBrowser({
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
    fetchMore: () => void;
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
            onEndReached={() => fetchMore()}
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
