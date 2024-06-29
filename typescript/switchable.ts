import { UrlSync } from "./state.ts";

export class Switchable {
    private enabled: boolean;
    private callbacks: { [key: string]: () => void };
    constructor() {
        this.enabled = true;
        this.callbacks = {};
    }
    disable() {
        if (this.enabled === false) {
            false;
        }
        this.enabled = false;
        this.callbacks = {};
    }
    enable() {
        if (this.enabled === true) {
            return;
        }
        this.enabled = true;
        Object.values(this.callbacks).forEach((callback) => {
            if (callback !== undefined && callback !== null) {
                callback();
            }
        });
        this.callbacks = {};
    }
    call_or_store(name: string, callback: () => void) {
        if (this.enabled) {
            return callback();
        }
        this.callbacks[name] = callback;
    }
}

export class TabSwitch {
    private defaults: { [key: string]: boolean };
    private sync: UrlSync;
    constructor(
        div_id: string,
        private callbacks: { [key: string]: Switchable },
    ) {
        this.defaults = {};
        const element = document.getElementById(div_id);
        if (element === null) {
            throw new Error(
                `Unable to initialize tab switching, element not found ${div_id}`,
            );
        }
        const buttons = element.getElementsByTagName("button");
        const ids = [];
        for (let i = 0; i < buttons.length; i++) {
            const button = buttons[i];
            if (!button.classList.contains("tablinks")) {
                continue;
            }
            if (button.id === undefined || button.id === null) {
                console.log("Error, this button should have id", button);
            }
            const sync_id = button.id.replace("TabSource", "Tab");
            ids.push(sync_id);
            const is_active_default = button.classList.contains("active");
            this.defaults[sync_id] = is_active_default;
        }
        this.sync = new UrlSync(ids);
        const url_params = this.sync.get();
        for (let i = 0; i < buttons.length; i++) {
            const button = buttons[i];
            if (!button.classList.contains("tablinks")) {
                continue;
            }
            if (button.id === undefined || button.id === null) {
                console.log("Error, this button should have id", button);
            }
            const sync_id = button.id.replace("TabSource", "Tab");
            const is_active_from_url = url_params.unparsed[sync_id];
            button.addEventListener("click", () => {
                this.switch_tab_visibility(button);
            });
            this.set_tab_visibility(
                is_active_from_url === undefined || is_active_from_url === null
                    ? this.defaults[sync_id]
                    : is_active_from_url === "true",
                button,
            );
        }
    }
    set_tab_visibility(is_active: boolean, button: HTMLElement) {
        const id = button.id;
        const target_class = id.replace("TabSource", "TabTarget");
        const sync_id = id.replace("TabSource", "Tab");
        const targets = document.getElementsByClassName(target_class);
        const url = this.sync.get();
        if (this.defaults[sync_id] === is_active) {
            delete url.unparsed[sync_id];
        } else {
            url.unparsed[sync_id] = is_active.toString();
        }
        this.sync.update(url.unparsed);
        const callback = this.callbacks[sync_id];
        if (is_active) {
            button.classList.add("active");
            for (let i = 0; i < targets.length; i++) {
                targets[i].classList.remove("disabled");
            }
            if (callback !== undefined && callback !== null) {
                callback.enable();
            }
        } else {
            button.classList.remove("active");
            for (let i = 0; i < targets.length; i++) {
                targets[i].classList.add("disabled");
            }
            if (callback !== undefined && callback !== null) {
                callback.disable();
            }
        }
    }
    switch_tab_visibility(button: HTMLElement) {
        const is_active = button.classList.contains("active");
        this.set_tab_visibility(!is_active, button);
    }
}
