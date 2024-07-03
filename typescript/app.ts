import * as L from "leaflet";

import data_model from "./data_model.generated.json";

import { Dates } from "./dates_chart.ts";
import { AggregateInfo, Gallery } from "./gallery";
import { InputForm, shift_float_params } from "./input";
import {
    parse_float_or_null,
    error_box,
    null_if_empty,
    base64_decode_object,
} from "./utils.ts";
import {
    AnnotationOverlay,
    MapSearch,
    PhotoMap,
    location_preview,
} from "./photo_map.ts";
import {
    AppState,
    CheckboxSync,
    UrlSync,
    parse_gallery_paging,
    parse_search_query,
    parse_sort_params,
} from "./state.ts";
import { JobProgress } from "./jobs";
import { Directories } from "./directories.ts";
import { TabSwitch } from "./switchable.ts";
import { SystemStatus } from "./system_status";

import * as pygallery_service from "./pygallery.generated/services.gen.ts";
import {
    SortParams,
    ManualLocationOverride,
    MassLocationAndTextAnnotation_Input,
    TextAnnotationOverride,
    SearchQuery,
} from "./pygallery.generated/types.gen.ts";
import { LocationTypes } from "./annotations.ts";

let ___state: AppState;
function update_dir(data: string) {
    ___state.search_query.update({ directory: data });
}
function update_url(data: SearchQuery) {
    ___state.search_query.update(data);
}
let ___map_search: MapSearch;
let ___map: PhotoMap;
function map_zoom(latitude: number, longitude: number) {
    ___map.map.flyTo([latitude, longitude], 13, { duration: 1 });
}
function map_bounds() {
    ___map.update_bounds(___state.search_query.get());
}
function map_refetch() {
    ___map.update_markers(___state.search_query.get(), false);
}
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
        if (Array.isArray(parsed)) {
            parsed = Object.fromEntries(
                parsed.map((e, i) => [i.toString(), e]),
            );
        }
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
function map_close_popup() {
    ___map.map.closePopup();
}
function fetch_map_search() {
    const formData = new FormData(
        document.getElementById("MapSearchId") as HTMLFormElement,
    );
    const values: { [key: string]: string } = {};
    for (const [key, value] of formData) {
        if (value) {
            if (typeof value === "string") {
                values[key] = value;
            }
        }
    }
    if (___map_search !== null) {
        ___map_search.fetch(values["query"] || null, ___checkbox_sync.get());
    }
}
function update_url_add_tag(tag: string) {
    const old_tag = ___state.search_query.get()["tag"];
    if (old_tag === undefined || old_tag === null) {
        ___state.search_query.update({ tag: tag });
    } else {
        ___state.search_query.update({ tag: `${old_tag},${tag}` });
    }
}
function set_page(page: number) {
    ___state.paging.update({ page });
}
export function submit_annotations(
    div_id: string,
    form_id: string,
    return_id: string,
    advance_in_time: number | null,
) {
    const formElement = document.getElementById(form_id);
    if (formElement === null) {
        throw new Error(`Unable to find element ${form_id}`);
    }
    const formData = new FormData(formElement as HTMLFormElement);
    const checkbox_value = formData.get("sanity_check");
    [...formElement.getElementsByClassName("uncheck")].forEach((element) => {
        // Prevent from accidentally submitting again
        (element as HTMLInputElement).checked = false;
    });
    const query = base64_decode_object(
        formData.get("query_json_base64") as string,
    );
    const request_type = formData.get("request_type");
    let location: LocationTypes;
    if (request_type == "NoLocation") {
        location = {
            t: request_type,
        };
    } else {
        const latitude = parse_float_or_null(formData.get("latitude"));
        if (latitude === null) {
            return error_box(return_id, {
                error: "Invalid request, latitude",
                formData,
            });
        }
        const longitude = parse_float_or_null(formData.get("longitude"));
        if (longitude === null) {
            return error_box(return_id, {
                error: "Invalid request, longitude",
                formData,
            });
        }
        const location_override = formData.get("location_override");
        let address_name = null_if_empty(formData.get("address_name"));
        const address_name_original = null_if_empty(
            formData.get("address_name_original"),
        );
        if (
            address_name === null ||
            address_name.trim() === address_name_original
        ) {
            address_name = address_name_original;
        }
        let address_country = null_if_empty(formData.get("address_country"));
        const address_country_original = null_if_empty(
            formData.get("address_country_original"),
        );
        if (
            address_country === null ||
            address_country.trim() === address_country_original
        ) {
            address_country = address_country_original;
        }
        const manualLocation = {
            latitude,
            longitude,
            address_name,
            address_country,
        };
        if (request_type == "FixedLocation") {
            location = {
                t: request_type,
                location: manualLocation,
                override: (location_override ??
                    "NoLocNoMan") as ManualLocationOverride,
            };
        } else if (request_type == "InterpolatedLocation") {
            location = {
                t: request_type,
                location: manualLocation,
            };
        } else {
            throw new Error(`Unsupported request type ${request_type}`);
        }
    }
    const extra_tags = null_if_empty(formData.get("extra_tags"));
    const extra_description = null_if_empty(formData.get("extra_description"));
    const text_override = formData.get("text_override");
    const text_request = {
        tags: extra_tags,
        description: extra_description,
    };
    const loc_only = formData.get("text_loc_only") == "on";
    const adjust_dates = formData.get("apply_timestamp_trans") == "on";
    const request: MassLocationAndTextAnnotation_Input = {
        t: "MassLocAndTxt",
        query: query as SearchQuery,
        location,
        text: {
            t: "FixedText",
            text: text_request,
            override: (text_override ?? "ExMan") as TextAnnotationOverride,
            loc_only,
        },
        date: {
            t: "TransDate",
            adjust_dates,
        },
    };
    if (checkbox_value !== "on") {
        return error_box(return_id, {
            error: "You have to check 'Check this box' box to prevent accidental submissions",
        });
    }
    return (
        pygallery_service
            .massManualAnnotationEndpointPost({ requestBody: request })
            .then(() => {
                if (advance_in_time !== undefined && advance_in_time !== null) {
                    // TODO: resolve these imports
                    shift_float_params(
                        ___state.search_query,
                        "tsfrom",
                        "tsto",
                        advance_in_time,
                    );
                    set_page(0);
                }
                const element = document.getElementById(div_id);
                if (element === null) {
                    throw Error(`Unable to find element ${div_id}`);
                }
                element.remove();
            })
            // TODO: put error into stuff
            .catch((err) => {
                return error_box(return_id, {
                    msg: "There was error while processing on the server.",
                    error: err,
                });
            })
    );
}

function annotation_overlay(latitude: number, longitude: number) {
    const overlay = new AnnotationOverlay("SubmitDataOverlay");
    overlay.fetch({
        request: { t: "FixedLocation", latitude, longitude },
        query: ___state.search_query.get(),
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
    ___state.search_query.register_hook((u) => search_query_sync.update(u));
    const paging_sync = new UrlSync(paging_fields);
    ___state.paging.register_hook((u) => paging_sync.update(u));
    const sort_sync = new UrlSync(sort_fields);
    ___state.sort.register_hook((u) => sort_sync.update(u));
    new InputForm("InputForm", ___state.search_query);
    /* Gallery */
    new Gallery(
        "GalleryImages",
        ___state.search_query,
        ___state.paging,
        ___state.sort,
        ___checkbox_sync,
    );
    /* Map */
    ___map = new PhotoMap(
        "map",
        "MapUseQuery",
        () => ___state.search_query.get(),
        location_preview,
    );
    ___map_search = new MapSearch("MapSearch");
    ___state.search_query.register_hook((url_params) => {
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
    ___state.search_query.register_hook((u) => dates.fetch(u));
    /* Directories */
    const directories = new Directories("Directories");
    ___state.search_query.register_hook((u) => directories.fetch(u));
    /* Aggregate Info */
    const aggregate_info = new AggregateInfo("AggregateInfo");
    ___state.search_query.register_hook((url_params) => {
        aggregate_info.fetch(url_params, ___state.paging.get());
    });

    /* Trigger redrawing of componentsl */
    // WARNING: here we assume that search_query will update everything
    ___state.paging.replace_no_hook_update(
        parse_gallery_paging(paging_sync.get()),
    );
    // WARNING: here we assume that search_query will update everything
    ___state.sort.replace_no_hook_update(parse_sort_params(sort_sync.get()));
    ___state.search_query.replace(parse_search_query(search_query_sync.get()));
    ___map_search.fetch(null, ___checkbox_sync.get());

    /* Job progress / list UI */
    const job_progress = new JobProgress("JobProgress", map_zoom);
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
    update_dir,
    update_url,
    map_zoom,
    map_bounds,
    map_refetch,
    map_add_point,
    map_close_popup,
    fetch_map_search,
    update_url_add_tag,
    set_page,
    annotation_overlay,
    delete_marker,
    submit_annotations,
    update_sort,
};
(window as unknown as { APP: object }).APP = app;
