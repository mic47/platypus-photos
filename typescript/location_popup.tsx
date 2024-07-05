import React from "react";

import { ImageAddress } from "./pygallery.generated/types.gen";

export function LocalMarkerLocationPopup({
    id,
    marker,
    callbacks,
}: {
    id: string;
    marker: {
        latitude: number;
        longitude: number;
        text: string;
    };
    callbacks: {
        annotation_overlay: (latitude: number, longitude: number) => void;
        delete_marker: (id: string) => void;
    };
}) {
    return (
        <>
            {marker.text}
            <br />
            <input
                type="button"
                value="Use this location for selected photos"
                onClick={() =>
                    callbacks.annotation_overlay(
                        marker.latitude,
                        marker.longitude,
                    )
                }
            />
            <br />
            <input
                type="button"
                value="Delete this marker"
                onClick={() => callbacks.delete_marker(id)}
            />
        </>
    );
}

export function LocationPopup({
    latitude,
    longitude,
    address,
    callbacks,
}: {
    latitude: number;
    longitude: number;
    address: ImageAddress;
    callbacks: {
        annotation_overlay: (latitude: number, longitude: number) => void;
        add_point_to_map: (
            latitude: number,
            longitude: number,
            text: string | null,
        ) => void;
        close_popup: () => void;
    };
}) {
    return (
        <>
            <b>Address:</b> {address.full}
            <br />
            <b>Name:</b> {address.name}
            <br />
            <b>Country:</b> {address.country}
            <br />
            <b>Latitude:</b> {latitude}
            <br />
            <b>Longitude:</b> {longitude}
            <br />
            <input
                type="button"
                value="Use this location for selected photos"
                onClick={() =>
                    callbacks.annotation_overlay(latitude, longitude)
                }
            />
            <br />
            <input
                type="button"
                value="Add temporary marker"
                onClick={() => {
                    callbacks.add_point_to_map(
                        latitude,
                        longitude,
                        address.full,
                    );
                    callbacks.close_popup();
                }}
            />
        </>
    );
}
