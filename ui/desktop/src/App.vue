<script setup lang="ts">
import { BriefcaseBusiness, ListChecks, Moon, Settings, Sun } from "@lucide/vue";
import { computed, ref, watchEffect } from "vue";
import { RouterLink, RouterView, useRoute } from "vue-router";

import PipelineProgress from "@/components/PipelineProgress.vue";
import { usePipelineStore } from "@/stores/pipeline";

const pipeline = usePipelineStore();
const route = useRoute();
const darkMode = ref(false);

const navItems = [
  { to: "/criteria", label: "Criteria", icon: ListChecks },
  { to: "/results", label: "Results", icon: BriefcaseBusiness },
  { to: "/settings", label: "Settings", icon: Settings },
];

const screenTitle = computed(() => String(route.meta.title ?? "JobHunter"));
const showProgress = computed(() => pipeline.status !== "idle" || pipeline.events.length > 0);

watchEffect(() => {
  document.documentElement.dataset.theme = darkMode.value ? "dark" : "light";
});
</script>

<template>
  <div class="app-shell">
    <aside class="app-nav" aria-label="Primary">
      <div class="brand">
        <span class="brand-mark" aria-hidden="true">JH</span>
        <span class="brand-name">JobHunter</span>
      </div>

      <nav class="nav-list">
        <RouterLink
          v-for="item in navItems"
          :key="item.to"
          class="nav-link"
          :to="item.to"
          :aria-label="item.label"
        >
          <component :is="item.icon" class="nav-icon" aria-hidden="true" />
          <span>{{ item.label }}</span>
        </RouterLink>
      </nav>
    </aside>

    <main class="app-main">
      <header class="app-header">
        <div>
          <h1>{{ screenTitle }}</h1>
          <p class="run-state" aria-live="polite">
            {{ pipeline.statusLabel }}
          </p>
        </div>

        <button
          class="icon-button"
          type="button"
          :aria-label="darkMode ? 'Use light theme' : 'Use dark theme'"
          @click="darkMode = !darkMode"
        >
          <Moon v-if="!darkMode" aria-hidden="true" />
          <Sun v-else aria-hidden="true" />
        </button>
      </header>

      <div
        v-if="showProgress"
        class="app-progress"
        data-testid="app-pipeline-progress"
      >
        <PipelineProgress />
      </div>

      <RouterView />
    </main>
  </div>
</template>
