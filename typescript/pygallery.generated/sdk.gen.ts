// This file is auto-generated by @hey-api/openapi-ts

import type { CancelablePromise } from './core/CancelablePromise';
import { OpenAPI } from './core/OpenAPI';
import { request as __request } from './core/request';
import type { ConfigExportDirsEndpointGetResponse, ExportPhotosGetData, ExportPhotosGetResponse, ExportPhotosToDirGetData, ExportPhotosToDirGetResponse, ImageEndpointGetData, ImageEndpointGetResponse, LocationClustersEndpointPostData, LocationClustersEndpointPostResponse, LocationBoundsEndpointPostData, LocationBoundsEndpointPostResponse, DateClustersEndpointPostData, DateClustersEndpointPostResponse, MassManualAnnotationEndpointPostData, MassManualAnnotationEndpointPostResponse, ManualIdentityAnnotationEndpointPostData, ManualIdentityAnnotationEndpointPostResponse, FindLocationPostData, FindLocationPostResponse, JobProgressStatePostData, JobProgressStatePostResponse, RemoteJobsGetResponse, SystemStatusGetResponse, GetAddressPostData, GetAddressPostResponse, MatchingDirectoriesPostData, MatchingDirectoriesPostResponse, ImagePagePostData, ImagePagePostResponse, TopIdentitiesPostResponse, FacesOnPagePostData, FacesOnPagePostResponse, FaceFeaturesForImagePostData, FaceFeaturesForImagePostResponse, AggregateImagesPostData, AggregateImagesPostResponse, ReadIndexGetResponse, ReadIndexGet1Response } from './types.gen';

/**
 * Config Export Dirs Endpoint
 * @returns string Successful Response
 * @throws ApiError
 */
export const configExportDirsEndpointGet = (): CancelablePromise<ConfigExportDirsEndpointGetResponse> => {
    return __request(OpenAPI, {
        method: 'GET',
        url: '/api/config_export_dirs'
    });
};

/**
 * Export Photos
 * @param data The data for the request.
 * @param data.query
 * @returns unknown tar file with selected photos
 * @throws ApiError
 */
export const exportPhotosGet = (data: ExportPhotosGetData): CancelablePromise<ExportPhotosGetResponse> => {
    return __request(OpenAPI, {
        method: 'GET',
        url: '/export',
        query: {
            query: data.query
        },
        errors: {
            422: 'Validation Error'
        }
    });
};

/**
 * Export Photos To Dir
 * @param data The data for the request.
 * @param data.query
 * @param data.base
 * @param data.subdir
 * @returns unknown txt file with list of copied files
 * @throws ApiError
 */
export const exportPhotosToDirGet = (data: ExportPhotosToDirGetData): CancelablePromise<ExportPhotosToDirGetResponse> => {
    return __request(OpenAPI, {
        method: 'GET',
        url: '/export_to_dir',
        query: {
            query: data.query,
            base: data.base,
            subdir: data.subdir
        },
        errors: {
            422: 'Validation Error'
        }
    });
};

/**
 * Image Endpoint
 * @param data The data for the request.
 * @param data.hsh
 * @param data.size
 * @param data.extension
 * @param data.position
 * @param data.frame
 * @returns unknown photo
 * @throws ApiError
 */
export const imageEndpointGet = (data: ImageEndpointGetData): CancelablePromise<ImageEndpointGetResponse> => {
    return __request(OpenAPI, {
        method: 'GET',
        url: '/img/{size}/{hsh}.{extension}',
        path: {
            hsh: data.hsh,
            size: data.size,
            extension: data.extension
        },
        query: {
            position: data.position,
            frame: data.frame
        },
        errors: {
            422: 'Validation Error'
        }
    });
};

/**
 * Location Clusters Endpoint
 * @param data The data for the request.
 * @param data.requestBody
 * @returns LocationCluster Successful Response
 * @throws ApiError
 */
export const locationClustersEndpointPost = (data: LocationClustersEndpointPostData): CancelablePromise<LocationClustersEndpointPostResponse> => {
    return __request(OpenAPI, {
        method: 'POST',
        url: '/api/location_clusters',
        body: data.requestBody,
        mediaType: 'application/json',
        errors: {
            422: 'Validation Error'
        }
    });
};

/**
 * Location Bounds Endpoint
 * @param data The data for the request.
 * @param data.requestBody
 * @returns unknown Successful Response
 * @throws ApiError
 */
export const locationBoundsEndpointPost = (data: LocationBoundsEndpointPostData): CancelablePromise<LocationBoundsEndpointPostResponse> => {
    return __request(OpenAPI, {
        method: 'POST',
        url: '/api/bounds',
        body: data.requestBody,
        mediaType: 'application/json',
        errors: {
            422: 'Validation Error'
        }
    });
};

/**
 * Date Clusters Endpoint
 * @param data The data for the request.
 * @param data.requestBody
 * @returns DateCluster Successful Response
 * @throws ApiError
 */
export const dateClustersEndpointPost = (data: DateClustersEndpointPostData): CancelablePromise<DateClustersEndpointPostResponse> => {
    return __request(OpenAPI, {
        method: 'POST',
        url: '/api/date_clusters',
        body: data.requestBody,
        mediaType: 'application/json',
        errors: {
            422: 'Validation Error'
        }
    });
};

/**
 * Mass Manual Annotation Endpoint
 * @param data The data for the request.
 * @param data.requestBody
 * @returns number Successful Response
 * @throws ApiError
 */
export const massManualAnnotationEndpointPost = (data: MassManualAnnotationEndpointPostData): CancelablePromise<MassManualAnnotationEndpointPostResponse> => {
    return __request(OpenAPI, {
        method: 'POST',
        url: '/api/mass_manual_annotation',
        body: data.requestBody,
        mediaType: 'application/json',
        errors: {
            422: 'Validation Error'
        }
    });
};

/**
 * Manual Identity Annotation Endpoint
 * @param data The data for the request.
 * @param data.requestBody
 * @returns number Successful Response
 * @throws ApiError
 */
export const manualIdentityAnnotationEndpointPost = (data: ManualIdentityAnnotationEndpointPostData): CancelablePromise<ManualIdentityAnnotationEndpointPostResponse> => {
    return __request(OpenAPI, {
        method: 'POST',
        url: '/api/manual_identity_annotation',
        body: data.requestBody,
        mediaType: 'application/json',
        errors: {
            422: 'Validation Error'
        }
    });
};

/**
 * Find Location
 * @param data The data for the request.
 * @param data.req
 * @returns MapSearchResponse Successful Response
 * @throws ApiError
 */
export const findLocationPost = (data: FindLocationPostData): CancelablePromise<FindLocationPostResponse> => {
    return __request(OpenAPI, {
        method: 'POST',
        url: '/api/map_search',
        query: {
            req: data.req
        },
        errors: {
            422: 'Validation Error'
        }
    });
};

/**
 * Job Progress State
 * @param data The data for the request.
 * @param data.requestBody
 * @returns JobProgressStateResponse Successful Response
 * @throws ApiError
 */
export const jobProgressStatePost = (data: JobProgressStatePostData): CancelablePromise<JobProgressStatePostResponse> => {
    return __request(OpenAPI, {
        method: 'POST',
        url: '/api/job_progress_state',
        body: data.requestBody,
        mediaType: 'application/json',
        errors: {
            422: 'Validation Error'
        }
    });
};

/**
 * Remote Jobs
 * @returns JobDescription Successful Response
 * @throws ApiError
 */
export const remoteJobsGet = (): CancelablePromise<RemoteJobsGetResponse> => {
    return __request(OpenAPI, {
        method: 'GET',
        url: '/api/remote_jobs'
    });
};

/**
 * System Status
 * @returns SystemStatus Successful Response
 * @throws ApiError
 */
export const systemStatusGet = (): CancelablePromise<SystemStatusGetResponse> => {
    return __request(OpenAPI, {
        method: 'GET',
        url: '/api/system_status'
    });
};

/**
 * Get Address
 * @param data The data for the request.
 * @param data.requestBody
 * @returns ImageAddress Successful Response
 * @throws ApiError
 */
export const getAddressPost = (data: GetAddressPostData): CancelablePromise<GetAddressPostResponse> => {
    return __request(OpenAPI, {
        method: 'POST',
        url: '/api/get_address',
        body: data.requestBody,
        mediaType: 'application/json',
        errors: {
            422: 'Validation Error'
        }
    });
};

/**
 * Matching Directories
 * @param data The data for the request.
 * @param data.requestBody
 * @returns DirectoryStats Successful Response
 * @throws ApiError
 */
export const matchingDirectoriesPost = (data: MatchingDirectoriesPostData): CancelablePromise<MatchingDirectoriesPostResponse> => {
    return __request(OpenAPI, {
        method: 'POST',
        url: '/api/directories',
        body: data.requestBody,
        mediaType: 'application/json',
        errors: {
            422: 'Validation Error'
        }
    });
};

/**
 * Image Page
 * @param data The data for the request.
 * @param data.requestBody
 * @returns ImageResponse Successful Response
 * @throws ApiError
 */
export const imagePagePost = (data: ImagePagePostData): CancelablePromise<ImagePagePostResponse> => {
    return __request(OpenAPI, {
        method: 'POST',
        url: '/api/images',
        body: data.requestBody,
        mediaType: 'application/json',
        errors: {
            422: 'Validation Error'
        }
    });
};

/**
 * Top Identities
 * @returns IdentityRowPayload Successful Response
 * @throws ApiError
 */
export const topIdentitiesPost = (): CancelablePromise<TopIdentitiesPostResponse> => {
    return __request(OpenAPI, {
        method: 'POST',
        url: '/api/top_identities'
    });
};

/**
 * Faces On Page
 * @param data The data for the request.
 * @param data.requestBody
 * @returns FacesResponse Successful Response
 * @throws ApiError
 */
export const facesOnPagePost = (data: FacesOnPagePostData): CancelablePromise<FacesOnPagePostResponse> => {
    return __request(OpenAPI, {
        method: 'POST',
        url: '/api/faces',
        body: data.requestBody,
        mediaType: 'application/json',
        errors: {
            422: 'Validation Error'
        }
    });
};

/**
 * Face Features For Image
 * @param data The data for the request.
 * @param data.requestBody
 * @returns FaceWithMeta Successful Response
 * @throws ApiError
 */
export const faceFeaturesForImagePost = (data: FaceFeaturesForImagePostData): CancelablePromise<FaceFeaturesForImagePostResponse> => {
    return __request(OpenAPI, {
        method: 'POST',
        url: '/api/face',
        body: data.requestBody,
        mediaType: 'application/json',
        errors: {
            422: 'Validation Error'
        }
    });
};

/**
 * Aggregate Images
 * @param data The data for the request.
 * @param data.requestBody
 * @returns ImageAggregation Successful Response
 * @throws ApiError
 */
export const aggregateImagesPost = (data: AggregateImagesPostData): CancelablePromise<AggregateImagesPostResponse> => {
    return __request(OpenAPI, {
        method: 'POST',
        url: '/api/aggregate',
        body: data.requestBody,
        mediaType: 'application/json',
        errors: {
            422: 'Validation Error'
        }
    });
};

/**
 * Read Index
 * @returns unknown Successful Response
 * @throws ApiError
 */
export const readIndexGet = (): CancelablePromise<ReadIndexGetResponse> => {
    return __request(OpenAPI, {
        method: 'GET',
        url: '/'
    });
};

/**
 * Read Index
 * @returns unknown Successful Response
 * @throws ApiError
 */
export const readIndexGet1 = (): CancelablePromise<ReadIndexGet1Response> => {
    return __request(OpenAPI, {
        method: 'GET',
        url: '/index.html'
    });
};