import React from "react";
import { SearchQuery } from "./pygallery.generated/types.gen";
import { Button, Text, View, StyleSheet, TextInput } from "react-native";
import { QueryContext } from "./globalState";
import { router } from "expo-router";

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

function InputForm({ submit }: { submit: (query: SearchQuery) => void }) {
    const [query, changeQuery] = React.useState<SearchQuery>({});
    const stringField = (
        field: "tag" | "cls" | "addr" | "directory" | "camera" | "identity",
    ) => {
        const f = query[field];
        return {
            value: f === undefined ? null : f,
            changeValue: (value: string) => {
                const ret = { ...query };
                if (value === "") {
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
    control: { value, changeValue },
}: {
    prefix: string;
    suffix: string;
    control: {
        value: string | null;
        changeValue: (text: string) => void;
    };
}) {
    return (
        <View style={styles.inputView}>
            <Button
                title="reset"
                onPress={() => {
                    changeValue("");
                }}
            />
            <Text>{prefix}</Text>
            <TextInput
                style={styles.textInput}
                editable
                onChangeText={(text) => changeValue(text)}
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
