import {
    GalleryPaging,
    SearchQuery,
    SortBy,
    SortOrder,
    SortParams,
} from "./pygallery.generated/types.gen";
import { impissible, parse_float_or_null, parse_string_or_null } from "./utils";

export type CheckboxesParams = { [key4: string]: boolean };

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

export class URLSetSync {
    private sync: UrlSync;
    constructor(
        private key: string,
        private defaultOn: Set<string>,
    ) {
        this.sync = new UrlSync([key]);
    }
    get(): Set<string> {
        const raw = this.sync.get().unparsed[this.key];
        const data = raw === undefined ? [] : raw.split(",");
        const on = new Set(this.defaultOn);
        data.forEach((item) => {
            if (item.startsWith("!")) {
                on.delete(item.slice(1));
            } else {
                on.add(item);
            }
        });
        return on;
    }
    update(data: Set<string>) {
        const allMentions = new Set([...this.defaultOn, ...data]);
        const out = [...allMentions]
            .map((mention) => {
                const defaultOn = this.defaultOn.has(mention);
                const isOn = data.has(mention);
                if (defaultOn === isOn) {
                    return null;
                } else if (isOn) {
                    return mention;
                } else if (!isOn) {
                    return `!${mention}`;
                } else {
                    impissible(isOn);
                }
            })
            .filter((x) => x !== null);
        this.sync.update(Object.fromEntries([[this.key, out.join(",")]]));
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

export class TypedUrlSync<T> extends UrlSync {
    constructor(
        registered_fields: string[],
        private parser: (data: { unparsed: { [key: string]: string } }) => T,
    ) {
        super(registered_fields);
    }
    get_parsed(): T {
        return this.parser(this.get());
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
function update_gallery_paging_value(
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
function update_sort_params_value(
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
