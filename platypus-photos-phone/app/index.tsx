import React from "react";
import { router } from "expo-router";

import { SearchQuery } from "@/components/pygallery.generated/types.gen";
import { QueryContext } from "@/components/GlobalState";
import { InputForm } from "@/components/InputForm";

export default function Page() {
    const { value: query, update: updateQuery } =
        React.useContext(QueryContext);
    // TODO: use query to preselect values?
    return (
        <InputForm
            submit={(query: SearchQuery) => {
                updateQuery(query);
                router.replace("/galleryBrowser");
            }}
        />
    );
}
