import { SearchQuery } from "./pygallery.generated/types.gen";
import * as pygallery_service from "./pygallery.generated/services.gen.ts";

export class InputForm {
    constructor(private div_id: string) {
        this.div_id = div_id;
    }

    fetch(url_data: SearchQuery) {
        pygallery_service
            .inputRequestPost({ requestBody: url_data })
            .then((text) => {
                const gallery = document.getElementById(this.div_id);
                if (gallery === null) {
                    throw Error(`Unable to find element ${this.div_id}`);
                }
                gallery.innerHTML = text;
            });
    }
}
