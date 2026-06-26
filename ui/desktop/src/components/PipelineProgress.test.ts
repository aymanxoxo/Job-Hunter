import { mount } from "@vue/test-utils";
import { createPinia, setActivePinia } from "pinia";
import { beforeEach, describe, expect, it } from "vitest";

import { usePipelineStore } from "@/stores/pipeline";
import PipelineProgress from "./PipelineProgress.vue";

describe("PipelineProgress", () => {
  beforeEach(() => {
    document.body.innerHTML = "";
    setActivePinia(createPinia());
  });

  it("shows partial connector failures and zero-result connector rows", () => {
    const store = usePipelineStore();
    store.events = [
      { type: "progress", run_id: "run-1", stage: "search", state: "active" },
      {
        type: "progress",
        run_id: "run-1",
        stage: "search",
        state: "done",
        connector: "mock",
        message: "0 results",
        metric: { jobs: 0 },
      },
      {
        type: "progress",
        run_id: "run-1",
        stage: "search",
        state: "failed",
        connector: "adzuna",
        message: "connector failed",
        metric: { jobs: 0 },
      },
      {
        type: "progress",
        run_id: "run-1",
        stage: "search",
        state: "done",
        metric: { jobs: 0 },
      },
      { type: "progress", run_id: "run-1", stage: "export", state: "done" },
    ];
    store.status = "succeeded";
    store.results = [];

    const wrapper = mount(PipelineProgress, { attachTo: document.body });

    expect(wrapper.text()).toContain("mock");
    expect(wrapper.text()).toContain("0 jobs");
    expect(wrapper.text()).toContain("adzuna");
    expect(wrapper.text()).toContain("failed");
    expect(wrapper.text()).toContain("Partial: adzuna failed");
    expect(wrapper.text()).toContain("0 from mock");
  });
});
