// This file is auto-generated by @hey-api/openapi-ts

import type { CancelablePromise } from './core/CancelablePromise';
import { OpenAPI } from './core/OpenAPI';
import { request as __request } from './core/request';
import type { ImageEndpointGetData, ImageEndpointGetResponse, LocationClustersEndpointPostData, LocationClustersEndpointPostResponse, LocationBoundsEndpointPostData, LocationBoundsEndpointPostResponse, DateClustersEndpointPostData, DateClustersEndpointPostResponse, MassManualAnnotationEndpointPostData, MassManualAnnotationEndpointPostResponse, MapSearchEndpointPostData, MapSearchEndpointPostResponse, JobProgressStatePostData, JobProgressStatePostResponse, RemoteJobsGetResponse, SystemStatusGetResponse, SubmitAnnotationOverlayFormEndpointPostData, SubmitAnnotationOverlayFormEndpointPostResponse, FetchLocationInfoEndpointPostData, FetchLocationInfoEndpointPostResponse, DirectoriesEndpointPostData, DirectoriesEndpointPostResponse, ImagePagePostData, ImagePagePostResponse, GalleryDivPostData, GalleryDivPostResponse, AggregateEndpointPostData, AggregateEndpointPostResponse, ReadIndexGetResponse, ReadIndexGet1Response } from './types.gen';

/**
 * Image Endpoint
 * @param data The data for the request.
 * @param data.hsh
 * @param data.size
 * @returns unknown photo
 * @throws ApiError
 */
export const imageEndpointGet = (data: ImageEndpointGetData): CancelablePromise<ImageEndpointGetResponse> => { return __request(OpenAPI, {
    method: 'GET',
    url: '/img',
    query: {
        hsh: data.hsh,
        size: data.size
    },
    errors: {
        422: 'Validation Error'
    }
}); };

/**
 * Location Clusters Endpoint
 * @param data The data for the request.
 * @param data.requestBody
 * @returns LocationCluster Successful Response
 * @throws ApiError
 */
export const locationClustersEndpointPost = (data: LocationClustersEndpointPostData): CancelablePromise<LocationClustersEndpointPostResponse> => { return __request(OpenAPI, {
    method: 'POST',
    url: '/api/location_clusters',
    body: data.requestBody,
    mediaType: 'application/json',
    errors: {
        422: 'Validation Error'
    }
}); };

/**
 * Location Bounds Endpoint
 * @param data The data for the request.
 * @param data.requestBody
 * @returns unknown Successful Response
 * @throws ApiError
 */
export const locationBoundsEndpointPost = (data: LocationBoundsEndpointPostData): CancelablePromise<LocationBoundsEndpointPostResponse> => { return __request(OpenAPI, {
    method: 'POST',
    url: '/api/bounds',
    body: data.requestBody,
    mediaType: 'application/json',
    errors: {
        422: 'Validation Error'
    }
}); };

/**
 * Date Clusters Endpoint
 * @param data The data for the request.
 * @param data.requestBody
 * @returns DateCluster Successful Response
 * @throws ApiError
 */
export const dateClustersEndpointPost = (data: DateClustersEndpointPostData): CancelablePromise<DateClustersEndpointPostResponse> => { return __request(OpenAPI, {
    method: 'POST',
    url: '/api/date_clusters',
    body: data.requestBody,
    mediaType: 'application/json',
    errors: {
        422: 'Validation Error'
    }
}); };

/**
 * Mass Manual Annotation Endpoint
 * @param data The data for the request.
 * @param data.requestBody
 * @returns number Successful Response
 * @throws ApiError
 */
export const massManualAnnotationEndpointPost = (data: MassManualAnnotationEndpointPostData): CancelablePromise<MassManualAnnotationEndpointPostResponse> => { return __request(OpenAPI, {
    method: 'POST',
    url: '/api/mass_manual_annotation',
    body: data.requestBody,
    mediaType: 'application/json',
    errors: {
        422: 'Validation Error'
    }
}); };

/**
 * Map Search Endpoint
 * @param data The data for the request.
 * @param data.requestBody
 * @returns string Successful Response
 * @throws ApiError
 */
export const mapSearchEndpointPost = (data: MapSearchEndpointPostData): CancelablePromise<MapSearchEndpointPostResponse> => { return __request(OpenAPI, {
    method: 'POST',
    url: '/internal/map_search.html',
    body: data.requestBody,
    mediaType: 'application/json',
    errors: {
        422: 'Validation Error'
    }
}); };

/**
 * Job Progress State
 * @param data The data for the request.
 * @param data.requestBody
 * @returns JobProgressStateResponse Successful Response
 * @throws ApiError
 */
export const jobProgressStatePost = (data: JobProgressStatePostData): CancelablePromise<JobProgressStatePostResponse> => { return __request(OpenAPI, {
    method: 'POST',
    url: '/api/job_progress_state',
    body: data.requestBody,
    mediaType: 'application/json',
    errors: {
        422: 'Validation Error'
    }
}); };

/**
 * Remote Jobs
 * @returns JobDescription Successful Response
 * @throws ApiError
 */
export const remoteJobsGet = (): CancelablePromise<RemoteJobsGetResponse> => { return __request(OpenAPI, {
    method: 'GET',
    url: '/api/remote_jobs'
}); };

/**
 * System Status
 * @returns SystemStatus Successful Response
 * @throws ApiError
 */
export const systemStatusGet = (): CancelablePromise<SystemStatusGetResponse> => { return __request(OpenAPI, {
    method: 'GET',
    url: '/api/system_status'
}); };

/**
 * Submit Annotation Overlay Form Endpoint
 * @param data The data for the request.
 * @param data.requestBody
 * @returns string Successful Response
 * @throws ApiError
 */
export const submitAnnotationOverlayFormEndpointPost = (data: SubmitAnnotationOverlayFormEndpointPostData): CancelablePromise<SubmitAnnotationOverlayFormEndpointPostResponse> => { return __request(OpenAPI, {
    method: 'POST',
    url: '/internal/submit_annotations_overlay.html',
    body: data.requestBody,
    mediaType: 'application/json',
    errors: {
        422: 'Validation Error'
    }
}); };

/**
 * Fetch Location Info Endpoint
 * @param data The data for the request.
 * @param data.requestBody
 * @returns string Successful Response
 * @throws ApiError
 */
export const fetchLocationInfoEndpointPost = (data: FetchLocationInfoEndpointPostData): CancelablePromise<FetchLocationInfoEndpointPostResponse> => { return __request(OpenAPI, {
    method: 'POST',
    url: '/internal/fetch_location_info.html',
    body: data.requestBody,
    mediaType: 'application/json',
    errors: {
        422: 'Validation Error'
    }
}); };

/**
 * Directories Endpoint
 * @param data The data for the request.
 * @param data.requestBody
 * @returns string Successful Response
 * @throws ApiError
 */
export const directoriesEndpointPost = (data: DirectoriesEndpointPostData): CancelablePromise<DirectoriesEndpointPostResponse> => { return __request(OpenAPI, {
    method: 'POST',
    url: '/internal/directories.html',
    body: data.requestBody,
    mediaType: 'application/json',
    errors: {
        422: 'Validation Error'
    }
}); };

/**
 * Image Page
 * @param data The data for the request.
 * @param data.requestBody
 * @returns ImageResponse Successful Response
 * @throws ApiError
 */
export const imagePagePost = (data: ImagePagePostData): CancelablePromise<ImagePagePostResponse> => { return __request(OpenAPI, {
    method: 'POST',
    url: '/api/images',
    body: data.requestBody,
    mediaType: 'application/json',
    errors: {
        422: 'Validation Error'
    }
}); };

/**
 * Gallery Div
 * @param data The data for the request.
 * @param data.requestBody
 * @param data.oi
 * @returns string Successful Response
 * @throws ApiError
 */
export const galleryDivPost = (data: GalleryDivPostData): CancelablePromise<GalleryDivPostResponse> => { return __request(OpenAPI, {
    method: 'POST',
    url: '/internal/gallery.html',
    query: {
        oi: data.oi
    },
    body: data.requestBody,
    mediaType: 'application/json',
    errors: {
        422: 'Validation Error'
    }
}); };

/**
 * Aggregate Endpoint
 * @param data The data for the request.
 * @param data.requestBody
 * @returns string Successful Response
 * @throws ApiError
 */
export const aggregateEndpointPost = (data: AggregateEndpointPostData): CancelablePromise<AggregateEndpointPostResponse> => { return __request(OpenAPI, {
    method: 'POST',
    url: '/internal/aggregate.html',
    body: data.requestBody,
    mediaType: 'application/json',
    errors: {
        422: 'Validation Error'
    }
}); };

/**
 * Read Index
 * @returns unknown Successful Response
 * @throws ApiError
 */
export const readIndexGet = (): CancelablePromise<ReadIndexGetResponse> => { return __request(OpenAPI, {
    method: 'GET',
    url: '/'
}); };

/**
 * Read Index
 * @returns unknown Successful Response
 * @throws ApiError
 */
export const readIndexGet1 = (): CancelablePromise<ReadIndexGet1Response> => { return __request(OpenAPI, {
    method: 'GET',
    url: '/index.html'
}); };