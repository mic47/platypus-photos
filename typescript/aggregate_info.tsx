import React from "react";

import {
    GalleryPaging,
    ImageAggregation,
    SearchQuery,
} from "./pygallery.generated/types.gen";
import { append_flag } from "./utils";

interface AggregateInfoViewProps {
    aggr: ImageAggregation;
    paging: GalleryPaging;
    show_links: boolean;
    callbacks: {
        update_url_add_tag: (tag: string) => void;
        update_url: (update: SearchQuery) => void;
        set_page: (page: number) => void;
    };
}

export function AggregateInfoView({
    aggr,
    paging,
    show_links,
    callbacks: { update_url_add_tag, update_url, set_page },
}: AggregateInfoViewProps) {
    const num_pages = Math.ceil(aggr.total / (paging.paging || 100));
    const tags = Object.entries(aggr.tag)
        .sort(([, a], [, b]) => b - a)
        .slice(0, 15)
        .flatMap(([tag, num]) => {
            if (show_links) {
                return [
                    <a
                        key={tag}
                        onClick={() => update_url_add_tag(tag)}
                        href="#"
                    >
                        {tag} ({num})
                    </a>,
                    " ",
                ];
            } else {
                return [
                    <>
                        {tag} ({num}){" "}
                    </>,
                ];
            }
        });
    const texts = Object.entries(aggr.classification)
        .sort(([, a], [, b]) => b - a)
        .slice(0, 5)
        .flatMap(([text, num]) => {
            if (show_links) {
                return [
                    <a
                        key={text}
                        onClick={() => update_url({ cls: text })}
                        href="#"
                    >
                        {text} ({num})
                    </a>,
                    " ",
                ];
            } else {
                return [
                    <>
                        {text} ({num}){" "}
                    </>,
                ];
            }
        });
    const locs = Object.entries(aggr.address)
        .sort(([, a], [, b]) => b - a)
        .slice(0, 15)
        .flatMap(([loc, num]) => {
            if (show_links) {
                return [
                    <a
                        key={loc}
                        onClick={() => update_url({ addr: loc })}
                        href="#"
                    >
                        {append_flag(loc)} ({num})
                    </a>,
                    " ",
                ];
            } else {
                return [
                    <>
                        {append_flag(loc)} ({num}){" "}
                    </>,
                ];
            }
        });
    const cameras = Object.entries(aggr.cameras)
        .sort(([, a], [, b]) => b - a)
        .slice(0, 15)
        .flatMap(([camera, num]) => {
            if (show_links || camera in ["unknown", "other", "distinct"]) {
                return [
                    <a
                        key={camera}
                        onClick={() => update_url({ camera: camera })}
                        href="#"
                    >
                        {camera} ({num})
                    </a>,
                    " ",
                ];
            } else {
                return [
                    <>
                        {camera} ({num}){" "}
                    </>,
                ];
            }
        });
    const pages = [...Array(num_pages).keys()]
        .filter((page) => page <= 10 || page >= num_pages - 10)
        .flatMap((page) => {
            if (page !== 10) {
                if (page === paging.page) {
                    return <b key={page}> {page} </b>;
                } else {
                    return [
                        <a key={page} href="#" onClick={() => set_page(page)}>
                            {page}
                        </a>,
                        " ",
                    ];
                }
            } else {
                return [" ... "];
            }
        });
    return (
        <div>
            Found {aggr.total} matches.
            <br />
            Top tags: {tags}
            <br />
            Top texts: {texts}
            <br />
            Top locs: {locs}
            <br />
            Cameras: {cameras}
            <br />
            {show_links === false ? null : (
                <>
                    Go to page: {pages}
                    <br />
                </>
            )}
        </div>
    );
}
