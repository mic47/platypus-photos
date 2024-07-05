import React from "react";

import { SortBy, SortOrder, SortParams } from "./pygallery.generated";

interface SortFormViewProps {
    sort: SortParams;
    update_sort: (update: SortParams) => void;
}

export function SortFormView({ sort, update_sort }: SortFormViewProps) {
    return (
        <div>
            Sort by{" "}
            <select
                defaultValue={sort.sort_by}
                onChange={(event) =>
                    update_sort({ sort_by: event.target.value as SortBy })
                }
            >
                <option value="TIMESTAMP">time 🕰️</option>
                <option value="RANDOM">Random 🎲</option>
            </select>{" "}
            in{" "}
            <select
                defaultValue={sort.order}
                onChange={(event) =>
                    update_sort({ order: event.target.value as SortOrder })
                }
            >
                <option value="DESC">descending 🤿</option>
                <option value="ASC">ascending 🧗</option>
            </select>{" "}
            order.
            <br />
        </div>
    );
}
