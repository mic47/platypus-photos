import { createRoot, Root } from "react-dom/client";
import React from "react";

import { GenericFetch } from "./generic_fetch.ts";
import { Switchable } from "./switchable.ts";
import * as pygallery_service from "./pygallery.generated/services.gen.ts";
import { JobProgressState } from "./pygallery.generated/types.gen.ts";

export class JobList extends GenericFetch<object> {
    private shown: boolean;
    constructor(div_id: string) {
        super(div_id, pygallery_service.jobListEndpointPost);
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

interface JobProgressViewProps {
    state: JobProgressState;
    diff: JobProgressState | null;
    eta_str: string | null;
    job_list_fn: () => void;
}

function JobProgressView({
    state,
    diff,
    eta_str,
    job_list_fn,
}: JobProgressViewProps) {
    const finished =
        diff === null
            ? ""
            : " +" +
              (
                  Math.round(10 * ((diff.t_finished / diff.ts) * 60)) / 10
              ).toString() +
              "/m";
    return (
        <table>
            <thead>
                <tr>
                    <td></td>
                    <td>🏗️</td>
                    <td>🚏</td>
                    <td>{eta_str || ""}✅</td>
                    <td>🌍</td>
                </tr>
            </thead>
            <tbody>
                <tr>
                    <td>🖼️</td>
                    <td>{state.t_total - state.t_finished}</td>
                    <td></td>
                    <td>
                        {state.t_finished}
                        {finished}
                    </td>
                    <td>{state.t_total}</td>
                </tr>
                <tr>
                    <td onClick={job_list_fn}>📦</td>
                    <td>
                        {state.j_total - state.j_finished - state.j_waiting}
                    </td>
                    <td>{state.j_waiting}</td>
                    <td>{state.j_finished}</td>
                    <td>{state.j_total}</td>
                </tr>
            </tbody>
        </table>
    );
}

export class JobProgress {
    public switchable: Switchable;
    private states: JobProgressState[];
    private root: Root;
    constructor(
        private div_id: string,
        private job_list_fn: () => void,
    ) {
        this.states = [];
        this.switchable = new Switchable();
        const element = document.getElementById(this.div_id);
        if (element === null) {
            throw new Error(`Unable to find element ${this.div_id}`);
        }
        this.root = createRoot(element);
    }
    fetch() {
        this.switchable.call_or_store("fetch", () => {
            pygallery_service
                .jobProgressStatePost({
                    requestBody: {
                        state: this.states[0],
                    },
                })
                .then((data) => {
                    this.add_state(data.state);
                    this.root.render(
                        <JobProgressView
                            state={data.state}
                            diff={data.diff}
                            eta_str={data.eta_str}
                            job_list_fn={this.job_list_fn}
                        />,
                    );
                });
        });
    }
    add_state(state: JobProgressState) {
        this.states.push(state);
        this.states = this.states.filter((x) => state.ts - x.ts < 300.0);
    }
}
