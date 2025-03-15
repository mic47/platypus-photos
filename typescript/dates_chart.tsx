import React from "react";

import { Chart, ChartEvent, TooltipItem } from "chart.js/auto";
import { getRelativePosition } from "chart.js/helpers";
import "date-fns";
import "chartjs-adapter-date-fns";
import { ColorAssigner } from "./color_assigner.ts";
import { FLAGS, pprange, pretty_print_duration } from "./utils.ts";
import {
    DateCluster,
    DateClusterGroupBy,
    SearchQuery,
} from "./pygallery.generated/types.gen.ts";

import * as pygallery_service from "./pygallery.generated/sdk.gen.ts";
import { UpdateCallbacks } from "./types.ts";

interface DatesComponentProps {
    query: SearchQuery;
    queryCallbacks: UpdateCallbacks<SearchQuery>;
}
export function DatesComponent({ query, queryCallbacks }: DatesComponentProps) {
    const dateContainerElementRef = React.useRef<null | HTMLCanvasElement>(
        null,
    );
    const dateRef = React.useRef<null | Dates>(null);

    const [groupBy, updateGroupBy] = React.useState<Set<string>>(new Set());
    const [selectedDateCluster, updateSelectedDateCluster] =
        React.useState<null | DateCluster>(null);
    const getDates = (): Dates => {
        if (dateRef.current === null) {
            dateRef.current = new Dates(
                dateContainerElementRef.current as HTMLCanvasElement,
                query,
                queryCallbacks,
                groupBy,
                updateSelectedDateCluster,
            );
        }
        return dateRef.current;
    };
    React.useEffect(() => {
        getDates().setSearchQuery(query).render();
    }, [query]);
    React.useEffect(() => {
        getDates().setGroupBy(groupBy).render();
    }, [groupBy]);
    const groupByItems = [
        ["country", "Country"],
        ["camera", "Camera"],
        ["has_location", "Has Location"],
        ["address_name", "Name of the Place"],
    ];
    return (
        <div>
            Group by:{" "}
            {groupByItems.flatMap(([key, text]) => [
                <input
                    key={key}
                    type="checkbox"
                    value={key}
                    onChange={(event) => {
                        const s = new Set(groupBy);
                        if (event.target.checked) {
                            s.add(key);
                        } else {
                            s.delete(key);
                        }
                        updateGroupBy(s);
                    }}
                />,
                text,
            ])}
            <div className="row">
                <div className="column">
                    <div className="date_chart">
                        <canvas ref={dateContainerElementRef}></canvas>
                    </div>
                </div>
                <div className="column">
                    <DateClusterTooltip
                        cluster={selectedDateCluster}
                        queryCallbacks={queryCallbacks}
                    />
                    <div id="DateSelection"></div>
                </div>
            </div>
        </div>
    );
}

function DateClusterTooltip({
    cluster,
    queryCallbacks,
}: {
    cluster: null | DateCluster;
    queryCallbacks: UpdateCallbacks<SearchQuery>;
}) {
    if (cluster === null) {
        return null;
    }
    const duration = pretty_print_duration(
        cluster.bucket_max - cluster.bucket_min,
    );
    const start = pprange(cluster.min_timestamp, cluster.max_timestamp);
    const image_md5 = cluster.example_path_md5;
    const image_extension = cluster.example_path_extension;
    const selections =
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
                    return `${x} ${flag}`;
                }
            })
            .join(", ") || "";
    return (
        <div className="date_tooltip">
            Selected time aggregation: {selections}
            <br />
            {start}
            <br />
            {cluster.total} images, {duration} bucket
            <br />
            <button
                onClick={() => {
                    queryCallbacks.update({
                        tsfrom: cluster.min_timestamp - 0.01,
                        tsto: cluster.max_timestamp + 0.01,
                    });
                }}
            >
                ➡️ from &amp; to ⬅️{" "}
            </button>
            <button
                onClick={() => {
                    queryCallbacks.update({
                        tsfrom: cluster.min_timestamp - 0.01,
                    });
                }}
            >
                ➡️ from
            </button>
            <button
                onClick={() => {
                    queryCallbacks.update({
                        tsto: cluster.max_timestamp + 0.01,
                    });
                }}
            >
                to ⬅️{" "}
            </button>
            <br />
            <img
                loading="lazy"
                src={`/img/preview/${image_md5}.${image_extension}`}
                className="gallery_image"
            />
        </div>
    );
}

export class Dates {
    private clickTimeStart: null | [number, number];
    private chart: Chart;
    private colors: ColorAssigner;
    constructor(
        ctx: HTMLCanvasElement,
        private query: SearchQuery,
        private searchQueryCallbacks: UpdateCallbacks<SearchQuery>,
        private groupBy: Set<string>,
        private setTooltip: (cluster: DateCluster | null) => void,
    ) {
        this.colors = new ColorAssigner([{ hue: 0, label: OVERFETCHED_LABEL }]);
        this.clickTimeStart = null;
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
                            afterFooter: (context: TooltipItem<"line">[]) => {
                                const cluster = (
                                    context[0].raw as {
                                        cluster: DateCluster;
                                    }
                                ).cluster;
                                this.setTooltip(cluster);
                                /*
                                 */
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
                                this.searchQueryCallbacks.update({
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
    setGroupBy(groupBy: Set<string>) {
        this.groupBy = groupBy;
        return this;
    }

    setSearchQuery(query: SearchQuery) {
        this.query = query;
        return this;
    }

    render() {
        this.setTooltip(null);
        const group_by = [...this.groupBy];
        pygallery_service
            .dateClustersEndpointPost({
                requestBody: {
                    url: this.query,
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
