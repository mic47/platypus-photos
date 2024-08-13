import React from "react";
import { Button, Text, View, StyleSheet, TextInput } from "react-native";

import { SearchQuery } from "@/components/pygallery.generated/types.gen";
import { Updateable } from "./GlobalState";
import DatePicker from "react-native-date-picker";

export function InputForm({
    query,
    submit,
    endpoint,
}: {
    query: Updateable<SearchQuery>;
    submit: () => void;
    endpoint: Updateable<string>;
}) {
    const stringField = (
        field: "tag" | "cls" | "addr" | "directory" | "camera" | "identity",
    ) => {
        const f = query.value[field];
        return {
            value: f === undefined ? null : f,
            update: (value: string | null) => {
                const ret = { ...query.value };
                if (value === "" || value === null) {
                    delete ret[field];
                } else {
                    ret[field] = value;
                }
                query.update(ret);
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
            <TextField
                prefix="🕸️"
                suffix="(server)"
                control={{
                    value: endpoint.value,
                    update: (value) =>
                        endpoint.update(value === null ? "" : value),
                }}
                hideReset={true}
            />
            <Text>
                {"     "}✈️{"     "}☀️{"          "}☁️☁️☁️☁️☁️🌧️⛈️🌧️🌧️🌧️
            </Text>
            <Text>🛫🌱🌊🌊🌊🦆〰️〰️〰️〰️〰️〰️〰️〰️🚢〰️〰️</Text>
            <TextField
                prefix="🏷️"
                suffix="(tags)"
                control={stringField("tag")}
            />
            <TextField
                prefix="📝"
                suffix="(text)"
                control={stringField("cls")}
            />
            <TextField
                prefix="📭"
                suffix="(address)"
                control={stringField("addr")}
            />
            <TextField
                prefix="🤓"
                suffix="(identity)"
                control={stringField("identity")}
            />
            <TextField
                prefix="📁"
                suffix="(folder)"
                control={stringField("directory")}
            />
            <TextField
                prefix="📷"
                suffix="(camera)"
                control={stringField("camera")}
            />
            <DateField
                prefix="🕰️"
                text="Date From"
                control={{
                    value:
                        query.value.tsfrom === undefined ||
                        query.value.tsfrom === null
                            ? null
                            : new Date(query.value.tsfrom * 1000),
                    update: (value) => {
                        if (value === null) {
                            const ret = { ...query.value };
                            delete ret.tsfrom;
                            query.update(ret);
                        } else {
                            query.update({
                                ...query.value,
                                tsfrom: value.valueOf() / 1000,
                            });
                        }
                    },
                }}
            />
            <DateField
                prefix="⌚"
                text="Date To"
                control={{
                    value:
                        query.value.tsto === undefined ||
                        query.value.tsto === null
                            ? null
                            : new Date(query.value.tsto * 1000),
                    update: (value) => {
                        if (value === null) {
                            const ret = { ...query.value };
                            delete ret.tsto;
                            query.update(ret);
                        } else {
                            query.update({
                                ...query.value,
                                tsto: value.valueOf() / 1000 + 86400,
                            });
                        }
                    },
                }}
            />
            <Button title="Submit" onPress={() => submit()} />
        </View>
    );
}

function DateField({
    prefix,
    text,
    control: { value, update },
}: {
    prefix: string;
    text: string;
    control: Updateable<Date | null>;
}) {
    const [open, changeOpen] = React.useState(false);
    return (
        <View style={styles.inputView}>
            <Button
                title="reset"
                onPress={() => {
                    update(null);
                }}
            />
            <Text>{prefix}</Text>
            <Button title={text} onPress={() => changeOpen(true)} />
            <Text style={{ flex: 1 }}>
                {value === null ? null : value.toString()}
            </Text>
            <DatePicker
                modal
                mode="date"
                open={open}
                date={value === null ? new Date(Date.now()) : value}
                onConfirm={(date) => {
                    console.log(date);
                    changeOpen(false);
                    update(date);
                }}
                onCancel={() => {
                    changeOpen(false);
                }}
            />
        </View>
    );
}

function TextField({
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
