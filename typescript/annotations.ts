import { SearchQueryParams } from "./state.ts";

type TextAnnotation = {
    description: string | null;
    tags: string | null;
};

type ManualLocation = {
    latitude: number;
    longitude: number;
    address_name: string | null;
    address_country: string | null;
};

export type TextOverride = "ExMan" | "NoMan" | "YeMan";
type TextQueryFixedText = {
    t: "FixedText";
    text: TextAnnotation;
    override: TextOverride;
    loc_only: boolean;
};

type TransDate = {
    t: "TransDate";
    adjust_dates: boolean;
};

type AnnotationOverlayInterpolateLocation = {
    t: "InterpolatedLocation";
    location: ManualLocation;
};

export type LocationOverride =
    | "NoLocNoMan"
    | "NoLocYeMan"
    | "YeLocNoMan"
    | "YeLocYeMan";
type LocationQueryFixedLocation = {
    t: "FixedLocation";
    location: ManualLocation;
    override: "NoLocNoMan" | "NoLocYeMan" | "YeLocNoMan" | "YeLocYeMan";
};

export type LocationTypes =
    | LocationQueryFixedLocation
    | AnnotationOverlayInterpolateLocation;
type TextTypes = TextQueryFixedText;
type DateTypes = TransDate;

export type MassLocationAndTextAnnotation = {
    t: "MassLocAndTxt";
    query: SearchQueryParams;
    location: LocationTypes;
    text: TextTypes;
    date: DateTypes;
};
