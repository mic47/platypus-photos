import React from "react";

import * as pygallery_service from "./pygallery.generated/services.gen.ts";
import {
    JobDescription,
    JobProgressState,
    JobProgressStateResponse,
} from "./pygallery.generated/types.gen.ts";
import { round } from "./utils.ts";

interface JobListViewProps {
    jobs: JobDescription[];
    switch_job_list: () => void;
    map_zoom: (latitude: number, longitude: number) => void;
}

function JobListView({ jobs, switch_job_list, map_zoom }: JobListViewProps) {
    const rows = jobs.map((job) => {
        let location = null;
        if (job.latitude !== null && job.longitude !== null) {
            const latitude = job.latitude;
            const longitude = job.longitude;
            const onClick = () => {
                switch_job_list();
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
Stats: ${JSON.stringify({ ...job.job, original_request: "(redacted)" }, null, 2)}
`;
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
                        <pre>{formattedText}</pre>
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

interface JobProgressViewProps {
    state: JobProgressState | null;
    diff: JobProgressState | null;
    job_list: null | JobDescription[];
    eta_str: string | null;
    switch_job_list: () => void;
    map_zoom: (latitude: number, longitude: number) => void;
}

function JobProgressView({
    state,
    diff,
    job_list,
    eta_str,
    switch_job_list,
    map_zoom,
}: JobProgressViewProps) {
    if (state === null) {
        return <></>;
    }
    const finished =
        diff === null
            ? ""
            : " +" +
              round((diff.t_finished / diff.ts) * 60, 1).toString() +
              "/m";
    let job_list_c = null;
    if (job_list !== null) {
        job_list_c = (
            <JobListView
                jobs={job_list}
                switch_job_list={switch_job_list}
                map_zoom={map_zoom}
            />
        );
    }
    return (
        <>
            <div className="JobProgress">
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
                            <td onClick={switch_job_list}>📦</td>
                            <td>
                                {state.j_total -
                                    state.j_finished -
                                    state.j_waiting}
                            </td>
                            <td>{state.j_waiting}</td>
                            <td>{state.j_finished}</td>
                            <td>{state.j_total}</td>
                        </tr>
                    </tbody>
                </table>
            </div>
            <div id="JobList" className="JobList">
                {job_list_c}
            </div>
        </>
    );
}

interface JobProgressComponentProps {
    interval_seconds: number;
    map_zoom: (latitude: number, longitude: number) => void;
}

export function JobProgressComponent({
    interval_seconds,
    map_zoom,
}: JobProgressComponentProps) {
    const [jobList, updateJobList] = React.useState<null | JobDescription[]>(
        null,
    );
    const [progress, updateProgress] = React.useState<{
        response: JobProgressStateResponse;
        states: JobProgressState[];
    } | null>(null);

    const show_or_close_job_list = () => {
        if (jobList === null) {
            pygallery_service.remoteJobsGet().then((jobs) => {
                updateJobList(jobs);
            });
        } else {
            updateJobList(null);
        }
    };
    React.useEffect(() => {
        const update_progress = () => {
            pygallery_service
                .jobProgressStatePost({
                    requestBody: { state: progress?.states[0] },
                })
                .then((response) => {
                    const newStates =
                        progress?.states.filter(
                            (x) => response.state.ts - x.ts < 300.0,
                        ) || [];
                    newStates.push(response.state);
                    updateProgress({ response, states: newStates });
                });
        };

        const interval = setInterval(() => {
            update_progress();
        }, interval_seconds * 1000);
        update_progress();
        return () => {
            clearInterval(interval);
        };
    }, []);

    return (
        <JobProgressView
            state={progress?.response.state || null}
            diff={progress?.response.diff || null}
            eta_str={progress?.response.eta_str || null}
            job_list={jobList}
            switch_job_list={show_or_close_job_list}
            map_zoom={map_zoom}
        />
    );
}
