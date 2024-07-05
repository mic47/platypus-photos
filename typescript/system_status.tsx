import { createRoot, Root } from "react-dom/client";
import React from "react";

import { Switchable } from "./switchable.ts";
import * as pygallery_service from "./pygallery.generated/services.gen.ts";
import { pretty_print_duration } from "./utils.ts";
import { SystemStatus as ServerSystemStatus } from "./pygallery.generated/types.gen.ts";

export class SystemStatus {
    public switchable: Switchable;
    private root: Root;
    constructor(private div_id: string) {
        const element = document.getElementById(this.div_id);
        if (element === null) {
            throw new Error(`Unable to find element ${this.div_id}`);
        }
        this.root = createRoot(element);
        this.switchable = new Switchable();
        this.root.render(
            <SystemStatusComponent
                switchable={this.switchable}
                intervalSeconds={10}
            />,
        );
    }
}

interface SystemStatusComponentProps {
    switchable: Switchable;
    intervalSeconds: number;
}

function SystemStatusComponent({
    switchable,
    intervalSeconds,
}: SystemStatusComponentProps) {
    const [data, updateData] = React.useState<ServerSystemStatus | null>(null);

    React.useEffect(() => {
        const updateProgress = () => {
            switchable.call_or_store("fetch", () => {
                return pygallery_service.systemStatusGet().then((data) => {
                    updateData(data);
                });
            });
        };
        const interval = setInterval(() => {
            updateProgress();
        }, intervalSeconds * 1000);
        updateProgress();
        return () => {
            clearInterval(interval);
        };
    }, []);
    return <SystemStatusView status={data} />;
}

interface SystemStatusViewProps {
    status: ServerSystemStatus | null;
}

function SystemStatusView({ status }: SystemStatusViewProps) {
    if (status === null) {
        return <></>;
    }
    const progress_rows = status.progress_bars.map((bar) => {
        const total = bar[1].total === 0 ? "" : bar[1].total.toString();
        const rate =
            bar[1].rate === null
                ? ""
                : (Math.round(bar[1].total * 10) / 10).toString();
        const elapsed =
            bar[1].elapsed === null
                ? ""
                : pretty_print_duration(bar[1].elapsed) || "0s";
        return (
            <tr key={bar[0]}>
                <td className="center">{bar[0]}</td>
                <td>{bar[1].desc}</td>
                <td className="center">{bar[1].progress}</td>
                <td className="center">{total}</td>
                <td className="center">{rate}</td>
                <td className="center">{elapsed}</td>
            </tr>
        );
    });
    const workers_rows = Object.values(status.current_state).map((worker) => {
        const duration = pretty_print_duration(Date.now() / 1000 - worker.when);
        const exception = [];
        if (worker.exception !== null) {
            if (worker.exception.exc_tb !== null) {
                exception.push(
                    ...worker.exception.exc_tb.map((ex) => (
                        <>
                            {ex}
                            <br />
                        </>
                    )),
                );
            }
            exception.push(
                <>
                    {worker.exception.exc_type || ""}:{" "}
                    {worker.exception.exc_val || ""}
                    <br />
                </>,
            );
        }
        return (
            <tr key={worker.name}>
                <td>{worker.name}</td>
                <td className="center">{worker.state}</td>
                <td className="center">{duration}</td>
                <td>{exception}</td>
            </tr>
        );
    });
    return (
        <div className="SystemStatusView">
            <h3>Progress of server queues</h3>
            <table>
                <thead>
                    <tr>
                        <th>ID</th>
                        <th>Description</th>
                        <th>Progress</th>
                        <th>Total</th>
                        <th>Rate</th>
                        <th>Elapsed</th>
                    </tr>
                </thead>
                <tbody>{progress_rows}</tbody>
            </table>
            <h3>Status of async workers</h3>
            <table>
                <thead>
                    <tr>
                        <th>Name</th>
                        <th>State</th>
                        <th>Running for</th>
                        <th>Error Info</th>
                    </tr>
                </thead>
                <tbody>{workers_rows}</tbody>
            </table>
        </div>
    );
}
