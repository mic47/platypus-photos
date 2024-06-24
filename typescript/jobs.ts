import { GenericFetch } from "./generic_fetch.ts";
import { Switchable } from "./switchable.ts";

export class JobList extends GenericFetch<object> {
    private shown: boolean;
    constructor(div_id: string) {
        super(div_id, "/internal/job_list.html");
        this.shown = false;
    }
    fetch() {
        return this.fetch_impl({}).then(() => {
            this.shown = true;
        });
    }
    show_or_close() {
        if (this.shown) {
            this.shown = false;
            const element = document.getElementById(this.div_id);
            if (element === null) {
                throw new Error(`Unable to fine element ${this.div_id})`);
            }
            element.innerHTML = "";
        } else {
            this.fetch();
        }
    }
}

export class JobProgress<S extends { ts: number }> extends GenericFetch<{
    job_list_fn: string;
    update_state_fn: string;
    state: S;
}> {
    public switchable: Switchable;
    private states: S[];
    constructor(
        div_id: string,
        private update_state_fn: string,
        private job_list_fn: string,
    ) {
        super(div_id, "/internal/job_progress.html");
        this.states = [];
        this.switchable = new Switchable();
    }
    fetch() {
        this.switchable.call_or_store("fetch", () => {
            return this.fetch_impl({
                job_list_fn: this.job_list_fn,
                update_state_fn: this.update_state_fn,
                state: this.states[0],
            });
        });
    }
    add_state(state: S) {
        this.states.push(state);
        this.states = this.states.filter((x) => state.ts - x.ts < 300.0);
    }
    add_state_base64(base64: string) {
        const state = JSON.parse(window.atob(base64));
        this.add_state(state);
    }
}
