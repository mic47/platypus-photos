import { GenericFetch } from "./generic_fetch.ts";
import { Switchable } from "./switchable.ts";

export class SystemStatus extends GenericFetch<object> {
    public switchable: Switchable;
    constructor(div_id: string) {
        super(div_id, "/internal/system_status.html");
        this.switchable = new Switchable();
    }

    fetch() {
        this.switchable.call_or_store("fetch", () => {
            return this.fetch_impl({});
        });
    }
}
