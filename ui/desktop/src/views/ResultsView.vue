<script setup lang="ts">
import { Download, ExternalLink, Play, Search, X } from "@lucide/vue";
import { computed, ref, watch } from "vue";

import { usePipelineStore, type JobResult } from "@/stores/pipeline";

type SortKey = "score" | "title" | "company" | "location" | "source" | "date";
type SortDirection = "asc" | "desc";

interface ResultRow {
  id: string;
  title: string;
  company: string;
  location: string;
  source: string;
  date: string;
  score: number | null;
  description: string;
  matchReason: string;
  redFlags: string[];
  url: string;
  raw: JobResult;
}

const pipeline = usePipelineStore();
const filterText = ref("");
const sortKey = ref<SortKey>("score");
const sortDirection = ref<SortDirection>("desc");
const selectedId = ref<string | null>(null);
const rows = ref<ResultRow[]>([]);
const exportMessage = ref("");

watch(
  () => pipeline.results,
  (results) => {
    rows.value = mergeRows(rows.value, normalizeResults(results));
    if (selectedId.value && !rows.value.some((row) => row.id === selectedId.value)) {
      selectedId.value = null;
    }
  },
  { immediate: true, deep: true },
);

const visibleRows = computed(() => rows.value.filter((row) => row.score === null || row.score >= 40));

const filteredRows = computed(() => {
  const terms = filterText.value
    .trim()
    .toLowerCase()
    .split(/\s+/)
    .filter(Boolean);

  if (terms.length === 0) {
    return visibleRows.value;
  }

  return visibleRows.value.filter((row) => {
    const haystack = [
      row.title,
      row.company,
      row.location,
      row.source,
      row.date,
      row.matchReason,
    ]
      .join(" ")
      .toLowerCase();
    return terms.every((term) => haystack.includes(term));
  });
});

const sortedRows = computed(() => {
  return [...filteredRows.value].sort((left, right) => {
    const comparison = compareRows(left, right, sortKey.value);
    return sortDirection.value === "asc" ? comparison : -comparison;
  });
});

const hiddenCount = computed(() => rows.value.length - visibleRows.value.length);
const selectedRow = computed(() => rows.value.find((row) => row.id === selectedId.value) ?? null);
const canRerun = computed(() => pipeline.status !== "running" && pipeline.lastRun !== null);

function stringValue(value: unknown, fallback: string): string {
  return typeof value === "string" && value.trim() ? value : fallback;
}

function numberValue(value: unknown): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function redFlagsValue(value: unknown): string[] {
  return Array.isArray(value) ? value.map(String).filter(Boolean) : [];
}

function rowIdentity(job: JobResult, index: number): string {
  return String(job.id ?? job.url ?? `${job.title ?? "job"}-${job.company ?? "company"}-${index}`);
}

function normalizeDate(value: unknown): string {
  const raw = stringValue(value, "");
  if (!raw) {
    return "Unknown";
  }
  const date = new Date(raw);
  if (Number.isNaN(date.valueOf())) {
    return raw;
  }
  return date.toISOString().slice(0, 10);
}

function normalizeResults(results: JobResult[]): ResultRow[] {
  return results.map((job, index) => ({
    id: rowIdentity(job, index),
    title: stringValue(job.title, "Untitled role"),
    company: stringValue(job.company, "Unknown company"),
    location: stringValue(job.location, "Unknown"),
    source: stringValue(job.source, "unknown"),
    date: normalizeDate(job.posted_date ?? job.date),
    score: numberValue(job.score),
    description: stringValue(job.description, "No description provided."),
    matchReason: stringValue(job.match_reason, "No match reason provided."),
    redFlags: redFlagsValue(job.red_flags),
    url: stringValue(job.url, ""),
    raw: job,
  }));
}

function mergeRows(existing: ResultRow[], incoming: ResultRow[]): ResultRow[] {
  const byId = new Map<string, ResultRow>();
  for (const row of existing) {
    byId.set(row.id, row);
  }
  for (const row of incoming) {
    byId.set(row.id, row);
  }
  return Array.from(byId.values());
}

function compareNullableScore(left: number | null, right: number | null): number {
  return (left ?? -1) - (right ?? -1);
}

function compareRows(left: ResultRow, right: ResultRow, key: SortKey): number {
  if (key === "score") {
    return compareNullableScore(left.score, right.score);
  }
  const leftValue = key === "date" ? left.date : left[key];
  const rightValue = key === "date" ? right.date : right[key];
  return leftValue.localeCompare(rightValue, undefined, { sensitivity: "base" });
}

function scoreBand(score: number | null): string {
  if (score === null) {
    return "score-gray";
  }
  if (score >= 80) {
    return "score-green";
  }
  if (score >= 60) {
    return "score-amber";
  }
  if (score >= 40) {
    return "score-orange";
  }
  return "score-gray";
}

function sortBy(key: SortKey) {
  if (sortKey.value === key) {
    sortDirection.value = sortDirection.value === "asc" ? "desc" : "asc";
    return;
  }
  sortKey.value = key;
  sortDirection.value = key === "score" ? "desc" : "asc";
}

function sortLabel(key: SortKey): string {
  if (sortKey.value !== key) {
    return "";
  }
  return sortDirection.value === "asc" ? " up" : " down";
}

function selectRow(row: ResultRow) {
  selectedId.value = row.id;
}

function closeDetail() {
  selectedId.value = null;
}

function exportResults() {
  const payload = JSON.stringify(sortedRows.value.map((row) => row.raw), null, 2);
  const blob = new Blob([payload], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = "jobhunter-results.json";
  anchor.click();
  URL.revokeObjectURL(url);
  exportMessage.value = `${sortedRows.value.length} exported`;
}

async function rerunSearch() {
  if (!pipeline.lastRun || pipeline.status === "running") {
    return;
  }
  const previous = rows.value;
  try {
    await pipeline.runPipeline(pipeline.lastRun);
  } finally {
    rows.value = mergeRows(previous, normalizeResults(pipeline.results));
  }
}
</script>

<template>
  <section class="results-view" aria-labelledby="results-title">
    <div class="results-toolbar">
      <div>
        <h2 id="results-title" class="section-title">Matches</h2>
        <p class="results-summary">
          {{ sortedRows.length }} shown
          <span v-if="hiddenCount">/ {{ hiddenCount }} hidden below 40</span>
        </p>
      </div>

      <div class="results-actions">
        <label class="filter-field">
          <Search aria-hidden="true" />
          <span class="sr-only">Filter results</span>
          <input
            v-model="filterText"
            type="search"
            data-testid="results-filter"
            placeholder="Filter"
          />
        </label>

        <button
          class="secondary-action"
          type="button"
          data-testid="export-results"
          :disabled="sortedRows.length === 0"
          @click="exportResults"
        >
          <Download aria-hidden="true" />
          <span>Export</span>
        </button>

        <button
          class="primary-button"
          type="button"
          data-testid="rerun-results"
          :disabled="!canRerun"
          @click="rerunSearch"
        >
          <Play aria-hidden="true" />
          <span>{{ pipeline.status === "running" ? "Running" : "Re-run" }}</span>
        </button>
      </div>
    </div>

    <p v-if="exportMessage" class="export-message" aria-live="polite">{{ exportMessage }}</p>

    <div v-if="sortedRows.length === 0" class="empty-state">
      No visible results yet.
    </div>

    <div v-else class="results-table-wrap">
      <table class="results-table">
        <thead>
          <tr>
            <th>
              <button type="button" data-testid="sort-score" @click="sortBy('score')">
                Score{{ sortLabel("score") }}
              </button>
            </th>
            <th>
              <button type="button" data-testid="sort-title" @click="sortBy('title')">
                Title{{ sortLabel("title") }}
              </button>
            </th>
            <th>
              <button type="button" data-testid="sort-company" @click="sortBy('company')">
                Company{{ sortLabel("company") }}
              </button>
            </th>
            <th>
              <button type="button" data-testid="sort-location" @click="sortBy('location')">
                Location{{ sortLabel("location") }}
              </button>
            </th>
            <th>
              <button type="button" data-testid="sort-source" @click="sortBy('source')">
                Source{{ sortLabel("source") }}
              </button>
            </th>
            <th>
              <button type="button" data-testid="sort-date" @click="sortBy('date')">
                Date{{ sortLabel("date") }}
              </button>
            </th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="row in sortedRows"
            :key="row.id"
            :data-testid="`result-row-${row.id}`"
            tabindex="0"
            @click="selectRow(row)"
            @keydown.enter.prevent="selectRow(row)"
          >
            <td>
              <span
                class="score-badge"
                :class="scoreBand(row.score)"
                :data-testid="`score-${row.id}`"
              >
                {{ row.score ?? "-" }}
              </span>
            </td>
            <td data-testid="result-title">{{ row.title }}</td>
            <td>{{ row.company }}</td>
            <td>{{ row.location }}</td>
            <td>{{ row.source }}</td>
            <td>{{ row.date }}</td>
          </tr>
        </tbody>
      </table>
    </div>

    <div v-if="selectedRow" class="detail-scrim" @click.self="closeDetail">
      <aside class="detail-panel" data-testid="result-detail" aria-label="Result detail">
        <div class="detail-header">
          <div>
            <h3>{{ selectedRow.title }}</h3>
            <p>{{ selectedRow.company }} - {{ selectedRow.location }}</p>
          </div>
          <button
            class="icon-action"
            type="button"
            data-testid="detail-close"
            aria-label="Close details"
            @click="closeDetail"
          >
            <X aria-hidden="true" />
          </button>
        </div>

        <section>
          <h4>Description</h4>
          <p>{{ selectedRow.description }}</p>
        </section>

        <section>
          <h4>Match</h4>
          <p>{{ selectedRow.matchReason }}</p>
        </section>

        <section>
          <h4>Red flags</h4>
          <ul v-if="selectedRow.redFlags.length">
            <li v-for="flag in selectedRow.redFlags" :key="flag">{{ flag }}</li>
          </ul>
          <p v-else>None reported.</p>
        </section>

        <a
          v-if="selectedRow.url"
          class="detail-link"
          data-testid="result-detail-link"
          :href="selectedRow.url"
          target="_blank"
          rel="noreferrer"
        >
          <ExternalLink aria-hidden="true" />
          <span>Open listing</span>
        </a>
      </aside>
    </div>
  </section>
</template>

<style scoped>
.results-view {
  display: grid;
  gap: var(--sp-4);
  width: 100%;
  max-width: var(--content-max);
  margin: 0 auto;
}

.results-toolbar,
.results-actions,
.filter-field,
.secondary-action,
.detail-header,
.detail-link {
  display: flex;
  align-items: center;
  gap: var(--sp-3);
}

.results-toolbar {
  justify-content: space-between;
  padding: var(--sp-5);
  border: 1px solid var(--border);
  border-radius: var(--r-lg);
  background: var(--surface);
  box-shadow: var(--sh-1);
}

.results-summary,
.export-message {
  margin: var(--sp-1) 0 0;
  color: var(--text-muted);
  font-size: var(--fs-sm);
  line-height: var(--lh-sm);
}

.filter-field {
  min-width: 220px;
  height: 38px;
  padding: 0 var(--sp-3);
  border: 1px solid var(--border);
  border-radius: var(--r-md);
  color: var(--text-muted);
  background: var(--surface);
}

.filter-field svg,
.secondary-action svg,
.detail-link svg,
.icon-action svg {
  width: 16px;
  height: 16px;
  flex: 0 0 auto;
  stroke-width: 1.7;
}

.filter-field input {
  width: 100%;
  min-width: 0;
  border: 0;
  outline: 0;
  color: var(--text);
  background: transparent;
  font: inherit;
}

.secondary-action,
.icon-action {
  border: 1px solid var(--border);
  color: var(--text);
  background: var(--surface);
}

.secondary-action {
  justify-content: center;
  min-height: 38px;
  padding: 0 var(--sp-4);
  border-radius: var(--r-md);
  font-weight: var(--fw-medium);
}

.secondary-action:hover:not(:disabled),
.icon-action:hover {
  background: var(--surface-2);
}

.secondary-action:disabled {
  opacity: .62;
}

.export-message {
  padding: 0 var(--sp-2);
  color: var(--success);
  font-weight: var(--fw-medium);
}

.results-table-wrap,
.empty-state {
  border: 1px solid var(--border);
  border-radius: var(--r-lg);
  background: var(--surface);
  box-shadow: var(--sh-1);
}

.results-table-wrap {
  overflow: auto;
}

.empty-state {
  padding: var(--sp-5);
  color: var(--text-muted);
}

.results-table {
  width: 100%;
  min-width: 760px;
  border-collapse: collapse;
}

.results-table th,
.results-table td {
  padding: var(--sp-3) var(--sp-4);
  border-bottom: 1px solid var(--border);
  text-align: left;
  vertical-align: middle;
}

.results-table th {
  color: var(--text-muted);
  background: var(--surface-2);
  font-size: var(--fs-xs);
  font-weight: var(--fw-semibold);
  line-height: var(--lh-xs);
  text-transform: uppercase;
}

.results-table th button {
  width: 100%;
  border: 0;
  color: inherit;
  background: transparent;
  font: inherit;
  text-align: left;
}

.results-table tbody tr {
  transition: background var(--dur-fast) var(--ease);
}

.results-table tbody tr:hover,
.results-table tbody tr:focus {
  outline: 0;
  background: var(--surface-2);
}

.results-table td {
  color: var(--text-muted);
}

.results-table td:nth-child(2),
.results-table td:nth-child(3) {
  color: var(--text);
  font-weight: var(--fw-medium);
}

.score-badge {
  display: inline-flex;
  min-width: 42px;
  justify-content: center;
  padding: 2px var(--sp-2);
  border-radius: var(--r-pill);
  font-family: var(--mono);
  font-size: var(--fs-xs);
  line-height: var(--lh-xs);
  font-variant-numeric: tabular-nums;
}

.score-green {
  color: var(--score-green);
  background: var(--score-green-soft);
}

.score-amber {
  color: var(--score-amber);
  background: var(--score-amber-soft);
}

.score-orange {
  color: var(--score-orange);
  background: var(--score-orange-soft);
}

.score-gray {
  color: var(--score-gray);
  background: var(--score-gray-soft);
}

.detail-scrim {
  position: fixed;
  inset: 0;
  z-index: 20;
  display: flex;
  justify-content: flex-end;
  background: rgba(14, 17, 22, .28);
}

.detail-panel {
  display: grid;
  align-content: start;
  gap: var(--sp-5);
  width: min(420px, 100%);
  height: 100%;
  overflow: auto;
  padding: var(--sp-5);
  color: var(--text);
  background: var(--surface);
  box-shadow: var(--sh-3);
}

.detail-header {
  justify-content: space-between;
}

.detail-header h3,
.detail-panel h4 {
  margin: 0;
  font-size: var(--fs-lg);
  line-height: var(--lh-lg);
}

.detail-header p,
.detail-panel p,
.detail-panel ul {
  margin: var(--sp-1) 0 0;
  color: var(--text-muted);
}

.icon-action {
  display: inline-grid;
  width: 32px;
  height: 32px;
  place-items: center;
  flex: 0 0 auto;
  border-radius: var(--r-pill);
}

.detail-link {
  justify-content: center;
  min-height: 38px;
  border: 1px solid var(--accent);
  border-radius: var(--r-md);
  color: var(--accent);
  text-decoration: none;
  font-weight: var(--fw-medium);
}

.sr-only {
  position: absolute;
  width: 1px;
  height: 1px;
  overflow: hidden;
  clip: rect(0 0 0 0);
  white-space: nowrap;
}

@media (max-width: 900px) {
  .results-toolbar,
  .results-actions {
    align-items: stretch;
    flex-direction: column;
  }

  .filter-field,
  .secondary-action,
  .primary-button {
    width: 100%;
  }
}
</style>
