export class GenericFetch<T> {
    constructor(
        protected readonly div_id: string,
        private endpoint: string,
    ) {}

    fetch_impl(request: T): Promise<void> {
        return fetch(this.endpoint, {
            method: "POST",
            body: JSON.stringify(request),
            headers: {
                "Content-type": "application/json; charset=UTF-8",
            },
        })
            .then((response) => response.text())
            .then((text) => {
                const element = document.getElementById(this.div_id);
                if (element === null) {
                    throw Error(`Unable to find element ${this.div_id}`);
                }
                element.innerHTML = text;
            });
    }
}
