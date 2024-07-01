import { createRoot, Root } from "react-dom/client";
import React from "react";

import { Switchable } from "./switchable.ts";
import * as pygallery_service from "./pygallery.generated/services.gen.ts";
import {
    JobDescription,
    JobProgressState,
} from "./pygallery.generated/types.gen.ts";

interface JobListViewProps {
    jobs: JobDescription[];
    show_job_list: () => void;
    map_zoom: (latitude: number, longitude: number) => void;
}

function round(n: number, digits: number = 0) {
    const mul = Math.pow(10, digits);
    return Math.round(mul * n) / n;
}

function JobListView({ jobs, show_job_list, map_zoom }: JobListViewProps) {
    const rows = jobs.map((job) => {
        let location = null;
        if (job.latitude !== null && job.longitude !== null) {
            const latitude = job.latitude;
            const longitude = job.longitude;
            const onClick = () => {
                show_job_list();
                map_zoom(latitude, longitude);
            };
            location =
                job.latitude === null || job.longitude === null ? null : (
                    <a href="#" onClick={onClick}>
                        {round(job.latitude, 5)} {round(job.longitude, 5)}
                    </a>
                );
        }
        const formattedText = `
ID: ${job.id}
Query: ${JSON.stringify(job.query, null, 2)}
Stats: ${JSON.stringify({...job.job, original_request: "(redacted)"}, null, 2)}
`
        return (
            <tr key={job.id}>
                <td>{job.icon}</td>
                <td>{job.total}</td>
                <td>{job.type}</td>
                <td>{job.time}</td>
                <td className="hovered">
                    hover
                    <div className="left_algn hover_show">
                        <img
                            loading="lazy"
                            src={`/img?hsh=${job.example_path_md5}&size=preview`}
                            className="gallery_image"
                        />
                        <pre>
                            {formattedText}
                        </pre>
                    </div>
                </td>
                <td>{job.replacements}</td>
                <td>{location}</td>
            </tr>
        );
    });
    return (
        <table>
            <thead>
                <tr>
                    <th></th>
                    <th>total</th>
                    <th>what</th>
                    <th>last update</th>
                    <th>raw</th>
                    <th>text changes</th>
                    <th>loc changes</th>
                </tr>
            </thead>
            <tbody>{rows}</tbody>
        </table>
    );
}

export class JobList {
    private shown: boolean;
    private root: Root;
    constructor(
        private div_id: string,
        private show_job_list: () => void,
        private map_zoom: (latitude: number, longitude: number) => void,
    ) {
        this.shown = false;
        const element = document.getElementById(this.div_id);
        if (element === null) {
            throw new Error(`Unable to find element ${this.div_id}`);
        }
        this.root = createRoot(element);
    }
    fetch() {
        pygallery_service.remoteJobsGet().then((jobs) => {
            this.shown = true;
            this.root.render(
                <JobListView
                    jobs={jobs}
                    show_job_list={this.show_job_list}
                    map_zoom={this.map_zoom}
                />
            );
        });
    }
    show_or_close() {
        if (this.shown) {
            this.shown = false;
            this.root.render(<></>);
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
