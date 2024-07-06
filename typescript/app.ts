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

import { SearchQuery } from "./pygallery.generated/types.gen";
import { AnnotationOverlay } from "./annotations";
import { MapSearch } from "./map_search.tsx";

import { init_fun as react_init_fun } from "./Application";

let ___state: AppState;
function update_url(data: SearchQuery) {
    ___state.search_query.update(data);
}

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
    const checkbox_sync = new CheckboxSync();

    /* AnnotationOverlay */
    const annotator = new AnnotationOverlay(
        "SubmitDataOverlay",
        ___state.search_query,
        ___state.paging,
    );
    /* InputForm */
    new InputForm("InputForm", ___state.search_query, (request) =>
        annotator.submitter(request),
    );
    /* Gallery */
    new Gallery(
        "GalleryImages",
        ___state.search_query,
        ___state.paging,
        ___state.sort,
        checkbox_sync,
        (request) => annotator.submitter(request),
    );
    /* Map */
    const map = new PhotoMap("map", false, ___state.search_query, {
        annotation_overlay: (latitude, longitude) =>
            annotator.fixed_location_submitter(latitude, longitude),
    });
    new MapSearch("MapSearch", checkbox_sync, ___state.search_query, map);
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
    const job_progress = new JobProgress(
        "JobProgress",
        (latitude: number, longitude: number) =>
            map.zoom_to(latitude, longitude),
    );
    /* System Status */
    const system_status = new SystemStatus("SystemStatus");
    /* Tab */
    new TabSwitch("RootTabs", {
        TabDirectories: directories.switchable,
        TabJobProgress: job_progress.switchable,
        TabSystemStatus: system_status.switchable,
        TabDates: dates.switchable,
    });
}

const app: object = {
    init_fun,
    react_init_fun,
    update_url,
};
(window as unknown as { APP: object }).APP = app;
