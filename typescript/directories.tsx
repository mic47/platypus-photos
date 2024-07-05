import React from "react";

import {
    DirectoryStats,
    SearchQuery,
} from "./pygallery.generated/types.gen.ts";
import { Switchable } from "./switchable.ts";
import * as pygallery_service from "./pygallery.generated/services.gen.ts";
import { round, timestamp_to_pretty_datetime } from "./utils.ts";

export class Directories {
    public switchable: Switchable;
    constructor(private div_id: string) {
        this.switchable = new Switchable();
    }

    fetch(url_data: SearchQuery) {
        return this.switchable.call_or_store("fetch", () =>
            this.fetch_impl(url_data),
        );
    }

    fetch_impl(url_data: SearchQuery) {
        pygallery_service
            .directoriesEndpointPost({ requestBody: url_data })
            .then((text) => {
                const element = document.getElementById(this.div_id);
                if (element === null) {
                    throw new Error(`Unable to find element ${this.div_id}`);
                }
                element.innerHTML = text;
            });
    }
}

interface DirectoryTableProps {
    directories: DirectoryStats[];
}

export function DirectoryTable({ directories }: DirectoryTableProps) {
    const rows = directories.map((d, index) => {
        return (
            <tr key={index}>
                <td>{d.directory}</td>
                <td>{d.total_images}</td>
                <td>{round((d.has_location * 100.0) / d.total_images, 1)}%</td>
                <td>{round((d.has_timestamp * 100.0) / d.total_images, 1)}%</td>
                <td>
                    {round((d.being_annotated * 100.0) / d.total_images, 1)}%
                </td>
                <td>
                    {d.since === null
                        ? ""
                        : timestamp_to_pretty_datetime(d.since)}
                    {" - "}
                    {d.until === null
                        ? ""
                        : timestamp_to_pretty_datetime(d.until)}
                </td>
            </tr>
        );
    });
    return (
        <table>
            <thead>
                <tr>
                    <th>Directory 📂</th>
                    <th>
                        <div className="hasTooltip">
                            # 🖼️
                            <div className="tooltipText">Number of images</div>
                        </div>
                    </th>
                    <th>
                        <div className="hasTooltip">
                            % 🗺️
                            <div className="tooltipText">
                                Percentage of images with location
                            </div>
                        </div>
                    </th>
                    <th>
                        <div className="hasTooltip">
                            % 🕝
                            <div className="tooltipText">
                                Percentage of images with time
                            </div>
                        </div>
                    </th>
                    <th>
                        <div className="hasTooltip">
                            % 🏗️
                            <div className="tooltipText">
                                Percentage of images being annotated
                            </div>
                        </div>
                    </th>
                    <th>Time range</th>
                </tr>
            </thead>
            <tbody>{rows}</tbody>
        </table>
    );
}
