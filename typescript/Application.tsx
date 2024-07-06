import { createRoot } from "react-dom/client";
import React from "react";

import data_model from "./data_model.generated.json";

import {
    CheckboxSync,
    TypedUrlSync,
    UrlSync,
    parse_gallery_paging,
    parse_search_query,
    parse_sort_params,
} from "./state";
import { GalleryPaging, SearchQuery, SortParams } from "./pygallery.generated";
import { InputFormView, WithTs } from "./input";
import { GalleryComponent } from "./gallery";

interface ApplicationProps {
    searchQuerySync: TypedUrlSync<SearchQuery>;
    pagingSync: TypedUrlSync<GalleryPaging>;
    sortSync: TypedUrlSync<SortParams>;
    checkboxSync: CheckboxSync;
}

export function Application({
    searchQuerySync,
    pagingSync,
    sortSync,
    checkboxSync,
}: ApplicationProps) {
    const [searchQueryWithTs, updateSearchQueryWithTs] = React.useState<
        WithTs<SearchQuery>
    >({ q: searchQuerySync.get_parsed(), ts: Date.now() });
    React.useEffect(
        () => searchQuerySync.update(searchQueryWithTs.q),
        [searchQueryWithTs.q],
    );
    const [paging, updatePaging] = React.useState<GalleryPaging>(
        pagingSync.get_parsed(),
    );
    React.useEffect(() => pagingSync.update(paging), [paging]);
    const [sort, updateSort] = React.useState<SortParams>(
        sortSync.get_parsed(),
    );
    React.useEffect(() => sortSync.update(paging), [paging]);
    const queryCallbacks = {
        update: (update: SearchQuery) => {
            updateSearchQueryWithTs({
                q: { ...searchQueryWithTs.q, ...update },
                ts: Date.now(),
            });
        },
        replace: (newState: SearchQuery) =>
            updateSearchQueryWithTs({ q: { ...newState }, ts: Date.now() }),
    };
    const pagingCallbacks = {
        update: (update: GalleryPaging) => {
            updatePaging({ ...paging, ...update });
        },
        replace: (newData: GalleryPaging) => {
            updatePaging({ ...newData });
        },
    };
    const sortCallbacks = {
        update: (update: SortParams) => {
            updateSort({ ...sort, ...update });
        },
        replace: (newData: SortParams) => {
            updateSort({ ...newData });
        },
    };
    const galleryUrlSync = new UrlSync(["oi"]);
    return (
        <>
            <InputFormView
                query={searchQueryWithTs}
                callbacks={queryCallbacks}
                submitAnnotations={() => {}}
            />
            <GalleryComponent
                query={searchQueryWithTs.q}
                paging={paging}
                sort={sort}
                queryCallbacks={queryCallbacks}
                pagingCallbacks={pagingCallbacks}
                sortCallbacks={sortCallbacks}
                checkboxSync={checkboxSync}
                urlSync={galleryUrlSync}
                submit_annotations={() => {}}
            />
        </>
    );
}

export function init_fun(divId: string) {
    const url_parameters_fields = data_model.fields.search_query;
    const paging_fields = data_model.fields.paging;
    const sort_fields = data_model.fields.sort;

    const searchQuerySync = new TypedUrlSync(
        url_parameters_fields,
        parse_search_query,
    );
    const pagingSync = new TypedUrlSync(paging_fields, parse_gallery_paging);
    const sortSync = new TypedUrlSync(sort_fields, parse_sort_params);

    const element = document.getElementById(divId);
    if (element === null) {
        throw new Error(`Unable to find element ${divId}`);
    }
    const root = createRoot(element);
    root.render(
        <React.StrictMode>
            <Application
                searchQuerySync={searchQuerySync}
                pagingSync={pagingSync}
                sortSync={sortSync}
                checkboxSync={new CheckboxSync()}
            />
        </React.StrictMode>,
    );
}
