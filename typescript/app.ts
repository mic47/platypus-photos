var ___state: AppState = null;
function update_dir(data: string) {
    ___state.update_url({ directory: data });
}
function update_url(data: SearchQueryParams) {
    ___state.update_url(data);
}
function reset_param(key: string) {
    if (key === "__ALL__") {
        ___state.replace_url({});
        return;
    }
    const state = ___state.get_url();
    delete state[key];
    ___state.replace_url(state);
}
function update_form(div_id: string) {
    const formData = new FormData(
        document.getElementById(div_id) as HTMLFormElement
    );
    const values = ___state.get_url();
    for (let [key, value] of formData) {
        if (value !== null && value !== undefined && value !== "") {
            if (typeof value === "string") {
                values[key] = value;
            }
        } else {
            delete values[key];
        }
    }
    ___state.replace_url(values);
}
var ___map_search: MapSearch = null;
var ___map: PhotoMap = null;
function map_zoom(latitude: number, longitude: number) {
    ___map.map.flyTo([latitude, longitude], 13, { duration: 1 });
}
function map_bounds() {
    ___map.update_bounds(___state.get_url());
}
function map_refetch() {
    ___map.update_markers(___state.get_url(), false);
}
var ___global_markers: { [id: string]: LeafMarker } = {};
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
                parsed.map((e, i) => [i.toString(), e])
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
    text: string
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
                    value.text
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
    text: string
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
        ].join("")
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
        document.getElementById("MapSearchId") as HTMLFormElement
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
        ___map_search.fetch(values["query"] || null);
    }
}
function update_url_add_tag(tag: string) {
    const old_tag = ___state.get_url()["tag"];
    if (old_tag === undefined || old_tag === null) {
        ___state.update_url({ tag: tag });
    } else {
        ___state.update_url({ tag: `${old_tag},${tag}` });
    }
}
function set_page(page: number) {
    ___state.update_paging({ page: page.toString() });
}
function prev_page() {
    const page = parseInt(___state.get_paging()["page"]) || 0;
    if (page > 0) {
        ___state.update_paging({ page: (page - 1).toString() });
    }
}
function next_page() {
    const page = parseInt(___state.get_paging()["page"]) || 0;
    const update = { page: (page + 1).toString() };
    ___state.update_paging(update);
}
function add_to_float_param(param: string, other: string, new_value: number) {
    const query = ___state.get_url();
    let value = parseFloat(query[param]) || parseFloat(query[other]);
    if (value != value) {
        return;
    }
    const update: { [key: string]: string } = {};
    update[param] = (value + new_value).toString();
    ___state.update_url(update);
}
function shift_float_params(
    param_to_start: string,
    second_param: string,
    shift_by: number | null = null
) {
    const query = ___state.get_url();
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
    ___state.update_url(update);
}
function annotation_overlay(latitude: number, longitude: number) {
    const overlay = new AnnotationOverlay("SubmitDataOverlay");
    overlay.fetch(latitude, longitude, ___state.get_url());
}

var job_progress: JobProgress = null;
function update_job_progress(state_base64: string) {
    job_progress.add_state_base64(state_base64);
}
var job_list: JobList = null;
function show_job_list() {
    job_list.show_or_close();
}

function init_fun() {
    if (___state !== null) {
        throw new Error("State is already initialized!");
    }

    // Set parameters
    return fetch("/api/url_field_partitioning", {
        method: "GET",
        headers: {
            "Content-type": "application/json; charset=UTF-8",
        },
    })
        .then((response) => response.json())
        .then((response) => {
            const url_parameters_fields = response.search_query;
            const paging_fields = response.paging;
            const sort_fields = response.sort;

            // Initialize all components
            ___state = new AppState({}, {}, {});
            const url_sync = new UrlSync(url_parameters_fields);
            const paging_sync = new UrlSync(paging_fields);
            const sort_sync = new UrlSync(sort_fields);
            const input_form = new InputForm("InputForm");
            const gallery = new Gallery("GalleryImages", prev_page, next_page);
            ___map = new PhotoMap(
                "map",
                "MapUseQuery",
                () => ___state.get_url(),
                location_preview
            );
            ___map_search = new MapSearch("MapSearch");
            const dates = new Dates(
                "DateChart",
                (x) => {
                    ___state.update_url(x);
                },
                "DateSelection"
            );
            const directories = new Directories("Directories");
            const aggregate_info = new AggregateInfo("AggregateInfo");
            ___state.register_url_hook((url_params) => {
                input_form.fetch(url_params);
                url_sync.update(url_params);
                gallery.fetch(
                    url_params,
                    ___state.get_paging(),
                    ___state.get_sort()
                );
                aggregate_info.fetch(url_params, ___state.get_paging());

                dates.fetch(url_params);

                directories.fetch(url_params);

                ___map.update_markers(url_params, true);
            });
            ___state.register_paging_hook((paging) => {
                paging_sync.update(paging);
                gallery.fetch(___state.get_url(), paging, ___state.get_sort());
            });
            ___state.register_sort_hook((sort) => {
                sort_sync.update(sort);
                gallery.fetch(___state.get_url(), ___state.get_paging(), sort);
            });

            // Set initial url, redraw everything
            // TODO: check that this does not trigger too many refreshes
            ___state.replace_paging(paging_sync.get_url());
            ___state.replace_url(url_sync.get_url());
            ___state.replace_sort(sort_sync.get_url());
            ___map_search.fetch(null);

            job_progress = new JobProgress(
                "JobProgress",
                "update_job_progress",
                "show_job_list"
            );
            job_progress.fetch();
            setInterval(() => {
                job_progress.fetch();
            }, 10000);
            job_list = new JobList("JobList");
            new TabSwitch("RootTabs", {
                TabDirectories: directories.switchable,
                TabJobProgress: job_progress.switchable,
                TabDates: dates.switchable,
            });

            load_markers_initially();
        });
}
function update_sort(params: SortParams) {
    ___state.update_sort(params);
}

const app: any = {
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
    update_job_progress,
    show_job_list,
    delete_marker,
    submit_annotations,
    update_sort,
};
(window as any).APP = app
