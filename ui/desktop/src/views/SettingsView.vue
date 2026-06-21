<script setup lang="ts">
import { Clipboard, KeyRound, Link, Save, ShieldCheck, SlidersHorizontal } from "@lucide/vue";
import { computed, onMounted, ref } from "vue";

import { usePipelineStore } from "@/stores/pipeline";

type Provider = "ollama" | "openrouter" | "gemini";

interface DesktopSettings {
  provider: Provider;
  connectors: {
    mock: boolean;
    adzuna: boolean;
  };
  maxResults: number;
  delaySeconds: number;
}

interface PersistedConfig {
  ai: {
    provider: Provider;
  };
  connectors: {
    mock: {
      enabled: boolean;
      max_results: number;
      delay_min: number;
      delay_max: number;
    };
    adzuna: {
      enabled: boolean;
      max_results: number;
      delay_min: number;
      delay_max: number;
    };
  };
  auth: {
    gemini_api_key_env: "GEMINI_API_KEY";
    openrouter_api_key_env: "OPENROUTER_API_KEY";
  };
}

const configKey = "jobhunter.desktopConfig.v1";

const pipeline = usePipelineStore();
const settings = ref<DesktopSettings>(defaultSettings());
const apiKey = ref("");
const savedMessage = ref("");
const secretMessage = ref("");
const providerEnvVars = {
  gemini: "GEMINI_API_KEY",
  openrouter: "OPENROUTER_API_KEY",
} as const;

const providerOptions: Array<{ value: Provider; label: string; detail: string }> = [
  { value: "ollama", label: "Ollama", detail: "Local, no API key" },
  { value: "openrouter", label: "OpenRouter", detail: "API key via OPENROUTER_API_KEY" },
  { value: "gemini", label: "Gemini", detail: "API key via GEMINI_API_KEY" },
];

const selectedProvider = computed(
  () => providerOptions.find((provider) => provider.value === settings.value.provider) ?? providerOptions[0],
);

const apiKeyRequired = computed(() => settings.value.provider !== "ollama");
const envVarName = computed(() => {
  return settings.value.provider === "ollama" ? "" : providerEnvVars[settings.value.provider];
});
const currentProviderSaved = computed(() => settings.value.provider === "ollama");

const authRows = computed(() => [
  {
    label: "Ollama",
    state: "Ready",
    detail: "Local provider",
    ready: true,
  },
  {
    label: "OpenRouter",
    state: "Missing",
    detail: providerEnvVars.openrouter,
    ready: false,
  },
  {
    label: "Gemini",
    state: "Missing",
    detail: providerEnvVars.gemini,
    ready: false,
  },
]);

onMounted(() => {
  settings.value = loadSettings();
});

function defaultSettings(): DesktopSettings {
  return {
    provider: "ollama",
    connectors: {
      mock: true,
      adzuna: false,
    },
    maxResults: 50,
    delaySeconds: 2,
  };
}

function isProvider(value: unknown): value is Provider {
  return value === "ollama" || value === "openrouter" || value === "gemini";
}

function clampNumber(value: unknown, fallback: number, min: number, max: number): number {
  const numeric = typeof value === "number" ? value : Number(value);
  if (!Number.isFinite(numeric)) {
    return fallback;
  }
  return Math.min(max, Math.max(min, Math.round(numeric)));
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function loadSettings(): DesktopSettings {
  try {
    const raw = localStorage.getItem(configKey);
    if (!raw) {
      return defaultSettings();
    }
    const parsed = JSON.parse(raw);
    if (!isRecord(parsed)) {
      return defaultSettings();
    }
    const ai = isRecord(parsed.ai) ? parsed.ai : {};
    const connectors = isRecord(parsed.connectors) ? parsed.connectors : {};
    const mock = isRecord(connectors.mock) ? connectors.mock : {};
    const adzuna = isRecord(connectors.adzuna) ? connectors.adzuna : {};
    const mockEnabled = typeof mock.enabled === "boolean" ? mock.enabled : defaultSettings().connectors.mock;
    const adzunaEnabled =
      typeof adzuna.enabled === "boolean" ? adzuna.enabled : defaultSettings().connectors.adzuna;

    return {
      provider: isProvider(ai.provider) ? ai.provider : defaultSettings().provider,
      connectors: {
        mock: mockEnabled,
        adzuna: adzunaEnabled,
      },
      maxResults: clampNumber(mock.max_results ?? adzuna.max_results, defaultSettings().maxResults, 1, 100),
      delaySeconds: clampNumber(mock.delay_min ?? adzuna.delay_min, defaultSettings().delaySeconds, 0, 10),
    };
  } catch {
    return defaultSettings();
  }
}

function configPayload(): PersistedConfig {
  return {
    ai: {
      provider: settings.value.provider,
    },
    connectors: {
      mock: {
        enabled: settings.value.connectors.mock,
        max_results: settings.value.maxResults,
        delay_min: settings.value.delaySeconds,
        delay_max: settings.value.delaySeconds,
      },
      adzuna: {
        enabled: settings.value.connectors.adzuna,
        max_results: settings.value.maxResults,
        delay_min: settings.value.delaySeconds,
        delay_max: settings.value.delaySeconds,
      },
    },
    auth: {
      gemini_api_key_env: providerEnvVars.gemini,
      openrouter_api_key_env: providerEnvVars.openrouter,
    },
  };
}

function saveSettings() {
  localStorage.setItem(configKey, JSON.stringify(configPayload()));
  savedMessage.value = "Saved";
}

async function saveApiKey() {
  const key = apiKey.value.trim();
  if (!apiKeyRequired.value || key.length === 0) {
    return;
  }
  try {
    await navigator.clipboard.writeText(key);
    secretMessage.value = `Copied! Paste into your shell: export ${envVarName.value}=<key>`;
  } catch {
    secretMessage.value = "Copy failed — paste the key manually into your environment.";
  }
  apiKey.value = "";
}
</script>

<template>
  <section class="settings-view" aria-labelledby="settings-title">
    <div class="settings-card settings-hero">
      <div>
        <h2 id="settings-title" class="section-title">Runtime</h2>
        <p class="settings-lead">{{ selectedProvider.detail }}</p>
      </div>
      <span class="status-pill" :class="{ ready: currentProviderSaved }">
        <ShieldCheck aria-hidden="true" />
        <span>{{ currentProviderSaved ? "Ready" : "Needs key" }}</span>
      </span>
    </div>

    <div class="settings-grid">
      <section class="settings-card" aria-labelledby="provider-title">
        <div class="card-header">
          <div>
            <h3 id="provider-title">AI provider</h3>
            <p>Controls the provider passed to the pipeline run.</p>
          </div>
          <SlidersHorizontal aria-hidden="true" />
        </div>

        <label class="field">
          <span>Provider</span>
          <select v-model="settings.provider" data-testid="provider-select">
            <option v-for="provider in providerOptions" :key="provider.value" :value="provider.value">
              {{ provider.label }}
            </option>
          </select>
        </label>

        <div class="connector-list" aria-label="Connectors">
          <label class="check-row">
            <input v-model="settings.connectors.mock" type="checkbox" data-testid="connector-mock" />
            <span>Mock connector</span>
          </label>
          <label class="check-row">
            <input v-model="settings.connectors.adzuna" type="checkbox" data-testid="connector-adzuna" />
            <span>Adzuna connector</span>
          </label>
        </div>
      </section>

      <section class="settings-card" aria-labelledby="limits-title">
        <div class="card-header">
          <div>
            <h3 id="limits-title">Search limits</h3>
            <p>Applies to enabled connectors.</p>
          </div>
        </div>

        <label class="slider-field">
          <span>Max results</span>
          <input
            v-model.number="settings.maxResults"
            type="range"
            min="1"
            max="100"
            step="1"
            data-testid="max-results"
          />
          <output>{{ settings.maxResults }}</output>
        </label>

        <label class="slider-field">
          <span>Delay</span>
          <input
            v-model.number="settings.delaySeconds"
            type="range"
            min="0"
            max="10"
            step="1"
            data-testid="delay-range"
          />
          <output>{{ settings.delaySeconds }}s</output>
        </label>

        <div class="footer-actions">
          <span class="saved-message" aria-live="polite">{{ savedMessage }}</span>
          <button class="primary-button" type="button" data-testid="save-settings" @click="saveSettings">
            <Save aria-hidden="true" />
            <span>Save Settings</span>
          </button>
        </div>
      </section>
    </div>

    <div class="settings-grid">
      <section class="settings-card" aria-labelledby="secret-title">
        <div class="card-header">
          <div>
            <h3 id="secret-title">API key</h3>
            <p>Your key is never stored by this app. Set it as an environment variable before running the pipeline.</p>
          </div>
          <KeyRound aria-hidden="true" />
        </div>

        <label class="field">
          <span>{{ selectedProvider.label }} key</span>
          <input
            v-model="apiKey"
            type="password"
            data-testid="api-key"
            autocomplete="off"
            :disabled="!apiKeyRequired"
            :placeholder="apiKeyRequired ? 'Paste key' : 'No key required'"
          />
        </label>

        <div class="footer-actions">
          <span class="saved-message" aria-live="polite">{{ secretMessage }}</span>
          <button
            class="secondary-action"
            type="button"
            data-testid="save-api-key"
            :disabled="!apiKeyRequired || apiKey.trim().length === 0"
            @click="saveApiKey"
          >
            <Clipboard aria-hidden="true" />
            <span>Copy to clipboard</span>
          </button>
        </div>
      </section>

      <section class="settings-card" aria-labelledby="auth-title">
        <div class="card-header">
          <div>
            <h3 id="auth-title">Auth status</h3>
            <p>OAuth and browser sessions are shown but deferred.</p>
          </div>
        </div>

        <div class="auth-list">
          <div v-for="row in authRows" :key="row.label" class="auth-row">
            <div>
              <strong>{{ row.label }}</strong>
              <span>{{ row.detail }}</span>
            </div>
            <span class="status-pill small" :class="{ ready: row.ready }">{{ row.state }}</span>
          </div>
        </div>

        <div class="deferred-actions">
          <button class="secondary-action" type="button" data-testid="connect-oauth" disabled>
            <Link aria-hidden="true" />
            <span>OAuth</span>
            <span class="soon-badge">Deferred</span>
          </button>
          <button class="secondary-action" type="button" data-testid="connect-linkedin" disabled>
            <Link aria-hidden="true" />
            <span>LinkedIn</span>
            <span class="soon-badge">Deferred</span>
          </button>
        </div>
      </section>
    </div>

    <p class="last-run">Last run provider: {{ pipeline.lastRun?.provider ?? "none" }}</p>
  </section>
</template>

<style scoped>
.settings-view {
  display: grid;
  gap: var(--sp-4);
  width: 100%;
  max-width: var(--content-max);
  margin: 0 auto;
}

.settings-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: var(--sp-4);
}

.settings-card {
  display: grid;
  gap: var(--sp-4);
  min-width: 0;
  padding: var(--sp-5);
  border: 1px solid var(--border);
  border-radius: var(--r-lg);
  background: var(--surface);
  box-shadow: var(--sh-1);
}

.settings-hero,
.card-header,
.footer-actions,
.check-row,
.auth-row,
.deferred-actions,
.status-pill {
  display: flex;
  align-items: center;
  gap: var(--sp-3);
}

.settings-hero,
.card-header,
.footer-actions,
.auth-row {
  justify-content: space-between;
}

.settings-lead,
.card-header p,
.last-run {
  margin: var(--sp-1) 0 0;
  color: var(--text-muted);
  font-size: var(--fs-sm);
  line-height: var(--lh-sm);
}

.card-header h3 {
  margin: 0;
  font-size: var(--fs-lg);
  line-height: var(--lh-lg);
}

.card-header svg {
  width: 20px;
  height: 20px;
  color: var(--text-subtle);
  stroke-width: 1.7;
}

.field,
.slider-field {
  display: grid;
  gap: var(--sp-2);
}

.field span,
.slider-field span {
  color: var(--text-muted);
  font-size: var(--fs-sm);
  font-weight: var(--fw-medium);
  line-height: var(--lh-sm);
}

.field select,
.field input {
  width: 100%;
  min-width: 0;
  height: 38px;
  padding: 0 var(--sp-3);
  border: 1px solid var(--border);
  border-radius: var(--r-md);
  color: var(--text);
  background: var(--surface);
  font: inherit;
}

.field input:disabled {
  color: var(--text-subtle);
  background: var(--surface-2);
}

.connector-list,
.auth-list {
  display: grid;
  gap: var(--sp-2);
}

.check-row {
  justify-content: flex-start;
  min-height: 34px;
  color: var(--text);
}

.check-row input {
  width: 16px;
  height: 16px;
  accent-color: var(--accent);
}

.slider-field {
  grid-template-columns: 108px minmax(0, 1fr) 44px;
  align-items: center;
}

.slider-field input {
  accent-color: var(--accent);
}

.slider-field output {
  color: var(--text-muted);
  font-family: var(--mono);
  font-size: var(--fs-sm);
  text-align: right;
}

.primary-button,
.secondary-action {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: var(--sp-2);
  min-height: 38px;
  padding: 0 var(--sp-4);
  border-radius: var(--r-md);
  font-weight: var(--fw-medium);
}

.secondary-action {
  border: 1px solid var(--border);
  color: var(--text);
  background: var(--surface);
}

.secondary-action:hover:not(:disabled) {
  background: var(--surface-2);
}

.secondary-action:disabled {
  opacity: .64;
}

.primary-button svg,
.secondary-action svg {
  width: 16px;
  height: 16px;
  stroke-width: 1.7;
}

.saved-message {
  flex: 1;
  color: var(--success);
  font-size: var(--fs-sm);
  font-weight: var(--fw-medium);
}

.status-pill {
  justify-content: center;
  padding: 3px var(--sp-2);
  border-radius: var(--r-pill);
  color: var(--warning);
  background: var(--warning-soft);
  font-size: var(--fs-xs);
  font-weight: var(--fw-medium);
  line-height: var(--lh-xs);
}

.status-pill.ready {
  color: var(--success);
  background: var(--success-soft);
}

.status-pill.small {
  min-width: 58px;
}

.status-pill svg {
  width: 14px;
  height: 14px;
  stroke-width: 1.7;
}

.auth-row {
  padding: var(--sp-3);
  border: 1px solid var(--border);
  border-radius: var(--r-md);
  background: var(--surface-2);
}

.auth-row div {
  display: grid;
  gap: 2px;
  min-width: 0;
}

.auth-row span {
  color: var(--text-muted);
  font-size: var(--fs-sm);
}

.deferred-actions {
  flex-wrap: wrap;
}

.soon-badge {
  padding: 1px var(--sp-2);
  border-radius: var(--r-pill);
  color: var(--text-muted);
  background: var(--surface-3);
  font-size: var(--fs-xs);
  line-height: var(--lh-xs);
}

.last-run {
  padding: 0 var(--sp-2);
}

@media (max-width: 900px) {
  .settings-grid {
    grid-template-columns: 1fr;
  }

  .settings-hero,
  .card-header,
  .footer-actions,
  .deferred-actions {
    align-items: stretch;
    flex-direction: column;
  }

  .slider-field {
    grid-template-columns: 1fr;
  }

  .primary-button,
  .secondary-action {
    width: 100%;
  }
}
</style>
