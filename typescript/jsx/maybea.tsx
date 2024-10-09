import React from "react";

export function MaybeA({
    onClick,
    children,
}: React.PropsWithChildren<{ onClick: null | (() => void) }>) {
    if (onClick === null) {
        return <>{children}</>;
    } else {
        return (
            <a href="#" onClick={onClick}>
                {children}
            </a>
        );
    }
}
