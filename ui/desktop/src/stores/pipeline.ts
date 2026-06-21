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

export interface RunPipelineRequest {
  profile: string;
  provider?: string;
}

export type JobResult = Record<string, unknown>;

type ProgressHandler = (event: { payload: unknown }) => void;
type Unlisten = () => void;

export interface PipelineClient {
  listen(eventName: "pipeline-progress", handler: ProgressHandler): Promise<Unlisten>;
  invoke(command: "run_pipeline", args: RunPipelineRequest): Promise<unknown>;
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

function isProgressEvent(payload: unknown): payload is ProgressEvent {
  return (
    typeof payload === "object" &&
    payload !== null &&
    (payload as { type?: unknown }).type === "progress"
  );
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

      const ipc = client ?? (await createTauriPipelineClient());
      const unlisten = await ipc.listen("pipeline-progress", (event) => {
        if (isProgressEvent(event.payload)) {
          this.recordProgress(event.payload);
        }
      });

      try {
        const result = await ipc.invoke("run_pipeline", request);
        this.setResult(result);
      } catch (error) {
        const message = error instanceof Error ? error.message : String(error);
        this.setError(message);
        throw error;
      } finally {
        unlisten();
      }
    },
  },
});
