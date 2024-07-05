import { Chart, ChartEvent, TooltipItem } from "chart.js/auto";
import { getRelativePosition } from "chart.js/helpers";
import "chartjs-adapter-date-fns";
import { ColorAssigner } from "./color_assigner.ts";
import { FLAGS, pprange, pretty_print_duration } from "./utils.ts";
import { Switchable } from "./switchable.ts";
import {
    DateCluster,
    DateClusterGroupBy,
    SearchQuery,
} from "./pygallery.generated/types.gen.ts";

import * as pygallery_service from "./pygallery.generated/services.gen.ts";

export class Dates {
    public switchable: Switchable;
    private clickTimeStart: null | [number, number];
    private chart: Chart;
    private colors: ColorAssigner;
    constructor(
        div_id: string,
        update_url: (data: SearchQuery) => void,
        private tooltip_div: string,
        private group_by_div: string,
    ) {
        this.colors = new ColorAssigner([{ hue: 0, label: OVERFETCHED_LABEL }]);
        this.switchable = new Switchable();
        this.clickTimeStart = null;
        const ctx = document.getElementById(div_id);
        if (ctx === null) {
            throw new Error(`Unable to find element ${div_id}`);
        }
        this.chart = new Chart(ctx as HTMLCanvasElement, {
            type: "line",
            data: {
                datasets: [],
            },
            options: {
                events: ["mousedown", "mouseup"],
                parsing: false,
                scales: {
                    y: {
                        type: "logarithmic",
                    },
                    x: {
                        type: "time",
                        time: {
                            displayFormats: {
                                quarter: "MMM YYYY",
                            },
                        },
                    },
                },
                plugins: {
                    tooltip: {
                        callbacks: {
                            afterFooter: function (
                                context: TooltipItem<"line">[],
                            ) {
                                const tooltip =
                                    document.getElementById(tooltip_div);
                                if (tooltip === null) {
                                    throw new Error(
                                        `${tooltip_div} was not found`,
                                    );
                                }
                                const cluster = (
                                    context[0].raw as {
                                        cluster: DateCluster;
                                    }
                                ).cluster;
                                const duration = pretty_print_duration(
                                    cluster.bucket_max - cluster.bucket_min,
                                );
                                const start = pprange(
                                    cluster.min_timestamp,
                                    cluster.max_timestamp,
                                );
                                const image_md5 = cluster.example_path_md5;
                                const selections =
                                    Object.entries(cluster.group_by)
                                        .filter(
                                            ([, x]) =>
                                                x !== null && x !== undefined,
                                        )
                                        .map(([k, x]) => {
                                            const flag =
                                                k === "country" &&
                                                typeof x === "string"
                                                    ? FLAGS[x.toLowerCase()]
                                                    : undefined;
                                            if (flag === undefined) {
                                                if (typeof x === "boolean") {
                                                    return `${k}=${x}`;
                                                } else {
                                                    return x;
                                                }
                                            } else {
                                                return `${x} ${flag}`;
                                            }
                                        })
                                        .join(", ") || "";
                                const innerHtml2 = `
<div class="date_tooltip">
Selected time aggregation: ${selections}<br/>
${start}<br/>
${cluster.total} images, ${duration} bucket<br/>
<button onclick="window.APP.update_url({tsfrom: ${cluster.min_timestamp - 0.01}, tsto: ${cluster.max_timestamp + 0.01}})">➡️ from &amp; to ⬅️ </button>
<button onclick="window.APP.update_url({tsfrom: ${cluster.min_timestamp - 0.01}})">➡️ from</button>
<button onclick="window.APP.update_url({tsto: ${cluster.max_timestamp + 0.01}})">to ⬅️ </button><br/>
<img loading="lazy" src="/img?hsh=${image_md5}&size=preview" class="gallery_image" />
</div>
        `;
                                tooltip.innerHTML = innerHtml2;
                            },
                        },
                    },
                },
            },
            plugins: [
                {
                    id: "Events",
                    beforeEvent: (
                        chart: Chart,
                        args: { event: ChartEvent },
                    ) => {
                        const event = args.event;

                        const canvasPosition =
                            // eslint-disable-next-line @typescript-eslint/no-explicit-any
                            getRelativePosition(event, chart as any); // Reason for any is that I am not sure what type to put there, and don't really care
                        const dataX: number | undefined =
                            chart.scales.x.getValueForPixel(canvasPosition.x);
                        if (dataX === undefined) {
                            return;
                        }
                        if (event.type === "mousedown") {
                            this.clickTimeStart = [canvasPosition.x, dataX];
                        } else if (event.type === "mouseup") {
                            if (this.clickTimeStart === null) {
                                return;
                            }
                            if (
                                Math.abs(
                                    canvasPosition.x - this.clickTimeStart[0],
                                ) > 1
                            ) {
                                const x = [
                                    this.clickTimeStart[1] / 1000.0,
                                    dataX / 1000.0,
                                ];
                                x.sort((x, y) => {
                                    if (x < y) {
                                        return -1;
                                    } else if (x > y) {
                                        return 1;
                                    } else {
                                        return 0;
                                    }
                                });
                                const [f, t] = x;
                                update_url({
                                    tsfrom: f,
                                    tsto: t,
                                });
                            }
                        }
                    },
                },
            ],
        });
    }

    fetch(location_url_json: SearchQuery) {
        return this.switchable.call_or_store("fetch", () => {
            const tool = document.getElementById(this.tooltip_div);
            if (tool !== null && tool !== undefined) {
                tool.innerHTML = "";
            }
            // TODO: move this off
            const group_by = [];
            const elements = document.getElementsByClassName(this.group_by_div);
            for (let i = 0; i < elements.length; i++) {
                const element = elements[i] as HTMLInputElement;
                if (element.checked) {
                    group_by.push(element.value);
                }
            }
            pygallery_service
                .dateClustersEndpointPost({
                    requestBody: {
                        url: location_url_json,
                        group_by: group_by as DateClusterGroupBy[],
                        buckets: 100,
                    },
                })
                .then((clusters) => {
                    const datasets = clusters_to_datasets(clusters);
                    const newDatasets = this.chart.data.datasets.map(
                        (oldDataset) => {
                            const label = oldDataset.label;
                            if (label === undefined) {
                                return null;
                            }
                            const newDataset = datasets[label];
                            if (newDataset === undefined) {
                                this.colors.remove(label);
                                return null;
                            }
                            newDataset.backgroundColor = this.colors.get_str(
                                newDataset.label,
                            );
                            delete datasets[label];
                            return newDataset;
                        },
                    );
                    for (const dataset of Object.values(datasets)) {
                        dataset.backgroundColor = this.colors.get_str(
                            dataset.label,
                        );
                        newDatasets.push(dataset);
                    }
                    this.chart.data.datasets = newDatasets.filter(
                        (x) => x !== null,
                    );
                    this.chart.update();
                });
        });
    }
}

const OVERFETCHED_LABEL = "❌⌚";
type DatasetPoints = {
    [label: string]: {
        label: string;
        data: Array<{ x: number; y: number; cluster: DateCluster }>;
        borderWidth: number;
        showLine: boolean;
        backgroundColor?: string;
    };
};
function clusters_to_datasets(clusters: DateCluster[]): DatasetPoints {
    const data_points: DatasetPoints = {};
    function to_datapoint(c: DateCluster) {
        return {
            x: c.avg_timestamp * 1000,
            y: c.total,
            cluster: c,
        };
    }
    clusters.forEach((cluster) => {
        let label = "⁉️";
        if (cluster.overfetched) {
            label = OVERFETCHED_LABEL;
        } else {
            label =
                Object.entries(cluster.group_by)
                    .filter(([, x]) => x !== null && x !== undefined)
                    .map(([k, x]) => {
                        const flag =
                            k === "country" && typeof x === "string"
                                ? FLAGS[x.toLowerCase()]
                                : undefined;
                        if (flag === undefined) {
                            if (typeof x === "boolean") {
                                return `${k}=${x}`;
                            } else {
                                return x;
                            }
                        } else {
                            return flag;
                        }
                    })
                    .join(" ") || "selected";
        }
        if (data_points[label] === undefined) {
            data_points[label] = {
                label,
                data: [],
                borderWidth: 1,
                showLine: false,
            };
        }
        data_points[label].data.push(to_datapoint(cluster));
    });
    return data_points;
}
