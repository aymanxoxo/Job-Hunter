import { mount } from "@vue/test-utils";
import { createPinia, setActivePinia } from "pinia";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { defineComponent } from "vue";

import { usePipelineStore } from "@/stores/pipeline";
import App from "./App.vue";

const route = vi.hoisted(() => ({
  meta: { title: "Criteria" },
}));

vi.mock("vue-router", () => ({
  RouterLink: defineComponent({
    props: {
      to: { type: String, required: true },
    },
    template: '<a :href="to"><slot /></a>',
  }),
  RouterView: defineComponent({
    template: '<main data-testid="route-view" />',
  }),
  useRoute: () => route,
}));

describe("App shell", () => {
  beforeEach(() => {
    document.body.innerHTML = "";
    setActivePinia(createPinia());
  });

  it("keeps the pipeline progress surface connected to running store state", async () => {
    const store = usePipelineStore();
    const wrapper = mount(App, { attachTo: document.body });

    expect(wrapper.find("[data-testid='app-pipeline-progress']").exists()).toBe(false);

    store.recordProgress({
      type: "progress",
      stage: "search",
      state: "active",
      run_id: "run-1",
      metric: { jobs: 3 },
    });
    await wrapper.vm.$nextTick();

    expect(wrapper.find("[data-testid='app-pipeline-progress']").exists()).toBe(true);
    expect(wrapper.text()).toContain("Pipeline running");
    expect(wrapper.text()).toContain("Search");
  });
});
