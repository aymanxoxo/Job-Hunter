# design — UI/UX design system + wireframes (versioned)

Versioned design deliverables from Claude design. **Current: `v1.1/`.**

## Versions
- **`v1.1/` (current)** — round 2. Adds `tokens.css` (the implementable token source for the Vue app:
  light `:root`, dark `[data-theme="dark"]`, + `prefers-color-scheme` fallback) and
  `JobHunter-wireframes.html` (**self-contained, opens in any browser, no React**). Adds the skipped
  stage state, the final summary card, the activity-log drawer, and empty/zero-results states. Also
  retains `JobHunter.dc.html` + `support.js` (the Claude-design "dc" format).
- `v1.0/` — initial round: `DESIGN.md` + `JobHunter.dc.html` + `support.js`.

## What to use when building the UI (C-032–C-036, progress UI C-033)
- Tokens → `v1.1/tokens.css` (import directly).
- Component/spec system → `v1.1/DESIGN.md` (identical to v1.0 — the system was stable).
- View the screens → `v1.1/JobHunter-wireframes.html`.

## Conventions
- Tokens defined once; theme = one `data-theme` flip; names never change between themes.
- Score bands (green 80–100 / amber 60–79 / orange 40–59 / gray <40) and the **non-blocking amber**
  connector-failure state are mandatory wherever they apply.

## Pointers
- Parent: [../AGENTS.md](../AGENTS.md) · Spec: `../Documents/JobHunter_SDD_v1.1.md` §11 ·
  Brief: `../Documents/UI_UX_DESIGN_PROMPT.md`
