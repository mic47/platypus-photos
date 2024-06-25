export type SearchQueryParams = { [key1: string]: string };
export type PagingParams = { [key2: string]: string };
export type SortParams = { [key3: string]: string };
export type CheckboxesParams = { [key4: string]: boolean };

type AppStateHook<T> = (data: T) => void;

class StateWithHooks<T> {
    private hooks: Array<AppStateHook<T>>;
    constructor(private data: T) {
        this.hooks = [];
    }
    register_hook(hook: AppStateHook<T>) {
        this.hooks.push(hook);
    }
    get(): T {
        return this.data;
    }
    call_hooks(): StateWithHooks<T> {
        const data = this.data;
        this.hooks.forEach((x) => x(data));
        return this;
    }
    update(update: T): StateWithHooks<T> {
        this.data = { ...this.data, ...update };
        this.call_hooks();
        return this;
    }
    replace(newData: T): StateWithHooks<T> {
        this.data = newData;
        this.call_hooks();
        return this;
    }
    replace_no_hook_update(newData: T): StateWithHooks<T> {
        this.data = newData;
        return this;
    }
}

export class AppState {
    public search_query: StateWithHooks<SearchQueryParams>;
    public paging: StateWithHooks<PagingParams>;
    public sort: StateWithHooks<SortParams>;
    constructor(
        search_query: SearchQueryParams,
        paging: PagingParams,
        sort: SortParams,
    ) {
        this.search_query = new StateWithHooks(search_query);
        this.paging = new StateWithHooks(paging);
        this.sort = new StateWithHooks(sort);
    }
}

export class CheckboxSync {
    private state: { [id: string]: boolean };
    constructor() {
        this.state = {};
    }
    get(): { [id: string]: boolean } {
        return this.state;
    }
    update_from_element(element: HTMLInputElement) {
        this.state[element.id] = element.checked;
    }
}

export class UrlSync {
    constructor(private registered_fields: string[]) {}
    get(): { [key: string]: string } {
        const url = new URL(window.location.href);
        return Object.fromEntries(
            this.registered_fields
                .map((field) => [field, url.searchParams.get(field)])
                .filter((x) => x[1] !== undefined && x[1] !== null && x[1]),
        );
    }
    update(new_url: { [key: string]: string }) {
        const url = new URL(window.location.href);
        this.registered_fields.forEach((field) => {
            const new_value = new_url[field];
            if (new_value === null || new_value === undefined) {
                url.searchParams.delete(field);
            } else {
                url.searchParams.set(field, new_value);
            }
        });
        if (window.history.replaceState) {
            window.history.replaceState(window.history.state, "", url.href);
        }
    }
}
