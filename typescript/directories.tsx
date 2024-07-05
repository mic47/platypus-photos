import { createRoot, Root } from "react-dom/client";
import React from "react";

import {
    DirectoryStats,
    SearchQuery,
} from "./pygallery.generated/types.gen.ts";
import { Switchable } from "./switchable.ts";
import * as pygallery_service from "./pygallery.generated/services.gen.ts";
import { round, timestamp_to_pretty_datetime } from "./utils.ts";
import { MaybeA } from "./jsx/maybea.tsx";
import { StateWithHooks } from "./state.ts";

export class Directories {
    public switchable: Switchable;
    private root: Root;
    constructor(
        private div_id: string,
        searchQueryHook: StateWithHooks<SearchQuery>,
    ) {
        const element = document.getElementById(this.div_id);
        if (element === null) {
            throw new Error(`Unable to find element ${this.div_id}`);
        }
        this.root = createRoot(element);
        this.switchable = new Switchable();
        this.root.render(
            <DirectoryTableComponent
                id={this.div_id}
                searchQueryHook={searchQueryHook}
            />,
        );
    }
}

interface DirectoryTableComponentProps {
    id: string;
    searchQueryHook: StateWithHooks<SearchQuery>;
}
export function DirectoryTableComponent({
    id,
    searchQueryHook,
}: DirectoryTableComponentProps) {
    const [query, updateQuery] = React.useState<SearchQuery>(
        searchQueryHook.get(),
    );
    const [pending, updatePending] = React.useState<boolean>(true);
    const [directories, updateDirectories] = React.useState<
        null | DirectoryStats[]
    >([]);
    React.useEffect(() => {
        searchQueryHook.register_hook(id, (data) => {
            updateQuery(data);
        });
        return () => searchQueryHook.unregister_hook(id);
    });
    React.useEffect(() => {
        let ignore = false;
        updatePending(true);
        pygallery_service
            .matchingDirectoriesPost({
                requestBody: query,
            })
            .then((data) => {
                if (!ignore) {
                    updateDirectories(data);
                    updatePending(false);
                }
            });
        return () => {
            ignore = true;
        };
    }, [query]);
    if (directories !== null) {
        return (
            <>
                {pending ? "(pending)" : null}
                <DirectoryTable
                    directories={directories}
                    callbacks={{
                        update_url: (update) => searchQueryHook.update(update),
                    }}
                />
            </>
        );
    } else {
        return <div>(pending)</div>;
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
