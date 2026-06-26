// C-033 — pure mapping from the streamed progress events to the Live Pipeline
// Progress timeline model (DEV_PLAN §9, data contract §9.3). No DOM, no I/O —
// the Vue component is pure presentation over this model (functional core).
import type { JobResult, PipelineStatus, ProgressEvent } from "../stores/pipeline";

export type StageKey = "profile" | "criteria" | "search" | "score" | "export";
export type StageState = "pending" | "active" | "done" | "failed" | "skipped";

export const STAGE_ORDER: StageKey[] = ["profile", "criteria", "search", "score", "export"];

export const STAGE_LABELS: Record<StageKey, string> = {
  profile: "Profile",
  criteria: "Criteria",
  search: "Search",
  score: "Score",
  export: "Export",
};

const STAGE_KEYS = new Set<string>(STAGE_ORDER);
const STAGE_STATES = new Set<string>(["pending", "active", "done", "failed", "skipped"]);

export interface ConnectorRow {
  name: string;
  state: StageState;
  jobs: number | null;
  message: string | null;
}

export interface StageModel {
  key: StageKey;
  label: string;
  state: StageState;
  current: number | null;
  total: number | null;
  jobs: number | null;
  connectors: ConnectorRow[];
}

export interface TimelineSummary {
  found: number | null;
  kept: number;
  failedConnectors: string[];
  zeroResultConnectors: string[];
  done: boolean;
  failed: boolean;
}

export interface TimelineModel {
  stages: StageModel[];
  activeIndex: number;
  doneCount: number;
  summary: TimelineSummary;
}

function asStageKey(stage: string | undefined): StageKey | null {
  return stage !== undefined && STAGE_KEYS.has(stage) ? (stage as StageKey) : null;
}

function asState(state: string | undefined): StageState | null {
  return state !== undefined && STAGE_STATES.has(state) ? (state as StageState) : null;
}

function metricJobs(metric: unknown): number | null {
  if (metric && typeof metric === "object" && "jobs" in (metric as Record<string, unknown>)) {
    const jobs = (metric as Record<string, unknown>).jobs;
    return typeof jobs === "number" ? jobs : null;
  }
  return null;
}

function emptyStages(): Record<StageKey, StageModel> {
  const stages = {} as Record<StageKey, StageModel>;
  for (const key of STAGE_ORDER) {
    stages[key] = {
      key,
      label: STAGE_LABELS[key],
      state: "pending",
      current: null,
      total: null,
      jobs: null,
      connectors: [],
    };
  }
  return stages;
}

/** Build the timeline model from the (ordered) progress events. Pure. */
export function buildTimeline(
  events: ProgressEvent[],
  opts: { pipelineStatus?: PipelineStatus; results?: JobResult[] } = {},
): TimelineModel {
  const stages = emptyStages();
  const failedConnectors: string[] = [];
  const zeroResultConnectors: string[] = [];

  for (const event of events) {
    const key = asStageKey(event.stage);
    if (key === null) {
      continue;
    }
    const stage = stages[key];
    const state = asState(event.state);
    const jobs = metricJobs(event.metric);

    if (event.connector) {
      let row = stage.connectors.find((connector) => connector.name === event.connector);
      if (!row) {
        row = { name: event.connector, state: "pending", jobs: null, message: null };
        stage.connectors.push(row);
      }
      if (state) {
        row.state = state;
      }
      if (jobs !== null) {
        row.jobs = jobs;
      }
      if (typeof event.message === "string" && event.message.trim()) {
        row.message = event.message;
      }
      if (state === "failed" && !failedConnectors.includes(event.connector)) {
        failedConnectors.push(event.connector);
      }
      if (state === "done" && jobs === 0 && !zeroResultConnectors.includes(event.connector)) {
        zeroResultConnectors.push(event.connector);
      }
      continue;
    }

    if (state) {
      stage.state = state;
    }
    if (typeof event.current === "number") {
      stage.current = event.current;
    }
    if (typeof event.total === "number") {
      stage.total = event.total;
    }
    if (jobs !== null) {
      stage.jobs = jobs;
    }
  }

  const stageList = STAGE_ORDER.map((key) => stages[key]);
  const activeIndex = stageList.findIndex((stage) => stage.state === "active");
  const doneCount = stageList.filter((stage) => stage.state === "done").length;

  const connectorJobs = stages.search.connectors.reduce<number | null>((sum, connector) => {
    if (connector.jobs === null) {
      return sum;
    }
    return (sum ?? 0) + connector.jobs;
  }, null);
  const found = stages.search.jobs ?? connectorJobs;

  const failed =
    opts.pipelineStatus === "failed" || stageList.some((stage) => stage.state === "failed");
  const done = opts.pipelineStatus === "succeeded" || stages.export.state === "done";

  return {
    stages: stageList,
    activeIndex,
    doneCount,
    summary: {
      found,
      kept: opts.results?.length ?? 0,
      failedConnectors,
      zeroResultConnectors,
      done,
      failed,
    },
  };
}
