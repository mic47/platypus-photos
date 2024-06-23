class AppState {
    constructor(url_params, paging, sort) {
        this._url_params = url_params;
        this._url_params_hooks = [];

        this._paging = paging;
        this._paging_hooks = [];

        this._sort = sort;
        this._sort_hooks = [];
    }

    register_paging_hook(hook) {
        this._paging_hooks.push(hook);
    }
    get_paging() {
        return this._paging;
    }
    update_paging(new_parts) {
        this._paging = { ...this._paging, ...new_parts };
        const paging = this._paging;
        this._paging_hooks.forEach((x) => x(paging));
    }
    replace_paging(new_paging) {
        this._paging = {};
        this.update_paging(new_paging);
    }

    register_sort_hook(hook) {
        this._sort_hooks.push(hook);
    }
    get_sort() {
        return this._sort;
    }
    update_sort(new_parts) {
        this._sort = { ...this._sort, ...new_parts };
        const sort = this._sort;
        this._sort_hooks.forEach((x) => x(sort));
    }
    replace_sort(new_sort) {
        this._sort = {};
        this.update_sort(new_sort);
    }

    get_url() {
        return { ...this._url_params };
    }
    update_url(new_parts) {
        // TODO: do this only on change
        this._url_params = { ...this._url_params, ...new_parts };
        const url = this._url_params;
        this._url_params_hooks.forEach((x) => x(url));
    }
    replace_url(new_url) {
        // TODO: do this only on change
        this._url_params = {};
        this.update_url(new_url);
    }
    register_url_hook(hook) {
        this._url_params_hooks.push(hook);
    }
}

class UrlSync {
    constructor(registered_fields) {
        this._registered_fields = registered_fields;
    }
    get_url() {
        var url = new URL(window.location.href);
        return Object.fromEntries(
            this._registered_fields
                .map((field) => [field, url.searchParams.get(field)])
                .filter((x) => x[1] !== undefined && x[1] !== null && x[1])
        );
    }
    update(new_url) {
        var url = new URL(window.location.href);
        this._registered_fields.forEach((field) => {
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

function changeState(index) {
    var url = new URL(window.location.href);
    old_parameter = url.searchParams.get("oi");
    if (old_parameter !== index) {
        return;
    }
    if (index == null) {
        url.searchParams.delete("oi");
    } else {
        url.searchParams.set("oi", index);
    }
    if (window.history.replaceState) {
        window.history.replaceState(window.history.state, "", url.href);
    }
}
function replace_image_size_inside(element, source, replacement) {
    if (element == null) {
        return;
    }
    var images = element.getElementsByTagName("img");
    for (var i = 0; i < images.length; i++) {
        var image = images[i];
        var repl = image.src.replace("size=" + source, "size=" + replacement);
        if (repl != image.src) {
            image.src = repl;
        }
        if (replacement == "original") {
            image.loading = "eager";
        }
    }
}
function this_is_overlay_element(element) {
    replace_image_size_inside(element, "preview", "original");
    var next = element.nextElementSibling;
    if (next != null) {
        replace_image_size_inside(next, "preview", "original");
        next = next.nextElementSibling;
    }
    var prev = element.previousElementSibling;
    if (prev != null) {
        replace_image_size_inside(prev, "preview", "original");
        prev = prev.previousElementSibling;
    }
    if (next != null) {
        replace_image_size_inside(next, "original", "preview");
    }
    if (prev != null) {
        replace_image_size_inside(prev, "original", "preview");
    }
}
function overlay(element, index) {
    this_is_overlay_element(element.parentElement);
    element.parentElement.classList.add("overlay");
    changeState(index);
}
function overlay_close(element) {
    var root = element.parentElement.parentElement;
    replace_image_size_inside(root, "original", "preview");
    replace_image_size_inside(
        root.previousElementSibling,
        "original",
        "preview"
    );
    replace_image_size_inside(root.nextElementSibling, "original", "preview");
    root.classList.remove("overlay");
    changeState(null);
}
function overlay_prev(element, index) {
    this_is_overlay_element(
        element.parentElement.parentElement.previousElementSibling
    );
    element.parentElement.parentElement.previousElementSibling.classList.add(
        "overlay"
    );
    element.parentElement.parentElement.classList.remove("overlay");
    changeState(index - 1);
}
function overlay_next(element, index) {
    this_is_overlay_element(
        element.parentElement.parentElement.nextElementSibling
    );
    element.parentElement.parentElement.nextElementSibling.classList.add(
        "overlay"
    );
    element.parentElement.parentElement.classList.remove("overlay");
    changeState(index + 1);
}

class PhotoMap {
    constructor(
        div_id,
        should_use_query_div,
        get_url,
        context_menu_callback
    ) {
        this.map = L.map(div_id).fitWorld();
        this._should_use_query_div = should_use_query_div;
        this._last_update_markers = {};
        L.control.scale({ imperial: false }).addTo(this.map);
        this.markers = {};
        this.last_update_timestamp = 0;
        this._context_menu_callback = context_menu_callback;
        const that = this;
        const update_markers = (e) => {
            if (e.flyTo) {
                return;
            }
            that.update_markers(get_url(), false);
        };
        const context_menu = (e) => {
            that.context_menu(e);
        };
        this.map.on("load", update_markers);
        this.map.on("zoomend", update_markers);
        this.map.on("moveend", update_markers);
        this.map.on("zoom", update_markers);
        this.map.on("move", update_markers);
        this.map.on("resize", update_markers);
        if (
            this._context_menu_callback !== undefined &&
            this._context_menu_callback !== null
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

    context_menu(e) {
        this._context_menu_callback(e.latlng, (content) => {
            return L.popup()
                .setLatLng(e.latlng)
                .setContent(content)
                .openOn(this.map);
        });
    }

    update_bounds(location_url_json, fit_not_fly=false) {
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
            .then((bounds) => {
                if (bounds === undefined || bounds === null) {
                    return;
                }
                const latlngs = [
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

    _similar(last_bounds, new_bounds, tolerance) {
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
                lat_tolerance &&
            Math.abs(last_bounds.br.latitude - new_bounds.br.latitude) <
                lat_tolerance &&
            Math.abs(last_bounds.br.longitude - new_bounds.br.longitude) <
                lat_tolerance
        );
    }
    _should_skip(timestamp, bounds_query, non_bounds, change_view) {
        const non_bounds_str = JSON.stringify(non_bounds);
        if (
            this._last_update_markers.timestamp + 10000 > timestamp &&
            this._last_update_markers.non_bounds === non_bounds_str &&
            this._similar(
                this._last_update_markers.bounds,
                bounds_query,
                0.1
            ) &&
            this._last_update_markers.change_view === change_view
        ) {
            return true;
        }
        this._last_update_markers.non_bounds = non_bounds_str;
        this._last_update_markers.bounds = bounds_query;
        this._last_update_markers.change_view = change_view;
        this._last_update_markers.timestamp = timestamp;
        return false;
    }

    update_markers(location_url_json, change_view = false) {
        // TODO: wrapped maps: shift from 0 + wrap around
        const should_use_query =
            document.getElementById(this._should_use_query_div)?.checked ||
            false;

        var bounds = this.map.getBounds();
        var nw = bounds.getNorthWest();
        var se = bounds.getSouthEast();
        var sz = this.map.getSize();
        var cluster_pixel_size = 10;
        var timestamp = new Date().getTime();
        const bounds_query = {
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
                }).filter((x) => x[0] !== "page" && x[0] !== "paging")
            ),
        };
        if (
            this._should_skip(timestamp, bounds_query, non_bounds, change_view)
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
                var new_markers = {};
                for (var i = 0; i < clusters.length; i++) {
                    var cluster = clusters[i];
                    var existing = this.markers[cluster.example_path_md5];
                    if (existing !== undefined) {
                        new_markers[cluster.example_path_md5] = existing;
                        delete this.markers[cluster.example_path_md5];
                        continue;
                    }
                    var marker = L.marker([
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
                            ")<br/><img src='/img?hsh=",
                            cluster.example_path_md5,
                            "&size=preview' class='popup'>",
                            '<input type="button" value="Use this location for selected photos" ',
                            `onclick="annotation_overlay(${cluster.position.latitude}, ${cluster.position.longitude})">`,
                        ].join("")
                    );
                    new_markers[cluster.example_path_md5] = marker;
                }
                Object.values(this.markers).forEach((m) => m.remove());
                Object.keys(this.markers).forEach(
                    (m) => delete this.markers[m]
                );
                Object.entries(new_markers).forEach(
                    (m) => (this.markers[m[0]] = m[1])
                );
            });
    }
}

class Switchable {
    constructor() {
        this._enabled = true;
        this._callbacks = {};
    }
    disable() {
        if (this._enabled === false) {
            false;
        }
        this._enabled = false;
        this._callbacks = {};
    }
    enable() {
        if (this._enabled === true) {
            return;
        }
        this._enabled = true;
        Object.values(this._callbacks).forEach((callback) => {
            if (callback !== undefined && callback !== null) {
                callback();
            }
        });
        this._callbacks = {};
    }
    call_or_store(name, callback) {
        if (this._enabled) {
            return callback();
        }
        this._callbacks[name] = callback;
    }
}

class Directories {
    constructor(div_id) {
        this._div_id = div_id;
        this.switchable = new Switchable();
    }

    fetch(url_data) {
        return this.switchable.call_or_store("fetch", () =>
            this.fetch_impl(url_data)
        );
    }

    fetch_impl(url_data) {
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
                const gallery = document.getElementById(this._div_id);
                gallery.innerHTML = text;
            });
    }
}

class AggregateInfo {
    constructor(div_id) {
        this._div_id = div_id;
    }

    fetch(url_data, paging) {
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
                const gallery = document.getElementById(this._div_id);
                gallery.innerHTML = text;
            });
    }
}

class GenericFetch {
    constructor(div_id, endpoint) {
        this._div_id = div_id;
        this._endpoint = endpoint;
    }

    fetch_impl(request) {
        return fetch(this._endpoint, {
            method: "POST",
            body: JSON.stringify(request),
            headers: {
                "Content-type": "application/json; charset=UTF-8",
            },
        })
            .then((response) => response.text())
            .then((text) => {
                const gallery = document.getElementById(this._div_id);
                gallery.innerHTML = text;
            });
    }
}
function now_s() {
    return Date.now() / 1000.0;
}
class JobProgress extends GenericFetch {
    constructor(div_id, update_state_fn, job_list_fn) {
        super(div_id, "/internal/job_progress.html");
        this._states = [];
        this._update_state_fn = update_state_fn;
        this._job_list_fn = job_list_fn;
        this.switchable = new Switchable();
    }
    fetch() {
        this.switchable.call_or_store("fetch", () => {
            return this.fetch_impl({
                job_list_fn: this._job_list_fn,
                update_state_fn: this._update_state_fn,
                state: this._states[0],
            });
        });
    }
    add_state(state) {
        this._states.push(state);
        this._states = this._states.filter((x) => state.ts - x.ts < 300.0);
    }
    add_state_base64(base64) {
        const state = JSON.parse(window.atob(base64));
        this.add_state(state);
    }
}
class JobList extends GenericFetch {
    constructor(div_id) {
        super(div_id, "/internal/job_list.html");
        self._div_id = div_id;
        this._shown = false;
    }
    fetch() {
        return this.fetch_impl({}).then(() => {
            this._shown = true;
        });
    }
    show_or_close() {
        if (this._shown) {
            this._shown = false;
            document.getElementById(this._div_id).innerHTML = "";
        } else {
            this.fetch();
        }
    }
}

class MapSearch extends GenericFetch {
    constructor(div_id) {
        super(div_id, "/internal/map_search.html");
    }
    fetch(search_str) {
        return this.fetch_impl({ query: search_str });
    }
}

class AddressInfo extends GenericFetch {
    constructor(div_id) {
        super(div_id, "/internal/fetch_location_info.html");
    }
    fetch(latitude, longitude) {
        return this.fetch_impl({ latitude, longitude });
    }
}

class AnnotationOverlay extends GenericFetch {
    constructor(div_id) {
        super(div_id, "/internal/submit_annotations_overlay.html");
    }
    fetch(latitude, longitude, query) {
        return this.fetch_impl({ latitude, longitude, query });
    }
}

function null_if_empty(str) {
    if (str === null || str === undefined || str.trim() === "") {
        return null;
    }
    return str;
}
function parse_float_or_null(str) {
    const value = parseFloat(str);
    if (value != value) {
        return null;
    }
    return value;
}

function error_box(div_id, value) {
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
        pre.innerHTML = value;
    }
    element.appendChild(pre);
    e.innerHTML = "";
    e.appendChild(element);
}

function submit_annotations(div_id, form_id, return_id, advance_in_time) {
    const formData = new FormData(document.getElementById(form_id));
    const checkbox_value = formData.get("sanity_check");
    [
        ...document.getElementById(form_id).getElementsByClassName("uncheck"),
    ].forEach((element) => {
        // Prevent from accidentally submitting again
        element.checked = false;
    });
    const query = JSON.parse(window.atob(formData.get("query_json_base64")));
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
    const address_name_original = formData.get("address_name_original");
    if (
        address_name === null ||
        address_name.trim() === address_name_original
    ) {
        address_name = address_name_original;
    }
    let address_country = null_if_empty(formData.get("address_country"));
    const address_country_original = formData.get("address_country_original");
    if (
        address_country === null ||
        address_country.trim() === address_country_original
    ) {
        address_country = address_country_original;
    }
    const location_request = {
        latitude,
        longitude,
        address_name,
        address_country,
    };
    const extra_tags = null_if_empty(formData.get("extra_tags"));
    const extra_description = null_if_empty(formData.get("extra_description"));
    const text_override = formData.get("text_override");
    const text_request = {
        tags: extra_tags,
        description: extra_description,
    };
    const request = {
        query,
        location: location_request,
        location_override,
        text: text_request,
        text_override,
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
            .then((response) => {
                if (advance_in_time !== undefined && advance_in_time !== null) {
                    // TODO: resolve these imports
                    shift_float_params("tsfrom", "tsto", advance_in_time);
                    set_page(0);
                }
                document.getElementById(div_id).remove();
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

function location_preview(loc, show_content_fn) {
    const existing = document.getElementById("LocPreview");
    if (existing !== undefined && existing !== null) {
        existing.remove();
    }
    const popup = show_content_fn('<div id="LocPreview"></div>');
    const info = new AddressInfo("LocPreview");
    info.fetch(loc.lat, loc.lng).then((_) => {
        popup._updateLayout();
    });
}

class InputForm {
    constructor(div_id) {
        this._div_id = div_id;
    }

    fetch(url_data) {
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
                const gallery = document.getElementById(this._div_id);
                gallery.innerHTML = text;
            });
    }
}

class Gallery {
    constructor(div_id, prev_page, next_page) {
        this._div_id = div_id;
        this._next_page = next_page;
        this._prev_page = prev_page;
    }

    fetch(url_data, paging, sort) {
        var url = `/internal/gallery.html?oi=${this._oi}`;
        if (this._oi === undefined || this._oi === null) {
            url = `/internal/gallery.html`;
        }
        fetch(url, {
            method: "POST",
            body: JSON.stringify({ query: url_data, paging, sort }),
            headers: {
                "Content-type": "application/json; charset=UTF-8",
            },
        })
            .then((response) => response.text())
            .then((text) => {
                const gallery = document.getElementById(this._div_id);
                gallery.innerHTML = text;
                const prev = gallery.getElementsByClassName("prev-url");
                for (var i = 0; i < prev.length; i++) {
                    const p = prev[i];
                    p.onclick = (e) => {
                        this._prev_page();
                    };
                }
                const next = gallery.getElementsByClassName("next-url");
                for (var i = 0; i < next.length; i++) {
                    const p = next[i];
                    p.onclick = (e) => {
                        this._next_page();
                    };
                }
            });
    }
}

class Dates {
    constructor(div_id, update_url, tooltip_div) {
        this.switchable = new Switchable();
        this._clickTimeStart = null;
        this._tooltip_div = tooltip_div;
        const ctx = document.getElementById(div_id);
        this._chart = new Chart(ctx, {
            type: "line",
            data: {
                datasets: [
                    {
                        label: "# Selected Images",
                        data: [],
                        borderWidth: 1,
                        showLine: false,
                    },
                    {
                        label: "# Overfetched Images",
                        data: [],
                        borderWidth: 1,
                        showLine: false,
                    },
                ],
            },
            options: {
                events: ["mousedown", "mouseup"],
                parsing: false,
                scales: {
                    y: {
                        beginAtZero: true,
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
                            afterFooter: function (context) {
                                const cluster = context[0].raw.cluster;
                                const duration = pretty_print_duration(
                                    cluster.bucket_max - cluster.bucket_min
                                );
                                const start = pprange(
                                    cluster.min_timestamp,
                                    cluster.max_timestamp
                                );
                                const image_md5 = cluster.example_path_md5;
                                const innerHtml2 = `
<div class="date_tooltip">
Selected time aggregation:<br/>
${start}<br/>
${cluster.total} images, ${duration} bucket<br/>
<button onclick="update_url({tsfrom: ${cluster.min_timestamp - 0.01}, tsto: ${cluster.max_timestamp + 0.01}})">➡️ from &amp; to ⬅️ </button>
<button onclick="update_url({tsfrom: ${cluster.min_timestamp - 0.01}})">➡️ from</button>
<button onclick="update_url({tsto: ${cluster.max_timestamp + 0.01}})">to ⬅️ </button><br/>
<img loading="lazy" src="/img?hsh=${image_md5}&size=preview" class="gallery_image" />
</div>
        `;
                                document.getElementById(tooltip_div).innerHTML =
                                    innerHtml2;
                            },
                        },
                    },
                },
            },
            plugins: [
                {
                    id: "Events",
                    beforeEvent(chart, args, pluginOptions) {
                        const event = args.event;
                        const canvasPosition =
                            Chart.helpers.getRelativePosition(event, chart);
                        const dataX = chart.scales.x.getValueForPixel(
                            canvasPosition.x
                        );
                        const dataY = chart.scales.y.getValueForPixel(
                            canvasPosition.y
                        );
                        if (event.type === "mousedown") {
                            this._clickTimeStart = [canvasPosition.x, dataX];
                        } else if (event.type === "mouseup") {
                            if (
                                Math.abs(
                                    canvasPosition.x - this._clickTimeStart[0]
                                ) > 1
                            ) {
                                const x = [
                                    this._clickTimeStart[1] / 1000.0,
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
                                update_url({ tsfrom: f, tsto: t });
                            }
                        }
                    },
                },
            ],
        });
    }

    fetch(location_url_json) {
        return this.switchable.call_or_store("fetch", () => {
            const tool = document.getElementById(this._tooltip_div);
            if (tool !== null && tool !== undefined) {
                tool.innerHTML = "";
            }
            return fetch("/api/date_clusters", {
                method: "POST",
                body: JSON.stringify({
                    url: location_url_json,
                    buckets: 100,
                }),
                headers: {
                    "Content-type": "application/json; charset=UTF-8",
                },
            })
                .then((response) => response.json())
                .then((clusters) => {
                    function to_datapoint(c) {
                        return {
                            x: c.avg_timestamp * 1000,
                            y: c.total,
                            cluster: c,
                        };
                    }
                    const dates = clusters
                        .filter((c) => c.overfetched == false)
                        .map(to_datapoint);
                    this._chart.data.datasets[0].data = dates;
                    const overfetched = clusters
                        .filter((c) => c.overfetched == true)
                        .map(to_datapoint);
                    this._chart.data.datasets[1].data = overfetched;
                    this._chart.update();
                });
        });
    }
}

class TabSwitch {
    constructor(div_id, callbacks) {
        this._defaults = {};
        this._callbacks = callbacks;
        const element = document.getElementById(div_id);
        const buttons = element.getElementsByTagName("button");
        const ids = [];
        for (var i = 0; i < buttons.length; i++) {
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
            this._defaults[sync_id] = is_active_default;
        }
        this._sync = new UrlSync(ids);
        const url_params = this._sync.get_url();
        const that = this;
        for (var i = 0; i < buttons.length; i++) {
            const button = buttons[i];
            if (!button.classList.contains("tablinks")) {
                continue;
            }
            if (button.id === undefined || button.id === null) {
                console.log("Error, this button should have id", button);
            }
            const sync_id = button.id.replace("TabSource", "Tab");
            const is_active_from_url = url_params[sync_id];
            button.addEventListener("click", function () {
                that.switch_tab_visibility(button);
            });
            this.set_tab_visibility(
                is_active_from_url === undefined || is_active_from_url === null
                    ? this._defaults[sync_id]
                    : is_active_from_url === "true",
                button
            );
        }
    }
    set_tab_visibility(is_active, button) {
        const id = button.id;
        const target_class = id.replace("TabSource", "TabTarget");
        const sync_id = id.replace("TabSource", "Tab");
        const targets = document.getElementsByClassName(target_class);
        const url = this._sync.get_url();
        if (this._defaults[sync_id] === is_active) {
            delete url[sync_id];
        } else {
            url[sync_id] = is_active;
        }
        this._sync.update(url);
        const callback = this._callbacks[sync_id];
        if (is_active) {
            button.classList.add("active");
            for (var i = 0; i < targets.length; i++) {
                targets[i].classList.remove("disabled");
            }
            if (callback !== undefined && callback !== null) {
                callback.enable();
            }
        } else {
            button.classList.remove("active");
            for (var i = 0; i < targets.length; i++) {
                targets[i].classList.add("disabled");
            }
            if (callback !== undefined && callback !== null) {
                callback.disable();
            }
        }
    }
    switch_tab_visibility(button) {
        const is_active = button.classList.contains("active");
        this.set_tab_visibility(!is_active, button);
    }
}

const _PRETTY_DURATIONS = [
    [365 * 86400, "y"],
    [30 * 86400, " mon"],
    [7 * 86400, "w"],
    [86400, "d"],
    [3600, "h"],
    [60, " min"],
    [1, "s"],
];

function pretty_print_duration(duration) {
    var dur = duration;
    let out = [];
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
function pprange(ts1, ts2) {
    const d1 = new Date();
    d1.setTime(ts1 * 1000);
    const d2 = new Date();
    d2.setTime(ts2 * 1000);
    const s1 = d1.toLocaleString();
    let out = [];
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
