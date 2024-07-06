import { init_fun as react_init_fun } from "./Application";

const app: object = {
    react_init_fun,
};
(window as unknown as { APP: object }).APP = app;
