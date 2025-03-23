import React, { FormEvent } from "react";

import { SearchQuery, SortParams } from "./pygallery.generated/types.gen";
import { update_search_query_value } from "./state.ts";
import { AnnotationOverlayRequest } from "./annotations.tsx";
import { SortFormView } from "./sort_form.tsx";
import { UpdateCallbacks } from "./types.ts";

export type WithTs<T> = {
    q: T;
    ts: number;
};

interface InputFormViewProps {
    query: WithTs<SearchQuery>;
    sort: SortParams;
    callbacks: Callbacks;
    sortCallbacks: UpdateCallbacks<SortParams>;
    submitAnnotations: (request: AnnotationOverlayRequest) => void;
}

export function InputFormView({
    query,
    sort,
    callbacks,
    sortCallbacks,
    submitAnnotations,
}: InputFormViewProps) {
    function update(form: FormEvent<HTMLFormElement>) {
        process_submitted_form(query.q, callbacks, form.currentTarget);
    }
    return (
        <>
            <form onSubmit={update} id="input" method="dialog">
                {formInputTextElement(
                    query.q,
                    callbacks,
                    "tag",
                    query.ts,
                    query.q.tag,
                    "🏷️",
                    "tags",
                )}
                <br />
                {formInputTextElement(
                    query.q,
                    callbacks,
                    "cls",
                    query.ts,
                    query.q.cls,
                    "📝",
                    "text",
                )}
                <br />
                {formInputTextElement(
                    query.q,
                    callbacks,
                    "addr",
                    query.ts,
                    query.q.addr,
                    "📭",
                    "address",
                )}
                <br />
                {formInputTextElement(
                    query.q,
                    callbacks,
                    "identity",
                    query.ts,
                    query.q.identity,
                    "🤓",
                    "identity",
                )}
                <br />
                {formInputTextElement(
                    query.q,
                    callbacks,
                    "directory",
                    query.ts,
                    query.q.directory,
                    "📁",
                    "folder",
                )}
                <br />
                {formInputTextElement(
                    query.q,
                    callbacks,
                    "camera",
                    query.ts,
                    query.q.camera,
                    "📷",
                    "camera",
                )}
                <br />
                {formInputTextElement(
                    query.q,
                    callbacks,
                    "timestamp_trans",
                    query.ts,
                    query.q.timestamp_trans,
                    "🕰️",
                    "timestamp_transformation -- SQL",
                )}
                <input
                    type="button"
                    value="Shift timestmap for selected photos"
                    onClick={() => {
                        submitAnnotations({
                            request: { t: "NoLocation" },
                            query: query.q,
                        });
                    }}
                />
                <br />
                {timestampInput(
                    query.q,
                    callbacks,
                    "tsfrom",
                    "tsto",
                    "Time from",
                    "➡️ to (fwd in time)",
                    query.q.tsfrom,
                )}
                <br />
                {timestampInput(
                    query.q,
                    callbacks,
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
                    onClick={() => reset_param(query.q, callbacks, "__ALL__")}
                />
            </form>
            <input
                type="checkbox"
                checked={query.q.skip_with_location}
                onChange={(event) =>
                    callbacks.update({
                        skip_with_location: event.target.checked,
                    })
                }
            />{" "}
            Skip photos with location 🗺️.
            <br />
            <input
                type="checkbox"
                checked={query.q.skip_being_annotated}
                onChange={(event) =>
                    callbacks.update({
                        skip_being_annotated: event.target.checked,
                    })
                }
            />{" "}
            Skip photos being annoted 🏗️.
            <br />
            <SortFormView
                sort={sort}
                update_sort={(update) => sortCallbacks.update(update)}
            />
        </>
    );
}

type Callbacks = {
    update: (update: SearchQuery) => void;
    replace: (newState: SearchQuery) => void;
};
function process_submitted_form(
    searchQuery: SearchQuery,
    callbacks: Callbacks,
    form: HTMLFormElement,
) {
    const formData = new FormData(form);
    const values = { ...searchQuery };
    for (const [key_untyped, value] of formData) {
        const key: keyof SearchQuery = key_untyped as keyof SearchQuery;
        if (value !== null && value !== undefined && value !== "") {
            update_search_query_value(values, key, value);
        } else {
            delete values[key];
        }
    }
    callbacks.replace(values);
}
function reset_param(
    search_query: SearchQuery,
    callbacks: Callbacks,
    key: keyof SearchQuery | "__ALL__",
) {
    if (key === "__ALL__") {
        callbacks.replace({});
        return;
    }
    const state = search_query;
    delete state[key];
    callbacks.replace(state);
}
function add_to_float_param(
    search_query: SearchQuery,
    callbacks: Callbacks,
    param: "tsfrom" | "tsto",
    other: "tsfrom" | "tsto",
    new_value: number,
) {
    const query = search_query;
    const value = query[param] || query[other];
    if (value != value || value === null || value === undefined) {
        return;
    }
    const update: SearchQuery = {};
    update[param] = value + new_value;
    callbacks.update(update);
}
export function shift_float_params(
    search_query: SearchQuery,
    callbacks: Callbacks,
    param_to_start: "tsto" | "tsfrom",
    second_param: "tsto" | "tsfrom",
    shift_by: number | null = null,
) {
    const query = search_query;
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
    callbacks.update(update);
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
    searchQuery: SearchQuery,
    callbacks: Callbacks,
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
                    reset_param(searchQuery, callbacks, name);
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
    searchQuery: SearchQuery,
    callbacks: Callbacks,
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
                onClick={() =>
                    add_to_float_param(searchQuery, callbacks, f, t, shift)
                }
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
                value={
                    query_value === null || query_value === undefined
                        ? ""
                        : query_value
                }
                hidden={true}
                readOnly={true}
            />
            <span className="date">{maybeTsToString(query_value)}</span>
            {timeOffsets}
            <input
                type="button"
                value="reset"
                onClick={() => reset_param(searchQuery, callbacks, f)}
            />
            <input
                type="button"
                value={timeshift_text}
                onClick={() => shift_float_params(searchQuery, callbacks, f, t)}
            />
        </>
    );
}
