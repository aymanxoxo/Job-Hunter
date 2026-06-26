import { setActivePinia, createPinia } from "pinia";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { usePipelineStore, type ProgressEvent, type ConnectorOverride } from "./pipeline";

// localStorage helpers for C-058 tests
const CONFIG_KEY = "jobhunter.desktopConfig.v1";

function setLocalStorage(value: unknown) {
  localStorage.setItem(CONFIG_KEY, JSON.stringify(value));
}

function clearLocalStorage() {
  localStorage.removeItem(CONFIG_KEY);
}

describe("pipeline store", () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    clearLocalStorage();
  });

  it("records streamed progress events in order", () => {
    const store = usePipelineStore();
    const event: ProgressEvent = {
      type: "progress",
      run_id: "run-1",
      stage: "search",
      state: "active",
      current: 2,
      total: 5,
    };

    store.recordProgress(event);

    expect(store.events).toEqual([event]);
    expect(store.latestProgress).toEqual(event);
    expect(store.status).toBe("running");
  });

  it("keeps connector-level failed progress non-fatal", () => {
    const store = usePipelineStore();
    const event: ProgressEvent = {
      type: "progress",
      run_id: "run-1",
      stage: "search",
      state: "failed",
      connector: "adzuna",
      message: "connector failed",
    };

    store.recordProgress(event);

    expect(store.events).toEqual([event]);
    expect(store.status).toBe("running");
    expect(store.error).toBeNull();
  });

  it("listens for Tauri progress events while invoking the sidecar", async () => {
    const store = usePipelineStore();
    const streamed: ProgressEvent = {
      type: "progress",
      run_id: "run-2",
      stage: "score",
      state: "done",
      current: 4,
      total: 4,
    };
    const result = [{ id: "job-1", title: "Python Engineer", score: 91 }];
    let listener: ((event: { payload: unknown }) => void) | undefined;
    let unlistenCalled = false;

    await store.runPipeline(
      { profile: "Senior Python developer", provider: "ollama" },
      {
        listen: async (eventName, handler) => {
          expect(eventName).toBe("pipeline-progress");
          listener = handler;
          return () => {
            unlistenCalled = true;
          };
        },
        invoke: async (command, args) => {
          expect(command).toBe("run_pipeline");
          expect(args).toEqual({
            profile: "Senior Python developer",
            provider: "ollama",
          });
          listener?.({ payload: streamed });
          return result;
        },
      },
    );

    expect(store.events).toEqual([streamed]);
    expect(store.results).toEqual(result);
    expect(store.status).toBe("succeeded");
    expect(store.error).toBeNull();
    expect(unlistenCalled).toBe(true);
  });

  it("invokes the sidecar criteria generation command", async () => {
    const store = usePipelineStore();
    const criteria = {
      titles: ["Platform Engineer"],
      keywords: ["python", "kubernetes"],
      exclude_keywords: ["php"],
      seniority_levels: ["senior"],
      locations: ["remote"],
      min_score_threshold: 70,
    };

    const result = await store.generateCriteria(
      { profile: "Senior Python platform engineer", provider: "ollama" },
      {
        listen: async () => () => undefined,
        invoke: async (command, args) => {
          expect(command).toBe("generate_criteria");
          expect(args).toEqual({
            profile: "Senior Python platform engineer",
            provider: "ollama",
          });
          return criteria;
        },
      },
    );

    expect(result).toMatchObject(criteria);
    expect(store.error).toBeNull();
  });

  it("invokes the sidecar export command and returns output paths", async () => {
    const store = usePipelineStore();
    const jobs = [
      {
        id: "job-1",
        title: "Python Engineer",
        company: "Northstar",
        url: "https://example.test/job-1",
        source: "mock",
        score: 91,
      },
    ];

    const paths = await store.exportResults(jobs, {
      listen: async () => () => undefined,
      invoke: async (command, args) => {
        expect(command).toBe("export_results");
        expect(args).toEqual({ jobs });
        return ["C:\\Users\\ayman\\JobHunter\\output\\results_2026-06-26_120000.csv"];
      },
    });

    expect(paths).toEqual(["C:\\Users\\ayman\\JobHunter\\output\\results_2026-06-26_120000.csv"]);
    expect(store.error).toBeNull();
  });

  it("rejects invalid exporter path responses", async () => {
    const store = usePipelineStore();

    await expect(
      store.exportResults([], {
        listen: async () => () => undefined,
        invoke: async () => [42],
      }),
    ).rejects.toThrow("Exporter returned invalid output paths.");

    expect(store.error).toBe("Exporter returned invalid output paths.");
  });

  // -------------------------------------------------------------------------
  // C-058 — connector overrides via localStorage
  // -------------------------------------------------------------------------

  it("runPipeline with no localStorage data does not include connector_overrides", async () => {
    const store = usePipelineStore();
    const invokeArgs: unknown[] = [];

    await store.runPipeline(
      { profile: "Senior Python developer", provider: "gemini" },
      {
        listen: async () => () => undefined,
        invoke: async (command, args) => {
          invokeArgs.push(args);
          return [];
        },
      },
    );

    expect(invokeArgs).toHaveLength(1);
    const sent = invokeArgs[0] as Record<string, unknown>;
    expect(sent.profile).toBe("Senior Python developer");
    expect(sent.provider).toBe("gemini");
    expect(sent.connector_overrides).toBeUndefined();
  });

  it("runPipeline with valid localStorage config includes connector_overrides", async () => {
    const store = usePipelineStore();
    setLocalStorage({
      ai: { provider: "gemini" },
      connectors: {
        mock: { enabled: false, max_results: 50, delay_min: 2, delay_max: 2 },
        adzuna: { enabled: true, max_results: 50, delay_min: 2, delay_max: 2 },
        duckduckgo: {
          enabled: true,
          max_results: 50,
          delay_min: 2,
          delay_max: 2,
          results_per_query: 10,
          trust_threshold: 60,
          trust_check_enabled: true,
        },
      },
    });

    const invokeArgs: unknown[] = [];
    await store.runPipeline(
      { profile: "Senior Python developer", provider: "gemini" },
      {
        listen: async () => () => undefined,
        invoke: async (command, args) => {
          invokeArgs.push(args);
          return [];
        },
      },
    );

    expect(invokeArgs).toHaveLength(1);
    const sent = invokeArgs[0] as Record<string, unknown>;
    expect(sent.connector_overrides).toEqual({
      mock: { enabled: false, max_results: 50, delay_min: 2, delay_max: 2 },
      adzuna: { enabled: true, max_results: 50, delay_min: 2, delay_max: 2 },
      duckduckgo: {
        enabled: true,
        max_results: 50,
        delay_min: 2,
        delay_max: 2,
        results_per_query: 10,
        trust_threshold: 60,
        trust_check_enabled: true,
      },
    });
  });

  it("runPipeline with malformed localStorage JSON falls back to no overrides", async () => {
    const store = usePipelineStore();
    localStorage.setItem(CONFIG_KEY, "not-json");

    const invokeArgs: unknown[] = [];
    await store.runPipeline(
      { profile: "Senior Python developer", provider: "gemini" },
      {
        listen: async () => () => undefined,
        invoke: async (command, args) => {
          invokeArgs.push(args);
          return [];
        },
      },
    );

    expect(invokeArgs).toHaveLength(1);
    const sent = invokeArgs[0] as Record<string, unknown>;
    expect(sent.connector_overrides).toBeUndefined();
  });

  it("generateCriteria does NOT include connector_overrides", async () => {
    const store = usePipelineStore();
    setLocalStorage({
      connectors: {
        mock: { enabled: false },
      },
    });

    const invokeArgs: unknown[] = [];
    await store.generateCriteria(
      { profile: "Senior Python developer", provider: "gemini" },
      {
        listen: async () => () => undefined,
        invoke: async (command, args) => {
          invokeArgs.push(args);
          return {
            titles: [],
            keywords: ["python"],
            exclude_keywords: [],
            seniority_levels: [],
            locations: [],
            min_score_threshold: 40,
          };
        },
      },
    );

    expect(invokeArgs).toHaveLength(1);
    const sent = invokeArgs[0] as Record<string, unknown>;
    expect(sent.connector_overrides).toBeUndefined();
  });

  it("buildConnectorOverrides returns undefined when localStorage is empty", async () => {
    const store = usePipelineStore();
    clearLocalStorage();
    // We can't directly test buildConnectorOverrides since it's private,
    // but we can verify the behaviour through runPipeline.
    const invokeArgs: unknown[] = [];
    await store.runPipeline(
      { profile: "Senior Python developer", provider: "gemini" },
      {
        listen: async () => () => undefined,
        invoke: async (command, args) => {
          invokeArgs.push(args);
          return [];
        },
      },
    );
    const sent = invokeArgs[0] as Record<string, unknown>;
    expect(sent.connector_overrides).toBeUndefined();
  });

  it("buildConnectorOverrides returns the connectors sub-object when storage is populated", async () => {
    const store = usePipelineStore();
    const connectors: Record<string, ConnectorOverride> = {
      mock: { enabled: false, max_results: 25 },
    };
    setLocalStorage({ connectors });

    const invokeArgs: unknown[] = [];
    await store.runPipeline(
      { profile: "Senior Python developer", provider: "gemini" },
      {
        listen: async () => () => undefined,
        invoke: async (command, args) => {
          invokeArgs.push(args);
          return [];
        },
      },
    );
    const sent = invokeArgs[0] as Record<string, unknown>;
    expect(sent.connector_overrides).toEqual(connectors);
  });

  // -------------------------------------------------------------------------
  // C-068 — desktop hardening
  // -------------------------------------------------------------------------

  it("ends the run cleanly (status failed) when the IPC client fails to initialise", async () => {
    const store = usePipelineStore();

    await expect(
      store.runPipeline(
        { profile: "Senior Python developer", provider: "ollama" },
        {
          listen: async () => {
            throw new Error("tauri unavailable");
          },
          invoke: async () => [],
        },
      ),
    ).rejects.toThrow("tauri unavailable");

    expect(store.status).toBe("failed");
    expect(store.error).toBe("tauri unavailable");
  });

  it("clears stale results when a run fails", () => {
    const store = usePipelineStore();
    store.results = [{ id: "old" }];

    store.setError("boom");

    expect(store.status).toBe("failed");
    expect(store.results).toEqual([]);
  });

  it("ignores an array under connectors instead of forwarding it as overrides", async () => {
    const store = usePipelineStore();
    setLocalStorage({ connectors: [{ enabled: false }] });

    const invokeArgs: unknown[] = [];
    await store.runPipeline(
      { profile: "Senior Python developer", provider: "gemini" },
      {
        listen: async () => () => undefined,
        invoke: async (command, args) => {
          invokeArgs.push(args);
          return [];
        },
      },
    );

    const sent = invokeArgs[0] as Record<string, unknown>;
    expect(sent.connector_overrides).toBeUndefined();
  });
});
