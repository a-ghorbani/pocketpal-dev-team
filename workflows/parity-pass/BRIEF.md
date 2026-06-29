# Figma Parity Pass — Brief (figma-parity-lead)

You are the **lead** for a Figma-vs-device visual parity pass on the integrated
`redesign/phase-3` branch. You manage this end-to-end and report results back to the
PM. You do NOT touch app code — this is analysis + artifact generation only.

## 0. Register in agistry (do this first)

Use the agistry skill (`~/.claude/skills/agistry/agistry.sh`):
- role: `figma-parity-lead`
- task: `Figma-vs-device visual parity pass for redesign/phase-3 (iOS+Android, light+dark). Reports to redesign-phase3-lead.`
- You report to: **redesign-phase3-lead**, session `5720f24d-6d3a-4cf9-8da2-c1afce16ab05`.

When you finish (or if you hit a blocker), `agistry.sh send` your summary to that session.

## 1. Goal

For every redesign screen, produce a **side-by-side montage** and a **drift verdict**:

```
[ Figma light │ iOS light │ Android light ]
[ Figma dark  │ iOS dark  │ Android dark  ]
```

Figma is the single source of truth both platforms answer to. So each montage must
surface two kinds of drift at once:
1. **our-render-vs-Figma** — parity bugs (spacing, color, typography, missing/extra
   elements, wrong/raster assets, wrong icon weight).
2. **iOS-vs-Android** — platform inconsistencies that are NOT legitimate OS chrome.

## 2. Inputs (already on disk — do NOT re-capture devices)

- **Device captures:** `workflows/stories/redesign-captures/`
  - `ios/light/`, `ios/dark/`, `android/light/`, `android/dark/` (raw PNGs)
  - `INDEX.md` — the screen list + what each file is
  - `sidebyside/` — existing iOS|Android montages (reference for screen naming)
- **Figma context maps (node-id → screen):** `workflows/stories/POC-*/figma-context.md`
  and the `workflows/stories/POC-*/figma/` screenshot folders (filenames embed node ids,
  e.g. `settings-root-registered-3011-25948.png`).
- **Canonical Figma file:** `RZxDJea4t6jnBZrV4YBacF`, page `0:1` ("App design").
  Dark renders are the `3011:*` band; light is the same structure via mode tokens.
  Do NOT source from non-canonical files `fyC1zC0eq0nJjG5SFDexbY` / `szXSjMGisopPpjgmVjovoB`.

## 3. Getting the Figma side (live)

The Figma MCP tools are **deferred** — load them first:
1. Run `ToolSearch` with query `figma` to discover + load the tools (you need
   get-metadata, get-design-context, get-screenshot, whoami; read exact names from the result).
2. Call the Figma `whoami` tool to confirm auth. If it errors, STOP and report to the PM
   (real outage) — do not fake the Figma side from the stale `figma/` PNGs except as a
   clearly-labelled fallback.
3. For each screen's light+dark node id, call the Figma `get-screenshot` tool
   (maxDimension ~1400 so detail is legible). Download the PNG via the returned URL+curl.

The stale `POC-*/figma/` PNGs are a fallback/cross-check only — prefer live renders so we
catch anything the manual extraction missed.

## 4. Building montages + mapping screens

- Screen names differ between the capture set (`settings-about`, `my-pals-downloaded`, …)
  and the figma-context maps (`settings-root-registered`, …). Build the mapping yourself;
  list any screen you cannot confidently map.
- Use ImageMagick: `magick montage`. Label each tile (Figma / iOS / Android). Keep a
  consistent tile height so rows align.
- Output montages to `workflows/parity-pass/montages/<screen>-{light,dark}.png`.

## 5. Verdict rules (important — avoid crying wolf)

For each screen, classify each finding:
- **DESIGN DRIFT** (in scope): layout/spacing, color/token, typography (font, weight,
  size, italic accents), missing/extra elements, wrong copy, raster-where-vector,
  wrong icon weight/glyph. Assign severity BLOCKER / CONCERN / NIT.
- **PLATFORM-LEGIT** (NOT a defect, note separately): status bar, iOS back-chevron vs
  Android hardware back, safe-area insets, OS keyboard, scrollbar, system nav bar.
- **NO FIGMA SOURCE**: screens invented from DS primitives (e.g. some POC-8 error/recovery
  states). Tag as `no-source / DS-derived` — do NOT fake a pass or a fail.

## 6. Scope / deferrals

- **PalsHub-server-gated screens** (Explore discovery populated, pal-details, filter/sort,
  search-results) need the 192.168.0.92:3010 server for OUR side — it is currently DOWN.
  Note these as **DEFERRED (3010 down)**; do the Figma side if cheap, skip the montage.
- Everything else (Home, Chat, Models, Settings, My Pals, empty/stub states) is in scope now.

## 7. Output

- `workflows/parity-pass/montages/` — the side-by-side PNGs.
- `workflows/parity-pass/REPORT.md` — an index table: screen | verdict | severity |
  findings | deferred?  Plus a short executive summary (how many clean / drift / no-source /
  deferred). Cite figma node ids and capture filenames.
- When done, `agistry.sh send` the PM (5720f24d) a 5-line summary + the REPORT.md path.

## Constraints

- Read-only on `repos/pocketpal-ai/` (submodule) and on app source. No app edits.
- Never commit to `main`. This work lives under `workflows/parity-pass/` only.
- Manage your own context — fan out per-screen workers if it helps, but keep the lead
  context lean. If you spawn sub-agents, have them return structured findings, not dumps.
