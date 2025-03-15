import React from "react";

import { SearchQuery } from "./pygallery.generated/types.gen";
import * as pygallery_service from "./pygallery.generated/sdk.gen.ts";

interface ExportFormComponentProps {
    query: SearchQuery;
}
export function ExportFormComponent({ query }: ExportFormComponentProps) {
    const [baseOptions, updateBaseOptions] = React.useState<string[]>([]);
    React.useEffect(() => {
        let ignore = false;
        pygallery_service.configExportDirsEndpointGet().then((data) => {
            if (!ignore) {
                updateBaseOptions(data);
            }
        });
        return () => {
            ignore = true;
        };
    }, []);
    return <ExportFormView baseOptions={baseOptions} query={query} />;
}

interface ExportFormViewProps {
    baseOptions: string[];
    query: SearchQuery;
}

export function ExportFormView({ baseOptions, query }: ExportFormViewProps) {
    const [subdir, updateSubdir] = React.useState<string>("");
    return (
        <>
            <form action="/export" method="get">
                <input
                    type="hidden"
                    name="query"
                    value={JSON.stringify(query)}
                />
                <input
                    type="submit"
                    name="button"
                    value="💾 Download: Export current query as tar archive ⚠️"
                />
            </form>
            <br />
            <form action="/export_to_dir" method="get">
                <input
                    type="hidden"
                    name="query"
                    value={JSON.stringify(query)}
                />
                <input
                    type="submit"
                    name="button"
                    value="💾 Export current query to selected directory ⚠️"
                />
                <select name="base" id="base">
                    {baseOptions.map((option) => (
                        <option key={option} value={option}>
                            {option}
                        </option>
                    ))}
                </select>
                Subdirectory:
                <input
                    type="text"
                    name="subdir"
                    value={subdir}
                    onChange={(event) => updateSubdir(event.target.value)}
                />
            </form>
            <br />
        </>
    );
}
