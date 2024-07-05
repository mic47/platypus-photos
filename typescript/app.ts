import * as L from "leaflet";

import data_model from "./data_model.generated.json";

import { Dates } from "./dates_chart";
import { Gallery } from "./gallery";
import { InputForm } from "./input";
import { PhotoMap } from "./photo_map";
import {
    AppState,
    CheckboxSync,
    UrlSync,
    parse_gallery_paging,
    parse_search_query,
    parse_sort_params,
} from "./state.ts";
import { JobProgress } from "./jobs";
import { Directories } from "./directories";
import { TabSwitch } from "./switchable";
import { SystemStatus } from "./system_status";

import * as pygallery_service from "./pygallery.generated/services.gen";
import { SortParams, SearchQuery } from "./pygallery.generated/types.gen";
import { AnnotationOverlay, submit_to_annotation_overlay } from "./annotations";
import { MapSearch } from "./map_search.tsx";

let ___state: AppState;
function update_url(data: SearchQuery) {
    ___state.search_query.update(data);
}
let ___map: PhotoMap;
const ___global_markers: { [id: string]: L.Marker } = {};
type Marker = {
    latitude: number;
    longitude: number;
    text: string;
};
type LocalStorageMarkers = { [id: string]: Marker | null };
function get_markers_from_local_storage(): LocalStorageMarkers {
    let current = window.localStorage.getItem("markers");
    if (current === undefined || current === null) {
        current = "{}";
    }
    let parsed = {};
    try {
        parsed = JSON.parse(current);
    } catch (error) {
        console.log("Error when getting data from local storage", error);
    }
    return parsed;
}
function add_marker_to_local_storage(
    latitude: number,
    longitude: number,
    text: string,
) {
    const markers = get_markers_from_local_storage();
    const id = Math.random().toString().replace("0.", "");
    markers[id] = { latitude, longitude, text };
    window.localStorage.setItem("markers", JSON.stringify(markers));
    return id;
}
function delete_marker(id: string) {
    const markers = get_markers_from_local_storage();
    markers[id] = null;
    window.localStorage.setItem("markers", JSON.stringify(markers));
    delete_marker_only(id);
}
function delete_marker_only(id: string) {
    const marker = ___global_markers[id];
    if (marker !== undefined && marker !== null) {
        marker.remove();
        delete ___global_markers[id];
    }
}
function load_markers_initially() {
    Object.entries(get_markers_from_local_storage()).forEach(([id, m]) => {
        if (m !== undefined && m !== null) {
            map_add_point_only(id, m.latitude, m.longitude, m.text);
        }
    });
    window.addEventListener("storage", (e) => {
        if (e.key !== "markers") {
            return;
        }
        const oldValue: LocalStorageMarkers = JSON.parse(e.oldValue || "{}");
        const newValue: LocalStorageMarkers = JSON.parse(e.newValue || "{}");
        const actions: Array<[string, null | Marker]> = [];
        Object.entries(newValue).forEach(([id, value]) => {
            const old = oldValue[id];
            if (old === undefined || old === null) {
                if (value !== undefined && value !== null) {
                    // Something was added
                    actions.push([id, value]);
                }
            } else if (value === undefined || value === null) {
                // Old is something, this is empty
                actions.push([id, null]);
            }
        });
        if (actions.length === 0) {
            // Nothing to do
            return;
        }
        const markers = get_markers_from_local_storage();
        actions.forEach(([id, value]) => {
            markers[id] = value;
            if (value === undefined || value === null) {
                delete_marker_only(id);
            } else {
                map_add_point_only(
                    id,
                    value.latitude,
                    value.longitude,
                    value.text,
                );
            }
        });
        window.localStorage.setItem("markers", JSON.stringify(markers));
    });
}
function map_add_point_only(
    id: string,
    latitude: number,
    longitude: number,
    text: string,
) {
    const marker = L.marker([latitude, longitude], {
        alt: "Ad-hoc marker: " + text,
        title: "Ad-hoc marker: " + text,
        opacity: 0.7,
    }).addTo(___map.map);
    marker.bindPopup(
        [
            text,
            "<br/>",
            '<input type="button" value="Use this location for selected photos" ',
            `onclick="window.APP.annotation_overlay(${latitude}, ${longitude})">`,
            "<br/>",
            '<input type="button" value="Delete this marker" ',
            `onclick="window.APP.delete_marker('${id}')">`,
        ].join(""),
    );
    ___global_markers[id] = marker;
}
function map_add_point(latitude: number, longitude: number, text: string) {
    const id = add_marker_to_local_storage(latitude, longitude, text);
    map_add_point_only(id, latitude, longitude, text);
}
function annotation_overlay(latitude: number, longitude: number) {
    pygallery_service
        .getAddressPost({ requestBody: { latitude, longitude } })
        .catch((reason) => {
            console.log(reason);
            return { country: null, name: null, full: null };
        })
        .then((address) => {
            submit_to_annotation_overlay("SubmitDataOverlay", {
                request: {
                    t: "FixedLocation",
                    latitude,
                    longitude,
                    address_name: address.name,
                    address_country: address.country,
                },
                query: ___state.search_query.get(),
            });
        });
}

const ___checkbox_sync: CheckboxSync = new CheckboxSync();

function init_fun() {
    if (___state !== undefined) {
        throw new Error("State is already initialized!");
    }

    const url_parameters_fields = data_model.fields.search_query;
    const paging_fields = data_model.fields.paging;
    const sort_fields = data_model.fields.sort;

    /* Initialize state and url syncs */
    ___state = new AppState({}, {}, {});
    const search_query_sync = new UrlSync(url_parameters_fields);
    ___state.search_query.register_hook("SearchQueryUrlSync", (u) =>
        search_query_sync.update(u),
    );
    const paging_sync = new UrlSync(paging_fields);
    ___state.paging.register_hook("PagingUrlSync", (u) =>
        paging_sync.update(u),
    );
    const sort_sync = new UrlSync(sort_fields);
    ___state.sort.register_hook("SortUrlSync", (u) => sort_sync.update(u));
    new InputForm("InputForm", ___state.search_query);
    /* Gallery */
    new Gallery(
        "GalleryImages",
        ___state.search_query,
        ___state.paging,
        ___state.sort,
        ___checkbox_sync,
    );
    /* AnnotationOverlay */
    new AnnotationOverlay(
        "SubmitDataOverlay",
        ___state.search_query,
        ___state.paging,
    );
    /* Map */
    ___map = new PhotoMap(
        "map",
        "MapUseQuery",
        () => ___state.search_query.get(),
        { annotation_overlay, add_point_to_map: map_add_point },
    );
    new MapSearch("MapSearch", ___checkbox_sync, ___state.search_query, ___map);
    ___state.search_query.register_hook("MasSearch", (url_params) => {
        ___map.update_markers(url_params, true);
    });
    /* Dates */
    const dates = new Dates(
        "DateChart",
        (x) => {
            ___state.search_query.update(x);
        },
        "DateSelection",
        "DateChartGroupBy",
    );
    ___state.search_query.register_hook("Dates", (u) => dates.fetch(u));
    /* Directories */
    const directories = new Directories("Directories", ___state.search_query);

    /* Trigger redrawing of componentsl */
    // WARNING: here we assume that search_query will update everything
    ___state.paging.replace_no_hook_update(
        parse_gallery_paging(paging_sync.get()),
    );
    // WARNING: here we assume that search_query will update everything
    ___state.sort.replace_no_hook_update(parse_sort_params(sort_sync.get()));
    ___state.search_query.replace(parse_search_query(search_query_sync.get()));

    /* Job progress / list UI */
    const job_progress = new JobProgress("JobProgress", ___map.zoom_to);
    /* System Status */
    const system_status = new SystemStatus("SystemStatus");
    /* Tab */
    new TabSwitch("RootTabs", {
        TabDirectories: directories.switchable,
        TabJobProgress: job_progress.switchable,
        TabSystemStatus: system_status.switchable,
        TabDates: dates.switchable,
    });

    load_markers_initially();
}
function update_sort(params: SortParams) {
    ___state.sort.update(params);
}

const app: object = {
    checkbox_sync: ___checkbox_sync,
    init_fun,
    update_url,
    map_add_point,
    annotation_overlay,
    delete_marker,
    update_sort,
};
(window as unknown as { APP: object }).APP = app;
