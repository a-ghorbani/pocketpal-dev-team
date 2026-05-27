---
name: figma-implement
description: Implement a Figma frame in PocketPal RN with 1:1 visual parity. Drives the implementer through metadata-first inspection, design-context-driven translation, vector-first assets, and committed visual-diff captures. Used for any redesign-rollout slice (FOU-112 phases) or any task that pins a canonical Figma file + node id.
user-invocable: true
argument-hint: "[figma-url-or-node-id]"
---

# Figma Implementation Workflow

You are implementing a Figma design into PocketPal RN. Figma is the source of truth for layout, copy, colour, typography, and assets. The job is **translation discipline**, not improvisation.

## When to use this skill

- The task lists a Figma file key + node IDs (e.g. FOU-112 phase slices, any "implement frame X" request).
- The user shares a `figma.com/design/<fileKey>/<file>?node-id=...` URL.

## When NOT to use this skill (switch to)

- Editing inside Figma → the `figma-use` skill.
- Generating a new Figma design from code/intent → `figma-generate-design`.
- Mapping a code component to a Figma component (Code Connect) → `figma-code-connect`.
- A non-design implementation task → the normal pipeline (`start-task` / `pocketpal-orchestrator`).

## Pre-flight

The intent brief must contain:

- Canonical Figma file key (e.g. `RZxDJea4t6jnBZrV4YBacF`).
- One or more in-scope node IDs (per-screen, per-component).
- Light frame (and dark frame, if light/dark parity is required).

If any are missing, emit `NEEDS_INPUT:` with the exact unanswered questions and stop. Do not guess node IDs from the URL alone.

## Step 1 — Metadata first, then design context

Order matters. For each in-scope node:

```text
mcp__plugin_figma_figma__get_metadata(fileKey, nodeId)
mcp__plugin_figma_figma__get_design_context(fileKey, nodeId)
```

- `get_metadata` enumerates every child (id, name, x/y/w/h). This is the canonical "what's in the design" list — **every child must end up in code OR in `designer-asks.md`**. Silently skipping a child is a defect.
- `get_design_context` returns the decoded Auto Layout as JSX + tokenised values. This is the implementation reference. Treat the output as representational — translate to RN + project tokens, do not ship the Tailwind verbatim.

If `get_design_context` returns truncated content, drill in: call it on smaller sub-trees instead of the whole frame.

## Step 2 — Asset pipeline (vector-first)

For each visual node, decide the source:

| Source in Figma | Use | How |
| --- | --- | --- |
| Iconify glyph name in design context (e.g. `fa6-solid:feather`, `material-community:*`, `fluent:*`, `typcn:code`) | `react-native-vector-icons` (already in deps) | Pick the matching family and glyph. Most iconify sets we need are covered. |
| Vector illustration | SVG via `react-native-svg` + `react-native-svg-transformer` (already wired) | Export the node as SVG from Figma (`get_design_context` returns localhost SVG URLs for vector nodes — use them directly when present). Save under `src/assets/onboarding/` or the appropriate slot. Import as a React component: `import {Mark} from '../../assets/.../mark.svg'`. |
| Photographic / raster source | PNG @3x at minimum | Export at 3× the on-screen size (e.g. 112×112 target → 336×336 PNG). Bitmap-only as a last resort. |

Never raster-export a vector node. The codebase already has 50+ SVG icons in `src/assets/icons/` using this exact pattern — follow it.

Verify each asset visually before committing: open in Preview, confirm it renders crisp at the target size.

## Step 3 — Translation discipline

For each screen / component:

1. **Decode coordinates, don't ship them**. Figma's `x=137, y=30, width=120` on a 393-wide frame is *responsive encoding*: `137 + 60 = center` → "horizontally centered, 30 from top". Translate to flex/padding/margin. Only ship fixed numbers for fixed-size things (icon sizes, hit targets, illustration boxes).
2. **Node-for-node coverage**. Every child the `get_metadata` walk returned has a code counterpart. If a node is deferred, add a one-line code comment AND an entry in `designer-asks.md`. No silent drops.
3. **Tokens-only in screens**. Map Figma variables → `theme.*` tokens. Zero raw hex in `src/screens/`. If a token doesn't exist, add it via the paired-edit handshake in `theming.md` (same I_UI8 pattern used for `spacing.xxl`, `accent.peach`).
4. **Reuse the DS**. Use existing components in `src/components/ui/` before building new ones. New internals live under `src/screens/<screen>/components/`.
5. **Auto Layout direction** maps to flex direction. `gap` maps to RN `gap`. `padding/px-* / py-*` map to `paddingHorizontal/Vertical`. `min-w-*` to `minWidth`. Etc. — preserve every numeric value.

## Step 4 — Visual-diff captures (MANDATORY gate)

Before the PR is ready for review, every in-scope screen must have a committed side-by-side under:

```
workflows/stories/<TASK-ID>/visual-diff/<screen>-figma.png
workflows/stories/<TASK-ID>/visual-diff/<screen>-sim.png
```

How:

1. **Figma render**: call `get_screenshot(fileKey, nodeId, maxDimension=2622)` for each screen. Download the PNG. The 2622 cap matches 3× of a 393×852 design frame on an iPhone-17-Pro-class device.
2. **Sim screenshot**: build and run the app on a sim whose logical width matches the design (iPhone 17 Pro = 393pt = 1206px @3x for the bottom half — confirm against device under test). Walk to each screen. Capture via `driver.saveScreenshot()` (E2E spec under `e2e/specs/visual-capture/<TASK-ID>.spec.ts`) OR `xcrun simctl io <udid> screenshot` if driving by hand.
3. **No automated pixel-diff gate**. Human eye is the gate. Commit both PNGs in the same commit so reviewers can flip between them in GitHub or any image viewer.

If a screen has light + dark + RTL variants, capture each separately (`<screen>-light-figma.png`, `<screen>-light-sim.png`, `<screen>-dark-*.png`, `<screen>-rtl-*.png`).

## Step 5 — Hand off to the parity reviewer

After commits land and gates pass (`yarn lint && yarn typecheck && yarn test`), invoke the `pocketpal-design-parity-reviewer` subagent before the pipeline reviewer:

```text
WORKTREE: <path>
TASK_ID: <TASK-ID>
FIGMA_FILE: <fileKey>
NODE_IDS: <comma-separated list of in-scope screen node ids>
```

The parity reviewer reads the committed `visual-diff/` captures + the Figma node tree, calls out node-for-node coverage gaps, raw-hex leaks, token misuse, typography drift, asset substitutions. Treat its findings the same way as a critic verdict: BLOCKER fixes, then re-route.

Once parity is approved, hand off to `pocketpal-pipeline-reviewer` as usual.

## Required implementer output format

Mirror this in the final report:

1. **Inputs** — Figma fileKey + node IDs covered + light/dark scope.
2. **Plan** — per-screen translation outline before coding (assets, components, token additions, deviations).
3. **Changes** — per-commit summary of what landed.
4. **Parity** — per-screen "matches Figma" / "differs because X" notes, citing the committed `visual-diff/` files.
5. **Tests** — lint/typecheck/jest results + the visual-capture spec commit SHA.

## Defects this skill prevents

- "Wireframe ships instead of design" (no Step 4 captures → caught by reviewer).
- "Silently dropped Figma children" (Step 1 metadata walk → Step 5 reviewer coverage check).
- "Raw hex in screen styles" (Step 3 tokens-only → reviewer grep).
- "Blurry raster icons" (Step 2 vector-first → reviewer eyeball).
- "x=137 shipped as `left: 137`" (Step 3 decode → reviewer responsive check).
