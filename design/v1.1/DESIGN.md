# JobHunter — Design System (`DESIGN.md`)

Neutral, minimal, information-dense desktop UI for a Windows-primary Tauri + Vue 3 app.
Every value below is a **CSS custom property defined once** and referenced everywhere. Light is the
`:root` default; dark is the `[data-theme="dark"]` override of the *same* token names, so theming is a
single attribute flip and ports directly to Vue.

---

## 1. Design tokens

### 1.1 Color — neutrals (light → dark)

| Token | Light | Dark | Use |
|---|---|---|---|
| `--bg` | `#f6f7f9` | `#0e1116` | App background |
| `--surface` | `#ffffff` | `#161b22` | Cards, panels, table |
| `--surface-2` | `#f1f3f5` | `#1b2229` | Insets, headers, hover |
| `--surface-3` | `#eaedf0` | `#212a33` | Pressed / nested inset |
| `--border` | `#e4e7eb` | `#283039` | Hairline dividers, inputs |
| `--border-strong` | `#d3d8de` | `#39434f` | Emphasised borders, handles |
| `--text` | `#1a1d21` | `#e6e9ee` | Primary text |
| `--text-muted` | `#5b636e` | `#9aa3ad` | Secondary text, labels |
| `--text-subtle` | `#8a929c` | `#6b7480` | Placeholder, disabled, meta |

### 1.2 Color — accent (single functional accent)

| Token | Light | Dark |
|---|---|---|
| `--accent` | `#2f6feb` | `#5b8cf6` |
| `--accent-hover` | `#235cc8` | `#7aa3f8` |
| `--accent-soft` | `#e9f0fd` | `#16243d` |
| `--on-accent` | `#ffffff` | `#0e1116` |

### 1.3 Color — score bands (mandatory; used wherever a score appears)

| Band | Range | Token (text) | Soft (fill) |
|---|---|---|---|
| Green | **80–100** | `--score-green` `#1f9d57` / `#46c483` | `--score-green-soft` |
| Amber | **60–79** | `--score-amber` `#c7891b` / `#e0a93f` | `--score-amber-soft` |
| Orange | **40–59** | `--score-orange` `#d9661f` / `#ec8a4b` | `--score-orange-soft` |
| Gray | **below 40** | `--score-gray` `#8a929c` / `#6b7480` | `--score-gray-soft` |

Below-40 rows are **hidden by default** (revealed via a "show hidden" affordance).

### 1.4 Color — state

`--success` (= green), `--warning` (= amber, **non-blocking** failures), `--error` (`#d24545`/`#ef6b6b`,
blocking), `--info` (= accent), plus `--text-subtle` for muted/disabled. Each has a `*-soft` fill.
**A connector failure uses `--warning`, never `--error`** — the pipeline continues (partial success).

### 1.5 Type

Font: `--font: -apple-system, "Segoe UI", Roboto, system-ui, sans-serif` · numeric/metrics use
`--mono: "SF Mono","Cascadia Code","Segoe UI Mono",ui-monospace,monospace`.

| Step | Size / line | Use |
|---|---|---|
| xs | 11 / 16 | Badges, meta, table caps |
| sm | 12 / 18 | Secondary, log |
| base | 13 / 20 | Body / dense UI default |
| md | 14 / 22 | Inputs, emphasis |
| lg | 16 / 24 | Sub-headings |
| xl | 20 / 28 | Screen titles |
| 2xl | 26 / 34 | Hero numbers |

Weights: 400 body · 500 labels/UI · 600 headings & numbers. Tabular numerals for all scores/counts.

### 1.6 Spacing — 4px base

`--sp-1:4 · --sp-2:8 · --sp-3:12 · --sp-4:16 · --sp-5:24 · --sp-6:32 · --sp-7:48`. Section rhythm = 24;
card padding = 16–24; control gap = 8–12.

### 1.7 Radius · border · elevation

Radii `--r-sm:4 · --r-md:6 · --r-lg:10 · --r-pill:999`. Borders are 1px hairlines (`--border`).
Elevation: `--sh-1` (cards), `--sh-2` (popovers/summary), `--sh-3` (drawers/side-panel).

### 1.8 Motion

`--dur-fast:120ms · --dur:200ms · --dur-slow:360ms`, easing `--ease: cubic-bezier(.2,.6,.2,1)`.
Motion is **subtle only**: gentle pulse on the active timeline node, connector-line fill between
completed stages, fades on panel mount. **No layout shift** — space for all five stages is reserved up
front and states swap in place.

---

## 2. Components & states

Every interactive element implements the full set: **default / hover / focus / active / disabled /
loading / empty / error** (where applicable).

- **Button** — primary (accent), secondary (surface + border), ghost (text-only), danger. Hover darkens,
  focus shows the 2px accent ring, active depresses, disabled drops to `--text-subtle` + no pointer,
  loading swaps label for an inline spinner and stays the same width.
- **Text input / textarea / masked input** — `--surface`, 1px border → `--accent` on focus + soft ring;
  error border `--error`; disabled `--surface-2`. Masked key shows dots, a show/hide eye, and a
  "saved to OS secure store" note.
- **Toggle switch** — pill track; off `--border-strong`, on `--accent`; 16px knob; focus ring.
- **Slider** — `--surface-3` track, `--accent` fill + 14px knob; live value label; keyboard arrows.
- **Checkbox** — 16px, `--accent` when checked; focus ring.
- **Select / dropdown** — input styling + chevron; menu uses `--sh-2`.
- **Keyword chip (editable pill)** — `--surface-2` pill, click text to edit inline, `×` to remove, `+` to
  add. Exclude-chips use `--error-soft`.
- **Score badge** — `--mono`, soft fill + band text colour from §1.3.
- **Provider / status badge** — small pill: dot + label; status colours from §1.4.
- **Table + sortable header** — zebra-free, 1px row dividers, hover `--surface-2`; sorted header shows ▲/▼;
  full keyboard sort.
- **Row detail side-panel (drawer)** — right slide-over, `--sh-3`, scrim; Esc / × to close.
- **Card** — `--surface`, `--sh-1`, radius `--r-lg`.
- **Tooltip** — dark popover, used on the disabled file-upload control.
- **Timeline / stepper node** — circle: pending (muted border + number), active (accent + pulse ring),
  done (green fill + check + metric), failed (amber fill + warn), skipped (dashed).
- **Progress bar** — determinate, `--accent` fill on `--surface-3`; shows batch + scored counts.
- **Nav** — persistent left rail, active item = `--accent-soft` fill + `--accent` text + 2px marker.

---

## 3. Accessibility

WCAG AA contrast on all text/badges (score badges verified against their soft fills, both themes).
Full keyboard operability (Tab order, Enter/Space activation, arrow-key sliders & sort, Esc closes
drawers). Every control has a visible `:focus-visible` ring (2px `--accent`, 2px offset). Screen-reader
labels via `aria-label`/`aria-live` — the activity log and progress header are `aria-live="polite"`.
**`prefers-reduced-motion: reduce`** collapses all durations to ~0 and stops the pulse/fill loops while
preserving the state changes.

---

## 4. Layout

App shell = CSS grid: fixed **240px left nav** + fluid main (header bar + scrollable content). Content
max-width ~1180px, gutters `--sp-6`. Spacing rhythm is the §1.6 scale. **Responsive to ~900px**: the nav
collapses to a 64px icon rail, the results table prioritises Score/Title/Company, and the side-panel goes
full-width.

## 5. Theming & iconography

Theme switches by toggling `data-theme="dark"` on the root — only token values change, no component code.
Icons are a single **line style**: 1.6px stroke, `currentColor`, round caps/joins, 20px grid — consistent
across nav, badges, and controls.
