import { GenericFetch } from "./generic_fetch.ts";
import { Switchable } from "./switchable.ts";
import * as pygallery_service from "./pygallery.generated/services.gen.ts";

export class SystemStatus extends GenericFetch<object> {
    public switchable: Switchable;
    constructor(div_id: string) {
        super(div_id, pygallery_service.systemStatusEndpointPost);
        this.switchable = new Switchable();
    }

    fetch() {
        this.switchable.call_or_store("fetch", () => {
            return this.fetch_impl({});
        });
    }
}
