import React from "react";

import {
    DirectoryStats,
    SearchQuery,
} from "./pygallery.generated/types.gen.ts";
import { Switchable } from "./switchable.ts";
import * as pygallery_service from "./pygallery.generated/services.gen.ts";
import { round, timestamp_to_pretty_datetime } from "./utils.ts";
import { MaybeA } from "./jsx/maybea.tsx";

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
    callbacks: null | {
        update_url: (update: SearchQuery) => void;
    };
}

export function DirectoryTable({
    directories,
    callbacks,
}: DirectoryTableProps) {
    const rows = directories.map((d, index) => {
        const parts = [];
        let currentIndex = 0;
        while (true) {
            const next = d.directory.indexOf("/", currentIndex);
            if (next < 0) {
                parts.push([d.directory, d.directory.substring(currentIndex)]);
                break;
            }
            parts.push([
                d.directory.substring(0, next + 1),
                d.directory.substring(currentIndex, next + 1),
            ]);
            currentIndex = next + 1;
        }
        return (
            <tr key={index}>
                <td>
                    {parts.map(([dir, part]) => (
                        <span key={dir} className="pdir">
                            <MaybeA
                                onClick={
                                    callbacks === null
                                        ? null
                                        : () =>
                                              callbacks.update_url({
                                                  directory: dir,
                                              })
                                }
                            >
                                {part}
                            </MaybeA>
                        </span>
                    ))}
                </td>
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
