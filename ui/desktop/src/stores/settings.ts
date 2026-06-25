import { defineStore } from "pinia";
import { ref, computed } from "vue";

const CONFIG_KEY = "jobhunter.desktopConfig.v1";

interface PersistedConfig {
  ai?: {
    provider?: string;
    min_score?: number | null;
  };
}

export const useSettingsStore = defineStore("settings", () => {
  const minScore = ref<number | null>(null);

  function loadFromStorage() {
    try {
      const raw = localStorage.getItem(CONFIG_KEY);
      if (!raw) {
        minScore.value = null;
        return;
      }
      const parsed = JSON.parse(raw) as PersistedConfig;
      const score = parsed.ai?.min_score;
      minScore.value =
        typeof score === "number" && Number.isFinite(score) ? score : null;
    } catch {
      minScore.value = null;
    }
  }

  function saveMinScore(value: number | null) {
    try {
      const raw = localStorage.getItem(CONFIG_KEY);
      const parsed: PersistedConfig = raw ? JSON.parse(raw) : {};
      if (!parsed.ai) parsed.ai = {};
      parsed.ai.min_score = value;
      localStorage.setItem(CONFIG_KEY, JSON.stringify(parsed));
    } catch {
      // ignore
    }
    minScore.value = value;
  }

  const effectiveMinScore = computed(() => minScore.value ?? 40);

  loadFromStorage();

  return { minScore, effectiveMinScore, loadFromStorage, saveMinScore };
});
