import React from "react";

type CheckboxConfig = {
    shortcut: string;
    activated: boolean;
    text: string;
};

type MaterializedCheckboxes<K extends string> = {
    config: Record<K, CheckboxConfig>;
    checkboxes: Record<K, boolean>;
    updateCheckboxes: (x: Record<K, boolean>) => void;
};

export function useCheckboxesShortcuts<K extends string>(
    config: Record<K, CheckboxConfig>,
): MaterializedCheckboxes<K> {
    const checkboxesShortcuts = React.useMemo(() => {
        return Object.fromEntries(
            Object.entries(config).map(([key, value]) => {
                return [(value as CheckboxConfig).shortcut, key];
            }),
        );
    }, [config]);
    const [checkboxes, updateCheckboxes] = React.useState<Record<K, boolean>>(
        Object.fromEntries(
            Object.entries(config).map(([key, value]) => {
                return [key, (value as CheckboxConfig).activated];
            }),
        ) as Record<K, boolean>,
    );
    function flipCheckbox(checkbox: string | undefined) {
        if (checkbox === undefined) {
            return;
        }
        const value = checkboxes[checkbox as K];
        if (value === undefined) {
            return;
        }
        const newc = { ...checkboxes };
        newc[checkbox as K] = !value;
        updateCheckboxes(newc);
    }
    React.useEffect(() => {
        const handleKeyPress = (e: KeyboardEvent) => {
            if (
                e.target !== null &&
                e.target instanceof HTMLElement &&
                e.target.tagName === "INPUT"
            ) {
                return;
            }
            const checkbox = checkboxesShortcuts[e.key];
            if (checkbox === undefined) {
                return;
            }
            flipCheckbox(checkbox);
        };

        document.addEventListener("keydown", handleKeyPress);
        return () => document.removeEventListener("keydown", handleKeyPress);
    }, [checkboxes]);
    return {
        config,
        checkboxes,
        updateCheckboxes,
    };
}

export function Checkboxes<K extends string>({
    materialized: { config, checkboxes, updateCheckboxes },
}: {
    materialized: MaterializedCheckboxes<K>;
}) {
    function updateCheckboxFromMouseEvent(
        event: React.MouseEvent<HTMLInputElement, MouseEvent>,
    ) {
        const element = event.currentTarget;
        const newc = { ...checkboxes };
        newc[element.id as K] = element.checked;
        updateCheckboxes(newc);
    }
    const input = Object.entries(config).map(([identifier, config]) => {
        return (
            <>
                <input
                    type="checkbox"
                    key={identifier}
                    id={identifier}
                    checked={checkboxes[identifier as K]}
                    onClick={updateCheckboxFromMouseEvent}
                />
                [{(config as CheckboxConfig).shortcut}]{" "}
                {(config as CheckboxConfig).text}
            </>
        );
    });
    return <>{input}</>;
}
