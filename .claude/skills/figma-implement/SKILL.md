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
- A non-design implementation task → the normal pipeline (`start-task` / `pocketpal-intake`).

## Pre-flight

The intent brief must contain:

- Canonical Figma file key (e.g. `RZxDJea4t6jnBZrV4YBacF`).
- One or more in-scope node IDs (per-screen, per-component).
- Light frame (and dark frame, if light/dark parity is required).

If any are missing, emit `NEEDS_INPUT:` with the exact unanswered questions and stop. Do not guess node IDs from the URL alone.

## Step 0 — Load the Figma MCP tools

The Figma MCP tools are **deferred** — they aren't in your tool list until you load their schemas, and a bare call fails with "tool not found." Load them first: run `ToolSearch` with the query `figma` to discover and load the Figma tools (you need *get-metadata*, *get-design-context*, *get-screenshot*, and *whoami*; read the exact names from the search result).

Call the Figma `whoami` tool once to confirm you're authenticated, then work directly against the canonical file — pull metadata, design context, and screenshots yourself. If `whoami` genuinely errors (auth/transport), stop and report it as a real outage; do not improvise layout from a screenshot alone.

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
| DS icon already exported (`src/assets/icons/<name>-{sm,md,lg}.svg`) | Direct import | `import {ChevronLeftLgIcon} from '../../../assets/icons'`. Always prefer this over hand-coded SVG components. |
| DS icon NOT yet exported (Figma library `746:26281`) | Export it before coding the consumer | `get_design_context` on each size variant, `curl` the asset URL, save as `src/assets/icons/<name>-{sm,md,lg}.svg`, register in `src/assets/icons/index.ts` as `<Name><Size>Icon`. |
| Iconify glyph name in design context (e.g. `fa6-solid:feather`, `material-community:*`, `fluent:*`, `typcn:code`) | `react-native-vector-icons` (already in deps) | Pick the matching family and glyph. Most iconify sets we need are covered. |
| Vector illustration (non-icon — hero art, mascot, etc.) | SVG via `react-native-svg` + `react-native-svg-transformer` | Export the node as SVG. Save under `src/assets/<flow>/`. Import as a React component. |
| Photographic / raster source | PNG @3x at minimum | Export at 3× the on-screen size (e.g. 112×112 target → 336×336 PNG). Bitmap-only as a last resort. |

**Never** hand-code an SVG component when the Figma library has the icon exported. Hand-drawn approximations drift in stroke weight, shape, and dimensions — exactly the class of bug the export library prevents.

**Three size variants per DS icon** (sm/md/lg) are NOT for scaling — SVG scales natively. They are different *visual weights* (sm = thinner geometry, lg = chunkier). Pick the variant Figma uses in the specific component; don't substitute.

### Figma SVG export gotchas (RN-specific)

When you save a Figma SVG asset into the repo, normalise it before committing:

1. **Strip CSS variables**: `react-native-svg-transformer` doesn't parse `fill="var(--fill-0, #181715)"` — the icon renders transparent. Replace with the plain hex fallback: `fill="#181715"`. Verify with `grep -l 'var(' src/assets/icons/*.svg` returns nothing.
2. **`preserveAspectRatio="none"` warning**: Figma exports set this so the icon stretches to its container. If you pass non-proportional `width`/`height`, the path distorts. Either pass dims proportional to the viewBox, OR remove the attribute to keep aspect locked.
3. **Theming**: hardcoded fills don't react to theme switches. If the icon needs to invert for dark mode, swap the path's hex to `currentColor` and pass `color={theme.colors.onBackground}` on the React component. Otherwise accept that the icon stays one colour across modes.

Verify each asset visually before committing: open in Preview, confirm it renders crisp at the target size; then run a screen capture to confirm it actually shows up in the app.

## Step 3 — Translation discipline

For each screen / component:

1. **Decode coordinates, don't ship them**. Figma's `x=137, y=30, width=120` on a 393-wide frame is *responsive encoding*: `137 + 60 = center` → "horizontally centered, 30 from top". Translate to flex/padding/margin. Only ship fixed numbers for fixed-size things (icon sizes, hit targets, illustration boxes).
2. **Node-for-node coverage**. Every child the `get_metadata` walk returned has a code counterpart. If a node is deferred, add a one-line code comment AND an entry in `designer-asks.md`. No silent drops.
3. **Tokens-only in screens**. Map Figma variables → `theme.*` tokens. Zero raw hex in `src/screens/`. If a token doesn't exist, add it via the paired-edit handshake in `theming.md` (same I_UI8 pattern used for `spacing.xxl`, `accent.peach`).
4. **Reuse the DS**. Use existing components in `src/components/ui/` before building new ones. New internals live under `src/screens/<screen>/components/`.
5. **Auto Layout direction** maps to flex direction. `gap` maps to RN `gap`. `padding/px-* / py-*` map to `paddingHorizontal/Vertical`. `min-w-*` to `minWidth`. Etc. — preserve every numeric value.

## Step 3.5 — Per-component spec table (MANDATORY)

For every component (NEW or modified) emit a table in the story doc BEFORE writing the component code, then re-verify after coding. The table forces an explicit Figma → code mapping for the properties most likely to drift: dimensions, colour fills, border widths/colours, radii, padding, sub-icon sizes.

Format:

```markdown
### Component: <name>  (Figma node `<id>`)

| Property         | Figma value                          | Code value                  | Status |
|------------------|--------------------------------------|-----------------------------|--------|
| container size   | 48×48                                | width: 48, height: 48       | ✓      |
| bg               | `Color/Secondary/Default` `#f3f2f2`  | theme.colors.secondaryDefault | ✓      |
| border           | 0.5px `Color/Border/Light-grey` `#e5e3e1` | theme.stroke.sm + theme.colors.mutedLight | ✓ |
| corner radius    | `Radius/ml` 16                       | theme.radius.ml             | ✓      |
| chevron asset    | `chevron-left lg` (746:26300)        | ChevronLeftLgIcon           | ✓      |
| chevron display  | 6.5×11.5 (viewBox native)            | width: 6.5, height: 11.5    | ✓      |
```

Rules:

- Every Figma property the visual depends on must appear. If a property is missing from the table, you don't know what Figma says — pull it before guessing.
- "Status" is one of `✓` (matches), `≈` (close enough by design — note why), `✗` (deviation — must justify under deferred items in `designer-asks.md`).
- If you find yourself writing a literal value (`borderColor: '#some-hex'`) in code, the corresponding token binding belongs in this table; if the token doesn't exist yet, that's a design-token follow-up.

This table is the single mechanical check that catches the class of bug where the implementer mapped Figma `Color/Secondary/Default` to RN `secondaryContainer` because "the names sound similar" — without verifying the hex values match. The check costs ~2 minutes per component and finds these mismatches every time.

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
- "Wrong token because the names sounded similar" (Step 3.5 per-component table — Figma hex side-by-side with the resolved theme token).
- "Hand-coded chevron at the wrong dimensions" (Step 2 prefers exported DS icons over hand-drawn SVGs; Step 3.5 captures the asset choice + dimensions).
- "Icon ships transparent because Figma SVG used a CSS var" (Step 2 normalisation requires stripping `var(...)` fills on import).
