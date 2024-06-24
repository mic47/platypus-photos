import { Chart, ChartEvent, TooltipItem } from "chart.js/auto";
import { getRelativePosition } from "chart.js/helpers";
import "chartjs-adapter-date-fns";
import * as L from "leaflet";

import { ColorAssigner } from "./color_assigner.ts";
import data_model from "./data_model.generated.json";

export type SearchQueryParams = { [key1: string]: string };
export type PagingParams = { [key2: string]: string };
export type SortParams = { [key3: string]: string };

type AppStateHook<T> = (data: T) => void;

export class AppState {
    private url_params_hooks: Array<AppStateHook<SearchQueryParams>>;
    private paging_hooks: Array<AppStateHook<PagingParams>>;
    private sort_hooks: Array<AppStateHook<SortParams>>;
    constructor(
        private url_params: SearchQueryParams,
        private paging: PagingParams,
        private sort: SortParams,
    ) {
        this.url_params_hooks = [];
        this.paging_hooks = [];
        this.sort_hooks = [];
    }

    register_paging_hook(hook: AppStateHook<SearchQueryParams>) {
        this.paging_hooks.push(hook);
    }
    get_paging(): PagingParams {
        return this.paging;
    }
    update_paging(new_parts: PagingParams) {
        this.paging = { ...this.paging, ...new_parts };
        const paging = this.paging;
        this.paging_hooks.forEach((x) => x(paging));
    }
    replace_paging(new_paging: PagingParams) {
        this.paging = {};
        this.update_paging(new_paging);
    }

    register_sort_hook(hook: AppStateHook<SortParams>) {
        this.sort_hooks.push(hook);
    }
    get_sort(): SortParams {
        return this.sort;
    }
    update_sort(new_parts: SortParams) {
        this.sort = { ...this.sort, ...new_parts };
        const sort = this.sort;
        this.sort_hooks.forEach((x) => x(sort));
    }
    replace_sort(new_sort: SortParams) {
        this.sort = {};
        this.update_sort(new_sort);
    }

    get_url(): SearchQueryParams {
        return { ...this.url_params };
    }
    update_url(new_parts: SearchQueryParams) {
        // TODO: do this only on change
        this.url_params = { ...this.url_params, ...new_parts };
        const url = this.url_params;
        this.url_params_hooks.forEach((x) => x(url));
    }
    replace_url(new_url: SearchQueryParams) {
        // TODO: do this only on change
        this.url_params = {};
        this.update_url(new_url);
    }
    register_url_hook(hook: AppStateHook<SearchQueryParams>) {
        this.url_params_hooks.push(hook);
    }
}

export class UrlSync {
    constructor(private registered_fields: string[]) {}
    get_url(): { [key: string]: string } {
        const url = new URL(window.location.href);
        return Object.fromEntries(
            this.registered_fields
                .map((field) => [field, url.searchParams.get(field)])
                .filter((x) => x[1] !== undefined && x[1] !== null && x[1]),
        );
    }
    update(new_url: { [key: string]: string }) {
        const url = new URL(window.location.href);
        this.registered_fields.forEach((field) => {
            const new_value = new_url[field];
            if (new_value === null || new_value === undefined) {
                url.searchParams.delete(field);
            } else {
                url.searchParams.set(field, new_value);
            }
        });
        if (window.history.replaceState) {
            window.history.replaceState(window.history.state, "", url.href);
        }
    }
}

function changeState(index: string | number | null) {
    const url = new URL(window.location.href);
    if (index == null) {
        url.searchParams.delete("oi");
    } else {
        url.searchParams.set("oi", index.toString());
    }
    if (window.history.replaceState) {
        window.history.replaceState(window.history.state, "", url.href);
    }
}
function replace_image_size_inside(
    element: null | HTMLElement,
    source: string,
    replacement: string,
) {
    if (element == null) {
        return;
    }
    const images = element.getElementsByTagName("img");
    for (let i = 0; i < images.length; i++) {
        const image = images[i];
        const repl = image.src.replace("size=" + source, "size=" + replacement);
        if (repl != image.src) {
            image.src = repl;
        }
        if (replacement == "original") {
            image.loading = "eager";
        }
    }
}
function this_is_overlay_element(element: HTMLElement) {
    replace_image_size_inside(element, "preview", "original");
    let next = element.nextElementSibling;
    if (next != null) {
        replace_image_size_inside(next as HTMLElement, "preview", "original");
        next = next.nextElementSibling;
    }
    let prev = element.previousElementSibling;
    if (prev != null) {
        replace_image_size_inside(prev as HTMLElement, "preview", "original");
        prev = prev.previousElementSibling;
    }
    if (next != null) {
        replace_image_size_inside(next as HTMLElement, "original", "preview");
    }
    if (prev != null) {
        replace_image_size_inside(prev as HTMLElement, "original", "preview");
    }
}
export function overlay(element: HTMLElement, index: string) {
    const parent = element.parentElement;
    if (parent === null) {
        throw new Error(`Element does not have parent ${element}`);
    }
    this_is_overlay_element(parent);
    parent.classList.add("overlay");
    changeState(index);
}
export function overlay_close(element: HTMLElement) {
    const root = element.parentElement?.parentElement;
    if (root === undefined || root === null) {
        throw new Error(`Element does not have grand-parent ${element}`);
    }
    replace_image_size_inside(root, "original", "preview");
    replace_image_size_inside(
        root.previousElementSibling as HTMLElement | null,
        "original",
        "preview",
    );
    replace_image_size_inside(
        root.nextElementSibling as HTMLElement | null,
        "original",
        "preview",
    );
    root.classList.remove("overlay");
    changeState(null);
}
export function overlay_prev(element: HTMLElement, index: number) {
    const grandpa = element.parentElement?.parentElement;
    const target = grandpa?.previousElementSibling;
    if (
        target === undefined ||
        target === null ||
        grandpa === undefined ||
        grandpa === null
    ) {
        throw new Error(
            `Element does not have grand-parent's previous sibling ${element}`,
        );
    }
    this_is_overlay_element(target as HTMLElement);
    target.classList.add("overlay");
    grandpa.classList.remove("overlay");
    changeState(index - 1);
}
export function overlay_next(element: HTMLElement, index: number) {
    const grandpa = element.parentElement?.parentElement;
    const target = grandpa?.nextElementSibling;
    if (
        target === undefined ||
        target === null ||
        grandpa === undefined ||
        grandpa === null
    ) {
        throw new Error(
            `Element does not have grand-parent's next sibling ${element}`,
        );
    }
    this_is_overlay_element(target as HTMLElement);
    target.classList.add("overlay");
    grandpa.classList.remove("overlay");
    changeState(index + 1);
}

type Position = {
    latitude: number;
    longitude: number;
};
// TODO: rename to nw, se
type Bounds = {
    tl: Position;
    br: Position;
};

type ServerBounds = {
    nw: Position;
    se: Position;
};
type LastUpdateMarkersCacheParam = {
    timestamp: number;
    non_bounds: {
        res: Position;
        of: number;
        url: SearchQueryParams;
    };
    bounds: Bounds;
    change_view: boolean;
};

export class PhotoMap {
    public map: L.Map;
    private last_update_markers: LastUpdateMarkersCacheParam | null = null;
    private last_update_timestamp: number = 0;
    private markers: { [id: string]: L.Marker };
    constructor(
        div_id: string,
        private should_use_query_div: string,
        get_url: () => SearchQueryParams,
        private context_menu_callback: (
            latlng: L.LatLng,
            callback: (content: string) => L.Popup,
        ) => void,
    ) {
        this.map = L.map(div_id).fitWorld();
        L.control.scale({ imperial: false }).addTo(this.map);
        this.markers = {};
        const update_markers: L.LeafletEventHandlerFn = (e) => {
            if ((e as unknown as { flyTo: boolean }).flyTo) {
                return;
            }
            this.update_markers(get_url(), false);
        };
        const context_menu: L.LeafletEventHandlerFn = (e) => {
            this.context_menu(e as L.LocationEvent);
        };
        this.map.on("load", update_markers);
        this.map.on("zoomend", update_markers);
        this.map.on("moveend", update_markers);
        this.map.on("zoom", update_markers);
        this.map.on("move", update_markers);
        this.map.on("resize", update_markers);
        if (
            this.context_menu_callback !== undefined &&
            this.context_menu_callback !== null
        ) {
            this.map.on("contextmenu", context_menu);
        }

        L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
            maxZoom: 19,
            attribution:
                '&copy; <a href="http://www.openstreetmap.org/copyright">OpenStreetMap</a>',
        }).addTo(this.map);
        this.update_bounds(get_url(), true);
    }

    context_menu(e: L.LocationEvent) {
        this.context_menu_callback(e.latlng, (content: string) => {
            return L.popup()
                .setLatLng(e.latlng)
                .setContent(content)
                .openOn(this.map);
        });
    }

    update_bounds(location_url_json: SearchQueryParams, fit_not_fly = false) {
        const query = {
            ...location_url_json,
            skip_with_location: false,
            skip_being_annotated: false,
        };
        return fetch("/api/bounds", {
            method: "POST",
            body: JSON.stringify(query),
            headers: {
                "Content-type": "application/json; charset=UTF-8",
            },
        })
            .then((response) => response.json())
            .then((bounds: ServerBounds) => {
                if (bounds === undefined || bounds === null) {
                    return;
                }
                const latlngs: L.LatLngBoundsLiteral = [
                    [bounds.nw.latitude, bounds.nw.longitude],
                    [bounds.se.latitude, bounds.se.longitude],
                ];
                if (fit_not_fly) {
                    this.map.fitBounds(latlngs);
                } else {
                    this.map.flyToBounds(latlngs, { duration: 1 });
                }
            });
    }

    _similar(last_bounds: Bounds, new_bounds: Bounds, tolerance: number) {
        if (last_bounds === undefined || last_bounds === null) {
            return false;
        }
        const lat_tolerance =
            Math.abs(last_bounds.tl.latitude - last_bounds.br.latitude) *
            tolerance;
        const lon_tolerance =
            Math.abs(last_bounds.tl.longitude - last_bounds.br.longitude) *
            tolerance;
        return (
            Math.abs(last_bounds.tl.latitude - new_bounds.tl.latitude) <
                lat_tolerance &&
            Math.abs(last_bounds.tl.longitude - new_bounds.tl.longitude) <
                lon_tolerance &&
            Math.abs(last_bounds.br.latitude - new_bounds.br.latitude) <
                lat_tolerance &&
            Math.abs(last_bounds.br.longitude - new_bounds.br.longitude) <
                lon_tolerance
        );
    }
    _should_skip(params: LastUpdateMarkersCacheParam) {
        const non_bounds_str = JSON.stringify(params.non_bounds);
        if (
            this.last_update_markers !== null &&
            this.last_update_markers.timestamp + 10000 > params.timestamp &&
            JSON.stringify(this.last_update_markers.non_bounds) ===
                non_bounds_str &&
            this._similar(
                this.last_update_markers.bounds,
                params.bounds,
                0.1,
            ) &&
            this.last_update_markers.change_view === params.change_view
        ) {
            return true;
        }
        this.last_update_timestamp = params.timestamp;
        this.last_update_markers = params;
        return false;
    }

    update_markers(location_url_json: SearchQueryParams, change_view = false) {
        // TODO: wrapped maps: shift from 0 + wrap around
        const should_use_query =
            (
                document.getElementById(
                    this.should_use_query_div,
                ) as HTMLInputElement | null
            )?.checked || false;

        const bounds = this.map.getBounds();
        const nw = bounds.getNorthWest();
        const se = bounds.getSouthEast();
        const sz = this.map.getSize();
        const cluster_pixel_size = 10;
        const timestamp = new Date().getTime();
        const bounds_query: Bounds = {
            tl: {
                latitude: nw.lat,
                longitude: nw.lng,
            },
            br: {
                latitude: se.lat,
                longitude: se.lng,
            },
        };
        const non_bounds = {
            res: {
                latitude: sz.y / cluster_pixel_size,
                longitude: sz.x / cluster_pixel_size,
            },
            of: 0.5,
            url: Object.fromEntries(
                Object.entries({
                    ...(should_use_query ? location_url_json : {}),
                }).filter((x) => x[0] !== "page" && x[0] !== "paging"),
            ),
        };
        if (
            this._should_skip({
                timestamp,
                bounds: bounds_query,
                non_bounds,
                change_view,
            })
        ) {
            return;
        }
        const query_final = {
            ...bounds_query,
            ...non_bounds,
        };
        fetch("/api/location_clusters", {
            method: "POST",
            body: JSON.stringify(query_final),
            headers: {
                "Content-type": "application/json; charset=UTF-8",
            },
        })
            .then((response) => response.json())
            .then((clusters) => {
                if (timestamp < this.last_update_timestamp) {
                    return;
                }
                if (change_view) {
                    this.update_bounds(location_url_json);
                }
                this.last_update_timestamp = timestamp;
                const new_markers: { [key: string]: L.Marker } = {};
                for (let i = 0; i < clusters.length; i++) {
                    const cluster = clusters[i];
                    const existing = this.markers[cluster.example_path_md5];
                    if (existing !== undefined) {
                        new_markers[cluster.example_path_md5] = existing;
                        delete this.markers[cluster.example_path_md5];
                        continue;
                    }
                    const marker = L.marker([
                        cluster.position.latitude,
                        cluster.position.longitude,
                    ]).addTo(this.map);
                    marker.bindPopup(
                        [
                            cluster.example_classification,
                            "@ ",
                            cluster.address_name,
                            ", ",
                            cluster.address_country,
                            " (",
                            cluster.size,
                            ")<br/>",
                            pprange(cluster.tsfrom, cluster.tsto),
                            "<br/>",
                            `<button onclick="window.APP.update_url({tsfrom: ${cluster.tsfrom - 0.01}, tsto: ${cluster.tsto + 0.01}})">➡️ from &amp; to ⬅️ </button>
                            <button onclick="window.APP.update_url({tsfrom: ${cluster.tsfrom - 0.01}})">➡️ from</button>
                            <button onclick="window.APP.update_url({tsto: ${cluster.tsto + 0.01}})">to ⬅️ </button><br/>`,
                            '<input type="button" value="Use this location for selected photos" ',
                            `onclick="window.APP.annotation_overlay(${cluster.position.latitude}, ${cluster.position.longitude})"><br/>`,
                            "<img src='/img?hsh=",
                            cluster.example_path_md5,
                            "&size=preview' class='popup'>",
                        ].join(""),
                    );
                    new_markers[cluster.example_path_md5] = marker;
                }
                Object.values(this.markers).forEach((m) => m.remove());
                Object.keys(this.markers).forEach(
                    (m) => delete this.markers[m],
                );
                Object.entries(new_markers).forEach(
                    (m) => (this.markers[m[0]] = m[1]),
                );
            });
    }
}

export class Switchable {
    private enabled: boolean;
    private callbacks: { [key: string]: () => void };
    constructor() {
        this.enabled = true;
        this.callbacks = {};
    }
    disable() {
        if (this.enabled === false) {
            false;
        }
        this.enabled = false;
        this.callbacks = {};
    }
    enable() {
        if (this.enabled === true) {
            return;
        }
        this.enabled = true;
        Object.values(this.callbacks).forEach((callback) => {
            if (callback !== undefined && callback !== null) {
                callback();
            }
        });
        this.callbacks = {};
    }
    call_or_store(name: string, callback: () => void) {
        if (this.enabled) {
            return callback();
        }
        this.callbacks[name] = callback;
    }
}

export class Directories {
    public switchable: Switchable;
    constructor(private div_id: string) {
        this.switchable = new Switchable();
    }

    fetch(url_data: SearchQueryParams) {
        return this.switchable.call_or_store("fetch", () =>
            this.fetch_impl(url_data),
        );
    }

    fetch_impl(url_data: SearchQueryParams) {
        const url = `/internal/directories.html`;
        fetch(url, {
            method: "POST",
            body: JSON.stringify(url_data),
            headers: {
                "Content-type": "application/json; charset=UTF-8",
            },
        })
            .then((response) => response.text())
            .then((text) => {
                const element = document.getElementById(this.div_id);
                if (element === null) {
                    throw new Error(`Unable to find element ${this.div_id}`);
                }
                element.innerHTML = text;
            });
    }
}

export class AggregateInfo {
    constructor(private div_id: string) {}

    fetch(url_data: SearchQueryParams, paging: PagingParams) {
        const url = `/internal/aggregate.html`;
        fetch(url, {
            method: "POST",
            body: JSON.stringify({ query: url_data, paging }),
            headers: {
                "Content-type": "application/json; charset=UTF-8",
            },
        })
            .then((response) => response.text())
            .then((text) => {
                const element = document.getElementById(this.div_id);
                if (element === null) {
                    throw new Error(`Unable to find element ${this.div_id}`);
                }
                element.innerHTML = text;
            });
    }
}

export class GenericFetch<T> {
    constructor(
        protected readonly div_id: string,
        private endpoint: string,
    ) {}

    fetch_impl(request: T): Promise<void> {
        return fetch(this.endpoint, {
            method: "POST",
            body: JSON.stringify(request),
            headers: {
                "Content-type": "application/json; charset=UTF-8",
            },
        })
            .then((response) => response.text())
            .then((text) => {
                const element = document.getElementById(this.div_id);
                if (element === null) {
                    throw Error(`Unable to find element ${this.div_id}`);
                }
                element.innerHTML = text;
            });
    }
}
export class JobProgress<S extends { ts: number }> extends GenericFetch<{
    job_list_fn: string;
    update_state_fn: string;
    state: S;
}> {
    public switchable: Switchable;
    private states: S[];
    constructor(
        div_id: string,
        private update_state_fn: string,
        private job_list_fn: string,
    ) {
        super(div_id, "/internal/job_progress.html");
        this.states = [];
        this.switchable = new Switchable();
    }
    fetch() {
        this.switchable.call_or_store("fetch", () => {
            return this.fetch_impl({
                job_list_fn: this.job_list_fn,
                update_state_fn: this.update_state_fn,
                state: this.states[0],
            });
        });
    }
    add_state(state: S) {
        this.states.push(state);
        this.states = this.states.filter((x) => state.ts - x.ts < 300.0);
    }
    add_state_base64(base64: string) {
        const state = JSON.parse(window.atob(base64));
        this.add_state(state);
    }
}
export class JobList extends GenericFetch<object> {
    private shown: boolean;
    constructor(div_id: string) {
        super(div_id, "/internal/job_list.html");
        this.shown = false;
    }
    fetch() {
        return this.fetch_impl({}).then(() => {
            this.shown = true;
        });
    }
    show_or_close() {
        if (this.shown) {
            this.shown = false;
            const element = document.getElementById(this.div_id);
            if (element === null) {
                throw new Error(`Unable to fine element ${this.div_id})`);
            }
            element.innerHTML = "";
        } else {
            this.fetch();
        }
    }
}

export class MapSearch extends GenericFetch<{ query: string | null }> {
    constructor(div_id: string) {
        super(div_id, "/internal/map_search.html");
    }
    fetch(search_str: string | null) {
        return this.fetch_impl({ query: search_str });
    }
}

export class AddressInfo extends GenericFetch<{
    latitude: number;
    longitude: number;
}> {
    constructor(div_id: string) {
        super(div_id, "/internal/fetch_location_info.html");
    }
    fetch(latitude: number, longitude: number) {
        return this.fetch_impl({ latitude, longitude });
    }
}

export class AnnotationOverlay extends GenericFetch<{
    latitude: number;
    longitude: number;
    query: SearchQueryParams;
}> {
    constructor(div_id: string) {
        super(div_id, "/internal/submit_annotations_overlay.html");
    }
    fetch(latitude: number, longitude: number, query: SearchQueryParams) {
        return this.fetch_impl({ latitude, longitude, query });
    }
}

export function null_if_empty(
    str: null | undefined | string | File,
): null | string {
    if (
        str === null ||
        str === undefined ||
        typeof str !== "string" ||
        str.trim() === ""
    ) {
        return null;
    }
    return str;
}
export function parse_float_or_null(str: string | null | File): number | null {
    if (str === null || typeof str !== "string") {
        return null;
    }
    const value = parseFloat(str);
    if (value != value) {
        return null;
    }
    return value;
}

export function error_box(div_id: string, value: object | number | string) {
    console.log(div_id, value);
    const e = document.getElementById(div_id);
    console.log(e);
    if (e === null || e === undefined) {
        alert(value);
        return;
    }
    const element = document.createElement("div");
    element.classList.add("error");
    const pre = document.createElement("pre");
    try {
        pre.innerHTML = JSON.stringify(value, null, 2);
    } catch {
        pre.innerHTML = value.toString();
    }
    element.appendChild(pre);
    e.innerHTML = "";
    e.appendChild(element);
}

type LeafPosition = {
    lat: number;
    lng: number;
};
export function location_preview(
    loc: LeafPosition,
    show_content_fn: (content: string) => L.Popup,
) {
    const existing = document.getElementById("LocPreview");
    if (existing !== undefined && existing !== null) {
        existing.remove();
    }
    const popup = show_content_fn('<div id="LocPreview"></div>');
    const info = new AddressInfo("LocPreview");
    info.fetch(loc.lat, loc.lng).then(() => {
        (popup as unknown as { _updateLayout: () => void })._updateLayout();
    });
}

export class InputForm {
    constructor(private div_id: string) {
        this.div_id = div_id;
    }

    fetch(url_data: SearchQueryParams) {
        const url = `/internal/input.html`;
        fetch(url, {
            method: "POST",
            body: JSON.stringify(url_data),
            headers: {
                "Content-type": "application/json; charset=UTF-8",
            },
        })
            .then((response) => response.text())
            .then((text) => {
                const gallery = document.getElementById(this.div_id);
                if (gallery === null) {
                    throw Error(`Unable to find element ${this.div_id}`);
                }
                gallery.innerHTML = text;
            });
    }
}

export class Gallery {
    constructor(
        private div_id: string,
        private prev_page: () => void,
        private next_page: () => void,
    ) {}

    fetch(url_data: SearchQueryParams, paging: PagingParams, sort: SortParams) {
        const url = "/internal/gallery.html";
        fetch(url, {
            method: "POST",
            body: JSON.stringify({ query: url_data, paging, sort }),
            headers: {
                "Content-type": "application/json; charset=UTF-8",
            },
        })
            .then((response) => response.text())
            .then((text) => {
                const gallery = document.getElementById(this.div_id);
                if (gallery === null) {
                    throw Error(`Unable to find element ${this.div_id}`);
                }
                gallery.innerHTML = text;
                const prev = gallery.getElementsByClassName("prev-url");
                for (let i = 0; i < prev.length; i++) {
                    const p = prev[i] as HTMLElement;
                    p.onclick = () => {
                        this.prev_page();
                    };
                }
                const next = gallery.getElementsByClassName("next-url");
                for (let i = 0; i < next.length; i++) {
                    const p = next[i] as HTMLElement;
                    p.onclick = () => {
                        this.next_page();
                    };
                }
            });
    }
}

export class Dates {
    public switchable: Switchable;
    private clickTimeStart: null | [number, number];
    private chart: Chart;
    private colors: ColorAssigner;
    constructor(
        div_id: string,
        update_url: (data: SearchQueryParams) => void,
        private tooltip_div: string,
        private group_by_div: string,
    ) {
        this.colors = new ColorAssigner([{ hue: 0, label: OVERFETCHED_LABEL }]);
        this.switchable = new Switchable();
        this.clickTimeStart = null;
        const ctx = document.getElementById(div_id);
        if (ctx === null) {
            throw new Error(`Unable to find element ${div_id}`);
        }
        this.chart = new Chart(ctx as HTMLCanvasElement, {
            type: "line",
            data: {
                datasets: [],
            },
            options: {
                events: ["mousedown", "mouseup"],
                parsing: false,
                scales: {
                    y: {
                        type: "logarithmic",
                    },
                    x: {
                        type: "time",
                        time: {
                            displayFormats: {
                                quarter: "MMM YYYY",
                            },
                        },
                    },
                },
                plugins: {
                    tooltip: {
                        callbacks: {
                            afterFooter: function (
                                context: TooltipItem<"line">[],
                            ) {
                                const tooltip =
                                    document.getElementById(tooltip_div);
                                if (tooltip === null) {
                                    throw new Error(
                                        `${tooltip_div} was not found`,
                                    );
                                }
                                const cluster = (
                                    context[0].raw as {
                                        cluster: DateClusterResponseItem;
                                    }
                                ).cluster;
                                const duration = pretty_print_duration(
                                    cluster.bucket_max - cluster.bucket_min,
                                );
                                const start = pprange(
                                    cluster.min_timestamp,
                                    cluster.max_timestamp,
                                );
                                const image_md5 = cluster.example_path_md5;
                                const selections =
                                    Object.entries(cluster.group_by)
                                        .filter(
                                            ([, x]) =>
                                                x !== null && x !== undefined,
                                        )
                                        .map(([k, x]) => {
                                            const flag =
                                                k === "country" &&
                                                typeof x === "string"
                                                    ? FLAGS[x.toLowerCase()]
                                                    : undefined;
                                            if (flag === undefined) {
                                                if (typeof x === "boolean") {
                                                    return `${k}={x}`;
                                                } else {
                                                    return x;
                                                }
                                            } else {
                                                return `${x} ${flag}`;
                                            }
                                        })
                                        .join(", ") || "";
                                const innerHtml2 = `
<div class="date_tooltip">
Selected time aggregation: ${selections}<br/>
${start}<br/>
${cluster.total} images, ${duration} bucket<br/>
<button onclick="window.APP.update_url({tsfrom: ${cluster.min_timestamp - 0.01}, tsto: ${cluster.max_timestamp + 0.01}})">➡️ from &amp; to ⬅️ </button>
<button onclick="window.APP.update_url({tsfrom: ${cluster.min_timestamp - 0.01}})">➡️ from</button>
<button onclick="window.APP.update_url({tsto: ${cluster.max_timestamp + 0.01}})">to ⬅️ </button><br/>
<img loading="lazy" src="/img?hsh=${image_md5}&size=preview" class="gallery_image" />
</div>
        `;
                                tooltip.innerHTML = innerHtml2;
                            },
                        },
                    },
                },
            },
            plugins: [
                {
                    id: "Events",
                    beforeEvent: (
                        chart: Chart,
                        args: { event: ChartEvent },
                    ) => {
                        const event = args.event;

                        const canvasPosition =
                            // eslint-disable-next-line @typescript-eslint/no-explicit-any
                            getRelativePosition(event, chart as any); // Reason for any is that I am not sure what type to put there, and don't really care
                        const dataX: number | undefined =
                            chart.scales.x.getValueForPixel(canvasPosition.x);
                        if (dataX === undefined) {
                            return;
                        }
                        if (event.type === "mousedown") {
                            this.clickTimeStart = [canvasPosition.x, dataX];
                        } else if (event.type === "mouseup") {
                            if (this.clickTimeStart === null) {
                                return;
                            }
                            if (
                                Math.abs(
                                    canvasPosition.x - this.clickTimeStart[0],
                                ) > 1
                            ) {
                                const x = [
                                    this.clickTimeStart[1] / 1000.0,
                                    dataX / 1000.0,
                                ];
                                x.sort((x, y) => {
                                    if (x < y) {
                                        return -1;
                                    } else if (x > y) {
                                        return 1;
                                    } else {
                                        return 0;
                                    }
                                });
                                const [f, t] = x;
                                update_url({
                                    tsfrom: f.toString(),
                                    tsto: t.toString(),
                                });
                            }
                        }
                    },
                },
            ],
        });
    }

    fetch(location_url_json: SearchQueryParams) {
        return this.switchable.call_or_store("fetch", () => {
            const tool = document.getElementById(this.tooltip_div);
            if (tool !== null && tool !== undefined) {
                tool.innerHTML = "";
            }
            // TODO: move this off
            const group_by = [];
            const elements = document.getElementsByClassName(this.group_by_div);
            for (let i = 0; i < elements.length; i++) {
                const element = elements[i] as HTMLInputElement;
                if (element.checked) {
                    group_by.push(element.value);
                }
            }
            return fetch("/api/date_clusters", {
                method: "POST",
                body: JSON.stringify({
                    url: location_url_json,
                    group_by,
                    buckets: 100,
                }),
                headers: {
                    "Content-type": "application/json; charset=UTF-8",
                },
            })
                .then((response) => response.json())
                .then((clusters: DateClusterResponseItem[]) => {
                    const datasets = clusters_to_datasets(clusters);
                    const newDatasets = this.chart.data.datasets.map(
                        (oldDataset) => {
                            const label = oldDataset.label;
                            if (label === undefined) {
                                return null;
                            }
                            const newDataset = datasets[label];
                            if (newDataset === undefined) {
                                return null;
                            }
                            newDataset.backgroundColor = this.colors.get_str(
                                newDataset.label,
                            );
                            delete datasets[label];
                            return newDataset;
                        },
                    );
                    for (const dataset of Object.values(datasets)) {
                        dataset.backgroundColor = this.colors.get_str(
                            dataset.label,
                        );
                        newDatasets.push(dataset);
                    }
                    this.chart.data.datasets = newDatasets.filter(
                        (x) => x !== null,
                    );
                    this.chart.update();
                });
        });
    }
}

const OVERFETCHED_LABEL = "❌⌚";
type DatasetPoints = {
    [label: string]: {
        label: string;
        data: Array<{ x: number; y: number; cluster: DateClusterResponseItem }>;
        borderWidth: number;
        showLine: boolean;
        backgroundColor?: string;
    };
};
const FLAGS: { [key: string]: string } = data_model.unicode.flags;
function clusters_to_datasets(
    clusters: DateClusterResponseItem[],
): DatasetPoints {
    const data_points: DatasetPoints = {};
    function to_datapoint(c: DateClusterResponseItem) {
        return {
            x: c.avg_timestamp * 1000,
            y: c.total,
            cluster: c,
        };
    }
    clusters.forEach((cluster) => {
        let label = "⁉️";
        if (cluster.overfetched) {
            label = OVERFETCHED_LABEL;
        } else {
            label =
                Object.entries(cluster.group_by)
                    .filter(([, x]) => x !== null && x !== undefined)
                    .map(([k, x]) => {
                        const flag =
                            k === "country" && typeof x === "string"
                                ? FLAGS[x.toLowerCase()]
                                : undefined;
                        if (flag === undefined) {
                            if (typeof x === "boolean") {
                                return `${k}={x}`;
                            } else {
                                return x;
                            }
                        } else {
                            return flag;
                        }
                    })
                    .join(" ") || "selected";
        }
        if (data_points[label] === undefined) {
            data_points[label] = {
                label,
                data: [],
                borderWidth: 1,
                showLine: false,
            };
        }
        data_points[label].data.push(to_datapoint(cluster));
    });
    return data_points;
}
type DateClusterResponseItem = {
    avg_timestamp: number;
    min_timestamp: number;
    max_timestamp: number;
    bucket_min: number;
    bucket_max: number;
    example_path_md5: string;
    total: number;
    overfetched: boolean;
    group_by: {
        country: string | null;
        camera: string | null;
        has_location: boolean | null;
        address_name: string | null;
    };
};

export class TabSwitch {
    private defaults: { [key: string]: boolean };
    private sync: UrlSync;
    constructor(
        div_id: string,
        private callbacks: { [key: string]: Switchable },
    ) {
        this.defaults = {};
        const element = document.getElementById(div_id);
        if (element === null) {
            throw new Error(
                `Unable to initialize tab switching, element not found ${div_id}`,
            );
        }
        const buttons = element.getElementsByTagName("button");
        const ids = [];
        for (let i = 0; i < buttons.length; i++) {
            const button = buttons[i];
            if (!button.classList.contains("tablinks")) {
                continue;
            }
            if (button.id === undefined || button.id === null) {
                console.log("Error, this button should have id", button);
            }
            const sync_id = button.id.replace("TabSource", "Tab");
            ids.push(sync_id);
            const is_active_default = button.classList.contains("active");
            this.defaults[sync_id] = is_active_default;
        }
        this.sync = new UrlSync(ids);
        const url_params = this.sync.get_url();
        for (let i = 0; i < buttons.length; i++) {
            const button = buttons[i];
            if (!button.classList.contains("tablinks")) {
                continue;
            }
            if (button.id === undefined || button.id === null) {
                console.log("Error, this button should have id", button);
            }
            const sync_id = button.id.replace("TabSource", "Tab");
            const is_active_from_url = url_params[sync_id];
            button.addEventListener("click", () => {
                this.switch_tab_visibility(button);
            });
            this.set_tab_visibility(
                is_active_from_url === undefined || is_active_from_url === null
                    ? this.defaults[sync_id]
                    : is_active_from_url === "true",
                button,
            );
        }
    }
    set_tab_visibility(is_active: boolean, button: HTMLElement) {
        const id = button.id;
        const target_class = id.replace("TabSource", "TabTarget");
        const sync_id = id.replace("TabSource", "Tab");
        const targets = document.getElementsByClassName(target_class);
        const url = this.sync.get_url();
        if (this.defaults[sync_id] === is_active) {
            delete url[sync_id];
        } else {
            url[sync_id] = is_active.toString();
        }
        this.sync.update(url);
        const callback = this.callbacks[sync_id];
        if (is_active) {
            button.classList.add("active");
            for (let i = 0; i < targets.length; i++) {
                targets[i].classList.remove("disabled");
            }
            if (callback !== undefined && callback !== null) {
                callback.enable();
            }
        } else {
            button.classList.remove("active");
            for (let i = 0; i < targets.length; i++) {
                targets[i].classList.add("disabled");
            }
            if (callback !== undefined && callback !== null) {
                callback.disable();
            }
        }
    }
    switch_tab_visibility(button: HTMLElement) {
        const is_active = button.classList.contains("active");
        this.set_tab_visibility(!is_active, button);
    }
}

const _PRETTY_DURATIONS: Array<[number, string]> = [
    [365 * 86400, "y"],
    [30 * 86400, " mon"],
    [7 * 86400, "w"],
    [86400, "d"],
    [3600, "h"],
    [60, " min"],
    [1, "s"],
];

function pretty_print_duration(duration: number): string | null {
    let dur = duration;
    const out: string[] = [];
    _PRETTY_DURATIONS.forEach(([seconds, tick]) => {
        const num = Math.trunc(dur / seconds);
        if (num === 0) {
            return;
        }
        dur = dur % seconds;
        out.push(`${num}${tick}`);
    });
    return out.join(" ");
}
function pprange(ts1: number, ts2: number): string {
    const d1 = new Date();
    d1.setTime(ts1 * 1000);
    const d2 = new Date();
    d2.setTime(ts2 * 1000);
    const s1 = d1.toLocaleString();
    let out: string[] = [];
    const ss1 = s1.split(" ");
    d2.toLocaleString()
        .split(" ")
        .forEach((part, index) => {
            if (part !== ss1[index]) {
                out.push(part);
            }
        });
    if (out.length === 0) {
        out = [s1];
    } else {
        out = [s1, "until", ...out];
    }
    return out.join(" ");
}
