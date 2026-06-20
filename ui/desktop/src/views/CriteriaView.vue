<script setup lang="ts">
import { Play } from "@lucide/vue";
import { computed, ref } from "vue";
import { useRouter } from "vue-router";

import { usePipelineStore } from "@/stores/pipeline";

const pipeline = usePipelineStore();
const router = useRouter();
const profile = ref("Senior Python developer seeking remote work");
const provider = ref("ollama");

const canRun = computed(() => profile.value.trim().length > 0 && pipeline.status !== "running");

async function run() {
  if (!canRun.value) {
    return;
  }

  try {
    await pipeline.runPipeline({
      profile: profile.value.trim(),
      provider: provider.value,
    });
    await router.push("/results");
  } catch {
    // The store owns the user-visible error state.
  }
}
</script>

<template>
  <section class="view-surface" aria-labelledby="criteria-title">
    <div class="view-body">
      <h2 id="criteria-title" class="section-title">Profile</h2>

      <div class="field-grid">
        <label class="field">
          <span>Profile</span>
          <textarea v-model="profile" class="text-input" />
        </label>

        <label class="field">
          <span>Provider</span>
          <select v-model="provider" class="select-input">
            <option value="ollama">Ollama</option>
            <option value="gemini">Gemini</option>
            <option value="openrouter">OpenRouter</option>
          </select>
        </label>
      </div>

      <div class="button-row">
        <button class="primary-button" type="button" :disabled="!canRun" @click="run">
          <Play aria-hidden="true" />
          <span>{{ pipeline.status === "running" ? "Running" : "Run" }}</span>
        </button>
      </div>
    </div>
  </section>
</template>
