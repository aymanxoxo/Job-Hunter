# JobHunter — UI/UX Design Brief (prompt for Claude design)

> Paste this entire file into Claude design as the brief. It is self-contained — you don't need the rest
> of the repo, though the source specs are SDD v1.1 §11 (views) and the Dev Plan §9 (progress UI) if you
> want to cross-check. Produce the two deliverables in §2.

---

## 1. Role & objective

You are a senior product designer. Design the complete UI/UX for **JobHunter**, a **desktop** application
(Windows-primary) for an individual job seeker. The app searches multiple job boards, uses AI to turn the
user's profile into search criteria, scores each result 0–100, and shows ranked, annotated results. It
runs as a Tauri v2 shell hosting a **Vue 3 (Composition API) + Vite + Pinia** frontend, so your design
must map cleanly to Vue components and CSS-variable design tokens.

Aesthetic: **neutral and minimal.** Restrained palette (neutral grays + one functional accent + the
semantic score colors below), generous whitespace, clean typographic hierarchy, subtle borders/elevation,
no heavy gradients or decoration. Efficient desktop density — information-rich but not cramped. Provide
**light and dark** themes.

## 2. Deliverables (produce both)

**A. `DESIGN.md` — the design system**, covering:
- **Design tokens** as CSS custom properties: color (neutrals, one accent, semantic), type scale,
  spacing scale, radii, border, elevation/shadow, and motion (durations + easing). Define each token
  once; everything else references it.
- **Color semantics**, including the mandatory **score bands** (used wherever a score appears):
  green = 80–100, amber = 60–79, orange = 40–59, gray = below 40 (hidden by default). Plus state colors:
  success, warning (non-blocking failure), error, info, muted/disabled.
- **Component inventory** with **all states** (default / hover / focus / active / disabled / loading /
  empty / error): buttons, text inputs, masked input, textarea, toggle switch, slider, checkbox, select/
  dropdown, keyword chip (editable pill), score badge, provider badge, status badge, table + sortable
  header, row detail side-panel, card, drawer, tooltip, timeline/stepper node, progress bar, nav.
- **Accessibility**: WCAG AA contrast, full keyboard operability, screen-reader labels, visible focus
  rings, and explicit `prefers-reduced-motion` behavior for every animation.
- **Layout**: app shell grid, spacing rhythm, responsive behavior down to a ~900px window.
- **Theming**: how light/dark switch via tokens. **Iconography**: a simple, consistent line-icon style.

**B. Interactive HTML wireframes** — self-contained HTML (inline CSS using the §A tokens; minimal vanilla
JS for interactivity + mock data; no external frameworks/CDNs). Either one file per screen with cross-nav,
or a single file with a left nav switching screens. "Interactive" means: nav works, panels/drawers expand,
toggles/sliders move, and **the progress timeline animates through its states from mock events**. Use the
realistic mock data in §5 so screens look real, not lorem-ipsum.

## 3. Screens to design

### 3.1 App shell
Persistent left nav with three destinations — **Criteria**, **Results**, **Settings**. Header shows the
active AI provider badge and the current run state (idle / running). Keep chrome minimal.

### 3.2 Criteria View
- Large **profile textarea** (one-shot input) with helpful placeholder.
- **"Generate with AI"** button (shows a loading state while running).
- After generation: an editable criteria panel — **keyword chips** (click to edit, × to remove, + to
  add), **seniority** checkboxes, **location** tags, and the score-threshold control.
- **"Refine"** affordance: the user can adjust criteria conversationally (multi-turn) before running.
- **Run Search** (primary; disabled while a run is in progress) and **Save Criteria**.
- A **file-upload control shown but disabled** (tooltip: "PDF/Word/image profiles — coming soon").
- States: empty (no profile yet), generating, generated, refining.

### 3.3 Live Pipeline Progress — the hero component (design this most carefully)
A polished, **data-driven** progress display — never a bare spinner. It must look excellent.
- A **5-stage timeline**: ① Profile → ② Criteria → ③ Search → ④ Score → ⑤ Export.
- **Per-stage states**: pending (muted) / active (animated) / done (check + metric) / failed (amber,
  with reason) / skipped (dashed). A connector **failure is amber and non-blocking** — the pipeline
  continues; the timeline must communicate "partial success," not total failure.
- The **Search stage expands** into one sub-row per connector with a **live job count** and its own state
  (e.g., LinkedIn 47 ✓, Indeed 38 ✓, or Indeed 0 ⚠). 
- The **Score stage** shows a **determinate bar**: `batch x / y` and `n / total scored`.
- **Header**: active provider badge, elapsed timer, overall position (`stage 3 of 5`).
- A **collapsible Activity-log drawer** (collapsed by default) streaming events in human-readable form.
- A **final summary card**: found / scored / kept (≥ threshold) / export file paths / duration, plus any
  connector warnings.
- **UX bar**: subtle motion only (gentle pulse on the active node, animated connector-line fill between
  completed stages); **no layout shift** (reserve space for all stages up front; states swap in place);
  score-band colors consistent with Results; full reduced-motion + keyboard/SR support.

### 3.4 Results View
- **Sortable table**: columns Score, Title, Company, Location, Source, Date.
- **Score badge** color-coded by the §2 bands.
- **Row click** opens a **detail side-panel**: full description, AI `match_reason`, `red_flags` list, and
  a link to the original posting.
- **Filter bar**: by source connector, a minimum-score slider, and a date-range picker.
- **Export** button and **Re-run** button (re-runs with the same criteria; merges new results).
- States: loading (with the progress component), populated, empty/zero-results, and per-row "below
  threshold/hidden."

### 3.5 Settings View
- **AI provider selector** (Gemini / Ollama / OpenRouter).
- **Masked API-key** field (note: saved to OS secure store, not shown in plain text).
- **OAuth Connect** button for Gemini with a status badge.
- **Connector toggles** (enable/disable each connector).
- **Max-results** slider (10–100) and **min/max delay** sliders per connector.
- **Auth status panel**: green/red badges for LinkedIn session and Google OAuth.
- **LinkedIn auth** button (kicks off a manual login flow).

### 3.6 Shared components to specify
Score badge, provider badge, keyword chip, connector sub-row, timeline/stepper node, job detail panel.

## 4. Constraints that must hold
- Maps cleanly to Vue 3 components; tokens are CSS variables so they port directly.
- Every interactive element has the full state set from §2.A.
- Cover **empty, loading, partial, and error** states everywhere — not just the happy path.
- WCAG AA contrast; keyboard-operable; `prefers-reduced-motion` honored on every animation.
- Neutral & minimal; light + dark; no external UI libraries in the wireframes.

## 5. Realistic mock data (use this so screens look real)

**SearchCriteria** (generated from a profile):
```json
{ "titles": ["Senior .NET Developer", "DevOps Lead", "Squad Lead"],
  "keywords": ["C#", "Kubernetes", "GCP", "CI/CD", "Azure DevOps"],
  "exclude_keywords": ["unpaid", "internship"],
  "seniority_levels": ["senior", "lead"],
  "locations": ["Cairo", "Remote", "Egypt"],
  "min_score_threshold": 40 }
```

**Job** (a scored result):
```json
{ "id": "…", "title": "Senior DevOps Lead", "company": "Accenture Egypt",
  "location": "Cairo (Hybrid)", "source": "linkedin", "posted_date": "2026-06-15",
  "salary_range": "—", "score": 94,
  "match_reason": "Strong match on Kubernetes, GCP, and CI/CD leadership; seniority aligns.",
  "red_flags": ["No salary listed"] }
```
Sample scored set (for the table): 94 Senior DevOps Lead · Accenture Egypt · linkedin; 91 .NET Squad
Lead · Vodafone Egypt · linkedin; 88 Cloud Engineer (GCP) · IBM Egypt · indeed; 67 Backend Engineer ·
Fawry · indeed; 52 .NET Developer · Startup X · linkedin; 33 Junior Dev · (hidden, below threshold).

**Progress events** (drive the timeline animation — one JSON object per event, streamed in order):
```jsonc
{ "type":"progress","stage":"profile","status":"done" }
{ "type":"progress","stage":"criteria","status":"active","label":"Generating criteria" }
{ "type":"progress","stage":"criteria","status":"done","metric":{"keywords":5} }
{ "type":"progress","stage":"search","status":"active","connector":"linkedin","metric":{"jobs":47} }
{ "type":"progress","stage":"search","status":"active","connector":"indeed","metric":{"jobs":38} }
{ "type":"progress","stage":"search","status":"done","metric":{"jobs":85} }
{ "type":"progress","stage":"score","status":"active","current":4,"total":6,"metric":{"scored":72} }
{ "type":"progress","stage":"score","status":"done","metric":{"scored":85} }
{ "type":"progress","stage":"export","status":"done","metric":{"files":2} }
```
Also show a **partial-failure** variant where one search sub-row ends `status:"failed"` (amber, reason
"auth expired") while the other succeeds and the pipeline still reaches Export.

## 6. Acceptance checklist for the design output
- [ ] `DESIGN.md` defines tokens once (color/type/space/radius/elevation/motion) and reuses them.
- [ ] Score bands (green/amber/orange/gray) defined and applied consistently.
- [ ] All four screens + the hero progress component designed, with every state (incl. empty/partial/error).
- [ ] Interactive HTML wireframes are self-contained, neutral/minimal, light + dark.
- [ ] Progress timeline animates from the §5 events, including the partial-failure variant, with no layout shift.
- [ ] WCAG AA contrast; keyboard operable; reduced-motion handled on all animation.
- [ ] Realistic mock data used throughout.

---

*When the design is delivered, save `DESIGN.md` and the wireframes into the project (e.g. a `design/`
folder), then we'll add a tracked design deliverable to PROGRESS.md and wire the Phase-2 UI chunks
(C-032–C-036) to depend on it.*
