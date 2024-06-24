import { SearchQueryParams } from "./state.ts";

export class InputForm {
    constructor(private div_id: string) {
        this.div_id = div_id;
    }

    fetch(url_data: SearchQueryParams) {
        const url = `/internal/input.html`;
        fetch(url, {
            method: "POST",
            body: JSON.stringify(url_data),
            headers: {
                "Content-type": "application/json; charset=UTF-8",
            },
        })
            .then((response) => response.text())
            .then((text) => {
                const gallery = document.getElementById(this.div_id);
                if (gallery === null) {
                    throw Error(`Unable to find element ${this.div_id}`);
                }
                gallery.innerHTML = text;
            });
    }
}
