import React from "react";

import { PhotoMap } from "./photo_map";
import { MapSearchView } from "./map_search";
import { SearchQuery } from "./pygallery.generated/types.gen";
import { StateWithHooks } from "./state";

interface MapViewProps {
    searchQuery: SearchQuery;
    zoom_to: null | { latitude: number; longitude: number };
    oneTime: {
        searchQueryHook: StateWithHooks<SearchQuery>;
        annotation_overlay: (latitude: number, longitude: number) => void;
    };
}

// Dependencies from react
// searchQueryHook -> input, output
// should_use_query_div -> input
// annotation overlay -> output
// map.zoomto -> input from jobProgress -- event
// map -> update bounds, markers, zoom_to, -- input like event from MapSearch
export function MapView({ searchQuery, zoom_to, oneTime }: MapViewProps) {
    const mapContainerElementRef = React.useRef<null | HTMLDivElement>(null);
    const mapRef = React.useRef<null | PhotoMap>(null);
    const [mapUseQuery, updateMapUseQuery] = React.useState<boolean>(false);

    const getMap = (): PhotoMap => {
        if (mapRef.current === null) {
            console.log(mapContainerElementRef.current);
            mapRef.current = new PhotoMap(
                mapContainerElementRef.current as HTMLElement,
                false,
                oneTime.searchQueryHook,
                {
                    annotation_overlay: oneTime.annotation_overlay,
                },
            );
        }
        return mapRef.current;
    };
    getMap(); // It's ok to initialize map on first render
    React.useEffect(() => {
        // It would be cleaner to have setSearchQuery interface, instead of hooks fetching
        getMap().update_markers(searchQuery, true);
    }, [searchQuery]);
    React.useEffect(() => {
        if (zoom_to !== null) {
            getMap().zoom_to(zoom_to.latitude, zoom_to.longitude);
        }
    }, [zoom_to]);
    return (
        <div className="TabTargetMap">
            <MapSearchView
                checkboxes={{ MapUseQuery: mapUseQuery }}
                callbacks={{
                    map_bounds: () => {
                        getMap().update_bounds(searchQuery);
                    },
                    map_refetch: () => {
                        getMap().update_markers(searchQuery, false);
                    },
                    map_zoom: (latitude: number, longitude: number) => {
                        getMap().zoom_to(latitude, longitude);
                    },
                    update_checkbox: (element: HTMLInputElement) => {
                        getMap().set_should_use_query(element.checked);
                        updateMapUseQuery(element.checked);
                    },
                }}
            />
            <div ref={mapContainerElementRef} />
        </div>
    );
}
