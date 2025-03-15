import React from "react";

import { FoundLocation } from "./pygallery.generated/types.gen";
import * as pygallery_service from "./pygallery.generated/sdk.gen.ts";

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
        <div>
            <form
                id="MapSearchId"
                method="dialog"
                onSubmit={(event) => {
                    let data = new FormData(event.currentTarget).get("query");
                    if (data === null) {
                        data = "";
                    }
                    updateQuery(data.toString());
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
                        callbacks.update_checkbox(event.currentTarget);
                        callbacks.map_refetch();
                    }}
                />
                Map uses query
            </form>
            {searchResult}
            {error === null ? null : <pre>{error}</pre>}
        </div>
    );
}
