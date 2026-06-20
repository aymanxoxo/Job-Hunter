import { createRouter, createWebHashHistory, type RouteRecordRaw } from "vue-router";

import CriteriaView from "@/views/CriteriaView.vue";
import ResultsView from "@/views/ResultsView.vue";
import SettingsView from "@/views/SettingsView.vue";

const routes: RouteRecordRaw[] = [
  { path: "/", redirect: "/criteria" },
  { path: "/criteria", component: CriteriaView, meta: { title: "Criteria" } },
  { path: "/results", component: ResultsView, meta: { title: "Results" } },
  { path: "/settings", component: SettingsView, meta: { title: "Settings" } },
];

export default createRouter({
  history: createWebHashHistory(),
  routes,
});
