import { mount } from "@vue/test-utils";
import { createPinia, setActivePinia } from "pinia";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { usePipelineStore, type JobResult } from "@/stores/pipeline";
import ResultsView from "./ResultsView.vue";

const firstRun: JobResult[] = [
  {
    id: "job-1",
    title: "Platform Engineer",
    company: "Northstar",
    location: "Remote",
    source: "mock",
    posted_date: "2026-06-18",
    score: 92,
    description: "Own Kubernetes platform work.",
    match_reason: "Strong cloud and platform match.",
    red_flags: ["On-call rotation"],
    url: "https://example.test/job-1",
  },
  {
    id: "job-2",
    title: "Backend Engineer",
    company: "Cairo Labs",
    location: "Cairo",
    source: "adzuna",
    posted_date: "2026-06-15",
    score: 68,
    description: "Build APIs.",
    match_reason: "Good Python API fit.",
    red_flags: [],
    url: "https://example.test/job-2",
  },
  {
    id: "job-3",
    title: "Support Developer",
    company: "Quiet Desk",
    location: "Hybrid",
    source: "mock",
    posted_date: "2026-06-10",
    score: 35,
  },
  {
    id: "job-4",
    title: "Data Integrations Engineer",
    company: "Signal Forge",
    location: "Remote",
    source: "mock",
    posted_date: "2026-06-19",
    score: 47,
  },
];

function mountView(results = firstRun) {
  setActivePinia(createPinia());
  const store = usePipelineStore();
  store.results = [...results];
  store.lastRun = { profile: "Senior platform engineer", provider: "ollama" };
  return {
    store,
    wrapper: mount(ResultsView, {
      attachTo: document.body,
    }),
  };
}

function renderedTitles(wrapper: ReturnType<typeof mount>) {
  return wrapper.findAll("[data-testid='result-title']").map((cell) => cell.text());
}

describe("ResultsView", () => {
  beforeEach(() => {
    document.body.innerHTML = "";
    vi.restoreAllMocks();
  });

  it("hides scores below 40, can reveal them, and applies score band classes", async () => {
    const { wrapper } = mountView();

    expect(renderedTitles(wrapper)).toEqual([
      "Platform Engineer",
      "Backend Engineer",
      "Data Integrations Engineer",
    ]);
    expect(wrapper.text()).not.toContain("Support Developer");
    expect(wrapper.get("[data-testid='score-job-1']").classes()).toContain("score-green");
    expect(wrapper.get("[data-testid='score-job-2']").classes()).toContain("score-amber");
    expect(wrapper.get("[data-testid='score-job-4']").classes()).toContain("score-orange");

    await wrapper.get("[data-testid='toggle-hidden-results']").trigger("click");

    expect(renderedTitles(wrapper)).toEqual([
      "Platform Engineer",
      "Backend Engineer",
      "Data Integrations Engineer",
      "Support Developer",
    ]);
    expect(wrapper.get("[data-testid='score-job-3']").classes()).toContain("score-gray");
  });

  it("sorts table columns in both directions", async () => {
    const { wrapper } = mountView();

    await wrapper.get("[data-testid='sort-company']").trigger("click");
    expect(renderedTitles(wrapper)).toEqual([
      "Backend Engineer",
      "Platform Engineer",
      "Data Integrations Engineer",
    ]);

    await wrapper.get("[data-testid='sort-company']").trigger("click");
    expect(renderedTitles(wrapper)).toEqual([
      "Data Integrations Engineer",
      "Platform Engineer",
      "Backend Engineer",
    ]);
  });

  it("filters by title, company, location, and source text", async () => {
    const { wrapper } = mountView();

    await wrapper.get("[data-testid='results-filter']").setValue("adzuna cairo");

    expect(renderedTitles(wrapper)).toEqual(["Backend Engineer"]);
    expect(wrapper.text()).toContain("1 shown");
  });

  it("opens and closes the row detail panel", async () => {
    const { wrapper } = mountView();

    await wrapper.get("[data-testid='result-row-job-1']").trigger("click");

    expect(wrapper.get("[data-testid='result-detail']").text()).toContain("Own Kubernetes platform work.");
    expect(wrapper.get("[data-testid='result-detail']").text()).toContain("Strong cloud and platform match.");
    expect(wrapper.get("[data-testid='result-detail']").text()).toContain("On-call rotation");
    expect(wrapper.get("[data-testid='result-detail-link']").attributes("href")).toBe("https://example.test/job-1");

    await wrapper.get("[data-testid='detail-close']").trigger("click");
    expect(wrapper.find("[data-testid='result-detail']").exists()).toBe(false);
  });

  it("does not render the detail link for javascript: URLs", async () => {
    const { wrapper } = mountView([
      {
        id: "job-evil",
        title: "Malicious Job",
        company: "Bad Corp",
        location: "Remote",
        source: "mock",
        score: 85,
        url: "javascript:alert(document.cookie)",
      },
    ]);

    await wrapper.get("[data-testid='result-row-job-evil']").trigger("click");

    expect(wrapper.find("[data-testid='result-detail-link']").exists()).toBe(false);
  });

  it("merges newly run results with existing rows", async () => {
    const { store, wrapper } = mountView();
    vi.spyOn(store, "runPipeline").mockImplementation(async () => {
      store.results = [
        {
          id: "job-5",
          title: "Cloud Reliability Engineer",
          company: "Runsteady",
          location: "Remote",
          source: "mock",
          score: 88,
        },
      ];
    });

    await wrapper.get("[data-testid='rerun-results']").trigger("click");

    expect(renderedTitles(wrapper)).toEqual([
      "Platform Engineer",
      "Cloud Reliability Engineer",
      "Backend Engineer",
      "Data Integrations Engineer",
    ]);
    expect(store.runPipeline).toHaveBeenCalledWith({
      profile: "Senior platform engineer",
      provider: "ollama",
    });
  });

  // --- C-068 new tests below ---

  it("reads threshold from settings store config", async () => {
    setActivePinia(createPinia());
    const store = usePipelineStore();
    store.results = [...firstRun];
    store.lastRun = { profile: "Senior platform engineer", provider: "ollama" };

    const { useSettingsStore } = await import("@/stores/settings");
    const settings = useSettingsStore();
    settings.saveMinScore(60);

    const wrapper = mount(ResultsView, { attachTo: document.body });
    await wrapper.vm.$nextTick();

    // Only scores >= 60 should be visible
    expect(renderedTitles(wrapper)).toEqual([
      "Platform Engineer",
      "Backend Engineer",
    ]);
    expect(wrapper.text()).not.toContain("Support Developer");
    expect(wrapper.text()).not.toContain("Data Integrations Engineer");
  });

  it("falls back to 40 when settings store min_score is null", async () => {
    setActivePinia(createPinia());
    const store = usePipelineStore();
    store.results = [...firstRun];
    store.lastRun = { profile: "Senior platform engineer", provider: "ollama" };

    const { useSettingsStore } = await import("@/stores/settings");
    const settings = useSettingsStore();
    settings.saveMinScore(null);

    const wrapper = mount(ResultsView, { attachTo: document.body });
    await wrapper.vm.$nextTick();

    // Default 40pt behavior
    expect(renderedTitles(wrapper)).toEqual([
      "Platform Engineer",
      "Backend Engineer",
      "Data Integrations Engineer",
    ]);
  });

  it("reactively updates visible rows when threshold changes", async () => {
    setActivePinia(createPinia());
    const store = usePipelineStore();
    store.results = [...firstRun];
    store.lastRun = { profile: "Senior platform engineer", provider: "ollama" };

    const { useSettingsStore } = await import("@/stores/settings");
    const settings = useSettingsStore();
    settings.saveMinScore(40);

    const wrapper = mount(ResultsView, { attachTo: document.body });
    await wrapper.vm.$nextTick();

    // At 40, Data Integrations Engineer (score 47) is visible
    expect(renderedTitles(wrapper)).toContain("Data Integrations Engineer");

    // Change threshold to 70 — only scores >= 70 visible
    settings.saveMinScore(70);
    await wrapper.vm.$nextTick();

    expect(renderedTitles(wrapper)).toEqual(["Platform Engineer"]);
    expect(wrapper.text()).not.toContain("Backend Engineer");
    expect(wrapper.text()).not.toContain("Data Integrations Engineer");
    expect(wrapper.text()).not.toContain("Support Developer");
  });
});
