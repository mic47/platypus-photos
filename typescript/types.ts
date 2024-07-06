export type UpdateCallbacks<T> = {
    update: (update: T) => void;
    replace: (newData: T) => void;
};
