import {
    GalleryPaging,
    SearchQuery,
    SortBy,
    SortOrder,
    SortParams,
} from "./pygallery.generated/types.gen";
import { impissible, parse_float_or_null, parse_string_or_null } from "./utils";

export type CheckboxesParams = { [key4: string]: boolean };

type AppStateHook<T> = (data: T) => void;

class StateWithHooks<T> {
    private hooks: Array<AppStateHook<T>>;
    constructor(private data: T) {
        this.hooks = [];
    }
    register_hook(hook: AppStateHook<T>) {
        this.hooks.push(hook);
    }
    get(): T {
        return this.data;
    }
    call_hooks(): StateWithHooks<T> {
        const data = this.data;
        this.hooks.forEach((x) => x(data));
        return this;
    }
    update(update: T): StateWithHooks<T> {
        this.data = { ...this.data, ...update };
        this.call_hooks();
        return this;
    }
    replace(newData: T): StateWithHooks<T> {
        this.data = newData;
        this.call_hooks();
        return this;
    }
    replace_no_hook_update(newData: T): StateWithHooks<T> {
        this.data = newData;
        return this;
    }
}

export class AppState {
    public search_query: StateWithHooks<SearchQuery>;
    public paging: StateWithHooks<GalleryPaging>;
    public sort: StateWithHooks<SortParams>;
    constructor(
        search_query: SearchQuery,
        paging: GalleryPaging,
        sort: SortParams,
    ) {
        this.search_query = new StateWithHooks(search_query);
        this.paging = new StateWithHooks(paging);
        this.sort = new StateWithHooks(sort);
    }
}

export class CheckboxSync {
    private state: { [id: string]: boolean };
    constructor() {
        this.state = {};
    }
    get(): { [id: string]: boolean } {
        return this.state;
    }
    update_from_element(element: HTMLInputElement) {
        this.state[element.id] = element.checked;
    }
}

// TODO: this could be better, and convert types properly
export class UrlSync {
    constructor(private registered_fields: string[]) {}
    get(): { unparsed: { [key: string]: string } } {
        const url = new URL(window.location.href);
        return {
            unparsed: Object.fromEntries(
                this.registered_fields
                    .map((field) => [field, url.searchParams.get(field)])
                    .filter((x) => x[1] !== undefined && x[1] !== null && x[1]),
            ),
        };
    }
    update(new_url: { [key: string]: string | number | boolean | null }) {
        const url = new URL(window.location.href);
        this.registered_fields.forEach((field) => {
            const new_value = new_url[field];
            if (new_value === null || new_value === undefined) {
                url.searchParams.delete(field);
            } else {
                if (typeof new_value === "string") {
                    url.searchParams.set(field, new_value);
                } else {
                    url.searchParams.set(field, new_value.toString());
                }
            }
        });
        if (window.history.replaceState) {
            window.history.replaceState(window.history.state, "", url.href);
        }
    }
}
export function parse_search_query(data: {
    unparsed: { [key: string]: string };
}): SearchQuery {
    const q: SearchQuery = {};
    for (const [key, value] of Object.entries(data.unparsed)) {
        update_search_query_value(q, key as keyof SearchQuery, value);
    }
    return q;
}
export function update_search_query_value(
    query: SearchQuery,
    key: keyof SearchQuery,
    value: string | null | undefined | File,
): SearchQuery {
    if (
        key === "tag" ||
        key === "cls" ||
        key === "addr" ||
        key === "directory" ||
        key === "camera" ||
        key === "timestamp_trans"
    ) {
        const val = parse_string_or_null(value);
        if (val === null) {
            delete query[key];
        } else {
            query[key] = val;
        }
    } else if (key === "tsfrom" || key === "tsto") {
        const val = parse_float_or_null(value);
        if (val === null) {
            delete query[key];
        } else {
            query[key] = val;
        }
    } else if (key === "skip_with_location" || key === "skip_being_annotated") {
        if (value === "true" || value === "false") {
            query[key] = value === "true";
        } else if (value === "1" || value === "0") {
            query[key] = value === "1";
        } else {
            delete query[key];
        }
    } else {
        impissible(key);
    }
    return query;
}
export function parse_gallery_paging(data: {
    unparsed: { [key: string]: string };
}): GalleryPaging {
    const q: GalleryPaging = {};
    for (const [key, value] of Object.entries(data.unparsed)) {
        update_gallery_paging_value(q, key as keyof GalleryPaging, value);
    }
    return q;
}
export function update_gallery_paging_value(
    query: GalleryPaging,
    key: keyof GalleryPaging,
    value: string | null | undefined | File,
): GalleryPaging {
    if (key === "page" || key === "paging") {
        const val = parse_float_or_null(value);
        if (val === null) {
            delete query[key];
        } else {
            query[key] = val;
        }
    } else {
        impissible(key);
    }
    return query;
}
export function parse_sort_params(data: {
    unparsed: { [key: string]: string };
}): SortParams {
    const q: SortParams = {};
    for (const [key, value] of Object.entries(data.unparsed)) {
        update_sort_params_value(q, key as keyof SortParams, value);
    }
    return q;
}
export function update_sort_params_value(
    query: SortParams,
    key: keyof SortParams,
    value: string | null | undefined | File,
): SortParams {
    if (key === "order") {
        const val = parse_string_or_null(value);
        if (val === null) {
            delete query[key];
        } else {
            query[key] = val as SortOrder;
        }
    } else if (key === "sort_by") {
        const val = parse_string_or_null(value);
        if (val === null) {
            delete query[key];
        } else {
            query[key] = val as SortBy;
        }
    } else {
        impissible(key);
    }
    return query;
}
