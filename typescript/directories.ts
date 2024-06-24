import { SearchQueryParams } from "./state.ts";
import { Switchable } from "./switchable.ts";

export class Directories {
    public switchable: Switchable;
    constructor(private div_id: string) {
        this.switchable = new Switchable();
    }

    fetch(url_data: SearchQueryParams) {
        return this.switchable.call_or_store("fetch", () =>
            this.fetch_impl(url_data),
        );
    }

    fetch_impl(url_data: SearchQueryParams) {
        const url = `/internal/directories.html`;
        fetch(url, {
            method: "POST",
            body: JSON.stringify(url_data),
            headers: {
                "Content-type": "application/json; charset=UTF-8",
            },
        })
            .then((response) => response.text())
            .then((text) => {
                const element = document.getElementById(this.div_id);
                if (element === null) {
                    throw new Error(`Unable to find element ${this.div_id}`);
                }
                element.innerHTML = text;
            });
    }
}
