class AppState {
    constructor(url_params, paging) {
        this._url_params = url_params;
        this._url_params_hooks = [];

        this._paging = paging;
        this._paging_hooks = [];
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

function update_boundary(nw, se) {
    var input = document.getElementById("fbnd");
    if (input === null || input === undefined) {
        return;
    }
    const fac = 1000000;
    input.innerHTML = JSON.stringify({
        tl: {
            latitude: Math.round(nw.lat * fac) / fac,
            longitude: Math.round(nw.lng * fac) / fac,
        },
        br: {
            latitude: Math.round(se.lat * fac) / fac,
            longitude: Math.round(se.lng * fac) / fac,
        },
    });
}

class PhotoMap {
    constructor(div_id, bounds, get_url, context_menu_callback) {
        this.map = L.map(div_id).setView([51.505, -0.09], 13);
        this.markers = {};
        this.last_update_timestamp = 0;
        this._context_menu_callback = context_menu_callback;
        const that = this;
        const update_markers = (e) => {
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
        if (bounds !== undefined && bounds !== null) {
            this.map.fitBounds(bounds);
        }
    }

    context_menu(e) {
        this._context_menu_callback(e.latlng, (content) => {
            return L.popup()
                .setLatLng(e.latlng)
                .setContent(content)
                .openOn(this.map);
        });
    }

    update_markers(location_url_json, change_view = false) {
        // TODO: wrapped maps: shift from 0 + wrap around

        var bounds = this.map.getBounds();
        var nw = bounds.getNorthWest();
        var se = bounds.getSouthEast();
        update_boundary(nw, se);
        var sz = this.map.getSize();
        var cluster_pixel_size = 10;
        var timestamp = new Date().getTime();
        fetch("/api/location_clusters", {
            method: "POST",
            body: JSON.stringify({
                tl: {
                    latitude: nw.lat,
                    longitude: nw.lng,
                },
                br: {
                    latitude: se.lat,
                    longitude: se.lng,
                },
                res: {
                    latitude: sz.y / cluster_pixel_size,
                    longitude: sz.x / cluster_pixel_size,
                },
                of: 0.5,
                url: Object.fromEntries(
                    Object.entries(location_url_json).filter(
                        (x) => x[0] !== "page" && x[0] !== "paging"
                    )
                ),
            }),
            headers: {
                "Content-type": "application/json; charset=UTF-8",
            },
        })
            .then((response) => response.json())
            .then((clusters) => {
                if (timestamp < this.last_update_timestamp) {
                    return;
                }
                if (change_view && clusters.length > 0) {
                    const lats = clusters.map((x) => x.position.latitude);
                    const longs = clusters.map((x) => x.position.longitude);
                    var bounds = [
                        [Math.max(...lats), Math.max(...longs)],
                        [Math.min(...lats), Math.min(...longs)],
                    ];
                    this.map.fitBounds(bounds);
                    bounds = this.map.getBounds();
                    var nw = bounds.getNorthWest();
                    var se = bounds.getSouthEast();
                    update_boundary(nw, se);
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

class Directories {
    constructor(div_id) {
        this._div_id = div_id;
    }

    fetch(url_data) {
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

    fetch(url_data) {
        const url = `/internal/aggregate.html`;
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

function submit_annotations(div_id, form_id, return_id) {
    const formData = new FormData(document.getElementById(form_id));
    const query = JSON.parse(window.atob(formData.get("query_json_base64")));
    const latitude = parse_float_or_null(formData.get("latitude"));
    if (latitude === null) {
        alert("Invalid request, latitude", formData);
        return;
    }
    const longitude = parse_float_or_null(formData.get("longitude"));
    if (longitude === null) {
        alert("Invalid request, latitude", formData);
        return;
    }
    const location_override = formData.get("location_override");
    let address_name = null_if_empty(formData.get("address_name"));
    const address_name_original = formData.get("address_name_original");
    if (address_name === null || address_name.trim() === address_name_original) {
        address_name = null;
    }
    let address_country = null_if_empty(formData.get("address_country"));
    const address_country_original = formData.get("address_country_original");
    if (address_country === null || address_country.trim() === address_country_original) {
        address_country = null;
    }
    const location_request = {
        latitude,
        longitude,
        address_name,
        address_country,
        override: location_override,
    };
    const extra_tags = null_if_empty(formData.get("extra_tags"));
    const extra_description = null_if_empty(formData.get("extra_description"));
    const text_override = formData.get("text_override");
    const text_request = {
        tags: extra_tags,
        description: extra_description,
        override: text_override,
    };
    const checkbox_value = formData.get("sanity_check");
    const request = {
        query,
        location: location_request,
        text: text_request,
    };
    if (checkbox_value !== "on") {
        alert("You have to check 'Check this box' box to prevent accidental submissions");
        return;
    }
    console.log(request);
    return fetch("api/mass_manual_annotation", {
        method: "POST",
        body: JSON.stringify(request),
        headers: {
            "Content-type": "application/json; charset=UTF-8",
        },
    })
        .then((response) => response.json())
        .then((response) => {
            alert(JSON.stringify(response));
        })
        // TODO: put error into stuff
        .catch(err => alert(err))
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

    fetch(url_data, paging) {
        var url = `/internal/gallery.html?oi=${this._oi}`;
        if (this._oi === undefined || this._oi === null) {
            url = `/internal/gallery.html`;
        }
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
    constructor(div_id, update_url) {
        this._clickTimeStart = null;
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
                                x.sort();
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
        fetch("/api/date_clusters", {
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
                const dates = clusters
                    .filter((c) => c.overfetched == false)
                    .map((c) => {
                        return { x: c.avg_timestamp * 1000, y: c.total };
                    });
                this._chart.data.datasets[0].data = dates;
                const overfetched = clusters
                    .filter((c) => c.overfetched == true)
                    .map((c) => {
                        return { x: c.avg_timestamp * 1000, y: c.total };
                    });
                this._chart.data.datasets[1].data = overfetched;
                this._chart.update();
            });
    }
}
