---
name: figma-implement
description: Implement a Figma frame in PocketPal RN with 1:1 visual parity. Drives the implementer through metadata-first inspection, design-context-driven translation, vector-first assets, and visual-diff captures. Used for any redesign-rollout slice (FOU-112 phases) or any task that pins a canonical Figma file + node id.
user-invocable: true
argument-hint: "[figma-url-or-node-id]"
---

# Figma Implementation Workflow

Figma is the source of truth for layout, copy, colour, typography, and assets. The job is **translation discipline**, not improvisation.

## When to use

- The task lists a Figma file key + node IDs (e.g. FOU-112 phase slices, any "implement frame X" request).
- The user shares a `figma.com/design/<fileKey>/<file>?node-id=...` URL.

Switch instead: editing inside Figma → `figma-use`; new Figma design from code/intent → `figma-generate-design`; Code Connect mapping → `figma-code-connect`; non-design work → the normal pipeline (`start-task` / `pocketpal-intake`).

## Pre-flight

The intent brief must contain the canonical Figma file key (e.g. `RZxDJea4t6jnBZrV4YBacF`), one or more in-scope node IDs (per-screen, per-component), and the light frame (plus dark, if light/dark parity is required). If any are missing, emit `NEEDS_INPUT:` with the exact unanswered questions and stop. Do not guess node IDs from the URL alone.

## Step 0 — Load the Figma MCP tools

The Figma MCP tools are **deferred**; a bare call fails with "tool not found." Run `ToolSearch` with query `figma` and load *get-metadata*, *get-design-context*, *get-screenshot*, and *whoami* (exact names from the result). Two servers; prefer whichever is already live:

- **`plugin:figma:figma`** — hosted (`mcp.figma.com`), reads any file by `fileKey`, no desktop app, OAuth-gated. If the search returns only `authenticate` / `complete_authentication`, call `authenticate`, hand the URL to the user, and wait. Do not improvise layout while you wait. Better for pulling a node from a file nobody has open.
- **`figma-local`** — the desktop app's Dev Mode server on `http://127.0.0.1:3845/mcp` (registered in this repo's `.mcp.json`). No auth; serves the file open in the app, so `nodeId` alone is enough. Needs the desktop app running with the canonical file open. Better when the user is in the file.

Call `whoami` once, then pull metadata, design context, and screenshots yourself. If `whoami` genuinely errors (auth/transport), stop and report a real outage; never improvise layout from a screenshot alone.

## Step 1 — Metadata first, then design context

For each in-scope node, in this order:

```text
mcp__plugin_figma_figma__get_metadata(fileKey, nodeId)
mcp__plugin_figma_figma__get_design_context(fileKey, nodeId)
```

- `get_metadata` lists every child (id, name, x/y/w/h): **every child must end up in code OR in `designer-asks.md`**. Silently skipping a child is a defect.
- `get_design_context` returns Auto Layout as JSX + tokenised values. It is representational: translate to RN + project tokens, never ship the Tailwind verbatim. If truncated, call it on smaller sub-trees.

## Step 2 — Asset pipeline (vector-first)

| Source in Figma | Use | How |
| --- | --- | --- |
| DS icon already exported (`src/assets/icons/<name>-{sm,md,lg}.svg`) | Direct import | `import {ChevronLeftLgIcon} from '../../../assets/icons'`. Always prefer over hand-coded SVG components. |
| DS icon NOT yet exported (Figma library `746:26281`) | Export before coding the consumer | `get_design_context` on each size variant, `curl` the asset URL, save as `src/assets/icons/<name>-{sm,md,lg}.svg`, register in `src/assets/icons/index.ts` as `<Name><Size>Icon`. |
| Iconify glyph in design context (e.g. `fa6-solid:feather`, `material-community:*`, `fluent:*`, `typcn:code`) | `react-native-vector-icons` (in deps) | Pick the matching family and glyph. |
| Vector illustration (hero art, mascot) | SVG via `react-native-svg` + `react-native-svg-transformer` | Export the node as SVG, save under `src/assets/<flow>/`, import as a component. |
| Photographic / raster | PNG @3x minimum | Export at 3× on-screen size (112×112 → 336×336). Bitmap only as a last resort. |

- **Never** hand-code an SVG when the Figma library has the icon exported; hand-drawn approximations drift in stroke, shape, and size.
- The sm/md/lg variants are different *visual weights*, not scales. Use the variant Figma uses; don't substitute.
- Normalise every saved Figma SVG before committing; read `references/svg-export.md`. In short: strip `var(...)` fills (`grep -l 'var(' src/assets/icons/*.svg` returns nothing) and in the same step choose the colour: `currentColor` + `color={theme.colors.<token>}` for themed icons (a baked hex outside `.svgrrc` `replaceAttrValues` ignores call-site `fill=`/`stroke=`); multicolour brand marks keep their hexes, noted in the spec table; mind `preserveAspectRatio="none"`. No gate catches a baked hex: check dark mode yourself.
- Verify each asset visually (crisp at target size in Preview), then capture the screen **in light and dark** to confirm it shows in the app.

## Step 3 — Translation discipline

1. **Decode coordinates, don't ship them.** `x=137, y=30, width=120` on a 393-wide frame (`137 + 60 = center`) means "centered, 30 from top" → flex/padding/margin. Fixed numbers only for fixed-size things (icon sizes, hit targets, illustration boxes).
2. **Node-for-node coverage.** Every `get_metadata` child has a code counterpart; a deferred node gets a one-line code comment AND a `designer-asks.md` entry.
3. **Tokens-only in screens.** Figma variables → `theme.*` tokens; zero raw hex in `src/screens/`. A missing token is added via the paired-edit handshake in `theming.md` (I_UI8 pattern, as for `spacing.xxl`, `accent.peach`).
4. **Reuse the DS.** Existing `src/components/ui/` components first; new internals under `src/screens/<screen>/components/`.
5. **Auto Layout** direction → flex direction; `gap` → RN `gap`; `px-*`/`py-*` → `paddingHorizontal/Vertical`; `min-w-*` → `minWidth`. Preserve every numeric value.

## Step 3.5 — Per-component spec table (MANDATORY)

For every NEW or modified component, write a Figma → code table in the story doc BEFORE coding it and re-verify after; read `references/spec-table.md` for the format and the defect map. Rules:

- Every property the visual depends on appears (dimensions, fills, border widths/colours, radii, padding, sub-icon sizes, asset choice). A missing property means you don't know what Figma says: pull it before guessing.
- Status is `✓` (matches), `≈` (close by design, note why), or `✗` (deviation, justified under deferred items in `designer-asks.md`).
- A literal value in code (`borderColor: '#some-hex'`) means its token binding belongs in the table; a missing token is a design-token follow-up.
- Compare Figma hex with the resolved theme token; never map by similar-sounding names.

## Step 4 — Visual-diff captures (MANDATORY gate)

Before review, every in-scope screen has a side-by-side in the story dir (local story space, not the app branch):

```
<STORY_DIR>/visual-diff/<screen>-figma.png
<STORY_DIR>/visual-diff/<screen>-sim.png
```

1. **Figma render**: `get_screenshot(fileKey, nodeId, maxDimension=2622)` per screen (3× of a 393×852 frame on an iPhone-17-Pro-class device); download the PNG.
2. **Sim screenshot**: run the app on a sim whose logical width matches the design (iPhone 17 Pro = 393pt = 1206px @3x; confirm against the device under test). Capture via `driver.saveScreenshot()` in `e2e/specs/visual-capture/<TASK-ID>.spec.ts` (PR-fix rounds: `TASK-PR-<n>.spec.ts`, so it stays gitignored) or `xcrun simctl io <udid> screenshot` by hand. This host has no iOS toolchain: sim runs go through `ios-router`.
3. **No automated pixel-diff gate**; the human eye is. The pipeline reviewer posts each pair with `tools/post-pr-visual-evidence.sh`; that comment is the durable copy.

Light, dark, and RTL variants are captured separately (`<screen>-light-figma.png`, `<screen>-light-sim.png`, `<screen>-dark-*.png`, `<screen>-rtl-*.png`). Story-dir rationale, the parity gate, and restyle pre/post: `docs/workflows/visual-capture.md`, Flavour C.

## Step 5 — Hand off to the parity reviewer

After commits land and `yarn lint && yarn typecheck && yarn test` pass, reply `COMPLETE`. The orchestrator routes to `pocketpal-design-parity-reviewer` (after the tester, before the pipeline reviewer). Handoff:

```text
WORKTREE: <path>
TASK_ID: <TASK-ID>
STORY_DIR: <path>
FIGMA_FILE: <fileKey>
NODE_IDS: <comma-separated list of in-scope screen node ids>
```

The reviewer checks the `visual-diff/` captures and the node tree for coverage gaps, raw hex, token misuse, typography drift, and asset substitutions. Its `NEEDS_FIXES` routes back to you: fix BLOCKERs, then `COMPLETE` again.

## Required implementer output

1. **Inputs** — fileKey, node IDs covered, light/dark scope.
2. **Plan** — per-screen outline before coding (assets, components, token additions, deviations).
3. **Changes** — per-commit summary.
4. **Parity** — per-screen "matches Figma" / "differs because X", citing `visual-diff/` files.
5. **Tests** — lint/typecheck/jest results + the visual-capture spec path (gitignored, not committed).
