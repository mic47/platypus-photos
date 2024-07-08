import { createRoot } from "react-dom/client";
import React from "react";

import data_model from "./data_model.generated.json";

import {
    CheckboxSync,
    TypedUrlSync,
    URLSetSync,
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
    getFixedLocationAnnotationOverlayRequest,
} from "./annotations";
import { DirectoryTableComponent } from "./directories";
import { Switchable, TabBar } from "./jsx/switchable";
import { JobProgressComponent } from "./jobs";
import { SystemStatusComponent } from "./system_status";
import { MapView } from "./map";
import { DatesComponent } from "./dates_chart";

interface ApplicationProps {
    searchQuerySync: TypedUrlSync<SearchQuery>;
    pagingSync: TypedUrlSync<GalleryPaging>;
    sortSync: TypedUrlSync<SortParams>;
    galleryUrlSync: TypedUrlSync<GalleryUrlParams>;
    tabBarSync: URLSetSync;
    checkboxSync: CheckboxSync;
}

export function Application({
    searchQuerySync,
    pagingSync,
    sortSync,
    galleryUrlSync,
    tabBarSync,
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
    React.useEffect(() => sortSync.update(sort), [sort]);
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
    const [activeTabs, updateActiveTabsInternal] = React.useState(() => {
        const tabBarCurrent = tabBarSync.get();
        return Object.fromEntries(
            [
                ["query", "Query ⌨️"],
                ["dates", "Dates Chart 📆📈"],
                ["directories", "Directories 📂"],
                ["map", "Map 🗺️"],
                ["gallery", "Gallery 🖼️"],
                ["jobs", "Job Progress 🏗️"],
                ["system_status", "System Status 🙈"],
            ].map(([key, text]) => [
                key,
                { active: tabBarCurrent.has(key), text },
            ]),
        );
    });
    /* Map related */
    const [zoomTo, updateZoomTo] = React.useState<null | {
        latitude: number;
        longitude: number;
    }>(null);
    return (
        <>
            <TabBar
                items={activeTabs}
                setActive={
                    ((key: string, active: boolean) => {
                        const newTabs = setActiveTab(activeTabs, key, active);
                        updateActiveTabsInternal(newTabs);
                        tabBarSync.update(getActiveTabs(newTabs));
                    }) as (key: string, active: boolean) => void
                }
            />
            <Switchable switchedOn={activeTabs.jobs.active}>
                <JobProgressComponent
                    interval_seconds={10}
                    map_zoom={(latitude, longitude) =>
                        updateZoomTo({ latitude, longitude })
                    }
                />
            </Switchable>
            <Switchable switchedOn={activeTabs.system_status.active}>
                <SystemStatusComponent intervalSeconds={10} />
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
            <Switchable switchedOn={activeTabs.dates.active}>
                <DatesComponent
                    query={searchQueryWithTs.q}
                    queryCallbacks={queryCallbacks}
                />
            </Switchable>
            <Switchable switchedOn={activeTabs.directories.active}>
                <div className="directories">
                    <DirectoryTableComponent
                        query={searchQueryWithTs.q}
                        queryCallbacks={queryCallbacks}
                    />
                </div>
            </Switchable>
            <Switchable switchedOn={activeTabs.map.active}>
                <MapView
                    searchQuery={searchQueryWithTs.q}
                    zoom_to={zoomTo}
                    resetZoomTo={() => updateZoomTo(null)}
                    oneTime={{
                        searchQueryCallbacks: queryCallbacks,
                        annotation_overlay: (
                            searchQuery,
                            latitude,
                            longitude,
                        ) => {
                            getFixedLocationAnnotationOverlayRequest(
                                searchQuery,
                                latitude,
                                longitude,
                            ).then((request) => {
                                updateAnnotationRequest(request);
                            });
                        },
                    }}
                />
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
    const tabBarSync = new URLSetSync(
        "tb",
        new Set(["query", "map", "gallery"]),
    );

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
                tabBarSync={tabBarSync}
                checkboxSync={new CheckboxSync()}
            />
        </React.StrictMode>,
    );
}

type ActiveTabs = { [key: string]: { active: boolean; text: string } };
function getActiveTabs(tabs: ActiveTabs): Set<string> {
    return new Set(
        Object.entries(tabs)
            .map(([key, value]) => {
                if (value.active) {
                    return key;
                }
                return null;
            })
            .filter((value) => value !== null) as string[],
    );
}
function setActiveTab(current: ActiveTabs, key: string, active: boolean) {
    const newTabs = Object.fromEntries(
        Object.entries(current).map(([key, settings]) => [
            key,
            { ...settings },
        ]),
    );
    if (newTabs[key] !== undefined) {
        newTabs[key].active = active;
    }
    return newTabs;
}
