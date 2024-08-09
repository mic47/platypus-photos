import { Stack } from "expo-router";
import * as React from "react";
import { GestureHandlerRootView } from "react-native-gesture-handler";
import { SearchQuery } from "./pygallery.generated/types.gen";
import {
    FetchedImages,
    FetchedImagesContext,
    QueryContext,
    RefreshingContext,
} from "./globalState";
import { ImageFetcher } from "./imageFetcher";

export default function RootLayout() {
    const [query, updateQuery] = React.useState<SearchQuery>({});
    const [fetchedImages, updateFetchedImages] = React.useState<FetchedImages>({
        page: 0,
        images: [],
        hasNextPage: false,
    });
    const [refreshing, updateRefreshing] = React.useState<boolean>(false);
    return (
        <GestureHandlerRootView>
            <QueryContext.Provider
                value={{ value: query, update: updateQuery }}
            >
                <FetchedImagesContext.Provider
                    value={{
                        value: fetchedImages,
                        update: updateFetchedImages,
                    }}
                >
                    <RefreshingContext.Provider
                        value={{
                            value: refreshing,
                            update: updateRefreshing,
                        }}
                    >
                        <ImageFetcher />
                        <Stack>
                            <Stack.Screen name="index" />
                        </Stack>
                    </RefreshingContext.Provider>
                </FetchedImagesContext.Provider>
            </QueryContext.Provider>
        </GestureHandlerRootView>
    );
}
