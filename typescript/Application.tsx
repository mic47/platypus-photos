import { createRoot } from "react-dom/client";
import React from "react";

import data_model from "./data_model.generated.json";

import {
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
import { FacesComponent } from "./faces";
import { ExportFormComponent } from "./exporter";
import { QueryCallbacks } from "./types";
import { AggregateInfoComponent } from "./aggregate_info";

interface ApplicationProps {
    searchQuerySync: TypedUrlSync<SearchQuery>;
    pagingSync: TypedUrlSync<GalleryPaging>;
    sortSync: TypedUrlSync<SortParams>;
    galleryUrlSync: TypedUrlSync<GalleryUrlParams>;
    tabBarSync: URLSetSync;
}

const checkboxesConfig = {
    ShowMetadataCheck: {
        shortcut: "m",
        activated: false,
    },
    ShowTimeSelectionCheck: {
        shortcut: "t",
        activated: false,
    },
    ShowDiffCheck: {
        shortcut: "d",
        activated: false,
    },
    LocPredCheck: {
        shortcut: "l",
        activated: false,
    },
    ShowFaceMetadata: {
        shortcut: "f",
        activated: false,
    },
};
type ValidCheckboxes = keyof typeof checkboxesConfig;
const checkboxesShortcuts: {
    [shortcut: string]: ValidCheckboxes;
} = Object.fromEntries(
    Object.entries(checkboxesConfig).map(([key, value]) => {
        return [value.shortcut, key as ValidCheckboxes];
    }),
);

export function Application({
    searchQuerySync,
    pagingSync,
    sortSync,
    galleryUrlSync,
    tabBarSync,
}: ApplicationProps) {
    /* URL Params State */
    const [searchQueryWithTs, updateSearchQueryWithTs] = React.useState<
        WithTs<SearchQuery>
    >({ q: searchQuerySync.get_parsed(), ts: Date.now() });
    React.useEffect(
        () => searchQuerySync.update(searchQueryWithTs.q),
        [searchQueryWithTs.q],
    );
    const paging = React.useState<GalleryPaging>(pagingSync.get_parsed())[0];
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
    const updateQueryCallbacks: QueryCallbacks = {
        update_url: (update: SearchQuery) => {
            queryCallbacks.update(update);
        },
        update_url_add_tag: (tag: string) => {
            const old_tag = searchQueryWithTs.q["tag"];
            if (old_tag === undefined || old_tag === null) {
                queryCallbacks.update({ tag: tag });
            } else {
                queryCallbacks.update({ tag: `${old_tag},${tag}` });
            }
        },
        update_url_add_identity: (identity: string) => {
            const old_identity = searchQueryWithTs.q["identity"];
            if (old_identity === undefined || old_identity === null) {
                queryCallbacks.update({ identity: identity });
            } else {
                queryCallbacks.update({
                    identity: `${old_identity},${identity}`,
                });
            }
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
                ["stats", "Stats 📊"],
                ["dates", "Dates Chart 📆📈"],
                ["directories", "Directories 📂"],
                ["map", "Map 🗺️"],
                ["faces", "Faces 🤓"],
                ["gallery", "Gallery 🖼️"],
                ["export", "Export 💾"],
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

    const [checkboxes, updateCheckboxes] = React.useState<{
        [cb: string]: boolean;
    }>(
        Object.fromEntries(
            Object.entries(checkboxesConfig).map(([key, value]) => {
                return [key, value.activated];
            }),
        ),
    );
    function flipCheckbox(checkbox: string | undefined) {
        if (checkbox === undefined) {
            return;
        }
        const value = (checkboxes as { [name: string]: boolean })[checkbox];
        if (value === undefined) {
            return;
        }
        const newc = { ...checkboxes };
        newc[checkbox] = !value;
        updateCheckboxes(newc);
    }
    function updateCheckboxFromMouseEvent(
        event: React.MouseEvent<HTMLInputElement, MouseEvent>,
    ) {
        const element = event.currentTarget;
        const newc = { ...checkboxes };
        newc[element.id] = element.checked;
        updateCheckboxes(newc);
    }
    React.useEffect(() => {
        const handleKeyPress = (e: KeyboardEvent) => {
            if (
                e.target !== null &&
                e.target instanceof HTMLElement &&
                e.target.tagName === "INPUT"
            ) {
                return;
            }
            const checkbox = checkboxesShortcuts[e.key];
            if (checkbox === undefined) {
                return;
            }
            flipCheckbox(checkbox);
        };

        document.addEventListener("keydown", handleKeyPress);
        return () => document.removeEventListener("keydown", handleKeyPress);
    }, [checkboxes]);

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
            <Switchable switchedOn={activeTabs.export.active}>
                <ExportFormComponent query={searchQueryWithTs.q} />
            </Switchable>
            <Switchable switchedOn={activeTabs.query.active}>
                <InputFormView
                    query={searchQueryWithTs}
                    sort={sort}
                    callbacks={queryCallbacks}
                    sortCallbacks={sortCallbacks}
                    submitAnnotations={(request) =>
                        updateAnnotationRequest(request)
                    }
                />
            </Switchable>
            <AnnotationOverlayComponent
                request={annotationRequest}
                queryCallbacks={queryCallbacks}
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
            <Switchable switchedOn={activeTabs.faces.active}>
                <FacesComponent
                    query={searchQueryWithTs.q}
                    paging={paging}
                    sort={sort}
                />
            </Switchable>
            <Switchable switchedOn={activeTabs.stats.active}>
                <AggregateInfoComponent
                    query={searchQueryWithTs.q}
                    callbacks={updateQueryCallbacks}
                />
            </Switchable>
            <Switchable switchedOn={activeTabs.gallery.active}>
                <GalleryComponent
                    query={searchQueryWithTs.q}
                    paging={paging}
                    sort={sort}
                    queryCallbacks={updateQueryCallbacks}
                    checkboxes={checkboxes}
                    galleryUrl={galleryUrl}
                    galleryUrlCallbacks={galleryUrlCallbacks}
                    submit_annotations={(request) => {
                        updateAnnotationRequest(request);
                    }}
                >
                    <input
                        type="checkbox"
                        id="ShowTimeSelectionCheck"
                        checked={checkboxes["ShowTimeSelection"]}
                        onClick={updateCheckboxFromMouseEvent}
                    />
                    Show Time Selection
                    <input
                        type="checkbox"
                        id="ShowDiffCheck"
                        checked={checkboxes["ShowDiffCheck"]}
                        onClick={updateCheckboxFromMouseEvent}
                    />
                    Show Diff
                    <input
                        type="checkbox"
                        id="ShowMetadataCheck"
                        checked={checkboxes["ShowMetadataCheck"]}
                        onClick={updateCheckboxFromMouseEvent}
                    />
                    Show Metadata
                    <input
                        type="checkbox"
                        id="LocPredCheck"
                        checked={checkboxes["LocPredCheck"]}
                        onClick={updateCheckboxFromMouseEvent}
                    />
                    Show Location Interpolation
                    <input
                        type="checkbox"
                        id="ShowFaceMetadata"
                        checked={checkboxes["ShowFaceMetadata"]}
                        onClick={updateCheckboxFromMouseEvent}
                    />
                    Show Faces
                </GalleryComponent>
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
    const tabBarSync = new URLSetSync("tb", new Set(["gallery"]));

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
