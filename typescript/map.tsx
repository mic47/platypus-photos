import React from "react";

import { PhotoMap } from "./photo_map";
import { MapSearchView } from "./map_search";
import { SearchQuery } from "./pygallery.generated/types.gen";
import { UpdateCallbacks } from "./types";

interface MapViewProps {
    searchQuery: SearchQuery;
    zoom_to: null | { latitude: number; longitude: number };
    oneTime: {
        searchQueryCallbacks: UpdateCallbacks<SearchQuery>;
        annotation_overlay: (latitude: number, longitude: number) => void;
    };
}

export function MapView({ searchQuery, zoom_to, oneTime }: MapViewProps) {
    const mapContainerElementRef = React.useRef<null | HTMLDivElement>(null);
    const mapRef = React.useRef<null | PhotoMap>(null);

    const getMap = (): PhotoMap => {
        if (mapRef.current === null) {
            mapRef.current = new PhotoMap(
                mapContainerElementRef.current as HTMLElement,
                false,
                searchQuery,
                oneTime.searchQueryCallbacks,
                {
                    annotation_overlay: oneTime.annotation_overlay,
                },
            );
        }
        return mapRef.current;
    };
    // Note it's not ok to call get map here, use it only on callbacks, effects
    React.useEffect(() => {
        getMap().setSearchQuery(searchQuery);
        getMap().update_markers(searchQuery, true);
    }, [searchQuery]);
    React.useEffect(() => {
        if (zoom_to !== null) {
            getMap().zoom_to(zoom_to.latitude, zoom_to.longitude);
        }
    }, [zoom_to]);
    const [mapUseQuery, updateMapUseQuery] = React.useState<boolean>(false);
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
            <div className="map" ref={mapContainerElementRef} />
        </div>
    );
}
