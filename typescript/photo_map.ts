import { createRoot } from "react-dom/client";
import { flushSync } from "react-dom";

import * as L from "leaflet";

import { SearchQuery } from "./pygallery.generated/types.gen.ts";
import * as pygallery_service from "./pygallery.generated/services.gen.ts";
import {
    LocalMarkerLocationPopup,
    LocationClusterPopup,
    LocationPopup,
} from "./location_popup.tsx";
import { LocalStorageState } from "./local_storage_state.ts";
import { UpdateCallbacks } from "./types.ts";

type Position = {
    latitude: number;
    longitude: number;
};
type Bounds = {
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

type Marker = {
    latitude: number;
    longitude: number;
    text: string;
};

export class PhotoMap {
    public map: L.Map;
    private last_update_markers: LastUpdateMarkersCacheParam | null = null;
    private last_update_timestamp: number = 0;
    private markers: { [id: string]: L.Marker };
    private local_markers: { [id: string]: L.Marker };
    private localStorageMarkers: LocalStorageState<Marker>;
    constructor(
        div_id: string | HTMLElement,
        private should_use_query: boolean,
        private searchQuery: SearchQuery,
        private searchQueryCallbacks: UpdateCallbacks<SearchQuery>,
        private callbacks: {
            annotation_overlay: (
                query: SearchQuery,
                latitude: number,
                longitude: number,
            ) => void;
        },
    ) {
        this.map = L.map(div_id).fitWorld();
        L.control.scale({ imperial: false }).addTo(this.map);
        this.markers = {};
        this.local_markers = {};
        this.localStorageMarkers = new LocalStorageState("markers", {
            item_was_added: (id: string, item: Marker) => {
                this.add_local_marker_callback(id, item);
            },
            item_was_removed: (id: string) => {
                this.delete_local_marker_callback(id);
            },
        });
        const update_markers: L.LeafletEventHandlerFn = (e) => {
            if ((e as unknown as { flyTo: boolean }).flyTo) {
                return;
            }
            this.update_markers(this.searchQuery, false);
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
        this.map.on("contextmenu", context_menu);

        L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
            maxZoom: 19,
            attribution:
                '&copy; <a href="http://www.openstreetmap.org/copyright">OpenStreetMap</a>',
        }).addTo(this.map);
        this.update_bounds(this.searchQuery, true);
    }
    setSearchQuery(query: SearchQuery) {
        this.searchQuery = query;
    }
    set_should_use_query(should_use: boolean) {
        this.should_use_query = should_use;
    }

    private delete_local_marker_callback(id: string) {
        const marker = this.local_markers[id];
        if (marker !== undefined && marker !== null) {
            marker.remove();
            delete this.local_markers[id];
        }
    }
    private add_local_marker_callback(id: string, item: Marker) {
        const marker = L.marker([item.latitude, item.longitude], {
            alt: "Ad-hoc marker: " + item.text,
            title: "Ad-hoc marker: " + item.text,
            opacity: 0.7,
        }).addTo(this.map);
        const element = document.createElement("div");
        const root = createRoot(element);
        flushSync(() => {
            root.render(
                LocalMarkerLocationPopup({
                    id,
                    marker: item,
                    callbacks: {
                        annotation_overlay: (
                            latitude: number,
                            longitude: number,
                        ) =>
                            this.callbacks.annotation_overlay(
                                this.searchQuery,
                                latitude,
                                longitude,
                            ),
                        delete_marker: (id: string) =>
                            this.localStorageMarkers.remove(id),
                    },
                }),
            );
        });
        marker.bindPopup(element);
        this.local_markers[id] = marker;
    }

    private context_menu(e: L.LocationEvent) {
        const loc = e.latlng;
        const existing = document.getElementById("LocPreview");
        if (existing !== undefined && existing !== null) {
            existing.remove();
        }
        pygallery_service
            .getAddressPost({
                requestBody: { latitude: loc.lat, longitude: loc.lng },
            })
            .then((address) => {
                const element = document.createElement("div");
                const root = createRoot(element);
                flushSync(() => {
                    root.render(
                        LocationPopup({
                            latitude: loc.lat,
                            longitude: loc.lng,
                            address,
                            callbacks: {
                                annotation_overlay: (
                                    latitude: number,
                                    longitude: number,
                                ) =>
                                    this.callbacks.annotation_overlay(
                                        this.searchQuery,
                                        latitude,
                                        longitude,
                                    ),
                                add_point_to_map: (
                                    latitude: number,
                                    longitude: number,
                                    text: string | null,
                                ) =>
                                    this.localStorageMarkers.add({
                                        latitude,
                                        longitude,
                                        text: text || "Unknown location",
                                    }),
                                close_popup: () => {
                                    this.map.closePopup();
                                },
                            },
                        }),
                    );
                });
                const popup = L.popup()
                    .setLatLng(loc)
                    .setContent(element)
                    .openOn(this.map) as unknown as {
                    _updateLayout: () => void;
                };
                popup._updateLayout();
            });
    }

    update_bounds(location_url_json: SearchQuery, fit_not_fly = false) {
        const query = {
            ...location_url_json,
            skip_with_location: false,
            skip_being_annotated: false,
        };
        pygallery_service
            .locationBoundsEndpointPost({ requestBody: query })
            .then((bounds) => {
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

    private _similar(
        last_bounds: Bounds,
        new_bounds: Bounds,
        tolerance: number,
    ) {
        if (last_bounds === undefined || last_bounds === null) {
            return false;
        }
        const lat_tolerance =
            Math.abs(last_bounds.nw.latitude - last_bounds.se.latitude) *
            tolerance;
        const lon_tolerance =
            Math.abs(last_bounds.nw.longitude - last_bounds.se.longitude) *
            tolerance;
        return (
            Math.abs(last_bounds.nw.latitude - new_bounds.nw.latitude) <
                lat_tolerance &&
            Math.abs(last_bounds.nw.longitude - new_bounds.nw.longitude) <
                lon_tolerance &&
            Math.abs(last_bounds.se.latitude - new_bounds.se.latitude) <
                lat_tolerance &&
            Math.abs(last_bounds.se.longitude - new_bounds.se.longitude) <
                lon_tolerance
        );
    }
    private _should_skip(params: LastUpdateMarkersCacheParam) {
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

    // TODO: this should be just update markers
    update_markers(location_url_json: SearchQuery, change_view = false) {
        // TODO: wrapped maps: shift from 0 + wrap around
        const should_use_query = this.should_use_query;

        const bounds = this.map.getBounds();
        const nw = bounds.getNorthWest();
        const se = bounds.getSouthEast();
        const sz = this.map.getSize();
        const cluster_pixel_size = 10;
        const timestamp = new Date().getTime();
        const bounds_query: Bounds = {
            nw: {
                latitude: nw.lat,
                longitude: nw.lng,
            },
            se: {
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
        pygallery_service
            .locationClustersEndpointPost({ requestBody: query_final })
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
                    const element = document.createElement("div");
                    const root = createRoot(element);
                    flushSync(() => {
                        root.render(
                            LocationClusterPopup({
                                cluster,
                                callbacks: {
                                    update_url: (update) =>
                                        this.searchQueryCallbacks.update(
                                            update,
                                        ),
                                    annotation_overlay: (
                                        latitude: number,
                                        longitude: number,
                                    ) =>
                                        this.callbacks.annotation_overlay(
                                            this.searchQuery,
                                            latitude,
                                            longitude,
                                        ),
                                },
                            }),
                        );
                    });
                    marker.bindPopup(element);
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
    zoom_to(latitude: number, longitude: number) {
        this.map.flyTo([latitude, longitude], 13, { duration: 1 });
    }
}
