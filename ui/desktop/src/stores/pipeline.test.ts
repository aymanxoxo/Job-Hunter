import { setActivePinia, createPinia } from "pinia";
import { beforeEach, describe, expect, it } from "vitest";

import { usePipelineStore, type ProgressEvent } from "./pipeline";

describe("pipeline store", () => {
  beforeEach(() => {
    setActivePinia(createPinia());
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
});
