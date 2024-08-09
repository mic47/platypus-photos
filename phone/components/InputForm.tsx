import React from "react";
import { Button, Text, View, StyleSheet, TextInput } from "react-native";

import { SearchQuery } from "@/components/pygallery.generated/types.gen";
import { Updateable } from "./GlobalState";

export function InputForm({
    submit,
    endpoint,
}: {
    submit: (query: SearchQuery) => void;
    endpoint: Updateable<string>;
}) {
    const [query, changeQuery] = React.useState<SearchQuery>({});
    const stringField = (
        field: "tag" | "cls" | "addr" | "directory" | "camera" | "identity",
    ) => {
        const f = query[field];
        return {
            value: f === undefined ? null : f,
            update: (value: string | null) => {
                const ret = { ...query };
                if (value === "" || value === null) {
                    delete ret[field];
                } else {
                    ret[field] = value;
                }
                changeQuery(ret);
            },
        };
    };
    return (
        <View
            style={{
                flex: 1,
                justifyContent: "center",
                alignItems: "center",
            }}
        >
            <InputField
                prefix="🕸️"
                suffix="(server)"
                control={{
                    value: endpoint.value,
                    update: (value) =>
                        endpoint.update(value === null ? "" : value),
                }}
                hideReset={true}
            />
            <Text>🌱〰️〰️〰️🦆〰️〰️〰️〰️〰️〰️〰️〰️🚢〰️〰️</Text>
            <InputField
                prefix="🏷️"
                suffix="(tags)"
                control={stringField("tag")}
            />
            <InputField
                prefix="📝"
                suffix="(text)"
                control={stringField("cls")}
            />
            <InputField
                prefix="📭"
                suffix="(address)"
                control={stringField("addr")}
            />
            <InputField
                prefix="🤓"
                suffix="(identity)"
                control={stringField("identity")}
            />
            <InputField
                prefix="📁"
                suffix="(folder)"
                control={stringField("directory")}
            />
            <InputField
                prefix="📷"
                suffix="(camera)"
                control={stringField("camera")}
            />
            <Button title="Submit" onPress={() => submit(query)} />
        </View>
    );
}

function InputField({
    prefix,
    suffix,
    control: { value, update },
    hideReset,
}: {
    prefix: string;
    suffix: string;
    control: Updateable<string | null>;
    hideReset?: boolean;
}) {
    return (
        <View style={styles.inputView}>
            {hideReset === true ? null : (
                <Button
                    title="reset"
                    onPress={() => {
                        update("");
                    }}
                />
            )}
            <Text>{prefix}</Text>
            <TextInput
                style={styles.textInput}
                editable
                onChangeText={(text) => update(text)}
                value={value || ""}
            ></TextInput>
            <Text>{suffix}</Text>
        </View>
    );
}

const styles = StyleSheet.create({
    textInput: {
        margin: 3,
        borderWidth: 1,
        padding: 3,
        flex: 1,
    },
    inputView: {
        flexDirection: "row",
        justifyContent: "center",
        alignItems: "center",
        flexWrap: "wrap",
    },
});
