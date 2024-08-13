import * as React from "react";
import { StyleSheet, View, Text, TouchableHighlight } from "react-native";
import Gallery, {
    GalleryRef,
    RenderItemInfo,
} from "react-native-awesome-gallery";
import { Image } from "expo-image";

import { FetchedImages, QueryContext } from "@/components/GlobalState";
import { ImageWithMeta } from "@/components/pygallery.generated/types.gen";
import { OpenAPI } from "./pygallery.generated";
import { router } from "expo-router";

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

type TextField = "cls" | "tag" | "identity" | "addr" | "camera" | "directory";
function useUpdateStringQuery() {
    const query = React.useContext(QueryContext);
    return {
        replace: (field: TextField, newValue: null | string) => () => {
            const ret = { ...query.value };
            if (newValue === null) {
                return;
            } else {
                ret[field] = newValue;
            }
            query.update(ret);
            router.back();
        },
        append: (field: TextField, newValue: null | string) => () => {
            const ret = { ...query.value };
            if (newValue === null) {
                return;
            }
            const existingValue = ret[field];
            if (existingValue === null || existingValue === undefined) {
                ret[field] = newValue;
            } else {
                ret[field] = `${existingValue},${newValue}`;
            }
            query.update(ret);
            router.back();
        },
    };
}

function RenderedItem({
    item,
    setImageDimensions,
}: RenderItemInfo<ImageWithMeta>) {
    const showDetails = React.useContext(ShowDetailsContext);
    const stringQuery = useUpdateStringQuery();
    const url = `${OpenAPI.BASE}/img/original/${item.omg.md5}.${item.omg.extension}`;
    const textParts = [];
    if (showDetails) {
        if (
            item.omg.classifications !== null &&
            item.omg.classifications !== ""
        ) {
            textParts.push(
                <View style={{ flexWrap: "wrap", flexDirection: "row" }}>
                    <Text>Desc:</Text>
                    <BreadCrumb
                        text={item.omg.classifications.trim()}
                        onPress={stringQuery.replace(
                            "cls",
                            item.omg.classifications,
                        )}
                        color="#00FF0055"
                    />
                </View>,
            );
        }
        if (item.omg.date !== null) {
            textParts.push(<Text>Date-time: {item.omg.date.toString()}</Text>);
        }
        if (item.omg.identities.length > 0) {
            textParts.push(
                <View style={{ flexWrap: "wrap", flexDirection: "row" }}>
                    <Text>People:</Text>
                    {item.omg.identities.map((identity, index) => {
                        return (
                            <BreadCrumb
                                onPress={stringQuery.append(
                                    "identity",
                                    identity,
                                )}
                                text={identity}
                                color="#0000FF55"
                            />
                        );
                    })}
                </View>,
            );
        }
        const addressParts: string[] = [];
        if (item.omg.address.name !== null && item.omg.address.name !== "") {
            addressParts.push(item.omg.address.name);
        }
        if (
            item.omg.address.country !== null &&
            item.omg.address.country !== ""
        ) {
            addressParts.push(item.omg.address.country);
        }
        if (addressParts.length > 0) {
            textParts.push(
                <View style={{ flexWrap: "wrap", flexDirection: "row" }}>
                    <Text>Location:</Text>
                    {addressParts.map((part, index) => {
                        return (
                            <BreadCrumb
                                onPress={stringQuery.append("addr", part)}
                                text={part}
                                color="#00FFFF55"
                            />
                        );
                    })}
                </View>,
            );
        }
        if (item.omg.tags !== null) {
            const max_tag = Math.min(
                1,
                Math.max(1.0, ...Object.values(item.omg.tags || {})),
            );
            textParts.push(
                <View style={{ flexWrap: "wrap", flexDirection: "row" }}>
                    <Text>In Picture: </Text>
                    {Object.entries(item.omg.tags)
                        .filter(([, score]) => {
                            return null == classifyTag(score / max_tag);
                        })
                        .map(([tag], index) => (
                            <BreadCrumb
                                onPress={stringQuery.append("tag", tag)}
                                text={tag}
                                color="#FF000055"
                            />
                        ))}
                </View>,
            );
        }
        if (item.omg.camera !== null && item.omg.camera !== "") {
            textParts.push(
                <View style={{ flexWrap: "wrap", flexDirection: "row" }}>
                    <Text>Camera:</Text>
                    <BreadCrumb
                        onPress={stringQuery.append("camera", item.omg.camera)}
                        text={item.omg.camera}
                        color="#FF00FF55"
                    />
                </View>,
            );
        }
        item.paths.forEach((path) => {
            const dirParts = [];
            let start = 0;
            for (let i = 0; i < path.dir.length; i++) {
                if (path.dir[i] === "/") {
                    const part = path.dir.slice(start, i + 1);
                    const prefix = path.dir.slice(0, i + 1);
                    start = i + 1;
                    dirParts.push(
                        <BreadCrumb
                            onPress={stringQuery.replace("directory", prefix)}
                            text={part}
                            color="#FFFF0055"
                        />,
                    );
                }
            }
            if (start < path.dir.length) {
                const part = path.dir.slice(start);
                dirParts.push(
                    <BreadCrumb
                        onPress={stringQuery.replace("directory", path.dir)}
                        text={`${part}/`}
                        color="#FFFF0055"
                    />,
                );
            }
            dirParts.push(
                <BreadCrumb
                    onPress={stringQuery.replace("directory", path.dir)}
                    text={path.file}
                    color="#FFFF0055"
                />,
            );
            textParts.push(
                <View style={{ flexWrap: "wrap", flexDirection: "row" }}>
                    <Text>File:</Text>
                    {dirParts}
                </View>,
            );
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
                <View style={{ backgroundColor: "#FFFFFFaa" }}>
                    {textParts}
                </View>
            ) : null}
        </View>
    );
}

function BreadCrumb({
    text,
    onPress,
    color,
}: {
    text: string;
    onPress: () => void;
    color: string;
}) {
    return (
        <TouchableHighlight
            style={{
                borderRadius: 3,
                backgroundColor: color,
                padding: 2,
                marginLeft: 4,
            }}
            onPress={onPress}
        >
            <Text>{text}</Text>
        </TouchableHighlight>
    );
}

function classifyTag(value: number): string | null {
    if (value >= 0.5) return null;
    if (value >= 0.2) return "🤷";
    return "🗑️";
}
