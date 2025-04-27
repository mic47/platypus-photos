import {
    FaceFeaturesForImagePostResponse,
    FacesOnPagePostData,
    FacesOnPagePostResponse,
    GalleryRequest,
    ImagePagePostResponse,
    ManualIdentityAnnotationEndpointPostResponse,
    ManualIdentityClusterRequest_Input,
    TopIdentitiesPostResponse,
} from "./pygallery.generated/types.gen";
import * as pygallery_service from "./pygallery.generated/sdk.gen.ts";

export interface ImageDatabaseInterface {
    fetchImages(requestBody: GalleryRequest): Promise<ImagePagePostResponse>;
}

export interface IdentityDatabaseInterface {
    topIdentities(): Promise<TopIdentitiesPostResponse>;
    faceFeaturesForImage(
        md5: string,
        extension: string,
    ): Promise<FaceFeaturesForImagePostResponse>;
    submitManualAnnotation(
        request: Array<ManualIdentityClusterRequest_Input>,
    ): Promise<ManualIdentityAnnotationEndpointPostResponse>;
    facesOnPage(data: FacesOnPagePostData): Promise<FacesOnPagePostResponse>;
}

export class GalleryBackend
    implements ImageDatabaseInterface, IdentityDatabaseInterface
{
    facesOnPage(data: FacesOnPagePostData): Promise<FacesOnPagePostResponse> {
        return pygallery_service.facesOnPagePost(data);
    }
    submitManualAnnotation(
        request: Array<ManualIdentityClusterRequest_Input>,
    ): Promise<ManualIdentityAnnotationEndpointPostResponse> {
        return pygallery_service.manualIdentityAnnotationEndpointPost({
            requestBody: request,
        });
    }
    topIdentities(): Promise<TopIdentitiesPostResponse> {
        return pygallery_service.topIdentitiesPost();
    }
    faceFeaturesForImage(
        md5: string,
        extension: string,
    ): Promise<FaceFeaturesForImagePostResponse> {
        return pygallery_service.faceFeaturesForImagePost({
            requestBody: { md5: md5, extension: extension },
        });
    }
    fetchImages(requestBody: GalleryRequest): Promise<ImagePagePostResponse> {
        return pygallery_service.imagePagePost({
            requestBody,
        });
    }
}
