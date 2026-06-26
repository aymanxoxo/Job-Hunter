import { flushPromises, mount } from "@vue/test-utils";
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
    localStorage.clear();
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

  it("exports currently visible sorted rows through the pipeline store", async () => {
    const { store, wrapper } = mountView();
    const exportSpy = vi.spyOn(store, "exportResults").mockResolvedValue([
      "C:\\Users\\ayman\\JobHunter\\output\\results_2026-06-26_120000.csv",
    ]);

    await wrapper.get("[data-testid='export-results']").trigger("click");
    await flushPromises();

    expect(exportSpy).toHaveBeenCalledTimes(1);
    expect(exportSpy).toHaveBeenCalledWith([
      firstRun[0],
      firstRun[1],
      firstRun[3],
    ]);
    expect(wrapper.text()).toContain("Exported to C:\\Users\\ayman\\JobHunter\\output\\results_2026-06-26_120000.csv");
  });

  it("shows exporter errors without clearing results", async () => {
    const { store, wrapper } = mountView();
    vi.spyOn(store, "exportResults").mockRejectedValue(new Error("export failed"));

    await wrapper.get("[data-testid='export-results']").trigger("click");
    await flushPromises();

    expect(wrapper.text()).toContain("export failed");
    expect(renderedTitles(wrapper)).toEqual([
      "Platform Engineer",
      "Backend Engineer",
      "Data Integrations Engineer",
    ]);
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

  it("hides rows below the user-configured threshold from the criteria draft", () => {
    localStorage.setItem(
      "jobhunter.criteriaDraft.v1",
      JSON.stringify({ min_score_threshold: 60 }),
    );
    const { wrapper } = mountView();

    expect(renderedTitles(wrapper)).toEqual(["Platform Engineer", "Backend Engineer"]);
    expect(wrapper.text()).toContain("hidden below 60");
  });

  it("drops stale rows when the run clears its results", async () => {
    const { store, wrapper } = mountView();
    expect(renderedTitles(wrapper).length).toBeGreaterThan(0);

    store.results = [];
    await wrapper.vm.$nextTick();

    expect(renderedTitles(wrapper)).toEqual([]);
  });

  it("shows a partial-results warning when a connector failed but results remain", async () => {
    const { store, wrapper } = mountView();
    store.events = [
      {
        type: "progress",
        run_id: "run-1",
        stage: "search",
        state: "failed",
        connector: "adzuna",
        message: "connector failed",
      },
    ];
    await wrapper.vm.$nextTick();

    expect(wrapper.get("[data-testid='partial-results-warning']").text()).toContain(
      "Partial results: adzuna failed.",
    );
    expect(renderedTitles(wrapper)).toContain("Platform Engineer");
  });

  it("explains a completed empty result set with connector failures", async () => {
    const { store, wrapper } = mountView([]);
    store.status = "succeeded";
    store.events = [
      {
        type: "progress",
        run_id: "run-1",
        stage: "search",
        state: "failed",
        connector: "mock",
        message: "connector failed",
      },
    ];
    await wrapper.vm.$nextTick();

    expect(wrapper.text()).toContain("No results from completed connectors");
    expect(wrapper.text()).toContain("Partial results: mock failed.");
  });

  it("explains when all rows are hidden below the configured threshold", () => {
    localStorage.setItem(
      "jobhunter.criteriaDraft.v1",
      JSON.stringify({ min_score_threshold: 95 }),
    );

    const { wrapper } = mountView();

    expect(renderedTitles(wrapper)).toEqual([]);
    expect(wrapper.text()).toContain("All results are hidden");
    expect(wrapper.text()).toContain("below the 95 threshold");
  });
});
