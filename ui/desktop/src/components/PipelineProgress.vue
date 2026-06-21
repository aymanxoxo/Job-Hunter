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
          >
            <span class="pp-connector-name">{{ connector.name }}</span>
            <span class="pp-connector-jobs">{{ connector.jobs ?? "—" }}</span>
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
        {{ timeline.summary.failedConnectors.join(", ") }} failed
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
  --pp-pending: var(--color-muted, #9ca3af);
  --pp-active: var(--color-accent, #2563eb);
  --pp-done: var(--score-high, #16a34a);
  --pp-failed: var(--score-mid, #d97706);
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}
.pp-header {
  display: flex;
  gap: 0.75rem;
  align-items: center;
  font-size: 0.85rem;
}
.pp-provider {
  font-weight: 600;
  padding: 0.1rem 0.5rem;
  border-radius: 999px;
  background: var(--color-surface-alt, #eef2ff);
}
.pp-position {
  margin-left: auto;
}
/* Reserve all five stages up front so states swap in place (no layout shift). */
.pp-timeline {
  display: grid;
  grid-template-columns: repeat(5, 1fr);
  gap: 0.5rem;
  list-style: none;
  margin: 0;
  padding: 0;
}
.pp-stage {
  min-height: 5.5rem;
  padding: 0.5rem;
  border-radius: 0.5rem;
  background: var(--color-surface, #f8fafc);
  border: 1px solid var(--color-border, #e5e7eb);
}
.pp-node {
  display: flex;
  align-items: center;
  gap: 0.4rem;
}
.pp-dot {
  width: 0.6rem;
  height: 0.6rem;
  border-radius: 50%;
  background: var(--pp-pending);
}
.pp-label {
  font-weight: 600;
}
.is-active .pp-dot {
  background: var(--pp-active);
  animation: pp-pulse 1.2s ease-in-out infinite;
}
.is-done .pp-dot {
  background: var(--pp-done);
}
.is-failed .pp-dot,
.is-failed .pp-connector-name {
  color: var(--pp-failed);
  background: var(--pp-failed);
}
.is-skipped .pp-stage,
.pp-connector.is-skipped {
  border-style: dashed;
  opacity: 0.6;
}
.pp-metric,
.pp-score-text {
  font-size: 0.75rem;
  color: var(--color-muted, #6b7280);
  margin: 0.35rem 0 0;
}
.pp-bar {
  height: 0.35rem;
  border-radius: 999px;
  background: var(--color-border, #e5e7eb);
  overflow: hidden;
}
.pp-bar-fill {
  height: 100%;
  background: var(--pp-active);
  transition: width 0.3s ease;
}
.pp-connectors {
  list-style: none;
  margin: 0.4rem 0 0;
  padding: 0;
  font-size: 0.72rem;
}
.pp-connector {
  display: flex;
  justify-content: space-between;
}
.pp-connector.is-failed {
  color: var(--pp-failed);
}
.pp-summary {
  display: flex;
  gap: 0.75rem;
  flex-wrap: wrap;
  padding: 0.5rem 0.75rem;
  border-radius: 0.5rem;
  background: var(--color-surface-alt, #f0fdf4);
  font-size: 0.85rem;
}
.pp-summary.is-failed {
  background: var(--color-surface-warn, #fffbeb);
}
.pp-warn {
  color: var(--pp-failed);
}
.pp-log {
  font-size: 0.78rem;
}
.pp-log ul {
  margin: 0.4rem 0 0;
  padding-left: 1rem;
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
