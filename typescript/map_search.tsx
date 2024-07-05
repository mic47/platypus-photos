import { createRoot, Root } from "react-dom/client";
import React from "react";

import { FoundLocation, SearchQuery } from "./pygallery.generated/types.gen";
import * as pygallery_service from "./pygallery.generated/services.gen.ts";
import { CheckboxSync, StateWithHooks } from "./state.ts";
import { PhotoMap } from "./photo_map.ts";

export class MapSearch {
    private root: Root;
    constructor(
        private div_id: string,
        checkboxes: CheckboxSync,
        searchQueryHook: StateWithHooks<SearchQuery>,
        map: PhotoMap,
    ) {
        const element = document.getElementById(this.div_id);
        if (element === null) {
            throw new Error(`Unable to find element ${this.div_id}`);
        }
        this.root = createRoot(element);
        this.root.render(
            <MapSearchView
                checkboxes={checkboxes.get()}
                callbacks={{
                    map_bounds: () => {
                        map.update_bounds(searchQueryHook.get());
                    },
                    map_refetch: () => {
                        map.update_markers(searchQueryHook.get(), false);
                    },
                    map_zoom: (latitude: number, longitude: number) => {
                        map.map.flyTo([latitude, longitude], 13, {
                            duration: 1,
                        });
                    },
                    update_checkbox: (element: HTMLInputElement) => {
                        checkboxes.update_from_element(element);
                    },
                }}
            />,
        );
    }
}
export function MapSearchView({
    checkboxes,
    callbacks,
}: {
    checkboxes: { [x: string]: boolean };
    callbacks: {
        map_bounds: () => void;
        map_refetch: () => void;
        map_zoom: (latitude: number, longitude: number) => void;
        update_checkbox: (element: HTMLInputElement) => void;
    };
}) {
    const [error, updateError] = React.useState<null | string>(null);
    const [data, updateData] = React.useState<null | FoundLocation[]>(null);
    const [query, updateQuery] = React.useState<string>("");
    const [pending, updatePending] = React.useState<boolean>(false);
    React.useEffect(() => {
        let ignore = false;
        if (query === "") {
            return;
        }
        updatePending(true);
        pygallery_service
            .findLocationPost({
                req: query,
            })
            .then((data) => {
                if (!ignore) {
                    updateError(data.error);
                    updateData(data.response);
                    updatePending(false);
                }
            });
        return () => {
            ignore = true;
        };
    }, [query]);
    let searchResult = null;
    if (data !== null || error !== null || pending) {
        searchResult = (
            <div className="search_result">
                {pending ? (
                    <>
                        (pending)
                        <br />
                    </>
                ) : null}
                {(data || []).map((loc, index) => {
                    return (
                        <>
                            <a
                                key={index}
                                onClick={() => {
                                    callbacks.map_zoom(
                                        loc.latitude,
                                        loc.longitude,
                                    );
                                }}
                                href="#"
                            >
                                {loc.address}
                            </a>
                            <br />
                        </>
                    );
                })}
            </div>
        );
    }
    return (
        <>
            <form
                id="MapSearchId"
                method="dialog"
                onSubmit={(event) => {
                    let data = new FormData(event.currentTarget).get("query");
                    if (data === null) {
                        data = "";
                    }
                    updateQuery(data.toString());
                    console.log("search", data, event);
                }}
            >
                <input type="text" name="query" />
                <input
                    type="button"
                    onClick={() => callbacks.map_bounds()}
                    value="Zoom to query"
                />
                <input
                    type="checkbox"
                    id="MapUseQuery"
                    defaultChecked={checkboxes["MapUseQuery"] || false}
                    onChange={(event) => {
                        console.log(
                            event,
                            event.currentTarget,
                            event.currentTarget.checked,
                        );
                        callbacks.update_checkbox(event.currentTarget);
                        callbacks.map_refetch();
                    }}
                />
                Map uses query
            </form>
            {searchResult}
            {error === null ? null : <pre>{error}</pre>}
        </>
    );
}
