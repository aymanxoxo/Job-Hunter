import { describe, expect, it } from "vitest";

import { buildTimeline, STAGE_ORDER } from "./timeline";
import type { ProgressEvent } from "../stores/pipeline";

function ev(partial: Partial<ProgressEvent>): ProgressEvent {
  return { type: "progress", ...partial };
}

describe("buildTimeline", () => {
  it("starts every stage pending with no events", () => {
    const model = buildTimeline([]);
    expect(model.stages.map((s) => s.key)).toEqual(STAGE_ORDER);
    expect(model.stages.every((s) => s.state === "pending")).toBe(true);
    expect(model.activeIndex).toBe(-1);
    expect(model.summary.done).toBe(false);
  });

  it("applies the latest state per stage and finds the active stage", () => {
    const model = buildTimeline([
      ev({ stage: "profile", state: "done" }),
      ev({ stage: "criteria", state: "done" }),
      ev({ stage: "search", state: "active" }),
    ]);
    expect(model.stages[0].state).toBe("done");
    expect(model.stages[1].state).toBe("done");
    expect(model.stages[2].state).toBe("active");
    expect(model.activeIndex).toBe(2);
    expect(model.doneCount).toBe(2);
  });

  it("collects per-connector search sub-rows and flags failures (non-blocking)", () => {
    const model = buildTimeline([
      ev({ stage: "search", state: "active" }),
      ev({ stage: "search", connector: "adzuna", state: "done", metric: { jobs: 47 } }),
      ev({ stage: "search", connector: "linkedin", state: "failed" }),
    ]);
    const search = model.stages[2];
    expect(search.connectors).toEqual([
      { name: "adzuna", state: "done", jobs: 47, message: null },
      { name: "linkedin", state: "failed", jobs: null, message: null },
    ]);
    expect(model.summary.failedConnectors).toEqual(["linkedin"]);
    expect(model.summary.found).toBe(47);
    // a failed connector must NOT fail the whole pipeline by itself
    expect(model.summary.failed).toBe(false);
  });

  it("tracks zero-result connector rows and connector messages", () => {
    const model = buildTimeline([
      ev({
        stage: "search",
        connector: "mock",
        state: "done",
        message: "0 results",
        metric: { jobs: 0 },
      }),
    ]);

    expect(model.stages[2].connectors).toEqual([
      { name: "mock", state: "done", jobs: 0, message: "0 results" },
    ]);
    expect(model.summary.zeroResultConnectors).toEqual(["mock"]);
    expect(model.summary.found).toBe(0);
  });

  it("tracks the score stage determinate progress", () => {
    const model = buildTimeline([ev({ stage: "score", state: "active", current: 4, total: 6 })]);
    const score = model.stages[3];
    expect(score.current).toBe(4);
    expect(score.total).toBe(6);
  });

  it("summarizes a completed run from results + export done", () => {
    const model = buildTimeline(
      [ev({ stage: "export", state: "done" })],
      { pipelineStatus: "succeeded", results: [{ id: "a" }, { id: "b" }] },
    );
    expect(model.summary.done).toBe(true);
    expect(model.summary.kept).toBe(2);
  });

  it("marks the run failed when the pipeline status is failed", () => {
    const model = buildTimeline([ev({ stage: "criteria", state: "failed" })], {
      pipelineStatus: "failed",
    });
    expect(model.summary.failed).toBe(true);
  });

  it("ignores unknown stage/state values defensively", () => {
    const model = buildTimeline([
      ev({ stage: "bogus", state: "active" }),
      ev({ stage: "profile", state: "weird" }),
    ]);
    expect(model.stages[0].state).toBe("pending");
    expect(model.activeIndex).toBe(-1);
  });
});
