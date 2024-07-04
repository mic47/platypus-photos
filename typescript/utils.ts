import data_model from "./data_model.generated.json";
export const FLAGS: { [key: string]: string } = data_model.unicode.flags;

export function append_flag(country: string): string {
    const flag = FLAGS[country.toLowerCase()] || "";
    return `${country}${flag}`;
}
export function time_to_clock(value: Date | number): string {
    if (typeof value === "number") {
        value = new Date(value * 1000);
    }
    const minutes = Math.round(value.getMinutes());
    const hours = Math.round(value.getHours());
    if (minutes < 30) {
        return data_model.unicode.clocks_oh[hours % 12];
    }
    return data_model.unicode.clocks_thirty[hours % 12];
}
export function round(n: number, digits: number = 0) {
    const mul = Math.pow(10, digits);
    return Math.round(mul * n) / mul;
}

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
export function pprange(ts1: number | null, ts2: number | null): string {
    if (ts1 === null || ts2 === null) {
        return "Dates cannot be null";
    }
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
// eslint-disable-next-line @typescript-eslint/no-unused-vars
export function impissible(_unused: never): never {
    throw new Error("This shoudl be impissible");
}
export function parse_string_or_null(
    str: string | null | undefined | File,
): string | null {
    if (str === null || str === undefined || typeof str !== "string") {
        return null;
    }
    return str;
}
export function parse_float_or_null(
    str: string | null | undefined | File,
): number | null {
    if (str === null || str === undefined || typeof str !== "string") {
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

export function base64_decode_object(data: string): object {
    return JSON.parse(window.atob(data));
}
export function format_seconds_to_duration(
    seconds: number,
    none_threshold: number = -1,
): string | null {
    seconds = Math.round(seconds);
    if (seconds < none_threshold) {
        return null;
    }
    if (seconds < 60) {
        return `${seconds}s`;
    }
    const minutes = Math.trunc(seconds / 60);
    if (minutes < 100) {
        return `${minutes}m`;
    }
    const hours = Math.trunc(seconds / 3600);
    if (hours < 48) {
        return `${hours}h`;
    }
    const days = Math.trunc(seconds / 86400);
    if (days < 14) {
        return `${days}d`;
    }
    const weeks = Math.trunc(seconds / (86400 * 7));
    if (weeks < 6) {
        return `${weeks}w`;
    }
    const months = Math.trunc(seconds / (86400 * 30));
    if (months < 19) {
        return `${months}mon`;
    }
    const years = Math.trunc(seconds / (86400 * 365.25));
    return `${years}y`;
}
export function noop() {}
const TIME_FORMAT = new Intl.DateTimeFormat("en-GB", {
    hour12: false,
    weekday: "short",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
});
export function timestamp_to_pretty_datetime(timestamp: number): string {
    return TIME_FORMAT.format(new Date(1000 * timestamp));
}
