const _PRETTY_DURATIONS: Array<[number, string]> = [
    [365 * 86400, "y"],
    [30 * 86400, " mon"],
    [7 * 86400, "w"],
    [86400, "d"],
    [3600, "h"],
    [60, " min"],
    [1, "s"],
];

export function pretty_print_duration(duration: number): string | null {
    let dur = duration;
    const out: string[] = [];
    _PRETTY_DURATIONS.forEach(([seconds, tick]) => {
        const num = Math.trunc(dur / seconds);
        if (num === 0) {
            return;
        }
        dur = dur % seconds;
        out.push(`${num}${tick}`);
    });
    return out.join(" ");
}
export function pprange(ts1: number, ts2: number): string {
    const d1 = new Date();
    d1.setTime(ts1 * 1000);
    const d2 = new Date();
    d2.setTime(ts2 * 1000);
    const s1 = d1.toLocaleString();
    let out: string[] = [];
    const ss1 = s1.split(" ");
    d2.toLocaleString()
        .split(" ")
        .forEach((part, index) => {
            if (part !== ss1[index]) {
                out.push(part);
            }
        });
    if (out.length === 0) {
        out = [s1];
    } else {
        out = [s1, "until", ...out];
    }
    return out.join(" ");
}
export function null_if_empty(
    str: null | undefined | string | File,
): null | string {
    if (
        str === null ||
        str === undefined ||
        typeof str !== "string" ||
        str.trim() === ""
    ) {
        return null;
    }
    return str;
}
export function parse_float_or_null(str: string | null | File): number | null {
    if (str === null || typeof str !== "string") {
        return null;
    }
    const value = parseFloat(str);
    if (value != value) {
        return null;
    }
    return value;
}

export function error_box(div_id: string, value: object | number | string) {
    console.log(div_id, value);
    const e = document.getElementById(div_id);
    console.log(e);
    if (e === null || e === undefined) {
        alert(value);
        return;
    }
    const element = document.createElement("div");
    element.classList.add("error");
    const pre = document.createElement("pre");
    try {
        pre.innerHTML = JSON.stringify(value, null, 2);
    } catch {
        pre.innerHTML = value.toString();
    }
    element.appendChild(pre);
    e.innerHTML = "";
    e.appendChild(element);
}
