import {
    GalleryPaging,
    SearchQuery,
    SortParams,
} from "./pygallery.generated/types.gen.ts";
import { CheckboxesParams } from "./state.ts";

export class AggregateInfo {
    constructor(private div_id: string) {}

    fetch(url_data: SearchQuery, paging: GalleryPaging) {
        const url = `/internal/aggregate.html`;
        fetch(url, {
            method: "POST",
            body: JSON.stringify({ query: url_data, paging }),
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

export class Gallery {
    constructor(
        private div_id: string,
        private prev_page: () => void,
        private next_page: () => void,
    ) {}

    fetch(
        url_data: SearchQuery,
        paging: GalleryPaging,
        sort: SortParams,
        checkboxes: CheckboxesParams,
    ) {
        const url = "/internal/gallery.html";
        fetch(url, {
            method: "POST",
            body: JSON.stringify({ query: url_data, paging, sort, checkboxes }),
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
                const prev = gallery.getElementsByClassName("prev-url");
                for (let i = 0; i < prev.length; i++) {
                    const p = prev[i] as HTMLElement;
                    p.onclick = () => {
                        this.prev_page();
                    };
                }
                const next = gallery.getElementsByClassName("next-url");
                for (let i = 0; i < next.length; i++) {
                    const p = next[i] as HTMLElement;
                    p.onclick = () => {
                        this.next_page();
                    };
                }
            });
    }
}

function changeState(index: string | number | null) {
    const url = new URL(window.location.href);
    if (index == null) {
        url.searchParams.delete("oi");
    } else {
        url.searchParams.set("oi", index.toString());
    }
    if (window.history.replaceState) {
        window.history.replaceState(window.history.state, "", url.href);
    }
}
function replace_image_size_inside(
    element: null | HTMLElement,
    source: string,
    replacement: string,
) {
    if (element == null) {
        return;
    }
    const images = element.getElementsByTagName("img");
    for (let i = 0; i < images.length; i++) {
        const image = images[i];
        const repl = image.src.replace("size=" + source, "size=" + replacement);
        if (repl != image.src) {
            image.src = repl;
        }
        if (replacement == "original") {
            image.loading = "eager";
        }
    }
}
function this_is_overlay_element(element: HTMLElement) {
    replace_image_size_inside(element, "preview", "original");
    let next = element.nextElementSibling;
    if (next != null) {
        replace_image_size_inside(next as HTMLElement, "preview", "original");
        next = next.nextElementSibling;
    }
    let prev = element.previousElementSibling;
    if (prev != null) {
        replace_image_size_inside(prev as HTMLElement, "preview", "original");
        prev = prev.previousElementSibling;
    }
    if (next != null) {
        replace_image_size_inside(next as HTMLElement, "original", "preview");
    }
    if (prev != null) {
        replace_image_size_inside(prev as HTMLElement, "original", "preview");
    }
}
export function overlay(element: HTMLElement, index: string) {
    const parent = element.parentElement;
    if (parent === null) {
        throw new Error(`Element does not have parent ${element}`);
    }
    this_is_overlay_element(parent);
    parent.classList.add("overlay");
    changeState(index);
}
export function overlay_close(element: HTMLElement) {
    const root = element.parentElement?.parentElement;
    if (root === undefined || root === null) {
        throw new Error(`Element does not have grand-parent ${element}`);
    }
    replace_image_size_inside(root, "original", "preview");
    replace_image_size_inside(
        root.previousElementSibling as HTMLElement | null,
        "original",
        "preview",
    );
    replace_image_size_inside(
        root.nextElementSibling as HTMLElement | null,
        "original",
        "preview",
    );
    root.classList.remove("overlay");
    changeState(null);
}
export function overlay_prev(element: HTMLElement, index: number) {
    const grandpa = element.parentElement?.parentElement;
    const target = grandpa?.previousElementSibling;
    if (
        target === undefined ||
        target === null ||
        grandpa === undefined ||
        grandpa === null
    ) {
        throw new Error(
            `Element does not have grand-parent's previous sibling ${element}`,
        );
    }
    this_is_overlay_element(target as HTMLElement);
    target.classList.add("overlay");
    grandpa.classList.remove("overlay");
    changeState(index - 1);
}
export function overlay_next(element: HTMLElement, index: number) {
    const grandpa = element.parentElement?.parentElement;
    const target = grandpa?.nextElementSibling;
    if (
        target === undefined ||
        target === null ||
        grandpa === undefined ||
        grandpa === null
    ) {
        throw new Error(
            `Element does not have grand-parent's next sibling ${element}`,
        );
    }
    this_is_overlay_element(target as HTMLElement);
    target.classList.add("overlay");
    grandpa.classList.remove("overlay");
    changeState(index + 1);
}
