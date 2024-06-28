import * as L from "leaflet";

import data_model from "./data_model.generated.json";

import { Dates } from "./dates_chart.ts";
import {
    AggregateInfo,
    Gallery,
    overlay,
    overlay_close,
    overlay_next,
    overlay_prev,
} from "./gallery.ts";
import { InputForm } from "./input.ts";
import {
    parse_float_or_null,
    error_box,
    null_if_empty,
    base64_decode_object,
} from "./utils.ts";
import {
    AnnotationOverlay,
    ManualLocation,
    MapSearch,
    PhotoMap,
    location_preview,
} from "./photo_map.ts";
import {
    AppState,
    CheckboxSync,
    SearchQueryParams,
    SortParams,
    UrlSync,
} from "./state.ts";
import { JobList, JobProgress } from "./jobs.ts";
import { Directories } from "./directories.ts";
import { TabSwitch } from "./switchable.ts";
import {
    LocationOverride,
    LocationTypes,
    MassLocationAndTextAnnotation,
    TextOverride,
} from "./annotations.ts";

let ___state: AppState;
function update_dir(data: string) {
    ___state.search_query.update({ directory: data });
}
function update_url(data: SearchQueryParams) {
    ___state.search_query.update(data);
}
function reset_param(key: string) {
    if (key === "__ALL__") {
        ___state.search_query.replace({});
        return;
    }
    const state = ___state.search_query.get();
    delete state[key];
    ___state.search_query.replace(state);
}
function update_form(div_id: string) {
    const formData = new FormData(
        document.getElementById(div_id) as HTMLFormElement,
    );
    const values = ___state.search_query.get();
    for (const [key, value] of formData) {
        if (value !== null && value !== undefined && value !== "") {
            if (typeof value === "string") {
                values[key] = value;
            }
        } else {
            delete values[key];
        }
    }
    ___state.search_query.replace(values);
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
    ___state.paging.update({ page: page.toString() });
}
function prev_page() {
    const page = parseInt(___state.paging.get()["page"]) || 0;
    if (page > 0) {
        ___state.paging.update({ page: (page - 1).toString() });
    }
}
function next_page() {
    const page = parseInt(___state.paging.get()["page"]) || 0;
    const update = { page: (page + 1).toString() };
    ___state.paging.update(update);
}
function add_to_float_param(param: string, other: string, new_value: number) {
    const query = ___state.search_query.get();
    const value = parseFloat(query[param]) || parseFloat(query[other]);
    if (value != value) {
        return;
    }
    const update: { [key: string]: string } = {};
    update[param] = (value + new_value).toString();
    ___state.search_query.update(update);
}
function shift_float_params(
    param_to_start: string,
    second_param: string,
    shift_by: number | null = null,
) {
    const query = ___state.search_query.get();
    const start_value = parseFloat(query[param_to_start]);
    const end_value = parseFloat(query[second_param]);
    if (end_value != end_value) {
        // This does not make sense, second param is empty
        return;
    }
    const update: { [key: string]: string } = {};
    update[param_to_start] = end_value.toString();
    if (shift_by !== undefined && shift_by !== null) {
        update[second_param] = (end_value + shift_by).toString();
    } else {
        if (start_value != start_value) {
            delete update[second_param];
        } else {
            update[second_param] = (
                end_value +
                end_value -
                start_value
            ).toString();
        }
    }
    ___state.search_query.update(update);
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
    let location: LocationTypes;
    const request_type = formData.get("request_type");
    if (request_type == "FixedLocation") {
        location = {
            t: request_type,
            location: manualLocation,
            override: (location_override ?? "NoLocNoMan") as LocationOverride,
        };
    } else if (request_type == "InterpolatedLocation") {
        location = {
            t: request_type,
            location: manualLocation,
        };
    } else if (request_type == "NoLocation") {
        location = {
            t: request_type,
        };
    } else {
        throw new Error(`Unsupported request type ${request_type}`);
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
    const request: MassLocationAndTextAnnotation = {
        t: "MassLocAndTxt",
        query: query as SearchQueryParams,
        location,
        text: {
            t: "FixedText",
            text: text_request,
            override: (text_override ?? "ExMan") as TextOverride,
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
        fetch("api/mass_manual_annotation", {
            method: "POST",
            body: JSON.stringify(request),
            headers: {
                "Content-type": "application/json; charset=UTF-8",
            },
        })
            .then((response) => response.json())
            .then(() => {
                if (advance_in_time !== undefined && advance_in_time !== null) {
                    // TODO: resolve these imports
                    shift_float_params("tsfrom", "tsto", advance_in_time);
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
    overlay.fetch(
        { t: "FixedLocation", latitude, longitude },
        ___state.search_query.get(),
    );
}
function annotation_overlay_no_location() {
    const overlay = new AnnotationOverlay("SubmitDataOverlay");
    overlay.fetch({ t: "NoLocation" }, ___state.search_query.get());
}
function annotation_overlay_interpolated(location_encoded_base64: string) {
    const overlay = new AnnotationOverlay("SubmitDataOverlay");
    overlay.fetch(
        {
            t: "InterpolatedLocation",
            location: base64_decode_object(
                location_encoded_base64,
            ) as ManualLocation,
        },
        ___state.search_query.get(),
    );
}

let job_progress: JobProgress<{ ts: number }>;
function update_job_progress(state_base64: string) {
    job_progress.add_state_base64(state_base64);
}
let job_list: JobList;
function show_job_list() {
    job_list.show_or_close();
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
    const input_form = new InputForm("InputForm");
    ___state.search_query.register_hook((u) => input_form.fetch(u));
    /* Gallery */
    const gallery = new Gallery("GalleryImages", prev_page, next_page);
    ___state.search_query.register_hook((search_query) => {
        gallery.fetch(
            search_query,
            ___state.paging.get(),
            ___state.sort.get(),
            ___checkbox_sync.get(),
        );
    });
    ___state.paging.register_hook((paging) => {
        gallery.fetch(
            ___state.search_query.get(),
            paging,
            ___state.sort.get(),
            ___checkbox_sync.get(),
        );
    });
    ___state.sort.register_hook((sort) => {
        gallery.fetch(
            ___state.search_query.get(),
            ___state.paging.get(),
            sort,
            ___checkbox_sync.get(),
        );
    });
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
    ___state.paging.replace_no_hook_update(paging_sync.get());
    // WARNING: here we assume that search_query will update everything
    ___state.sort.replace_no_hook_update(sort_sync.get());
    ___state.search_query.replace(search_query_sync.get());
    ___map_search.fetch(null, ___checkbox_sync.get());

    /* Job progress / list UI */
    job_progress = new JobProgress(
        "JobProgress",
        "update_job_progress",
        "show_job_list",
    );
    job_progress.fetch();
    setInterval(() => {
        job_progress.fetch();
    }, 10000);
    job_list = new JobList("JobList");
    /* Tab */
    new TabSwitch("RootTabs", {
        TabDirectories: directories.switchable,
        TabJobProgress: job_progress.switchable,
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
    reset_param,
    update_form,
    map_zoom,
    map_bounds,
    map_refetch,
    map_add_point,
    map_close_popup,
    fetch_map_search,
    update_url_add_tag,
    set_page,
    prev_page,
    next_page,
    add_to_float_param,
    shift_float_params,
    annotation_overlay,
    annotation_overlay_interpolated,
    annotation_overlay_no_location,
    update_job_progress,
    show_job_list,
    delete_marker,
    submit_annotations,
    update_sort,
    overlay,
    overlay_close,
    overlay_next,
    overlay_prev,
};
(window as unknown as { APP: object }).APP = app;
