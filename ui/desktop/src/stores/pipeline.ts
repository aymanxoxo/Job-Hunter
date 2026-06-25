import { defineStore } from "pinia";

export type PipelineStatus = "idle" | "running" | "succeeded" | "failed";

export interface ProgressEvent {
  type: "progress";
  run_id?: string;
  stage?: string;
  state?: string;
  connector?: string;
  message?: string;
  label?: string;
  current?: number;
  total?: number;
  metric?: unknown;
}

export interface ConnectorOverride {
  enabled?: boolean;
  max_results?: number;
  delay_min?: number;
  delay_max?: number;
  results_per_query?: number;
  trust_threshold?: number;
  trust_check_enabled?: boolean;
}

export interface RunPipelineRequest {
  profile: string;
  provider?: string;
  connector_overrides?: Record<string, ConnectorOverride>;
}

export type GenerateCriteriaRequest = Omit<RunPipelineRequest, "connector_overrides">;

export interface CriteriaResult {
  titles: string[];
  keywords: string[];
  exclude_keywords: string[];
  seniority_levels: string[];
  locations: string[];
  min_score_threshold: number;
  max_results?: number;
  date_posted_days?: number | null;
  raw_profile?: string | null;
}

export type JobResult = Record<string, unknown>;

type ProgressHandler = (event: { payload: unknown }) => void;
type Unlisten = () => void;

export interface PipelineClient {
  listen(eventName: "pipeline-progress", handler: ProgressHandler): Promise<Unlisten>;
  invoke(command: "run_pipeline", args: RunPipelineRequest): Promise<unknown>;
  invoke(command: "generate_criteria", args: GenerateCriteriaRequest): Promise<unknown>;
}

async function createTauriPipelineClient(): Promise<PipelineClient> {
  const [{ invoke }, { listen }] = await Promise.all([
    import("@tauri-apps/api/core"),
    import("@tauri-apps/api/event"),
  ]);

  return {
    listen,
    invoke: (command, args) => invoke(command, args as unknown as Record<string, unknown>),
  };
}

function buildConnectorOverrides(): Record<string, ConnectorOverride> | undefined {
  try {
    const raw = localStorage.getItem("jobhunter.desktopConfig.v1");
    if (!raw) return undefined;
    const parsed = JSON.parse(raw);
    if (typeof parsed?.connectors !== "object" || parsed.connectors === null) return undefined;
    return parsed.connectors as Record<string, ConnectorOverride>;
  } catch {
    return undefined;
  }
}

function isProgressEvent(payload: unknown): payload is ProgressEvent {
  return (
    typeof payload === "object" &&
    payload !== null &&
    (payload as { type?: unknown }).type === "progress"
  );
}

function stringArray(value: unknown): string[] {
  return Array.isArray(value) ? value.map(String).filter(Boolean) : [];
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function normalizeCriteria(value: unknown): CriteriaResult {
  if (!isRecord(value)) {
    throw new Error("Provider returned invalid criteria.");
  }
  const threshold = value.min_score_threshold;
  return {
    titles: stringArray(value.titles),
    keywords: stringArray(value.keywords),
    exclude_keywords: stringArray(value.exclude_keywords),
    seniority_levels: stringArray(value.seniority_levels),
    locations: stringArray(value.locations),
    min_score_threshold:
      typeof threshold === "number" && Number.isFinite(threshold) ? threshold : 40,
    max_results: typeof value.max_results === "number" ? value.max_results : undefined,
    date_posted_days:
      typeof value.date_posted_days === "number" || value.date_posted_days === null
        ? value.date_posted_days
        : undefined,
    raw_profile: typeof value.raw_profile === "string" ? value.raw_profile : null,
  };
}

export const usePipelineStore = defineStore("pipeline", {
  state: () => ({
    status: "idle" as PipelineStatus,
    events: [] as ProgressEvent[],
    latestProgress: null as ProgressEvent | null,
    results: [] as JobResult[],
    error: null as string | null,
    lastRun: null as RunPipelineRequest | null,
  }),

  getters: {
    statusLabel(state): string {
      if (state.status === "running") {
        return state.latestProgress?.message ?? "Pipeline running";
      }
      if (state.status === "succeeded") {
        return `${state.results.length} results ready`;
      }
      if (state.status === "failed") {
        return state.error ?? "Pipeline failed";
      }
      return "Ready";
    },
  },

  actions: {
    reset() {
      this.status = "idle";
      this.events = [];
      this.latestProgress = null;
      this.results = [];
      this.error = null;
    },

    recordProgress(event: ProgressEvent) {
      this.events.push(event);
      this.latestProgress = event;
      this.status = event.state === "failed" ? "failed" : "running";
    },

    setResult(data: unknown) {
      this.results = Array.isArray(data) ? (data as JobResult[]) : [];
      this.status = "succeeded";
      this.error = null;
    },

    setError(message: string) {
      this.status = "failed";
      this.error = message;
    },

    async runPipeline(request: RunPipelineRequest, client?: PipelineClient) {
      this.reset();
      this.status = "running";
      this.lastRun = request;

      let unlisten: (() => void) | undefined;

      try {
        const overrides = buildConnectorOverrides();
        const ipcRequest: RunPipelineRequest = {
          ...request,
          ...(overrides ? { connector_overrides: overrides } : {}),
        };

        const ipc = client ?? (await createTauriPipelineClient());
        unlisten = await ipc.listen("pipeline-progress", (event) => {
          if (isProgressEvent(event.payload)) {
            this.recordProgress(event.payload);
          }
        });

        const result = await ipc.invoke("run_pipeline", ipcRequest);
        this.setResult(result);
      } catch (error) {
        const message = error instanceof Error ? error.message : String(error);
        this.setError(message);
        this.results = [];
        throw error;
      } finally {
        if (unlisten) {
          unlisten();
        }
        if (this.status === "running") {
          this.status = "idle";
        }
      }
    },

    async generateCriteria(request: GenerateCriteriaRequest, client?: PipelineClient) {
      this.error = null;
      const ipc = client ?? (await createTauriPipelineClient());
      try {
        const result = await ipc.invoke("generate_criteria", request);
        return normalizeCriteria(result);
      } catch (error) {
        const message = error instanceof Error ? error.message : String(error);
        this.setError(message);
        throw error;
      }
    },
  },
});
