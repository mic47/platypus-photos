import React from "react";
import { router } from "expo-router";

import { SearchQuery } from "@/components/pygallery.generated/types.gen";
import { QueryContext } from "@/components/GlobalState";
import { InputForm } from "@/components/InputForm";
import AsyncStorage from "@react-native-async-storage/async-storage";
import { OpenAPI } from "@/components/pygallery.generated";

export default function Page() {
    const { value: query, update: updateQuery } =
        React.useContext(QueryContext);
    const [endpoint, updateEndpoint] = React.useState<string>(
        "http://10.0.2.2:8000",
    );
    React.useEffect(() => {
        OpenAPI.BASE = endpoint;
        updateQuery({ ...query });
    }, [endpoint]);
    React.useEffect(() => {
        AsyncStorage.getItem("endpoint")
            .then((value) => {
                console.log("Received data from local storage", value);
                if (value !== null) {
                    updateEndpoint(value);
                }
            })
            .catch((e) => {
                console.log("Error while getting data from async storage", e);
            });
    }, []);
    const updateEndpointFn = (newEndpoint: string) => {
        updateEndpoint(newEndpoint);
        AsyncStorage.setItem("endpoint", newEndpoint)
            .catch((e) => {
                console.log("Error while writing data to async storage", e);
            })
            .then((x) =>
                console.log("Stored data in local storage", x, newEndpoint),
            );
    };
    // TODO: use query to preselect values?
    return (
        <InputForm
            submit={(query: SearchQuery) => {
                updateQuery(query);
                router.push("/galleryBrowser");
            }}
            endpoint={{
                value: endpoint,
                update: updateEndpointFn,
            }}
        />
    );
}
