import React from "react";

import { AggregateInfoView } from "./aggregate_info.tsx";
import { GalleryImage } from "./gallery_image.tsx";
import {
    AnnotationOverlayInterpolateLocation,
    AnnotationOverlayNoLocation,
    DirectoryStats,
    ImageAggregation,
    ImageResponse,
    ImageWithMeta,
    LocationQueryFixedLocation,
    ManualLocationOverride,
    MassLocationAndTextAnnotation_Input,
    SearchQuery,
    TextAnnotationOverride,
} from "./pygallery.generated/types.gen.ts";
import { impissible, noop, null_if_empty } from "./utils.ts";
import * as pygallery_service from "./pygallery.generated/sdk.gen.ts";
import { shift_float_params } from "./input.tsx";
import { DirectoryTable } from "./directories.tsx";
import { UpdateCallbacks } from "./types.ts";

export type AnnotationOverlayFixedLocation = {
    t: "FixedLocation";
    latitude: number;
    longitude: number;
    address_name: string | null;
    address_country: string | null;
};

export type AnnotationOverlayRequest = {
    request:
        | AnnotationOverlayFixedLocation
        | AnnotationOverlayInterpolateLocation
        | AnnotationOverlayNoLocation;
    query: SearchQuery;
};

export type LocationTypes =
    | LocationQueryFixedLocation
    | AnnotationOverlayInterpolateLocation
    | AnnotationOverlayNoLocation;

export function getFixedLocationAnnotationOverlayRequest(
    query: SearchQuery,
    latitude: number,
    longitude: number,
): Promise<AnnotationOverlayRequest> {
    return pygallery_service
        .getAddressPost({ requestBody: { latitude, longitude } })
        .catch((reason) => {
            console.log(reason);
            return { country: null, name: null, full: null };
        })
        .then((address) => {
            return {
                request: {
                    t: "FixedLocation",
                    latitude,
                    longitude,
                    address_name: address.name,
                    address_country: address.country,
                },
                query,
            };
        });
}
interface AnnotationOverlayComponentProps {
    request: null | AnnotationOverlayRequest;
    queryCallbacks: UpdateCallbacks<SearchQuery>;
    reset: () => void;
}

export function AnnotationOverlayComponent({
    request,
    queryCallbacks,
    reset,
}: AnnotationOverlayComponentProps) {
    const [images, updateImages] = React.useState<null | ImageResponse>(null);
    const [aggr, updateAggr] = React.useState<null | ImageAggregation>(null);
    const [directories, updateDirectories] = React.useState<
        null | DirectoryStats[]
    >(null);
    const [error, updateError] = React.useState<null | ERROR>(null);
    const paging = {}; // Using default

    const resetData = () => {
        updateImages(null);
        updateAggr(null);
        updateDirectories(null);
        updateError(null);
    };
    const resetAll = () => {
        resetData();
        reset();
    };
    // TODO: solve out of date info -- maybe some incremental counter for version
    React.useEffect(() => {
        let ignore = false;
        if (request === null) {
            resetData();
            return;
        }
        pygallery_service
            .imagePagePost({
                requestBody: {
                    query: request.query,
                    paging,
                    sort: { sort_by: "RANDOM" },
                },
            })
            .then((data) => {
                if (!ignore) {
                    updateImages(data);
                }
            });
        return () => {
            ignore = true;
        };
    }, [request]);
    React.useEffect(() => {
        let ignore = false;
        if (request === null) {
            resetData();
            return;
        }
        pygallery_service
            .aggregateImagesPost({
                requestBody: { query: request.query },
            })
            .then((data) => {
                if (!ignore) {
                    updateAggr(data);
                }
            });
        return () => {
            ignore = true;
        };
    }, [request]);
    React.useEffect(() => {
        let ignore = false;
        if (request === null) {
            resetData();
            return;
        }
        pygallery_service
            .matchingDirectoriesPost({ requestBody: request.query })
            .then((data) => {
                if (!ignore) {
                    updateDirectories(data);
                }
            });
        return () => {
            ignore = true;
        };
    }, [request]);

    if (request === null) {
        return null;
    }

    return (
        <AnnotationOverlayView
            request={request}
            images={images === null ? null : images.omgs}
            aggr={aggr}
            directories={directories}
            error={error}
            callbacks={{
                close: () => resetAll(),
                submit: (
                    form: HTMLFormElement,
                    request: AnnotationOverlayRequest,
                    advance_in_time: number | null,
                ) => {
                    validate_form_and_send_request_to_server(form, request)
                        .then(() => {
                            if (
                                advance_in_time !== undefined &&
                                advance_in_time !== null
                            ) {
                                shift_float_params(
                                    request.query,
                                    queryCallbacks,
                                    "tsfrom",
                                    "tsto",
                                    advance_in_time,
                                );
                            }
                            resetAll();
                        })
                        .catch((error) => {
                            updateError(error);
                        });
                },
            }}
        />
    );
}

interface AnnotationOverlayViewProps {
    request: AnnotationOverlayRequest;
    images: ImageWithMeta[] | null;
    aggr: ImageAggregation | null;
    directories: DirectoryStats[] | null;
    error: ERROR | null;
    callbacks: {
        close: () => void;
        submit: (
            form: HTMLFormElement,
            request: AnnotationOverlayRequest,
            advance_in_time: number | null,
        ) => void;
    };
}

function AnnotationOverlayView({
    request,
    images,
    aggr,
    directories,
    error,
    callbacks: { close, submit },
}: AnnotationOverlayViewProps) {
    const disabled = images === null || aggr === null || directories === null;
    let interpolationCheckbox = null;
    if (request.request.t === "InterpolatedLocation") {
        interpolationCheckbox = (
            <>
                <input type="checkbox" name="text_loc_only" checked={true} />
                Apply text annotation only when applying location
                <br />
            </>
        );
    }
    let queryTransformationForm = null;
    if (
        request.query.timestamp_trans !== null &&
        request.query.timestamp_trans !== undefined &&
        request.query.timestamp_trans !== ""
    ) {
        queryTransformationForm = (
            <>
                <h3>Time transformation</h3>
                There seems to be following timestamp transformation:{" "}
                {request.query.timestamp_trans}
                <br />
                <input type="checkbox" name="apply_timestamp_trans" checked />
                Apply time transformation on photos where it made difference
            </>
        );
    }
    const exampleImages =
        images === null
            ? "(loading)"
            : images.map(({ omg, paths }) => (
                  <GalleryImage
                      key={omg.md5}
                      image={{
                          omg,
                          paths,
                          media_class: null,
                          predicted_location: null,
                      }}
                      sort={{ order: "ASC", sort_by: "RANDOM" }}
                      previous_timestamp={null}
                      isOverlay={false}
                      showLocationIterpolation={false}
                      callbacks={null}
                  />
              ));
    return (
        <div className="submit_overlay" id="submit_overlay">
            <h2>Going to annotate {aggr?.total || "(loading)"} photos </h2>
            {disabled ? <h3>Data is loading, submitting is disabled</h3> : null}
            <div className="annotation_scrollable_area">
                <ErrorBox error={error} />
                <form
                    onSubmit={() => {}}
                    method="dialog"
                    id="SubmitAnnotations"
                >
                    <LocationFormPart request={request.request} />
                    {queryTransformationForm}
                    <h3>Annotation Info</h3>
                    {interpolationCheckbox}
                    <b>How to override text info?</b>
                    <select name="text_override">
                        <option value="ExMan">Extend manual annotations</option>
                        <option value="NoMan">
                            Override images wihout manual annotation
                        </option>
                        <option value="YeMan">
                            Override even manual annotations
                        </option>
                    </select>
                    <br />
                    <b>Extra tags:</b>
                    <input type="text" name="extra_tags" defaultValue="" />
                    <br />
                    <b>Extra description:</b>
                    <input
                        type="text"
                        name="extra_description"
                        defaultValue=""
                    />
                    <br />
                    <input
                        type="checkbox"
                        className="uncheck"
                        name="sanity_check"
                    />
                    Check this box
                    <br />
                    <input
                        type="button"
                        value="Add"
                        onClick={(event) => {
                            if (disabled) return;
                            submit(
                                event.currentTarget
                                    .parentElement as HTMLFormElement,
                                request,
                                null,
                            );
                        }}
                    />
                    <input
                        type="button"
                        value="Add, fwd in time, end +1d"
                        onClick={(event) => {
                            if (disabled) return;
                            submit(
                                event.currentTarget
                                    .parentElement as HTMLFormElement,
                                request,
                                24 * 60 * 60,
                            );
                        }}
                    />
                    <input
                        type="button"
                        value="Add, fwd in time, end +1w"
                        onClick={(event) => {
                            if (disabled) return;
                            submit(
                                event.currentTarget
                                    .parentElement as HTMLFormElement,
                                request,
                                7 * 24 * 60 * 60,
                            );
                        }}
                    />
                    <input
                        type="button"
                        value="cancel"
                        onClick={() => close()}
                    />
                </form>

                <h2>Summary of selection</h2>
                <h3>Stats</h3>
                {aggr === null ? (
                    "(loading)"
                ) : (
                    <AggregateInfoView
                        aggr={aggr}
                        show_links={false}
                        callbacks={{
                            update_url_add_tag: noop,
                            update_url_add_identity: noop,
                            update_url: noop,
                        }}
                    />
                )}
                <h3>Directories:</h3>
                {directories === null ? (
                    "(loading)"
                ) : (
                    <DirectoryTable
                        directories={directories}
                        callbacks={null}
                    />
                )}
                <h3>Raw selection</h3>
                <pre>{JSON.stringify(request.query)}</pre>
                <h2>Sample of photos</h2>
                {exampleImages}
            </div>
        </div>
    );
}

function LocationFormPart({
    request,
}: {
    request: AnnotationOverlayRequest["request"];
}) {
    if (request.t === "FixedLocation") {
        return (
            <>
                <h3>Fixed Location Info</h3>
                <b>How to override location?</b>
                <select name="location_override">
                    <option value="NoLocNoMan">
                        Override images without location and manual annotation
                    </option>
                    <option value="NoLocYeMan">
                        Override images without location, even with manual
                        annotation
                    </option>
                    <option value="YeLocNoMan">
                        Override images without manual annotation
                    </option>
                    <option value="YeLocYeMan">
                        Override all selected images
                    </option>
                </select>
                <br />
                <b>Address:</b>{" "}
                {[request.address_name, request.address_country]
                    .filter((x) => x !== null)
                    .join(", ")}
                <br />
                <b>Name:</b>
                <input
                    type="text"
                    name="address_name"
                    defaultValue={request.address_name || ""}
                />
                <br />
                <b>Country:</b>
                <input
                    type="text"
                    name="address_country"
                    defaultValue={request.address_country || ""}
                />
                <br />
                <b>Latitude:</b> {request.latitude}
                <br />
                <b>Longitude:</b> {request.longitude}
                <br />
            </>
        );
    } else if (request.t === "InterpolatedLocation") {
        return (
            <>
                <h3>Interpolated Location Info</h3>
                This will interpolate only for photos that does not have
                location information. All photos in selection will be annotated.
                There is no sanity check for long distances or times. Change the
                query if you don&apos;t like which photos are being annotated.
                <br />
                Following address will be used to identify job in UI (this is
                random address from the selection).
                <br />
                <b>Name:</b> {request.location.address_name}
                <br />
                <b>Country:</b> {request.location.address_country}
                <br />
                <b>Latitude:</b> {request.location.latitude}
                <br />
                <b>Longitude:</b> {request.location.longitude}
                <br />
            </>
        );
    } else if (request.t === "NoLocation") {
        return <h3>No location will be assigned</h3>;
    } else {
        impissible(request);
    }
}

function resolve_address(
    str_original: string | null,
    str_provided: string | null,
): string | null {
    str_original = null_if_empty(str_original);
    if (str_provided === null || str_provided.trim() === str_original) {
        return str_original;
    }
    return str_provided;
}

function validate_form_and_send_request_to_server(
    formElement: HTMLFormElement,
    og_request: AnnotationOverlayRequest,
): Promise<number> {
    const formData = new FormData(formElement as HTMLFormElement);

    const checkbox_value = formData.get("sanity_check");
    [...formElement.getElementsByClassName("uncheck")].forEach((element) => {
        // Prevent from accidentally submitting again
        (element as HTMLInputElement).checked = false;
    });
    let location: LocationTypes;
    if (og_request.request.t == "NoLocation") {
        location = {
            t: og_request.request.t,
        };
    } else {
        const location_override = formData.get("location_override");
        const address_name = (original: string | null) =>
            resolve_address(
                original,
                null_if_empty(formData.get("address_name")),
            );
        const address_country = (original: string | null) =>
            resolve_address(
                original,
                null_if_empty(formData.get("address_country")),
            );
        if (og_request.request.t == "FixedLocation") {
            location = {
                t: og_request.request.t,
                location: {
                    address_name: address_name(og_request.request.address_name),
                    address_country: address_country(
                        og_request.request.address_country,
                    ),
                    latitude: og_request.request.latitude,
                    longitude: og_request.request.longitude,
                },
                override: (location_override ??
                    "NoLocNoMan") as ManualLocationOverride,
            };
        } else if (og_request.request.t == "InterpolatedLocation") {
            location = {
                t: og_request.request.t,
                location: {
                    address_name: address_name(
                        og_request.request.location.address_name,
                    ),
                    address_country: address_country(
                        og_request.request.location.address_country,
                    ),
                    latitude: og_request.request.location.latitude,
                    longitude: og_request.request.location.longitude,
                },
            };
        } else {
            impissible(og_request.request);
        }
    }
    const extra_tags = null_if_empty(formData.get("extra_tags"));
    const extra_description = null_if_empty(formData.get("extra_description"));
    const text_override = formData.get("text_override");
    const text_request = {
        tags: extra_tags,
        description: extra_description,
    };
    const loc_only = formData.get("text_loc_only") == "on";
    const adjust_dates = formData.get("apply_timestamp_trans") == "on";
    const request: MassLocationAndTextAnnotation_Input = {
        t: "MassLocAndTxt",
        query: og_request.query,
        location,
        text: {
            t: "FixedText",
            text: text_request,
            override: (text_override ?? "ExMan") as TextAnnotationOverride,
            loc_only,
        },
        date: {
            t: "TransDate",
            adjust_dates,
        },
    };
    if (checkbox_value !== "on") {
        return Promise.reject({
            error: "You have to check 'Check this box' box to prevent accidental submissions",
        });
    }
    return pygallery_service.massManualAnnotationEndpointPost({
        requestBody: request,
    }).promise;
}

type ERROR = string | number | object;
function ErrorBox({ error }: { error: ERROR | null }) {
    if (error === null) {
        return null;
    }
    console.log(error);
    let content = null;
    try {
        content = JSON.stringify(error, null, 2);
    } catch {
        content = error.toString();
    }
    return (
        <div className="error">
            <pre>{content}</pre>
        </div>
    );
}
