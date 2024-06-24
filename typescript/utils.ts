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
