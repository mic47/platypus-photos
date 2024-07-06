import { Dates } from "./dates_chart";
import { TabSwitch } from "./switchable";

import { init_fun as react_init_fun } from "./Application";

function init_fun() {
    /* Initialize state and url syncs */

    /* Dates */
    const dates = new Dates(
        "DateChart",
        () => {
            // ___state.search_query.update(x);
        },
        "DateSelection",
        "DateChartGroupBy",
    );

    /* Trigger redrawing of componentsl */
    // WARNING: here we assume that search_query will update everything
    // WARNING: here we assume that search_query will update everything

    /* Tab */
    new TabSwitch("RootTabs", {
        TabDates: dates.switchable,
    });
}

const app: object = {
    init_fun,
    react_init_fun,
};
(window as unknown as { APP: object }).APP = app;
