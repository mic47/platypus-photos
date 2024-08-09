import React from "react";
import { ImageWithMeta, SearchQuery } from "./pygallery.generated/types.gen";

export type Updateable<T> = {
    value: T;
    update: (update: T) => void;
};

export type FetchedImages = {
    page: number;
    images: ImageWithMeta[];
    hasNextPage: boolean;
};
export const QueryContext = React.createContext<Updateable<SearchQuery>>({
    value: {},
    update: () => {},
});
export const FetchedImagesContext = React.createContext<
    Updateable<FetchedImages>
>({
    value: { page: 0, images: [], hasNextPage: false },
    update: () => {},
});
export const RefreshingContext = React.createContext<Updateable<boolean>>({
    value: false,
    update: () => {},
});
