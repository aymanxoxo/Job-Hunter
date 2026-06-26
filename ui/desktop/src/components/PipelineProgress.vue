<script setup lang="ts">
// C-033 — Live Pipeline Progress UX (DEV_PLAN §9, SDD §11.2).
// Pure presentation over the timeline model derived from the streamed events;
// no business logic lives here.
import { computed, onBeforeUnmount, onMounted, ref } from "vue";

import { buildTimeline, type StageModel } from "../lib/timeline";
import { usePipelineStore } from "../stores/pipeline";

const store = usePipelineStore();

const timeline = computed(() =>
  buildTimeline(store.events, { pipelineStatus: store.status, results: store.results }),
);

const currentStageDisplay = computed(() => {
  const idx = timeline.value.activeIndex;
  if (idx >= 0) {
    return idx + 1;
  }
  return Math.min(timeline.value.doneCount + 1, timeline.value.stages.length);
});

const provider = computed(() => store.lastRun?.provider ?? "—");

// Elapsed timer (runs only while the pipeline is running).
const elapsed = ref(0);
let startedAt: number | null = null;
let timer: ReturnType<typeof setInterval> | undefined;

function tick() {
  if (store.status === "running") {
    if (startedAt === null) {
      startedAt = Date.now();
    }
    elapsed.value = Math.floor((Date.now() - startedAt) / 1000);
  } else if (store.status === "idle") {
    startedAt = null;
    elapsed.value = 0;
  }
}

onMounted(() => {
  timer = setInterval(tick, 1000);
});
onBeforeUnmount(() => {
  if (timer) {
    clearInterval(timer);
  }
});

function scoreWidth(stage: StageModel): string {
  if (!stage.total) {
    return "0%";
  }
  return `${Math.round(((stage.current ?? 0) / stage.total) * 100)}%`;
}

function connectorJobsLabel(connector: StageModel["connectors"][number]): string {
  if (connector.state === "failed") {
    return "failed";
  }
  if (connector.state === "skipped") {
    return "skipped";
  }
  if (connector.jobs === 0) {
    return "0 jobs";
  }
  if (connector.jobs !== null) {
    return `${connector.jobs} jobs`;
  }
  return "-";
}

function connectorTitle(connector: StageModel["connectors"][number]): string {
  return connector.message ?? `${connector.name}: ${connector.state}`;
}

const elapsedLabel = computed(() => {
  const total = elapsed.value;
  const m = Math.floor(total / 60);
  const s = total % 60;
  return `${m}:${s.toString().padStart(2, "0")}`;
});
</script>

<template>
  <section class="pipeline-progress" aria-label="Pipeline progress">
    <header class="pp-header">
      <span class="pp-provider" :title="`Provider: ${provider}`">{{ provider }}</span>
      <span class="pp-status">{{ store.statusLabel }}</span>
      <span class="pp-position">Stage {{ currentStageDisplay }} of {{ timeline.stages.length }}</span>
      <span class="pp-elapsed" aria-label="Elapsed time">{{ elapsedLabel }}</span>
    </header>

    <ol class="pp-timeline">
      <li
        v-for="stage in timeline.stages"
        :key="stage.key"
        class="pp-stage"
        :class="`is-${stage.state}`"
        tabindex="0"
        :aria-label="`${stage.label}: ${stage.state}`"
      >
        <div class="pp-node">
          <span class="pp-dot" aria-hidden="true" />
          <span class="pp-label">{{ stage.label }}</span>
        </div>

        <p v-if="stage.jobs !== null" class="pp-metric">{{ stage.jobs }} jobs</p>

        <div v-if="stage.key === 'score' && stage.total" class="pp-score">
          <div class="pp-bar">
            <div
              class="pp-bar-fill"
              :style="{ width: scoreWidth(stage) }"
            />
          </div>
          <span class="pp-score-text">batch {{ stage.current ?? 0 }} / {{ stage.total }}</span>
        </div>

        <ul v-if="stage.connectors.length" class="pp-connectors">
          <li
            v-for="connector in stage.connectors"
            :key="connector.name"
            class="pp-connector"
            :class="`is-${connector.state}`"
            :title="connectorTitle(connector)"
          >
            <span class="pp-connector-name">{{ connector.name }}</span>
            <span class="pp-connector-jobs">{{ connectorJobsLabel(connector) }}</span>
          </li>
        </ul>
      </li>
    </ol>

    <div
      v-if="timeline.summary.done || timeline.summary.failed"
      class="pp-summary"
      :class="{ 'is-failed': timeline.summary.failed }"
    >
      <span v-if="timeline.summary.found !== null">Found {{ timeline.summary.found }}</span>
      <span>Kept {{ timeline.summary.kept }}</span>
      <span v-if="timeline.summary.failedConnectors.length" class="pp-warn">
        Partial: {{ timeline.summary.failedConnectors.join(", ") }} failed
      </span>
      <span v-if="timeline.summary.zeroResultConnectors.length">
        0 from {{ timeline.summary.zeroResultConnectors.join(", ") }}
      </span>
      <span class="pp-elapsed">{{ elapsedLabel }}</span>
    </div>

    <details v-if="store.events.length" class="pp-log">
      <summary>Activity log ({{ store.events.length }})</summary>
      <ul>
        <li v-for="(event, index) in store.events" :key="index">
          {{ event.stage ?? "?" }} · {{ event.state ?? "?" }}
          <template v-if="event.connector"> · {{ event.connector }}</template>
          <template v-if="event.message"> — {{ event.message }}</template>
        </li>
      </ul>
    </details>
  </section>
</template>

<style scoped>
.pipeline-progress {
  display: flex;
  flex-direction: column;
  gap: var(--sp-3);
  padding: var(--sp-4);
  border: 1px solid var(--border);
  border-radius: var(--r-lg);
  background: var(--surface);
  box-shadow: var(--sh-1);
}
.pp-header {
  display: flex;
  gap: var(--sp-3);
  align-items: center;
  font-size: var(--fs-sm);
  line-height: var(--lh-sm);
}
.pp-provider {
  padding: 1px var(--sp-2);
  border-radius: var(--r-pill);
  color: var(--accent);
  background: var(--accent-soft);
  font-weight: var(--fw-semibold);
}
.pp-position {
  margin-left: auto;
}
/* Reserve all five stages up front so states swap in place (no layout shift). */
.pp-timeline {
  display: grid;
  grid-template-columns: repeat(5, 1fr);
  gap: var(--sp-2);
  list-style: none;
  margin: 0;
  padding: 0;
}
.pp-stage {
  min-height: 5.5rem;
  padding: var(--sp-3);
  border: 1px solid var(--border);
  border-radius: var(--r-md);
  background: var(--surface-2);
}
.pp-node {
  display: flex;
  align-items: center;
  gap: var(--sp-2);
}
.pp-dot {
  width: 10px;
  height: 10px;
  border: 1px solid var(--text-subtle);
  border-radius: var(--r-pill);
  background: var(--surface);
}
.pp-label {
  font-weight: var(--fw-semibold);
}
.is-active .pp-dot {
  border-color: var(--accent);
  background: var(--accent);
  animation: pp-pulse 1.2s ease-in-out infinite;
}
.is-done .pp-dot {
  border-color: var(--score-green);
  background: var(--score-green);
}
.pp-stage.is-failed .pp-dot {
  color: var(--warning);
  border-color: var(--warning);
  background: var(--warning);
}
.pp-connector.is-failed .pp-connector-name {
  color: var(--warning);
}
.is-skipped,
.pp-connector.is-skipped {
  border-style: dashed;
  opacity: 0.6;
}
.pp-metric,
.pp-score-text {
  margin: var(--sp-2) 0 0;
  color: var(--text-muted);
  font-size: var(--fs-xs);
  line-height: var(--lh-xs);
}
.pp-bar {
  height: 6px;
  border-radius: var(--r-pill);
  background: var(--surface-3);
  overflow: hidden;
}
.pp-bar-fill {
  height: 100%;
  background: var(--accent);
  transition: width var(--dur) var(--ease);
}
.pp-connectors {
  list-style: none;
  margin: var(--sp-2) 0 0;
  padding: 0;
  font-size: var(--fs-xs);
  line-height: var(--lh-xs);
}
.pp-connector {
  display: flex;
  justify-content: space-between;
  gap: var(--sp-2);
}
.pp-connector.is-failed {
  color: var(--warning);
}
.pp-summary {
  display: flex;
  gap: var(--sp-3);
  flex-wrap: wrap;
  padding: var(--sp-3);
  border-radius: var(--r-md);
  color: var(--success);
  background: var(--success-soft);
  font-size: var(--fs-sm);
  line-height: var(--lh-sm);
}
.pp-summary.is-failed {
  color: var(--warning);
  background: var(--warning-soft);
}
.pp-warn {
  color: var(--warning);
}
.pp-log {
  font-size: var(--fs-sm);
  line-height: var(--lh-sm);
}
.pp-log ul {
  margin: var(--sp-2) 0 0;
  padding-left: var(--sp-4);
  max-height: 12rem;
  overflow: auto;
}
@keyframes pp-pulse {
  0%,
  100% {
    opacity: 1;
  }
  50% {
    opacity: 0.4;
  }
}
@media (prefers-reduced-motion: reduce) {
  .is-active .pp-dot {
    animation: none;
  }
  .pp-bar-fill {
    transition: none;
  }
}
</style>
