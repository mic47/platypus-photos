import * as L from "leaflet";

import { CheckboxesParams } from "./state.ts";
import { pprange } from "./utils.ts";
import { GenericFetch } from "./generic_fetch.ts";
import { SearchQuery } from "./pygallery.generated/types.gen.ts";

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
        url: SearchQuery;
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
        get_url: () => SearchQuery,
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

    update_bounds(location_url_json: SearchQuery, fit_not_fly = false) {
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

    update_markers(location_url_json: SearchQuery, change_view = false) {
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

export class MapSearch extends GenericFetch<{
    query: string | null;
    checkboxes: CheckboxesParams;
}> {
    constructor(div_id: string) {
        super(div_id, "/internal/map_search.html");
    }
    fetch(search_str: string | null, checkboxes: CheckboxesParams) {
        return this.fetch_impl({ query: search_str, checkboxes });
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

export type ManualLocation = {
    latitude: number;
    longitude: number;
    address_name: string | null;
    address_country: string | null;
};
type AnnotationOverlayRequest =
    | {
          t: "FixedLocation";
          latitude: number;
          longitude: number;
      }
    | {
          t: "InterpolatedLocation";
          location: ManualLocation;
      }
    | {
          t: "NoLocation";
      };

export class AnnotationOverlay extends GenericFetch<{
    request: AnnotationOverlayRequest;
    query: SearchQuery;
}> {
    constructor(div_id: string) {
        super(div_id, "/internal/submit_annotations_overlay.html");
    }
    fetch(request: AnnotationOverlayRequest, query: SearchQuery) {
        console.log(request);
        return this.fetch_impl({
            request,
            query,
        });
    }
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
