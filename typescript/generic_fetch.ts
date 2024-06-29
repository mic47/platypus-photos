import { CancelablePromise } from "./pygallery.generated/core/CancelablePromise";

export class GenericFetch<T> {
    constructor(
        protected readonly div_id: string,
        private api: (req: { requestBody: T }) => CancelablePromise<string>,
    ) {}

    fetch_impl(request: T): Promise<void> {
        return this.api({ requestBody: request }).then((text) => {
            const element = document.getElementById(this.div_id);
            if (element === null) {
                throw Error(`Unable to find element ${this.div_id}`);
            }
            element.innerHTML = text;
        });
    }
}
