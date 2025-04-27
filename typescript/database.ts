import {
    GalleryRequest,
    ImagePagePostResponse,
} from "./pygallery.generated/types.gen";
import * as pygallery_service from "./pygallery.generated/sdk.gen.ts";

export interface ImageDatabaseInterface {
    fetchImages(requestBody: GalleryRequest): Promise<ImagePagePostResponse>;
}

export class GalleryBackend implements ImageDatabaseInterface {
    fetchImages(requestBody: GalleryRequest): Promise<ImagePagePostResponse> {
        return pygallery_service.imagePagePost({
            requestBody,
        });
    }
}
