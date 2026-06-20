import { createPinia } from "pinia";
import { createApp } from "vue";

import "../../../design/v1.1/tokens.css";
import App from "./App.vue";
import router from "./router";
import "./styles/app.css";

createApp(App).use(createPinia()).use(router).mount("#app");
