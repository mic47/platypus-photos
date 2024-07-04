import {
    AnnotationOverlayInterpolateLocation,
    AnnotationOverlayNoLocation,
    LocationQueryFixedLocation,
} from "./pygallery.generated/types.gen.ts";

export type LocationTypes =
    | LocationQueryFixedLocation
    | AnnotationOverlayInterpolateLocation
    | AnnotationOverlayNoLocation;
