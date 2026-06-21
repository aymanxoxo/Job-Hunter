<script setup lang="ts">
import { FileUp, Play, Plus, Save, Send, Sparkles, X } from "@lucide/vue";
import { computed, onMounted, ref } from "vue";
import { useRouter } from "vue-router";

import { usePipelineStore } from "@/stores/pipeline";

type CriteriaArrayKey =
  | "titles"
  | "keywords"
  | "exclude_keywords"
  | "seniority_levels"
  | "locations";

interface CriteriaDraft {
  titles: string[];
  keywords: string[];
  exclude_keywords: string[];
  seniority_levels: string[];
  locations: string[];
  min_score_threshold: number;
}

interface ConversationTurn {
  id: number;
  text: string;
}

const storageKey = "jobhunter.criteriaDraft.v1";
const seniorityOptions = ["junior", "mid", "senior", "lead", "staff", "principal"];
const keywordTerms = [
  "python",
  "c#",
  ".net",
  "kubernetes",
  "gcp",
  "aws",
  "azure",
  "ci/cd",
  "devops",
  "api",
  "typescript",
  "vue",
  "react",
];

const chipGroups: Array<{ key: CriteriaArrayKey; label: string }> = [
  { key: "titles", label: "Titles" },
  { key: "keywords", label: "Keywords" },
  { key: "exclude_keywords", label: "Exclude" },
  { key: "locations", label: "Locations" },
];

const pipeline = usePipelineStore();
const router = useRouter();

const profile = ref("Senior Python developer seeking remote work");
const provider = ref("ollama");
const draft = ref<CriteriaDraft | null>(null);
const isGenerating = ref(false);
const refineText = ref("");
const turns = ref<ConversationTurn[]>([]);
const savedMessage = ref("");

const hasProfile = computed(() => profile.value.trim().length > 0);
const canGenerate = computed(() => hasProfile.value && !isGenerating.value);
const canRunSearch = computed(() => hasProfile.value && pipeline.status !== "running");
const canSave = computed(() => draft.value !== null);

onMounted(() => {
  const saved = loadSavedDraft();
  if (saved) {
    draft.value = saved;
  }
});

function emptyDraft(): CriteriaDraft {
  return {
    titles: [],
    keywords: [],
    exclude_keywords: [],
    seniority_levels: [],
    locations: [],
    min_score_threshold: 40,
  };
}

function unique(items: string[]): string[] {
  const seen = new Set<string>();
  const result: string[] = [];
  for (const item of items) {
    const clean = item.trim();
    const key = clean.toLowerCase();
    if (clean && !seen.has(key)) {
      seen.add(key);
      result.push(clean);
    }
  }
  return result;
}

function includesTerm(text: string, term: string): boolean {
  if (term === "c#") {
    return /(^|[^a-z0-9])c#([^a-z0-9]|$)/i.test(text);
  }
  if (term === ".net") {
    return /\.net/i.test(text);
  }
  if (term === "ci/cd") {
    return /ci\s*\/\s*cd/i.test(text);
  }
  return new RegExp(`(^|[^a-z0-9])${term.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}([^a-z0-9]|$)`, "i").test(
    text,
  );
}

function deriveCriteriaDraft(source: string): CriteriaDraft {
  const text = source.toLowerCase();
  const keywords = keywordTerms.filter((term) => includesTerm(source, term));
  const titles: string[] = [];

  if (includesTerm(source, "devops")) {
    titles.push("DevOps Engineer");
  }
  if (includesTerm(source, "python")) {
    titles.push("Python Developer");
  }
  if (includesTerm(source, "c#") || includesTerm(source, ".net")) {
    titles.push(".NET Engineer");
  }
  if (["kubernetes", "gcp", "aws", "azure"].some((term) => includesTerm(source, term))) {
    titles.push("Platform Engineer");
  }
  if (includesTerm(source, "api")) {
    titles.push("Backend Engineer");
  }
  if (titles.length === 0) {
    titles.push("Software Engineer");
  }

  const seniority = seniorityOptions.filter((level) => includesTerm(source, level));
  if (seniority.length === 0 && /\b(7|8|9|10|11|12|13|14|15)\+?\s*(yrs?|years?)\b/i.test(text)) {
    seniority.push("senior");
  }

  const locations: string[] = [];
  if (includesTerm(source, "remote")) {
    locations.push("remote");
  }
  if (includesTerm(source, "cairo")) {
    locations.push("cairo");
  }

  return {
    ...emptyDraft(),
    titles: unique(titles),
    keywords: unique(keywords),
    seniority_levels: unique(seniority),
    locations: unique(locations),
  };
}

async function generateCriteria() {
  if (!canGenerate.value) {
    return;
  }
  isGenerating.value = true;
  savedMessage.value = "";
  await new Promise((resolve) => setTimeout(resolve, 0));
  draft.value = deriveCriteriaDraft(profile.value);
  isGenerating.value = false;
}

function updateChip(key: CriteriaArrayKey, index: number, value: string) {
  if (!draft.value) {
    return;
  }
  draft.value[key][index] = value;
}

function addChip(key: CriteriaArrayKey) {
  if (!draft.value) {
    draft.value = emptyDraft();
  }
  draft.value[key].push("");
}

function removeChip(key: CriteriaArrayKey, index: number) {
  draft.value?.[key].splice(index, 1);
}

function toggleSeniority(level: string) {
  if (!draft.value) {
    draft.value = emptyDraft();
  }
  const levels = draft.value.seniority_levels;
  const index = levels.findIndex((item) => item.toLowerCase() === level);
  if (index >= 0) {
    levels.splice(index, 1);
  } else {
    levels.push(level);
  }
}

function isSenioritySelected(level: string): boolean {
  return draft.value?.seniority_levels.some((item) => item.toLowerCase() === level) ?? false;
}

function ensureDraft(): CriteriaDraft {
  if (!draft.value) {
    draft.value = emptyDraft();
  }
  return draft.value;
}

function addUnique(key: CriteriaArrayKey, value: string) {
  const target = ensureDraft()[key];
  if (!target.some((item) => item.trim().toLowerCase() === value.trim().toLowerCase())) {
    target.push(value.trim());
  }
}

function removeMatchingFromDraft(value: string) {
  const current = ensureDraft();
  const normalized = value.trim().toLowerCase();
  for (const key of ["titles", "keywords", "locations"] as CriteriaArrayKey[]) {
    current[key] = current[key].filter((item) => item.trim().toLowerCase() !== normalized);
  }
}

function sendRefine() {
  const text = refineText.value.trim();
  if (!text) {
    return;
  }
  turns.value.push({ id: Date.now(), text });
  refineText.value = "";

  const excludeMatch = /^(drop|remove|exclude)\s+(.+)$/i.exec(text);
  if (excludeMatch) {
    const term = excludeMatch[2].trim();
    removeMatchingFromDraft(term);
    addUnique("exclude_keywords", term);
    return;
  }

  const addMatch = /^(add|include|focus)\s+(.+)$/i.exec(text);
  addUnique("keywords", (addMatch?.[2] ?? text).trim());
}

function isCriteriaDraft(value: unknown): value is CriteriaDraft {
  const candidate = value as CriteriaDraft;
  return (
    typeof candidate === "object" &&
    candidate !== null &&
    Array.isArray(candidate.titles) &&
    Array.isArray(candidate.keywords) &&
    Array.isArray(candidate.exclude_keywords) &&
    Array.isArray(candidate.seniority_levels) &&
    Array.isArray(candidate.locations) &&
    typeof candidate.min_score_threshold === "number"
  );
}

function loadSavedDraft(): CriteriaDraft | null {
  try {
    const raw = localStorage.getItem(storageKey);
    if (!raw) {
      return null;
    }
    const parsed = JSON.parse(raw);
    return isCriteriaDraft(parsed) ? parsed : null;
  } catch {
    return null;
  }
}

function saveCriteria() {
  if (!draft.value) {
    return;
  }
  localStorage.setItem(storageKey, JSON.stringify(draft.value));
  savedMessage.value = "Saved";
}

function summarizeList(label: string, values: string[]): string {
  const clean = unique(values);
  return clean.length ? `${label}: ${clean.join(", ")}` : "";
}

function criteriaSummary(current: CriteriaDraft): string {
  return [
    summarizeList("Titles", current.titles),
    summarizeList("Keywords", current.keywords),
    summarizeList("Exclude", current.exclude_keywords),
    summarizeList("Seniority", current.seniority_levels),
    summarizeList("Locations", current.locations),
    `Minimum score: ${current.min_score_threshold}`,
  ]
    .filter(Boolean)
    .join("\n");
}

function augmentedProfile(): string {
  if (!draft.value) {
    return profile.value.trim();
  }
  return `${profile.value.trim()}\n\nUser-edited search criteria:\n${criteriaSummary(draft.value)}`;
}

async function runSearch() {
  if (!canRunSearch.value) {
    return;
  }
  try {
    await pipeline.runPipeline({
      profile: augmentedProfile(),
      provider: provider.value,
    });
    await router.push("/results");
  } catch {
    // The pipeline store owns the visible error state.
  }
}
</script>

<template>
  <section class="criteria-view" aria-labelledby="criteria-title">
    <div class="criteria-intro">
      <div>
        <h2 id="criteria-title" class="section-title">Profile</h2>
        <p class="criteria-lead">
          Describe your background once. Fine-tune the generated criteria before running search.
        </p>
      </div>
      <button
        class="upload-control"
        type="button"
        aria-disabled="true"
        data-testid="upload-control"
        disabled
      >
        <FileUp aria-hidden="true" />
        <span>Upload file</span>
        <span class="soon-badge">Soon</span>
      </button>
    </div>

    <div class="criteria-card">
      <div class="profile-grid">
        <label class="criteria-field profile-field">
          <span>Profile</span>
          <textarea
            v-model="profile"
            class="criteria-textarea"
            data-testid="profile-input"
            placeholder="Senior .NET / DevOps engineer, 8 yrs experience..."
          />
        </label>

        <label class="criteria-field">
          <span>Provider</span>
          <select v-model="provider" class="criteria-select" data-testid="provider-select">
            <option value="ollama">Ollama</option>
            <option value="gemini">Gemini</option>
            <option value="openrouter">OpenRouter</option>
          </select>
        </label>
      </div>

      <div class="criteria-actions">
        <button
          class="secondary-action"
          type="button"
          data-testid="generate-button"
          :disabled="!canGenerate"
          @click="generateCriteria"
        >
          <Sparkles aria-hidden="true" />
          <span>{{ isGenerating ? "Generating..." : draft ? "Regenerate" : "Generate with AI" }}</span>
        </button>
      </div>
    </div>

    <div v-if="isGenerating" class="criteria-card muted-card" aria-live="polite">
      Generating criteria...
    </div>

    <div v-if="draft" class="criteria-card criteria-panel" aria-live="polite">
      <div class="panel-header">
        <div>
          <h3>Generated criteria</h3>
          <p>Click into any chip to edit before running.</p>
        </div>
      </div>

      <div class="criteria-grid">
        <template v-for="group in chipGroups" :key="group.key">
          <div class="criteria-label">{{ group.label }}</div>
          <div class="chip-row">
            <span v-for="(_, index) in draft[group.key]" :key="`${group.key}-${index}`" class="edit-chip">
              <input
                :value="draft[group.key][index]"
                :data-testid="`${group.key}-chip-input`"
                @input="updateChip(group.key, index, ($event.target as HTMLInputElement).value)"
              />
              <button
                type="button"
                :data-testid="`${group.key}-remove`"
                :aria-label="`Remove ${group.label}`"
                @click="removeChip(group.key, index)"
              >
                <X aria-hidden="true" />
              </button>
            </span>
            <button
              class="chip-add"
              type="button"
              :data-testid="`${group.key}-add`"
              :aria-label="`Add ${group.label}`"
              @click="addChip(group.key)"
            >
              <Plus aria-hidden="true" />
            </button>
          </div>
        </template>

        <div class="criteria-label">Seniority</div>
        <div class="seniority-row">
          <button
            v-for="level in seniorityOptions"
            :key="level"
            class="toggle-chip"
            type="button"
            :class="{ selected: isSenioritySelected(level) }"
            :aria-pressed="isSenioritySelected(level)"
            @click="toggleSeniority(level)"
          >
            {{ level }}
          </button>
        </div>

        <div class="criteria-label">Min score</div>
        <label class="threshold-row">
          <input
            v-model.number="draft.min_score_threshold"
            type="range"
            min="0"
            max="100"
            step="5"
            aria-label="Minimum score threshold"
          />
          <span>{{ draft.min_score_threshold }}</span>
        </label>
      </div>

      <div class="refine-box">
        <div>
          <h3>Refine</h3>
          <p>Use short commands like “focus platform engineering” or “exclude python”.</p>
        </div>
        <div class="refine-row">
          <input
            v-model="refineText"
            class="refine-input"
            data-testid="refine-input"
            placeholder="focus platform engineering"
            @keydown.enter.prevent="sendRefine"
          />
          <button class="icon-action" type="button" data-testid="refine-send" @click="sendRefine">
            <Send aria-hidden="true" />
          </button>
        </div>
        <ul v-if="turns.length" class="turn-list" aria-label="Refine conversation">
          <li v-for="turn in turns" :key="turn.id">{{ turn.text }}</li>
        </ul>
      </div>

      <div class="footer-actions">
        <button class="secondary-action" type="button" data-testid="save-button" :disabled="!canSave" @click="saveCriteria">
          <Save aria-hidden="true" />
          <span>Save Criteria</span>
        </button>
        <span class="saved-message">{{ savedMessage }}</span>
        <button
          class="primary-button"
          type="button"
          data-testid="run-search"
          :disabled="!canRunSearch"
          @click="runSearch"
        >
          <Play aria-hidden="true" />
          <span>{{ pipeline.status === "running" ? "Running" : "Run Search" }}</span>
        </button>
      </div>
    </div>
  </section>
</template>

<style scoped>
.criteria-view {
  display: grid;
  gap: var(--sp-4);
  width: 100%;
  max-width: var(--content-max);
  margin: 0 auto;
}

.criteria-intro,
.criteria-card,
.panel-header,
.criteria-actions,
.footer-actions,
.refine-row {
  display: flex;
  align-items: center;
  gap: var(--sp-4);
}

.criteria-intro,
.panel-header,
.footer-actions {
  justify-content: space-between;
}

.criteria-lead,
.panel-header p,
.refine-box p,
.muted-card {
  margin: var(--sp-1) 0 0;
  color: var(--text-muted);
  font-size: var(--fs-sm);
  line-height: var(--lh-sm);
}

.criteria-card {
  flex-direction: column;
  align-items: stretch;
  padding: var(--sp-5);
  border: 1px solid var(--border);
  border-radius: var(--r-lg);
  background: var(--surface);
  box-shadow: var(--sh-1);
}

.profile-grid {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 180px;
  gap: var(--sp-4);
  align-items: end;
}

.criteria-field {
  display: grid;
  gap: var(--sp-2);
  min-width: 0;
}

.criteria-field span,
.criteria-label {
  color: var(--text-muted);
  font-size: var(--fs-sm);
  font-weight: var(--fw-medium);
  line-height: var(--lh-sm);
}

.criteria-textarea,
.criteria-select,
.refine-input,
.edit-chip input {
  width: 100%;
  min-width: 0;
  border: 1px solid var(--border);
  border-radius: var(--r-md);
  color: var(--text);
  background: var(--surface);
}

.criteria-textarea {
  min-height: 132px;
  resize: vertical;
  padding: var(--sp-3);
}

.criteria-select {
  height: 38px;
  padding: 0 var(--sp-3);
}

.criteria-actions,
.footer-actions {
  justify-content: flex-end;
}

.upload-control,
.secondary-action,
.icon-action,
.chip-add,
.edit-chip button,
.toggle-chip {
  border: 1px solid var(--border);
  color: var(--text);
  background: var(--surface);
}

.upload-control,
.secondary-action,
.primary-button {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: var(--sp-2);
  min-height: 38px;
  padding: 0 var(--sp-4);
  border-radius: var(--r-md);
  font-weight: var(--fw-medium);
}

.upload-control {
  border-style: dashed;
  color: var(--text-subtle);
  background: var(--surface-2);
}

.secondary-action:hover:not(:disabled),
.icon-action:hover,
.chip-add:hover,
.edit-chip button:hover,
.toggle-chip:hover {
  background: var(--surface-2);
}

.secondary-action:disabled,
.upload-control:disabled {
  opacity: .64;
}

.soon-badge {
  padding: 1px var(--sp-2);
  border-radius: var(--r-pill);
  background: var(--surface-3);
  font-size: var(--fs-xs);
  line-height: var(--lh-xs);
}

.criteria-panel {
  gap: var(--sp-5);
}

.panel-header h3,
.refine-box h3 {
  margin: 0;
  font-size: var(--fs-lg);
  line-height: var(--lh-lg);
}

.criteria-grid {
  display: grid;
  grid-template-columns: 108px minmax(0, 1fr);
  gap: var(--sp-3) var(--sp-4);
  align-items: start;
}

.chip-row,
.seniority-row {
  display: flex;
  flex-wrap: wrap;
  gap: var(--sp-2);
  min-width: 0;
}

.edit-chip {
  display: inline-flex;
  align-items: center;
  min-width: 150px;
  max-width: 260px;
  border-radius: var(--r-pill);
  background: var(--surface-2);
}

.edit-chip input {
  height: 30px;
  border-color: transparent;
  border-radius: var(--r-pill) 0 0 var(--r-pill);
  background: transparent;
  padding: 0 var(--sp-2) 0 var(--sp-3);
}

.edit-chip button,
.chip-add,
.icon-action {
  display: inline-grid;
  width: 30px;
  height: 30px;
  place-items: center;
  flex: 0 0 auto;
  border-radius: var(--r-pill);
}

.edit-chip button {
  border-color: transparent;
  background: transparent;
}

.chip-add svg,
.edit-chip svg,
.icon-action svg,
.primary-button svg,
.secondary-action svg,
.upload-control svg {
  width: 16px;
  height: 16px;
  stroke-width: 1.7;
}

.toggle-chip {
  min-height: 30px;
  padding: 0 var(--sp-3);
  border-radius: var(--r-pill);
}

.toggle-chip.selected {
  border-color: var(--accent);
  color: var(--accent);
  background: var(--accent-soft);
}

.threshold-row {
  display: flex;
  align-items: center;
  gap: var(--sp-3);
}

.threshold-row input {
  flex: 1;
}

.threshold-row span {
  min-width: 32px;
  color: var(--text-muted);
  font-family: var(--mono);
  font-size: var(--fs-sm);
  text-align: right;
}

.refine-box {
  display: grid;
  gap: var(--sp-3);
  padding-top: var(--sp-4);
  border-top: 1px solid var(--border);
}

.refine-input {
  height: 38px;
  padding: 0 var(--sp-3);
}

.turn-list {
  display: grid;
  gap: var(--sp-2);
  margin: 0;
  padding: 0;
  list-style: none;
}

.turn-list li {
  padding: var(--sp-2) var(--sp-3);
  border-radius: var(--r-md);
  color: var(--text-muted);
  background: var(--surface-2);
}

.saved-message {
  flex: 1;
  color: var(--success);
  font-size: var(--fs-sm);
  font-weight: var(--fw-medium);
}

@media (max-width: 900px) {
  .criteria-intro,
  .footer-actions {
    align-items: stretch;
    flex-direction: column;
  }

  .profile-grid,
  .criteria-grid {
    grid-template-columns: 1fr;
  }

  .upload-control,
  .secondary-action,
  .primary-button {
    width: 100%;
  }
}
</style>
