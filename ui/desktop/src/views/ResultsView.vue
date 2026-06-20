<script setup lang="ts">
import { computed } from "vue";

import { usePipelineStore, type JobResult } from "@/stores/pipeline";

const pipeline = usePipelineStore();

const rows = computed(() =>
  pipeline.results.map((job: JobResult, index: number) => ({
    id: String(job.id ?? job.url ?? job.title ?? index),
    title: String(job.title ?? "Untitled role"),
    company: String(job.company ?? "Unknown company"),
    score: typeof job.score === "number" ? job.score : null,
  })),
);
</script>

<template>
  <section class="view-surface" aria-labelledby="results-title">
    <div class="view-body">
      <h2 id="results-title" class="section-title">Matches</h2>
    </div>

    <p v-if="rows.length === 0" class="empty-state">No results yet.</p>

    <dl v-else class="data-list">
      <div v-for="row in rows" :key="row.id" class="data-row">
        <dt>{{ row.title }}</dt>
        <dd>{{ row.company }}</dd>
        <dd>
          <span v-if="row.score !== null" class="score-badge">{{ row.score }}</span>
        </dd>
      </div>
    </dl>
  </section>
</template>
