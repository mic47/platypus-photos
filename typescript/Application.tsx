import { createRoot } from "react-dom/client";
import React from "react";

import data_model from "./data_model.generated.json";

import {
    CheckboxSync,
    TypedUrlSync,
    parse_gallery_paging,
    parse_search_query,
    parse_sort_params,
} from "./state";
import { GalleryPaging, SearchQuery, SortParams } from "./pygallery.generated";
import { InputFormView, WithTs } from "./input";
import {
    GalleryComponent,
    GalleryUrlParams,
    parse_gallery_url,
} from "./gallery";
import {
    AnnotationOverlayComponent,
    AnnotationOverlayRequest,
} from "./annotations";
import { DirectoryTableComponent } from "./directories";
import { Switchable, TabBar } from "./jsx/switchable";
import { JobProgressComponent } from "./jobs";

interface ApplicationProps {
    searchQuerySync: TypedUrlSync<SearchQuery>;
    pagingSync: TypedUrlSync<GalleryPaging>;
    sortSync: TypedUrlSync<SortParams>;
    galleryUrlSync: TypedUrlSync<GalleryUrlParams>;
    checkboxSync: CheckboxSync;
}

export function Application({
    searchQuerySync,
    pagingSync,
    sortSync,
    galleryUrlSync,
    checkboxSync,
}: ApplicationProps) {
    /* URL Params State */
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
    const [galleryUrl, updateGalleryUrl] = React.useState<GalleryUrlParams>(
        galleryUrlSync.get_parsed(),
    );
    React.useEffect(() => galleryUrlSync.update(galleryUrl), [galleryUrl]);
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
    const galleryUrlCallbacks = {
        update: (update: GalleryUrlParams) => {
            updateGalleryUrl({ ...galleryUrl, ...update });
        },
        replace: (newData: GalleryUrlParams) => {
            updateGalleryUrl({ ...newData });
        },
    };
    /* Annotation Overlay State */
    const [annotationRequest, updateAnnotationRequest] =
        React.useState<null | AnnotationOverlayRequest>(null);
    /* Tabs */
    // TODO: make it in sync with url
    const [activeTabs, updateActiveTabsInternal] = React.useState({
        query: { active: true, text: "Query" },
        dates: { active: false, text: "Dates Chart" },
        directories: { active: false, text: "Directories" },
        map: { active: true, text: "Map" },
        gallery: { active: true, text: "Gallery" },
        jobs: { active: false, text: "Job Progress" },
        system_status: { active: false, text: "System Status" },
    });

    return (
        <>
            <TabBar
                items={activeTabs}
                setActive={
                    ((key: keyof typeof activeTabs, active: boolean) => {
                        const newTabs = { ...activeTabs };
                        if (newTabs[key] !== undefined) {
                            newTabs[key].active = active;
                        }
                        updateActiveTabsInternal(newTabs);
                    }) as (key: string, active: boolean) => void
                }
            />
            <Switchable switchedOn={activeTabs.jobs.active}>
                <JobProgressComponent
                    interval_seconds={10}
                    map_zoom={() => {}}
                />
            </Switchable>
            <Switchable switchedOn={activeTabs.query.active}>
                <InputFormView
                    query={searchQueryWithTs}
                    callbacks={queryCallbacks}
                    submitAnnotations={(request) =>
                        updateAnnotationRequest(request)
                    }
                />
            </Switchable>
            <AnnotationOverlayComponent
                request={annotationRequest}
                queryCallbacks={queryCallbacks}
                pagingCallbacks={pagingCallbacks}
                reset={() => updateAnnotationRequest(null)}
            />
            <Switchable switchedOn={activeTabs.directories.active}>
                <div className="directories">
                    <DirectoryTableComponent
                        query={searchQueryWithTs.q}
                        queryCallbacks={queryCallbacks}
                    />
                </div>
            </Switchable>
            <Switchable switchedOn={activeTabs.gallery.active}>
                <GalleryComponent
                    query={searchQueryWithTs.q}
                    paging={paging}
                    sort={sort}
                    queryCallbacks={queryCallbacks}
                    pagingCallbacks={pagingCallbacks}
                    sortCallbacks={sortCallbacks}
                    checkboxSync={checkboxSync}
                    galleryUrl={galleryUrl}
                    galleryUrlCallbacks={galleryUrlCallbacks}
                    submit_annotations={(request) => {
                        updateAnnotationRequest(request);
                    }}
                />
            </Switchable>
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
    const galleryUrlSync = new TypedUrlSync(["oi"], parse_gallery_url);

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
                galleryUrlSync={galleryUrlSync}
                // TODO: remove checkbox sync passing
                checkboxSync={new CheckboxSync()}
            />
        </React.StrictMode>,
    );
}
