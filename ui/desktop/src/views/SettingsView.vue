<script setup lang="ts">
import { usePipelineStore } from "@/stores/pipeline";

const pipeline = usePipelineStore();
</script>

<template>
  <section class="view-surface" aria-labelledby="settings-title">
    <div class="view-body">
      <h2 id="settings-title" class="section-title">Runtime</h2>

      <div class="settings-grid">
        <div class="setting-line">
          <p class="setting-label">IPC event</p>
          <p class="setting-value">pipeline-progress</p>
        </div>

        <div class="setting-line">
          <p class="setting-label">Last run</p>
          <p class="setting-value">{{ pipeline.lastRun?.provider ?? "none" }}</p>
        </div>
      </div>
    </div>
  </section>
</template>
