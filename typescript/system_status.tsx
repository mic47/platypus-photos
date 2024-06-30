import { createRoot, Root } from "react-dom/client";
import React from 'react';

import { Switchable } from "./switchable.ts";
import * as pygallery_service from "./pygallery.generated/services.gen.ts";
import { pretty_print_duration } from "./utils.ts";

export class SystemStatus {
    public switchable: Switchable;
    private root: Root;
    constructor(private div_id: string) {
        const element = document.getElementById(this.div_id);
        if (element === null) {
            throw new Error(`Unable to find element ${this.div_id}`)
        }
        this.root = createRoot(element);
        this.switchable = new Switchable();
    }

    fetch() {
        this.switchable.call_or_store("fetch", () => {
            return pygallery_service.systemStatusGet().then((data) => {
                const progress_rows = data.progress_bars.map((bar) => {
                    const total = bar[1].total===0?"":bar[1].total.toString();
                    const rate = bar[1].rate===null?"":(Math.round(bar[1].total * 10) / 10).toString();
                    const elapsed = bar[1].elapsed===null?"":(pretty_print_duration(bar[1].elapsed) || "0s")
                    return (<tr key={bar[0]}>
                      <td className="center">{bar[0]}</td>
                      <td>{bar[1].desc}</td>
                      <td className="center">{bar[1].progress}</td>
                      <td className="center">{total}</td>
                      <td className="center">{rate}</td>
                      <td className="center">{elapsed}</td>
                    </tr>)
                })
                const workers_rows = Object.values(data.current_state).map((worker) => {
                    const duration = pretty_print_duration(Date.now() / 1000 - worker.when)
                    const exception = []
                    if (worker.exception !== null) {
                        if (worker.exception.exc_tb !== null) {
                            exception.push(...worker.exception.exc_tb.map((ex) => <>{ex}<br/></>))
                        }
                        exception.push(<>{worker.exception.exc_type || ""}: {worker.exception.exc_val || ""}<br/></>)
                    }
                    return <tr key={worker.name}>
                      <td>{worker.name}</td>
                      <td className="center">{worker.state}</td>
                      <td className="center">{duration}</td>
                      <td>{exception}</td>
                    </tr>
                })
                this.root.render(
                  <div>
                    <h3>Progress of server queues</h3>
                    <table>
                      <tr>
                        <th>ID</th>
                        <th>Description</th>
                        <th>Progress</th>
                        <th>Total</th>
                        <th>Rate</th>
                        <th>Elapsed</th>
                      </tr>
                      {progress_rows}
                    </table>
                    <h3>Status of async workers</h3>
                    <table>
                      <tr>
                        <th>Name</th>
                        <th>State</th>
                        <th>Since</th>
                        <th>Error Info</th>
                      </tr>
                      {workers_rows}
                    </table>
                  </div>
                )
            })
        });
    }
}
