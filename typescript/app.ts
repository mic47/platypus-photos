import data_model from "./data_model.generated.json";

import { Dates } from "./dates_chart";
import { Gallery } from "./gallery";
import { InputForm } from "./input";
import { Marker, PhotoMap } from "./photo_map";
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
import { LocalStorageState } from "./local_storage_state.ts";

let ___state: AppState;
function update_url(data: SearchQuery) {
    ___state.search_query.update(data);
}
let ___local_storage_markers: LocalStorageState<Marker>;

function delete_marker(id: string) {
    ___local_storage_markers.remove(id);
}

function map_add_point(latitude: number, longitude: number, text: string) {
    ___local_storage_markers.add({ latitude, longitude, text });
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
    const map = new PhotoMap(
        "map",
        "MapUseQuery",
        () => ___state.search_query.get(),
        { annotation_overlay, add_point_to_map: map_add_point, delete_marker },
    );
    new MapSearch("MapSearch", ___checkbox_sync, ___state.search_query, map);
    ___state.search_query.register_hook("MasSearch", (url_params) => {
        map.update_markers(url_params, true);
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
    const job_progress = new JobProgress("JobProgress", map.zoom_to);
    /* System Status */
    const system_status = new SystemStatus("SystemStatus");
    /* Tab */
    new TabSwitch("RootTabs", {
        TabDirectories: directories.switchable,
        TabJobProgress: job_progress.switchable,
        TabSystemStatus: system_status.switchable,
        TabDates: dates.switchable,
    });

    ___local_storage_markers = new LocalStorageState<Marker>("markers", {
        item_was_added: (id: string, item: Marker) => {
            map.add_local_marker(id, item);
        },
        item_was_removed: (id: string) => {
            map.delete_local_marker(id);
        },
    });
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
