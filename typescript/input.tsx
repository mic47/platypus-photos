import { createRoot, Root } from "react-dom/client";
import React, { FormEvent } from "react";

import { SearchQuery } from "./pygallery.generated/types.gen";
import { StateWithHooks, update_search_query_value } from "./state.ts";
import { AnnotationOverlay } from "./photo_map.ts";

export class InputForm {
    private root: Root;
    constructor(
        private div_id: string,
        hooks: StateWithHooks<SearchQuery>,
    ) {
        this.div_id = div_id;
        const element = document.getElementById(this.div_id);
        if (element === null) {
            throw new Error(`Unable to find element ${this.div_id}`);
        }
        this.root = createRoot(element);
        this.root.render(<InputFormComponent hooks={hooks} />);
    }
}

interface InputFormComponentProps {
    hooks: StateWithHooks<SearchQuery>;
}

type WithTs<T> = {
    q: T;
    ts: number;
};

function InputFormComponent({ hooks }: InputFormComponentProps) {
    const [query, updateQuery] = React.useState<WithTs<SearchQuery>>({
        q: hooks.get(),
        ts: Date.now(),
    });
    const [registered, updateRegistered] = React.useState<boolean>(false);
    if (!registered) {
        hooks.register_hook((newQuery) => {
            updateQuery({ q: newQuery, ts: Date.now() });
        });
        updateRegistered(true);
    }
    return (
        <InputFormView
            query={query}
            hook={hooks}
            formSubmitted={(form) => {
                const formData = new FormData(form);
                const values = hooks.get();
                for (const [key_untyped, value] of formData) {
                    const key: keyof SearchQuery =
                        key_untyped as keyof SearchQuery;
                    if (value !== null && value !== undefined && value !== "") {
                        update_search_query_value(values, key, value);
                    } else {
                        delete values[key];
                    }
                }
                hooks.replace(values);
            }}
        />
    );
}

interface InputFormViewProps {
    query: WithTs<SearchQuery>;
    formSubmitted: (form: HTMLFormElement) => void;
    hook: Hook;
}

function InputFormView({ query, hook, formSubmitted }: InputFormViewProps) {
    function update(form: FormEvent<HTMLFormElement>) {
        formSubmitted(form.currentTarget);
    }
    return (
        <>
            <form onSubmit={update} id="input" method="dialog">
                {formInputTextElement(
                    hook,
                    "tag",
                    query.ts,
                    query.q.tag,
                    "🏷️",
                    "tags",
                )}
                <br />
                {formInputTextElement(
                    hook,
                    "cls",
                    query.ts,
                    query.q.cls,
                    "📝",
                    "text",
                )}
                <br />
                {formInputTextElement(
                    hook,
                    "addr",
                    query.ts,
                    query.q.addr,
                    "📭",
                    "address",
                )}
                <br />
                {formInputTextElement(
                    hook,
                    "directory",
                    query.ts,
                    query.q.directory,
                    "📁",
                    "folder",
                )}
                <br />
                {formInputTextElement(
                    hook,
                    "camera",
                    query.ts,
                    query.q.camera,
                    "📷",
                    "camera",
                )}
                <br />
                {formInputTextElement(
                    hook,
                    "timestamp_trans",
                    query.ts,
                    query.q.timestamp_trans,
                    "🕰️",
                    "timestamp_transformation -- SQL",
                )}
                <input
                    type="button"
                    value="Shift timestmap for selected photos"
                    onClick={() => annotation_overlay_no_location(hook)}
                />
                <br />
                {timestampInput(
                    hook,
                    "tsfrom",
                    "tsto",
                    "Time from",
                    "➡️ to (fwd in time)",
                    query.q.tsfrom,
                )}
                <br />
                {timestampInput(
                    hook,
                    "tsto",
                    "tsfrom",
                    "Time to:  ",
                    "⬅️ from (bwd in time)",
                    query.q.tsto,
                )}
                <br />
                <input type="submit" value="Search" />
                <input
                    type="button"
                    value="Reset All"
                    onClick={() => reset_param(hook, "__ALL__")}
                />
            </form>
            <input
                type="checkbox"
                checked={query.q.skip_with_location}
                onChange={(event) =>
                    hook.update({ skip_with_location: event.target.checked })
                }
            />{" "}
            Skip photos with location 🗺️.
            <br />
            <input
                type="checkbox"
                checked={query.q.skip_being_annotated}
                onChange={(event) =>
                    hook.update({ skip_being_annotated: event.target.checked })
                }
            />{" "}
            Skip photos being annoted 🏗️.
            <br />
        </>
    );
}
type Hook = StateWithHooks<SearchQuery>;
function reset_param(search_query: Hook, key: keyof SearchQuery | "__ALL__") {
    if (key === "__ALL__") {
        search_query.replace({});
        return;
    }
    const state = search_query.get();
    delete state[key];
    search_query.replace(state);
}
function add_to_float_param(
    search_query: Hook,
    param: "tsfrom" | "tsto",
    other: "tsfrom" | "tsto",
    new_value: number,
) {
    const query = search_query.get();
    const value = query[param] || query[other];
    if (value != value || value === null || value === undefined) {
        return;
    }
    const update: { [key: string]: string } = {};
    update[param] = (value + new_value).toString();
    search_query.update(update);
}
export function shift_float_params(
    search_query: Hook,
    param_to_start: "tsto" | "tsfrom",
    second_param: "tsto" | "tsfrom",
    shift_by: number | null = null,
) {
    const query = search_query.get();
    const start_value = query[param_to_start];
    const end_value = query[second_param];
    if (end_value === null || end_value === undefined) {
        // This does not make sense, second param is empty
        return;
    }
    const update: SearchQuery = {};
    update[param_to_start] = end_value;
    if (shift_by !== undefined && shift_by !== null) {
        update[second_param] = end_value + shift_by;
    } else {
        if (
            start_value != start_value ||
            start_value === null ||
            start_value === undefined
        ) {
            delete update[second_param];
        } else {
            update[second_param] = end_value + end_value - start_value;
        }
    }
    search_query.update(update);
}
function annotation_overlay_no_location(search_query: Hook) {
    const overlay = new AnnotationOverlay("SubmitDataOverlay");
    overlay.fetch({
        request: { t: "NoLocation" },
        query: search_query.get(),
    });
}

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

const EMPTY_TIME_STRING = TIME_FORMAT.format(new Date(Date.now())).replace(
    /./g,
    "_",
);

function maybeTsToString(timestamp: number | null | undefined): string {
    if (timestamp === null || timestamp === undefined) {
        return EMPTY_TIME_STRING;
    }
    new Date(Date.now());
    return TIME_FORMAT.format(new Date(timestamp * 1000));
}

function formInputTextElement(
    hook: Hook,
    name: keyof SearchQuery,
    ts: number,
    value: string | number | null | undefined,
    icon: string,
    text: string,
) {
    const [val, updateVal] = React.useState<
        WithTs<string | number | undefined>
    >({ q: value === null ? undefined : value, ts: ts });
    let finalValue = val.ts < ts ? value : val.q;
    if (finalValue === null || finalValue === undefined) {
        finalValue = "";
    }
    const id = `f${name}`;
    return (
        <>
            <input
                type="button"
                value="reset"
                onClick={() => {
                    updateVal({ q: "", ts: Date.now() });
                    reset_param(hook, name);
                }}
            />
            <label htmlFor={id}>{icon}:</label>
            <input
                type="text"
                id={id}
                name={name}
                value={finalValue}
                onChange={(event) =>
                    updateVal({ q: event.target.value, ts: Date.now() })
                }
            />{" "}
            ({text})
        </>
    );
}

function timestampInput(
    search_query: Hook,
    f: "tsfrom" | "tsto",
    t: "tsfrom" | "tsto",
    label_text: string,
    timeshift_text: string,
    query_value: number | null | undefined,
) {
    const timeOffsets = [
        ["-1y", -365.25 * 24 * 60 * 60],
        ["-1m", -30 * 24 * 60 * 60],
        ["-1w", -7 * 24 * 60 * 60],
        ["-1d", -24 * 60 * 60],
        ["-1h", -60 * 60],
        ["-5m", -5 * 60],
        ["+5m", 5 * 60],
        ["+1h", 60 * 60],
        ["+1d", 24 * 60 * 60],
        ["+1w", 7 * 24 * 60 * 60],
        ["+1m", 30 * 24 * 60 * 60],
        ["+1y", 365.25 * 24 * 60 * 60],
    ].map(([text, shift_iter], index) => {
        const shift: number = shift_iter as number;
        return (
            <input
                key={index}
                type="button"
                value={text}
                onClick={() => add_to_float_param(search_query, f, t, shift)}
            />
        );
    });
    const id = `f${f}`;
    return (
        <>
            <label htmlFor={id}>{label_text}:</label>
            <input
                type="text"
                id={id}
                name={f}
                value={query_value === null ? undefined : query_value}
                hidden={true}
                readOnly={true}
            />
            <span className="date">{maybeTsToString(query_value)}</span>
            {timeOffsets}
            <input
                type="button"
                value="reset"
                onClick={() => reset_param(search_query, f)}
            />
            <input
                type="button"
                value={timeshift_text}
                onClick={() => shift_float_params(search_query, f, t)}
            />
        </>
    );
}
