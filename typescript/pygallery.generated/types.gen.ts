// This file is auto-generated by @hey-api/openapi-ts

export type AggregateQuery = {
    query: SearchQuery;
    paging: GalleryPaging;
};

export type AnnotationOverlayFixedLocation = {
    t: 'FixedLocation';
    latitude: number;
    longitude: number;
};

export type t = 'FixedLocation';

export type AnnotationOverlayInterpolateLocation = {
    t: 'InterpolatedLocation';
    location: ManualLocation;
};

export type t2 = 'InterpolatedLocation';

export type AnnotationOverlayNoLocation = {
    t: 'NoLocation';
};

export type t3 = 'NoLocation';

export type AnnotationOverlayRequest = {
    request: AnnotationOverlayFixedLocation | AnnotationOverlayInterpolateLocation | AnnotationOverlayNoLocation;
    query: SearchQuery;
};

export type DateCluster = {
    example_path_md5: string;
    bucket_min: number;
    bucket_max: number;
    overfetched: boolean;
    min_timestamp: number;
    max_timestamp: number;
    avg_timestamp: number;
    total: number;
    group_by: DateClusterGroup;
};

export type DateClusterGroup = {
    address_name: string | null;
    country: string | null;
    camera: string | null;
    has_location: boolean | null;
};

export type DateClusterGroupBy = 'country' | 'camera' | 'has_location' | 'address_name';

export type DateClusterParams = {
    url: SearchQuery;
    group_by: Array<DateClusterGroupBy>;
    buckets: number;
};

export type GalleryPaging = {
    page?: number;
    paging?: number;
};

export type GalleryRequest = {
    query: SearchQuery;
    paging: GalleryPaging;
    sort: SortParams;
    checkboxes: {
        [key: string]: (boolean);
    };
};

export type HTTPValidationError = {
    detail?: Array<ValidationError>;
};

export type ImageSize = 'original' | 'medium' | 'preview';

export type JobListRequest = unknown;

export type JobProgressRequest = {
    update_state_fn: string;
    job_list_fn: string;
    state?: JobProgressState | null;
};

export type JobProgressState = {
    ts: number;
    t_total: number;
    t_finished: number;
    j_total: number;
    j_finished: number;
    j_waiting: number;
};

export type LocClusterParams = {
    tl: LocPoint;
    br: LocPoint;
    url: SearchQuery;
    res: LocPoint;
    of?: number;
};

export type LocPoint = {
    latitude: number;
    longitude: number;
};

export type LocationBounds = {
    nw: LocPoint;
    se: LocPoint;
};

export type LocationCluster = {
    example_path_md5: string;
    example_classification: string | null;
    size: number;
    address_name: string | null;
    address_country: string | null;
    tsfrom: number | null;
    tsto: number | null;
    top_left: LocPoint;
    bottom_right: LocPoint;
    position: LocPoint;
};

export type LocationInfoRequest = {
    latitude: number;
    longitude: number;
};

export type LocationQueryFixedLocation = {
    t: 'FixedLocation';
    location: ManualLocation;
    override: ManualLocationOverride;
};

export type ManualLocation = {
    latitude: number;
    longitude: number;
    address_name: string | null;
    address_country: string | null;
};

export type ManualLocationOverride = 'NoLocNoMan' | 'NoLocYeMan' | 'YeLocNoMan' | 'YeLocYeMan';

export type MapSearchRequest = {
    query?: string | null;
    checkboxes?: {
        [key: string]: (boolean);
    };
};

export type MassLocationAndTextAnnotation = {
    t: 'MassLocAndTxt';
    query: SearchQuery;
    location: LocationQueryFixedLocation | AnnotationOverlayInterpolateLocation | AnnotationOverlayNoLocation;
    text: TextQueryFixedText;
    date: TransDate;
};

export type t4 = 'MassLocAndTxt';

export type SearchQuery = {
    tag?: string;
    cls?: string;
    addr?: string;
    directory?: string;
    camera?: string;
    tsfrom?: number | null;
    tsto?: number | null;
    skip_with_location?: boolean;
    skip_being_annotated?: boolean;
    timestamp_trans?: string | null;
};

export type SortBy = 'TIMESTAMP' | 'RANDOM';

export type SortOrder = 'DESC' | 'ASC';

export type SortParams = {
    sort_by?: SortBy;
    order?: SortOrder;
};

export type TextAnnotation = {
    description: string | null;
    tags: string | null;
};

export type TextAnnotationOverride = 'ExMan' | 'NoMan' | 'YeMan';

export type TextQueryFixedText = {
    t: 'FixedText';
    text: TextAnnotation;
    override: TextAnnotationOverride;
    loc_only: boolean;
};

export type t5 = 'FixedText';

export type TransDate = {
    t: 'TransDate';
    adjust_dates: boolean;
};

export type t6 = 'TransDate';

export type ValidationError = {
    loc: Array<(string | number)>;
    msg: string;
    type: string;
};

export type ImageEndpointGetData = {
    hsh: number | string;
    size?: ImageSize;
};

export type ImageEndpointGetResponse = unknown;

export type LocationClustersEndpointPostData = {
    requestBody: LocClusterParams;
};

export type LocationClustersEndpointPostResponse = Array<LocationCluster>;

export type LocationBoundsEndpointPostData = {
    requestBody: SearchQuery;
};

export type LocationBoundsEndpointPostResponse = LocationBounds | null;

export type DateClustersEndpointPostData = {
    requestBody: DateClusterParams;
};

export type DateClustersEndpointPostResponse = Array<DateCluster>;

export type MassManualAnnotationEndpointPostData = {
    requestBody: MassLocationAndTextAnnotation;
};

export type MassManualAnnotationEndpointPostResponse = number;

export type MapSearchEndpointPostData = {
    requestBody: MapSearchRequest;
};

export type MapSearchEndpointPostResponse = string;

export type JobProgressEndpointPostData = {
    requestBody: JobProgressRequest;
};

export type JobProgressEndpointPostResponse = string;

export type JobListEndpointPostData = {
    requestBody: JobListRequest;
};

export type JobListEndpointPostResponse = string;

export type SystemStatusEndpointPostResponse = string;

export type SubmitAnnotationOverlayFormEndpointPostData = {
    requestBody: AnnotationOverlayRequest;
};

export type SubmitAnnotationOverlayFormEndpointPostResponse = string;

export type FetchLocationInfoEndpointPostData = {
    requestBody: LocationInfoRequest;
};

export type FetchLocationInfoEndpointPostResponse = string;

export type DirectoriesEndpointPostData = {
    requestBody: SearchQuery;
};

export type DirectoriesEndpointPostResponse = string;

export type GalleryDivPostData = {
    oi?: number | null;
    requestBody: GalleryRequest;
};

export type GalleryDivPostResponse = string;

export type AggregateEndpointPostData = {
    requestBody: AggregateQuery;
};

export type AggregateEndpointPostResponse = string;

export type InputRequestPostData = {
    requestBody: SearchQuery;
};

export type InputRequestPostResponse = string;

export type ReadIndexGetResponse = unknown;

export type ReadIndexGet1Response = unknown;

export type $OpenApiTs = {
    '/img': {
        get: {
            req: ImageEndpointGetData;
            res: {
                /**
                 * photo
                 */
                200: unknown;
                /**
                 * Validation Error
                 */
                422: HTTPValidationError;
            };
        };
    };
    '/api/location_clusters': {
        post: {
            req: LocationClustersEndpointPostData;
            res: {
                /**
                 * Successful Response
                 */
                200: Array<LocationCluster>;
                /**
                 * Validation Error
                 */
                422: HTTPValidationError;
            };
        };
    };
    '/api/bounds': {
        post: {
            req: LocationBoundsEndpointPostData;
            res: {
                /**
                 * Successful Response
                 */
                200: LocationBounds | null;
                /**
                 * Validation Error
                 */
                422: HTTPValidationError;
            };
        };
    };
    '/api/date_clusters': {
        post: {
            req: DateClustersEndpointPostData;
            res: {
                /**
                 * Successful Response
                 */
                200: Array<DateCluster>;
                /**
                 * Validation Error
                 */
                422: HTTPValidationError;
            };
        };
    };
    '/api/mass_manual_annotation': {
        post: {
            req: MassManualAnnotationEndpointPostData;
            res: {
                /**
                 * Successful Response
                 */
                200: number;
                /**
                 * Validation Error
                 */
                422: HTTPValidationError;
            };
        };
    };
    '/internal/map_search.html': {
        post: {
            req: MapSearchEndpointPostData;
            res: {
                /**
                 * Successful Response
                 */
                200: string;
                /**
                 * Validation Error
                 */
                422: HTTPValidationError;
            };
        };
    };
    '/internal/job_progress.html': {
        post: {
            req: JobProgressEndpointPostData;
            res: {
                /**
                 * Successful Response
                 */
                200: string;
                /**
                 * Validation Error
                 */
                422: HTTPValidationError;
            };
        };
    };
    '/internal/job_list.html': {
        post: {
            req: JobListEndpointPostData;
            res: {
                /**
                 * Successful Response
                 */
                200: string;
                /**
                 * Validation Error
                 */
                422: HTTPValidationError;
            };
        };
    };
    '/internal/system_status.html': {
        post: {
            res: {
                /**
                 * Successful Response
                 */
                200: string;
            };
        };
    };
    '/internal/submit_annotations_overlay.html': {
        post: {
            req: SubmitAnnotationOverlayFormEndpointPostData;
            res: {
                /**
                 * Successful Response
                 */
                200: string;
                /**
                 * Validation Error
                 */
                422: HTTPValidationError;
            };
        };
    };
    '/internal/fetch_location_info.html': {
        post: {
            req: FetchLocationInfoEndpointPostData;
            res: {
                /**
                 * Successful Response
                 */
                200: string;
                /**
                 * Validation Error
                 */
                422: HTTPValidationError;
            };
        };
    };
    '/internal/directories.html': {
        post: {
            req: DirectoriesEndpointPostData;
            res: {
                /**
                 * Successful Response
                 */
                200: string;
                /**
                 * Validation Error
                 */
                422: HTTPValidationError;
            };
        };
    };
    '/internal/gallery.html': {
        post: {
            req: GalleryDivPostData;
            res: {
                /**
                 * Successful Response
                 */
                200: string;
                /**
                 * Validation Error
                 */
                422: HTTPValidationError;
            };
        };
    };
    '/internal/aggregate.html': {
        post: {
            req: AggregateEndpointPostData;
            res: {
                /**
                 * Successful Response
                 */
                200: string;
                /**
                 * Validation Error
                 */
                422: HTTPValidationError;
            };
        };
    };
    '/internal/input.html': {
        post: {
            req: InputRequestPostData;
            res: {
                /**
                 * Successful Response
                 */
                200: string;
                /**
                 * Validation Error
                 */
                422: HTTPValidationError;
            };
        };
    };
    '/': {
        get: {
            res: {
                /**
                 * Successful Response
                 */
                200: unknown;
            };
        };
    };
    '/index.html': {
        get: {
            res: {
                /**
                 * Successful Response
                 */
                200: unknown;
            };
        };
    };
};