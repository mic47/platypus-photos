import { SearchQuery } from "./pygallery.generated/types.gen";

export type UpdateCallbacks<T> = {
    update: (update: T) => void;
    replace: (newData: T) => void;
};

export type QueryCallbacks = {
    update_url: (update: SearchQuery) => void;
    update_url_add_tag: (tag: string) => void;
    update_url_add_identity: (identity: string) => void;
};
