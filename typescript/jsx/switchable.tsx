import React from "react";

export function Switchable({
    switchedOn,
    children,
}: React.PropsWithChildren<{ switchedOn: boolean }>) {
    if (switchedOn) {
        return <>{children}</>;
    } else {
        return null;
    }
}

export function TabBar({
    items,
    setActive,
}: {
    setActive: (key: string, active: boolean) => void;
    items: { [key: string]: { text: string; active: boolean } };
}) {
    return (
        <div className="tab">
            {Object.entries(items).map(([key, { text, active }]) => {
                const classes = active ? "tablinks active" : "tablinks";
                return (
                    <button
                        key={key}
                        className={classes}
                        onClick={() => setActive(key, !active)}
                    >
                        {text}
                    </button>
                );
            })}
        </div>
    );
}
