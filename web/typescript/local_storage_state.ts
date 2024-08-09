type LocalStorageDict<T> = { [id: string]: null | T };

export class LocalStorageState<T> {
    constructor(
        private key: string,
        private callbacks: {
            item_was_added: (id: string, item: T) => void;
            item_was_removed: (id: string) => void;
        },
    ) {
        Object.entries(this.get()).forEach(([id, m]) => {
            if (m !== undefined && m !== null) {
                this.callbacks.item_was_added(id, m);
            }
        });
        window.addEventListener("storage", (e) => {
            if (e.key !== this.key) {
                return;
            }
            const oldValue: LocalStorageDict<T> = JSON.parse(
                e.oldValue || "{}",
            );
            const newValue: LocalStorageDict<T> = JSON.parse(
                e.newValue || "{}",
            );
            const actions: Array<[string, null | T]> = [];
            Object.entries(newValue).forEach(([id, value]) => {
                const old = oldValue[id];
                if (old === undefined || old === null) {
                    if (value !== undefined && value !== null) {
                        // Something was added
                        actions.push([id, value]);
                    }
                } else if (value === undefined || value === null) {
                    // Old is something, this is empty
                    actions.push([id, null]);
                }
            });
            if (actions.length === 0) {
                // Nothing to do
                return;
            }
            const data = this.get();
            actions.forEach(([id, value]) => {
                data[id] = value;
                if (value === undefined || value === null) {
                    callbacks.item_was_removed(id);
                } else {
                    callbacks.item_was_added(id, value);
                }
            });
            window.localStorage.setItem(this.key, JSON.stringify(data));
        });
    }

    private get(): { [id: string]: null | T } {
        let current = window.localStorage.getItem(this.key);
        if (current === undefined || current === null) {
            current = "{}";
        }
        let parsed = {};
        try {
            parsed = JSON.parse(current);
        } catch (error) {
            console.log("Error when getting data from local storage", error);
        }
        return parsed as { [id: string]: null | T };
    }

    add(item: T): string {
        const data = this.get();
        const id = Math.random().toString().replace("0.", "");
        data[id] = item;
        window.localStorage.setItem(this.key, JSON.stringify(data));
        this.callbacks.item_was_added(id, item);
        return id;
    }
    remove(id: string) {
        const data = this.get();
        data[id] = null;
        window.localStorage.setItem(this.key, JSON.stringify(data));
        this.callbacks.item_was_removed(id);
    }
}
