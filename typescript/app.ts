import data_model from "./data_model.generated.json";

import { Dates } from "./dates_chart";
import {
    AppState,
    UrlSync,
    parse_gallery_paging,
    parse_search_query,
    parse_sort_params,
} from "./state.ts";
import { TabSwitch } from "./switchable";

import { SearchQuery } from "./pygallery.generated/types.gen";

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

    /* Trigger redrawing of componentsl */
    // WARNING: here we assume that search_query will update everything
    ___state.paging.replace_no_hook_update(
        parse_gallery_paging(paging_sync.get()),
    );
    // WARNING: here we assume that search_query will update everything
    ___state.sort.replace_no_hook_update(parse_sort_params(sort_sync.get()));
    ___state.search_query.replace(parse_search_query(search_query_sync.get()));

    /* Tab */
    new TabSwitch("RootTabs", {
        TabDates: dates.switchable,
    });
}

const app: object = {
    init_fun,
    react_init_fun,
    update_url,
};
(window as unknown as { APP: object }).APP = app;
