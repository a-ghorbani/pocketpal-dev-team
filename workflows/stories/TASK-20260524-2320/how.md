# Implementation Plan: FOU-115 Phase 2 shared component library (`src/components/ds/`)

**Purpose**: land the design specified in `what.md` (LGTM round 2). Phase 2 ships **library + snapshots + Surface proof-of-life only** — no screen wired (Phase 3 swaps). The build must look pixel-identical to today everywhere except the two `Surface` consumers (`UsageStats.tsx`, `PalDetailSheet.tsx`), which swap to `DSSurface` in this PR (the same `View`+background+elevation tree — visual diff = zero).

This HOW translates `what.md` §4a–§4j and decisions D1–D35 into ordered commits. No design decisions are introduced here; every step references the WHAT section it executes.

---

## Metadata

- **Task ID**: TASK-20260524-2320
- **Worktree**: `/Users/aghorbani/codes/pocketpal-dev-team/worktrees/TASK-20260524-2320`
- **Branch**: `feature/TASK-20260524-2320`
- **Native Changes**: NO (no new font, no new icon registration, no native module — see §0 and §1c of WHAT). If during implementation a chosen icon font or asset registration requires native linking, STOP and re-route through the orchestrator.
- **Visual Confirmation**: YES (component library — snapshots are the visual artefact; manual smoke for the two `Surface` swap consumers).
- **Intent Brief**: `./workflows/stories/TASK-20260524-2320/intent-brief.md`
- **WHAT**: `./workflows/stories/TASK-20260524-2320/what.md` (LGTM round 2)
- **Architecture doc updated in this PR**: `./context/architecture/theming.md` (two doc commits — see Step 2 and Step F1)
- **Status**: draft

### Planner-side decisions (resolved here, not in WHAT — see "Planner Decisions" section below)

- **PD1**: `Surface` lives at `src/components/ds/Surface/` (family, not primitive). Rationale and implications below.
- **PD2**: A small `__tests__/helpers/snapshotMatrix.tsx` generates the per-family snapshot matrix. Single helper, used by every family test.
- **PD3**: WHAT §4f summary text reads "rebuild 15 families" and §8 D3 reads "rebuild 14 families". Doc nit fixed in the same commit as the theming.md §1a update (Step 2) — see Step 2 sub-task 2b.

---

## Planner Decisions (resolutions of round-2 SUGGESTIONs and ambiguities)

### PD1 — `Surface` at `src/components/ds/Surface/` (NOT `src/components/ds/primitives/Surface/`)

WHAT §4b lists Surface alongside `Pressable`/`Stack` under `primitives/`, but §4f treats it as a 15th rebuild family (D32) with its own snapshot matrix, blocklist seed entry, and two consumer swaps. Two locations would split its tests, styles, and consumer imports across two paths and would force the public barrel to re-export from a primitive path. We pick **the family location** (`src/components/ds/Surface/`) because:

1. The barrel `src/components/ds/index.ts` re-exports every family from a flat `'./Family'` path. Putting Surface under `primitives/` would force a one-off `'./primitives/Surface'` re-export and break the convention readers rely on.
2. The two `Surface` consumer swaps in this PR import from the public barrel; consumers should not know about `primitives/`.
3. `primitives/` is reserved for DS-internal building blocks (`Pressable`) that other DS components import directly. `Surface` is consumed externally — it is a leaf, not a building block for other DS components.

The `primitives/` directory still exists for `Pressable` (and `Stack` if it ships). The §4b primitives tree mentioning Surface is interpreted as "primitive in the sense of visually simple", not "lives under `primitives/`". WHAT §4f is the authoritative location.

### PD2 — Snapshot matrix helper

A single helper `src/components/ds/__tests__/helpers/snapshotMatrix.tsx` exports `runSnapshotMatrix(name, render, axes)` so each family's test file is a one-liner per matrix. The helper iterates the bounded matrix from WHAT §4h.2–§4h.3 and emits one snapshot file per `(variant, size, state, mode, lang?)` tuple. Snapshot file naming: `<family>/<variant>-<size>-<state>-<mode>[-<lang>].snap` (encoded as `it()` block names inside the single `.snap` file Jest produces per test file).

### PD3 — WHAT doc nit (D3 says 14, §4f summary says 15)

`what.md` line 542 (D3) reads "rebuild 14 families"; `what.md` line 276 (§4f summary) and D32 read "rebuild 15 families" (Surface added as the 15th). The discrepancy is a copy-edit miss in D3 (D32 already records the addition). Step 2 sub-task 2b fixes D3 in `what.md` to "rebuild 15 families" to match §4f and D32, and adds a Review-History tail-note recording the planner-side fix.

### PD4 — Pressable primitive is not snapshotted as a family

`primitives/Pressable/` ships with unit tests (state-layer overlay correctness, prop forwarding) but no `__snapshots__/` of its own — it has no `variant`/`size` axis, and every rebuild-family snapshot exercises its state-layer pipeline transitively. This matches WHAT §4k row 1 (the primitive renders only the state-layer overlay; no padding, no radius).

### PD6 — WHAT §4b tree nit (Surface listed under `primitives/`, ships as top-level family)

WHAT §4b (`theming.md` §1b on absorption) lists `Surface/` inside the `primitives/` block, but every other authoritative section (§4f D32 matrix, §4g.7 consumer swaps, §4j I_DS5 snapshot contract) treats Surface as a top-level rebuild family with its own `__snapshots__/` and barrel re-export. PD1 in this HOW resolves the inconsistency by placing Surface at `src/components/ds/Surface/`. Step 2 sub-task 4 corrects the WHAT §4b tree to match the shipped location so Step F1's absorption of WHAT §4b into `theming.md` does not encode the contradiction. This is a doc-only edit, same class as PD3 (the "14→15 families" copy-edit fix). WHAT's contractual surface (§4f D32, §4g.7, §4j I_DS5) is unchanged.

### PD5 — `'@/components/ds'` alias

WHAT §4b parenthetical says "alias TBD by planner; not a WHAT concern". Verified: this repo has no `paths` entry in `tsconfig.json` and no `babel-plugin-module-resolver`. Adding either is out of scope for Phase 2. **All imports use relative paths** (`from '../../components/ds'` or `from 'src/components/ds'` — Metro resolves both). The public barrel is the import target.

---

## Progress Tracking

| Step | Status | Commit | Notes |
| --- | --- | --- | --- |
| 1  Apply folded token-rename patch (foundation) | DONE | 91dfd52 (worktree) | §4a / D1 / I_DS8 |
| 2  Update `theming.md` §1a key set + fix WHAT D3 + §4b nits | DONE | 556b56e (dev-team) | §4a #2 / I_DS8 / PD3 / PD6 |
| 3  Extend `jest/fixtures/theme.ts` with `byMode().byLocale()` factory | DONE | 346dbb4 | §4h.6 / D33 |
| 4  Add snapshot-matrix helper | DONE | 78a93a5 | §4h.1–§4h.3 / PD2 |
| 5  Build `primitives/Pressable/` + tests | DONE | 226cc0d | §4b primitives, §4c.4, §4k row 1 |
| 6  Build shared DS types (`CommonDSProps`, discriminated a11y union) | DONE | 16fca93 | §4c, D34 |
| 7  Build `Surface/` + tests | DONE | d79b95d | §4f D32 |
| 8  Build `Stack/` (only if needed by step 7 or downstream) | SKIPPED | - | no consumer needed; revisit in Phase 3 |
| 9  Build `Header/` + tests | DONE | 93f2d1a | §4d / D30 / I_DS3 |
| 10 Build `Button/` + tests | DONE | a3a2f3b | §4f D13 |
| 11 Build `IconButton/` + tests | DONE | 1da826b | §4f D14 |
| 12 Build `Card/` + `CardList/` + tests | DONE | 8ab5178 | §4f D17 |
| 13 Build `Chip/` + tests | DONE | 293ae73 | §4f D16 / D8 |
| 14 Build `Divider/` + tests | DONE | bc28504 | §4f (Divider absorbed in blocklist final state) |
| 15 Build `Input/` + tests | DONE | 74b14b1 | §4f D15 |
| 16 Build `Tabs/` + tests | DONE | fc4a62d | §4f D18 / D9 |
| 17 Build `BottomNavBar/` + tests | DONE | dac5913 | §4f D19 / D10 |
| 18 Build `Label/` + tests | DONE | 6830c44 | §4f D23 |
| 19 Build `CategoryBadge/` + tests | DONE | 98dc4cd | §4f D24 |
| 20 Build `Dropdown/` + tests | DONE | 1c47639 | §4f D25 |
| 21 Build `MessageContent/` + tests | DONE | c07308a | §4f D26 |
| 22 Build `Switch/` (Paper-wrap) + tests | DONE | 57a281d | §4f D22, §4g #6 |
| 23 Build `Checkbox/` (Paper-wrap) + tests | DONE | 80a03c5 + 0edf3e7 fix | §4f D21, §4g #6 |
| 24 Build `RadioButton/` + `RadioSection/` (Paper-wrap) + tests | DONE | 12b8e6a | §4f D20, §4g #6 |
| 25 Build `Sheet/` (gorhom + Header) + tests | DONE | 566ce0c | §4e / D27 / D7 |
| 26 Build `Modal/` (Portal + Header) + tests | DONE | 67822ef | §4e / D28 |
| 27 Build `Dialog/` (Portal + Surface + Header) + cross-overlay test | DONE | c2eb044 | §4e / D29 / Scenario F |
| 28 Public DS barrel | DONE | db8fb8e | §4b last paragraph |
| 29 Surface consumer swap #1 — `UsageStats.tsx` | DONE | 148f76c | §4g.7 / Scenario I |
| 30 Surface consumer swap #2 — `PalDetailSheet.tsx` | DONE | 4919fcb | §4g.7 / Scenario I |
| 31 ESLint `no-restricted-imports` Paper blocklist seed + wrap-Paper overrides + I_DS1 hex ban | DONE | 5f0ff16 (+ 5f631ed invariants allow-list fix) | §4g.1–§4g.7, D31, I_DS1, I_DS4 |
| 32 Run full `yarn jest` / `yarn lint` / `yarn typecheck` | DONE | - | 214 suites / 3159 tests pass, 364 snapshots, lint 0 errors, typecheck clean |
| F1 Absorb Phase 2 delta into `context/architecture/theming.md` | DONE | f4d50b8 (dev-team) | I_DS8 / WHAT Cleanup reminders #1–4 |

---

## Affected Files

| Path | Change kind | WHAT reference |
| --- | --- | --- |
| `src/theme/tokens/spacing.ts` | edit (patch) | §1 / D1 |
| `src/theme/tokens/radius.ts` | edit (patch) | §1 / D1 |
| `src/theme/tokens/stroke.ts` | edit (patch) | §1 / D1 |
| `src/theme/tokens/types.ts` | edit (patch) | §1 / D1 |
| `src/theme/tokens/__tests__/scales.test.ts` | edit (patch) | §4a.3 |
| `context/architecture/theming.md` (dev-team repo) | edit (§1a key set) | §4a.2 / I_DS8 |
| `workflows/stories/TASK-20260524-2320/what.md` | edit (D3 nit + §4b tree nit) | PD3 / PD6 |
| `jest/fixtures/theme.ts` | edit (add `byMode().byLocale()` factory) | §4h.6 / D33 |
| `src/components/ds/__tests__/helpers/snapshotMatrix.tsx` | add | §4h / PD2 |
| `src/components/ds/types.ts` | add (CommonDSProps + a11y union) | §4c, D34 |
| `src/components/ds/primitives/Pressable/{Pressable.tsx,styles.ts,index.ts,__tests__/Pressable.test.tsx}` | add | §4b, §4c.4 |
| `src/components/ds/Surface/{Surface.tsx,styles.ts,index.ts,__tests__/Surface.test.tsx,__tests__/__snapshots__/}` | add | §4f D32 |
| `src/components/ds/Header/{...}` | add | §4d / D30 |
| `src/components/ds/Button/{...}` | add | §4f D13 |
| `src/components/ds/IconButton/{...}` | add | §4f D14 |
| `src/components/ds/Card/{Card.tsx,CardList.tsx,styles.ts,index.ts,__tests__/}` | add | §4f D17 |
| `src/components/ds/Chip/{...}` | add | §4f D16 |
| `src/components/ds/Divider/{...}` | add | (Divider in §4g.4 final blocklist) |
| `src/components/ds/Input/{...}` | add | §4f D15 |
| `src/components/ds/Tabs/{...}` | add | §4f D18 |
| `src/components/ds/BottomNavBar/{...}` | add | §4f D19 |
| `src/components/ds/Label/{...}` | add | §4f D23 |
| `src/components/ds/CategoryBadge/{...}` | add | §4f D24 |
| `src/components/ds/Dropdown/{...}` | add | §4f D25 |
| `src/components/ds/MessageContent/{...}` | add | §4f D26 |
| `src/components/ds/Switch/{...}` | add | §4f D22 |
| `src/components/ds/Checkbox/{...}` | add | §4f D21 |
| `src/components/ds/RadioButton/{RadioButton.tsx,RadioSection.tsx,styles.ts,index.ts,__tests__/}` | add | §4f D20 |
| `src/components/ds/Sheet/{Sheet.tsx,Actions.tsx,styles.ts,index.ts,__tests__/}` | add | §4e / D27 |
| `src/components/ds/Modal/{...}` | add | §4e / D28 |
| `src/components/ds/Dialog/{...}` | add | §4e / D29 |
| `src/components/ds/index.ts` | add (public barrel) | §4b |
| `src/components/UsageStats/UsageStats.tsx` | edit (swap `Surface` import) | §4g.7 |
| `src/components/PalsHub/PalDetailSheet/PalDetailSheet.tsx` | edit (swap `Surface` import; keep `Text`/`Button`/`Divider`) | §4g.7 |
| `.eslintrc.js` | edit (add Paper `no-restricted-imports` entry + per-file overrides for wrap-Paper trio) | §4g.1–§4g.6 |

---

## Implementation Steps

Each step is one commit unless explicitly noted. Commit messages follow the repo convention (`feat(ds): ...`, `chore(theme): ...`, `docs(architecture): ...`). No `Co-Authored-By` trailers (hook-enforced per AGENTS.md).

---

### Step 1: Apply the folded token-rename patch (FIRST commit)

**Implements**: WHAT §1, §4a.1, §4a.3, D1, I_DS8.

**Files**:
- `src/theme/tokens/spacing.ts` (adds `xl: 32`)
- `src/theme/tokens/radius.ts` (drops `sm`, renumbers `m/ml/l/xl`, adds `xxl: 40`)
- `src/theme/tokens/stroke.ts` (renames `hairline/s/m/l` → `xs/sm/md/lg`)
- `src/theme/tokens/types.ts` (mirrors all of the above)
- `src/theme/tokens/__tests__/scales.test.ts` (12 patched assertions)

**Approach**:
1. From the worktree root: `git apply --check /tmp/fou-114-token-rename-leftover.patch` to re-confirm clean apply (Q1 already verified — but re-check at execution time per §9i).
2. `git apply /tmp/fou-114-token-rename-leftover.patch`.
3. If conflict: per §9i, hand-merge the rename onto current token files and update `scales.test.ts`. The contract is Figma-name parity; the patch is its representation.

**Verification**:
- `yarn jest src/theme/tokens/__tests__/scales.test.ts` — 12 assertions pass.
- `yarn jest --testPathPattern='src/theme'` — full theme module green.
- `yarn typecheck` — no errors (Q2 already verified zero consumers outside the token module).
- `grep -rn 'radius\.sm\b\|radius\.l = 32\|stroke\.\(hairline\|s\|m\|l\)\b' src/` returns zero hits outside `src/theme/tokens/`.

**Commit message**: `chore(theme): rename foundation token keys to mirror Figma (folded FOU-114 leftover)`

---

### Step 2: Update `theming.md` §1a key set + fix WHAT D3 nit

**Implements**: WHAT §4a.2, I_DS8, PD3.

**Files**:
- `context/architecture/theming.md` (lines 83–90 — replace with new key set per WHAT §1)
- `workflows/stories/TASK-20260524-2320/what.md` (line 542 — fix "14 families" → "15 families")

**Approach**:
1. Replace the §1a `spacing`/`radius`/`stroke` blocks in `theming.md` with exactly the text in WHAT §1:
   ```
   spacing: TokenSpacing
     none: 0, xxs: 2, xs: 4, s: 8, sm: 12, m: 16, ml: 20, l: 24, xl: 32   // NEW: xl
   radius: TokenRadius
     none: 0, xxs: 2, xs: 4, s: 8, m: 12, ml: 16, l: 20, xl: 32, xxl: 40
     // no `sm` step; mirrors canonical Figma Radius/None|XXS|XS|S|M|ML|L|XL|XXL
   stroke: TokenStroke
     xs: 0.5, sm: 1, md: 1.5, lg: 3
     // Renamed from {hairline, s, m, l} to mirror canonical Figma Stroke/*.
   ```
2. Add the two correctness facts from WHAT §1 ("Single source of truth = Figma name"; "No `radius.sm` exists") below the §1a block as prose, per WHAT §4a.2.
3. Fix `what.md` line 542: replace "rebuild 14 families" with "rebuild 15 families" (D3 text); append a one-line note to the Review History "Round 2 / planner doc fix" row referencing PD3.
4. **Fix `what.md` §4b directory tree (PD6 — doc-only, analogous to PD3)**: move `Surface/` out of the `primitives/` block to a top-level sibling entry, so the absorbed `theming.md` §1b tree matches the shipped tree (`src/components/ds/Surface/`, NOT `src/components/ds/primitives/Surface/`). Concrete edit in `what.md` §1b:
   - In the `primitives/` block (around line 90), remove the `Surface/` line (currently: `Surface/                        // (P) background + radius + optional elevation; Paper-free; **Phase 2 swap**: both Paper-Surface consumers migrate in this PR (see §4g.7)`).
   - Add `Surface/` as a sibling entry alongside `Header/`, `Button/`, etc. with the same descriptive comment (`// background + radius + optional elevation; Paper-free; **Phase 2 swap**: both Paper-Surface consumers migrate in this PR (see §4g.7)`).
   - Append a Review-History tail-note (Round 2 / planner doc fix) referencing PD6: "WHAT §4b tree: Surface moved out of primitives/ to top-level sibling to match shipped tree at `src/components/ds/Surface/` per PD1 in HOW. Same class as PD3 doc-only correction; WHAT contract is unchanged (§4f D32 already designates Surface as a family with its own snapshot matrix and consumer swaps)."
5. DO NOT remove the `"(currently withOpacity-derived, FOU-115)"` comment in §1a (§4a.2 — that work is a deferred cleanup; remains for a later FOU-115-suffix slice).

**Verification**:
- `git diff context/architecture/theming.md` shows only the §1a block + prose change.
- `git diff workflows/stories/TASK-20260524-2320/what.md` shows only:
  - line 542 (`14` → `15`)
  - the §4b primitives/ block (Surface line removed) + a new top-level `Surface/` sibling entry
  - two Review-History tail-notes (PD3 + PD6)
- No other files touched.

**Commit message**: `docs(architecture): align theming.md §1a with renamed token keys (FOU-115)`

---

### Step 3: Extend `jest/fixtures/theme.ts` with `byMode().byLocale()` factory

**Implements**: WHAT §4h.4, §4h.6, D33.

**Files**:
- `jest/fixtures/theme.ts` (extend exports — keep `lightTheme`, `darkTheme`, `createTheme` for back-compat)

**Approach**:
1. Add a memoized factory keyed by `(mode, language)`. Sketch:
   ```ts
   import {buildTheme} from '../../src/utils/theme';
   import type {Theme} from '../../src/utils/types';

   const cache = new Map<string, Theme>();
   const getByModeLocale = (mode: 'light' | 'dark', language: string): Theme => {
     const key = `${mode}::${language}`;
     let t = cache.get(key);
     if (!t) { t = buildTheme({mode, language: language as any}); cache.set(key, t); }
     return t;
   };

   export const themeFixtures = {
     lightTheme, darkTheme, createTheme,                       // existing
     byMode: (mode: 'light' | 'dark') => ({
       byLocale: (language: string) => getByModeLocale(mode, language),
     }),
   };
   ```
2. Confirm `AvailableLanguage` is widened by the consumer cast above (matches existing fixture surface; no need to import the union into the fixture file).
3. Do NOT remove existing `lightTheme`/`darkTheme`/`createTheme` exports — every existing test file uses them; this is additive.

**Verification**:
- `yarn jest jest/fixtures/` (if any fixture tests exist) green.
- `yarn typecheck` green.
- `yarn jest` full run green (existing tests unaffected — purely additive).

**Commit message**: `test(theme): extend theme fixture with byMode().byLocale() factory (FOU-115)`

---

### Step 4: Add snapshot-matrix helper

**Implements**: WHAT §4h.1–§4h.3, §4h.5, PD2.

**Files**:
- `src/components/ds/__tests__/helpers/snapshotMatrix.tsx` (add)

**Approach**:
1. Export `runSnapshotMatrix(name, factory, axes)` where:
   - `name`: family name string (used in `describe()` block).
   - `factory(props): React.ReactElement`: returns the component under test.
   - `axes`: `{ variants: V[]; sizes: S[]; states?: ('default'|'disabled'|'pressed'|'focused')[]; modes?: ('light'|'dark')[]; langs?: string[]; rtlCanaryVariant?: V }` — `states` defaults to `['default','disabled']`, `modes` defaults to `['light','dark']`, `langs` defaults to `[]` (matrix opts in to RTL canary). `rtlCanaryVariant` is an explicit override for the RTL-canary variant (see step 4 below); when absent, the helper falls back to `axes.variants[0]`.
2. For rebuilt families: iterate the baseline matrix `variant × size × {default,disabled} × {light,dark}` (one `it()` per cell with `toMatchSnapshot()`). Add optional pressed/focused per WHAT §4h.2 #3–#4 via separate `axes.pressedVariants` / `axes.focusedVariants` opt-in arrays.
3. For wrap-Paper families: pass `axes.value: boolean[]` and skip pressed/focused per WHAT §4h.3.
4. RTL canary: one `it()` per family iterating `axes.langs` for `variant=<rtlCanaryVariant ?? variants[0]>, size=<default>, state=default, mode=light`. **Caller chooses the canary variant explicitly when the first declared variant is non-interactive / under-tests state-layer behaviour.** Concrete cases:
   - Chip: pass `rtlCanaryVariant: 'selectable'` (the first declared variant `display` is non-interactive and would not exercise the state-layer RTL path — see Step 13).
   - Tabs: omit `rtlCanaryVariant` — the first declared variant `underline` is interactive and exercises the state-layer.
   - Other families: default (first variant) is fine unless documented otherwise in the family's step.
5. Theme parameterization: each `render()` call wraps with `PaperProvider theme={themeFixtures.byMode(mode).byLocale(lang)}` (reuse the existing `jest/test-utils.tsx` pattern; the helper accepts an injected wrapper or calls `render` directly from `@testing-library/react-native` with a minimal `PaperProvider` wrapper local to the helper).
6. Use `@testing-library/react-native`'s `render(...).toJSON()` + `toMatchSnapshot()` (matches WHAT §4h.1 and existing `ErrorSnackbar.test.tsx` pattern).

**Verification**:
- `yarn typecheck` green.
- Step 7 (Surface) is the first consumer — verifies the helper end-to-end.

**Commit message**: `test(ds): add snapshot-matrix helper for DS family tests (FOU-115)`

---

### Step 5: Build `primitives/Pressable/`

**Implements**: WHAT §4b, §4c.4, §4k row 1, §4j I_DS1, I_DS2.

**Files**:
- `src/components/ds/primitives/Pressable/Pressable.tsx`
- `src/components/ds/primitives/Pressable/styles.ts`
- `src/components/ds/primitives/Pressable/index.ts`
- `src/components/ds/primitives/Pressable/__tests__/Pressable.test.tsx`

**Approach**:
1. Wraps RN `Pressable`. Exposes the state-layer overlay (`theme.colors.stateLayerOpacity`, `pressedStateOpacity`) per WHAT §4k row 1 and the glossary entry "State layer" in §1b.
2. Props: forwards `onPress`, `disabled`, `hitSlop`, `accessibilityRole`, `accessibilityLabel`, `accessibilityState`, `testID`, `children`, `style`. Adds `stateLayerColor?: string` (default `theme.colors.onSurface`) — used in `styles.ts` with the opacity tokens to render the overlay.
3. `style` callback resolves `(state)` from `Pressable`'s child callback and passes `(pressed, hovered, focused, disabled)` to `createStyles(theme, state)`. No padding/radius — the consumer's outer style provides those.
4. The primitive does NOT read or write any store, does NOT import `mobx-react` (I_DS2). `styles.ts` reads only `theme.colors.*` (I_DS1).

**Verification**:
- `yarn jest src/components/ds/primitives/Pressable` — tests assert:
  - Renders children.
  - State-layer overlay only renders when `state.pressed` or `state.focused` (not in `default`).
  - Forwards `accessibilityRole`, `accessibilityLabel`, `testID`.
  - Calls `onPress` when pressed.
  - `disabled={true}` blocks `onPress` AND sets `accessibilityState.disabled = true`.
- `yarn lint` green.
- `yarn typecheck` green.

**Commit message**: `feat(ds): add Pressable primitive with state-layer overlay (FOU-115)`

---

### Step 6: Build shared DS types (`CommonDSProps` + a11y discriminated union)

**Implements**: WHAT §4c, D34.

**Files**:
- `src/components/ds/types.ts` (add)

**Approach**:
1. Export `CommonDSProps` exactly matching WHAT §4c:
   ```ts
   export type CommonDSProps = {
     testID?: string;
     accessibilityLabel?: string;
     accessibilityHint?: string;
     accessibilityRole?: AccessibilityRole;
     style?: StyleProp<ViewStyle>;
     disabled?: boolean;
   };
   ```
2. Export the a11y constraint generic per D34:
   ```ts
   export type WithRequiredA11yLabel<P extends {label?: string; accessibilityLabel?: string}> =
     | (Omit<P, 'label' | 'accessibilityLabel'> & {label: string; accessibilityLabel?: string})
     | (Omit<P, 'label' | 'accessibilityLabel'> & {label?: string; accessibilityLabel: string});
   ```
3. Export a dev-only fallback warner per WHAT §4c.5 second bullet:
   ```ts
   export function warnIfNoA11yLabel(componentName: string, label?: string, accessibilityLabel?: string): void {
     if (__DEV__ && !label && !accessibilityLabel) {
       console.warn(`[ds/${componentName}] accessibilityLabel or label required; types may have been bypassed.`);
     }
   }
   ```
4. Document the JSDoc rule per WHAT §4i.4 — primary mechanism is TS; runtime is fallback.

**Verification**:
- `yarn typecheck` green.
- Step 10 (Button) is the first consumer — proves the union rejects calls supplying neither `label` nor `accessibilityLabel`.

**Commit message**: `feat(ds): add CommonDSProps + a11y discriminated-union type (FOU-115)`

---

### Step 7: Build `Surface/` (rebuild family — proof-of-life for Paper-import discipline)

**Implements**: WHAT §4f D32, §4g.7, Scenario I, Scenario I'.

**Files**:
- `src/components/ds/Surface/Surface.tsx`
- `src/components/ds/Surface/styles.ts`
- `src/components/ds/Surface/index.ts`
- `src/components/ds/Surface/__tests__/Surface.test.tsx`
- `src/components/ds/Surface/__tests__/__snapshots__/Surface.test.tsx.snap` (generated)

**Approach**:
1. `Surface.tsx`: a `View` + token-bound `backgroundColor` (default `theme.colors.surface`) + `borderRadius` (prop `radius?: keyof TokenRadius`, default `'m'`) + optional `elevation?: number` (passed through to `style` as `elevation` on Android and `shadow*` on iOS).
2. **Default `elevation` = `1`** — matches Paper `Surface` v5 default (Android shadow of elevation 1; iOS shadow none). Paper-source-of-truth: `react-native-paper/lib/typescript/components/Surface.d.ts` documents default elevation 1. Matching the default is the parity gate for Scenario I (the two `Surface` swap consumers stay pixel-identical on Android). Step 30 (PalDetailSheet) explicitly passes `elevation={0}` so it is unaffected by the default; Step 29 (UsageStats) does NOT pass `elevation`, so this default keeps its Android shadow intact post-swap.
3. Props: `CommonDSProps` (minus `disabled`) + `variant?: 'default'` (single variant — matches D32 "1 variant × 1 size × 2 modes — minimal snapshot surface") + `radius?` + `elevation?` + `children`.
4. `testID` default `'ds-surface'`; `accessibilityRole` default `'none'` (per §4i table).
5. `styles.ts` reads ONLY through theme — no raw hex/px (I_DS1). The `elevation` prop value is passed directly through to the style object (`{elevation: n}` on Android via React Native's built-in style; iOS shadow is derived from elevation if/when the consumer also passes `shadowColor`/`shadowOffset` — but the two Surface consumers do not, so iOS visual remains as today).

**Verification**:
- `yarn jest src/components/ds/Surface` — snapshot matrix `variant=['default'] × size=['default'] × state=['default','disabled'] × mode=['light','dark']` plus RTL canary. 5 snapshots total.
- Behaviour tests: forwards `style` additively, forwards `testID`, renders children.
- **Elevation-parity unit test (CONCERN 4 gate, not relying on Step 29's screen snapshot):**
  - `it('defaults elevation to 1 to match Paper Surface', () => { ... })` — render `<Surface testID='s'>x</Surface>` (no elevation prop); query by testID; flatten resolved style; assert `style.elevation === 1`.
  - `it('passes explicit elevation through', () => { ... })` — render `<Surface elevation={0}>x</Surface>`; assert `style.elevation === 0`.
  - These two assertions are the mechanical parity gate. Step 29's `UsageStats` snapshot diff becomes a confirmation, not the primary gate.
- `yarn lint` green.
- `yarn typecheck` green.

**Commit message**: `feat(ds): add Surface family (rebuild, seeds Paper-import blocklist) (FOU-115)`

---

### Step 8: Build `Stack/` (defer if unused at this point)

**Implements**: WHAT §4b ("Stack — optional layout primitive — defer if unused").

**Approach**:
1. Inspect Steps 9–27 below as they're authored. If any family (most likely Sheet/Modal/Dialog body or Card list spacing) needs a `Stack` layout primitive (`direction` + `spacing` token-bound), build it. Otherwise SKIP this step entirely.
2. If skipped, mark the row as "SKIPPED" in Progress Tracking with note "no consumer; revisit in Phase 3".
3. If built: `Stack.tsx` exposes `direction?: 'row' | 'column'`, `spacing?: keyof TokenSpacing` (default `'m'`), `align?`, `justify?`. No state, no Pressable. Snapshot matrix: `direction × spacing=['s','m','l'] × mode`.

**Verification (if built)**: `yarn jest src/components/ds/Stack`.

**Commit message (if built)**: `feat(ds): add Stack layout primitive (FOU-115)`

---

### Step 9: Build `Header/` (Figma `3011:23955`)

**Implements**: WHAT §4d, D30, I_DS3, §4i row "Header".

**Files**:
- `src/components/ds/Header/Header.tsx`
- `src/components/ds/Header/styles.ts`
- `src/components/ds/Header/index.ts`
- `src/components/ds/Header/__tests__/Header.test.tsx` + `__snapshots__/`

**Approach**:
1. Props per WHAT §4d.1:
   ```ts
   type HeaderProps = CommonDSProps & {
     title?: string;
     subtitle?: string;
     leading?: ReactNode;
     trailing?: ReactNode;
     align?: 'leading' | 'center';   // default 'leading'
   };
   ```
2. Reads `theme.typography.titleM` for title, `theme.typography.captionS` for subtitle (WHAT §4d.2). Reads `theme.spacing.m` horizontal, `theme.spacing.s` vertical (WHAT §4d.3 — confirm against Figma `3011:23955` during impl; the contract is "single spacing token, not raw").
3. `testID` default `'ds-header'`; `accessibilityRole` default `'header'` (D35).
4. No `Pressable` — Header is non-interactive.

**Verification**:
- `yarn jest src/components/ds/Header` — snapshot matrix `align=['leading','center'] × {default} × {light,dark}` plus title-only / subtitle-only / leading-only / trailing-only render variants (one `it()` each, snapshot per).
- Behaviour test: when both `title='Hello'` rendered as `DSDialog`, `DSModal`, `DSSheet` children (later steps 25–27), the Header subtree is identical (Scenario F — but cross-overlay assertion lives in those steps' tests).
- `yarn lint`, `yarn typecheck` green.

**Commit message**: `feat(ds): add Header building block for overlays (FOU-115)`

---

### Steps 10–11: `Button/` and `IconButton/`

**Implements**: WHAT §4f D13–D14, §4c, §4i, D34.

**Files**: standard family layout under `src/components/ds/Button/` and `src/components/ds/IconButton/`.

**Approach (Button)**:
1. Built on `Pressable` primitive. No `react-native-paper` import.
2. Closed unions per WHAT §4c.1: `variant: 'primary' | 'secondary' | 'tertiary' | 'destructive'`; `size: 's' | 'm' | 'l'`. Defaults: `variant='primary'`, `size='m'` (declared in JSDoc per §4c.2).
3. Public Props type uses `WithRequiredA11yLabel` (D34) — must supply `label` (the visible text) OR `accessibilityLabel` OR both.
4. `testID` default `'ds-button'`; `accessibilityRole` default `'button'`.
5. `styles.ts` `createStyles(theme, {variant, size, state})` returns padding/radius/colors all token-bound (Figma `746:26337`/`746:26338`).
6. Snapshot matrix: baseline (`variants × sizes × {default,disabled} × {light,dark}`) + pressed (`variants × size='m' × pressed × light`) + focused (`variants × size='m' × focused × light` — per §4h.2 #4 Button gets focused snapshots) + RTL canary (`primary × m × default × light × fa`).

**Approach (IconButton)**:
1. Same as Button but content is an icon (from existing icon set). Closed unions: `variant: 'standard' | 'filled' | 'outlined'`; `size: 's' | 'm' | 'l'`. `icon` prop required.
2. `accessibilityLabel` required (no `label` slot — discriminated union collapses to single-form requirement).
3. `testID` default `'ds-icon-button'`; `accessibilityRole` default `'button'`.
4. Snapshot matrix: baseline + pressed canaries only. **No focused snapshots for IconButton.** Per literal reading of WHAT §4h.2 #4: the focused axis is restricted to `Input` and `Button`; IconButton is not in that list. This is the locked reading. If a future need surfaces for IconButton focused snapshots, that goes through a separate WHAT revision (re-enters architect loop), not an in-place HOW change.

**Verification (each)**: `yarn jest src/components/ds/Button` / `yarn jest src/components/ds/IconButton` green; snapshots reviewed for token bindings (no raw hex visible in any rendered style object).

**Commit messages**:
- `feat(ds): add Button family (rebuild from RN primitives) (FOU-115)`
- `feat(ds): add IconButton family (rebuild from RN primitives) (FOU-115)`

---

### Step 12: Build `Card/` + `CardList/`

**Implements**: WHAT §4f D17.

**Files**: `src/components/ds/Card/{Card.tsx,CardList.tsx,styles.ts,index.ts,__tests__/}`.

**Approach**:
1. `Card`: `variant: 'flat' | 'elevated' | 'outlined'`; `size: 's' | 'm' | 'l'`. `testID='ds-card'`, `accessibilityRole='none'`.
2. `CardList`: Card sub-namespace — same Card body but optimized for use inside a list (no shadow on Android; honors the existing list-divider tokens). One variant only (`'default'`).
3. Both non-interactive; no `Pressable` unless `onPress` is passed (then wrap children in `Pressable` primitive).
4. Snapshot matrix: standard rebuild matrix.

**Verification**: `yarn jest src/components/ds/Card`.

**Commit message**: `feat(ds): add Card + CardList family (rebuild from View + tokens) (FOU-115)`

---

### Step 13: Build `Chip/`

**Implements**: WHAT §4f D16, D8 (canonical = `890:29153`).

**Files**: `src/components/ds/Chip/{...}`.

**Approach**:
1. `variant: 'display' | 'selectable' | 'input'`; `size: 's' | 'm'`. Defaults: `variant='display'`, `size='m'`.
2. `display` is non-interactive; `selectable` and `input` use `Pressable`. For `selectable`, expose `selected?: boolean`.
3. `testID='ds-chip'`; `accessibilityRole`: `'button'` (interactive), `'text'` (display) per §4c.5.
4. Leading-icon slot prop. `label` required for interactive variants (D34); display chips accept `label` OR `children`.
5. Snapshot matrix: baseline + pressed canary (interactive only). Skip `display` from pressed canary. **Pass `rtlCanaryVariant: 'selectable'` to the snapshot-matrix helper** so the RTL canary exercises the interactive state-layer path, not the non-interactive `display` variant (per Step 4 sub-task 4).
6. **Defer non-canonical variants** (D8) — only the `890:29153` shape is shipped.

**Verification**: `yarn jest src/components/ds/Chip`.

**Commit message**: `feat(ds): add Chip family (canonical Figma 890:29153) (FOU-115)`

---

### Step 14: Build `Divider/`

**Implements**: WHAT §4g.4 (Divider appears in the final blocklist — must have a DS replacement before Phase 3 banns Paper Divider).

**Files**: `src/components/ds/Divider/{Divider.tsx,styles.ts,index.ts,__tests__/}`.

**Approach**:
1. `variant: 'horizontal' | 'vertical'`; size axis n/a (single thickness token); `thickness?: keyof TokenStroke` (default `'sm'`).
2. Token-bound `backgroundColor` reads `theme.colors.outlineVariant` (or equivalent — confirm during impl against existing usage).
3. `testID='ds-divider'`; `accessibilityRole='none'`.
4. Snapshot matrix: `variant × {default} × {light,dark}` (no states; non-interactive).

**Verification**: `yarn jest src/components/ds/Divider`.

**Commit message**: `feat(ds): add Divider family (rebuild) (FOU-115)`

---

### Step 15: Build `Input/`

**Implements**: WHAT §4f D15.

**Files**: `src/components/ds/Input/{...}`.

**Approach**:
1. Wraps RN `TextInput`. `variant: 'single' | 'multi'`; `size: 's' | 'm' | 'l'`. `label?`, `helperText?`, `errorText?`, `leading?`, `trailing?` slot props.
2. Bottom-divider style per Figma `161:9020` — `borderBottomColor` from `theme.colors.outline` (or `outlineVariant`), `borderBottomWidth` from `theme.stroke.sm`. No Paper TextInput.
3. `testID='ds-input'`; `accessibilityRole='none'` (RN TextInput owns its own a11y).
4. Snapshot matrix: baseline + focused canary per §4h.2 #4 (Input is one of the two families with focused snapshots).

**Verification**: `yarn jest src/components/ds/Input`.

**Commit message**: `feat(ds): add Input family (rebuild from RN TextInput) (FOU-115)`

---

### Step 16: Build `Tabs/`

**Implements**: WHAT §4f D18, D9 (canonical = `764:27807`).

**Files**: `src/components/ds/Tabs/{Tabs.tsx,TabItem.tsx,styles.ts,index.ts,__tests__/}`.

**Approach**:
1. `Tabs` is the tablist root: `variant: 'underline' | 'pill'`; `size: 's' | 'm'`. Items passed as `items: {value: string; label: string; disabled?: boolean}[]` + `selectedValue` + `onChange`.
2. Each item is a `Pressable` with state-layer overlay and an animated underline beneath (for `variant='underline'`).
3. `testID` defaults: root `'ds-tabs'`; item `'ds-tab-item-<value>'` (templated).
4. `accessibilityRole`: root `'tablist'`, item `'tab'`, item `accessibilityState.selected` reflects `selectedValue`.
5. Snapshot matrix: variants × sizes × {default,disabled} × {light,dark} for the rendered tablist with 3 mock items. Pressed canary per variant.

**Verification**: `yarn jest src/components/ds/Tabs` — includes a behaviour test that selecting an item fires `onChange` with the right value.

**Commit message**: `feat(ds): add Tabs family (canonical Figma 764:27807) (FOU-115)`

---

### Step 17: Build `BottomNavBar/`

**Implements**: WHAT §4f D19, D10 (canonical = `143:4685`).

**Files**: `src/components/ds/BottomNavBar/{BottomNavBar.tsx,NavItem.tsx,styles.ts,index.ts,__tests__/}`.

**Approach**:
1. Presentational shell only — no React Navigation wiring (Phase 3 concern). Props: `items: {value: string; icon: ReactNode; label: string}[]`, `selectedValue`, `onSelect`.
2. `testID` defaults: root `'ds-bottom-nav'`; item `'ds-bottom-nav-item-<value>'`. Roles: `'tablist'` + `'tab'`.
3. Snapshot matrix: baseline + pressed canary. Non-canonical variant (`764:28530`) deferred per D10.

**Verification**: `yarn jest src/components/ds/BottomNavBar`.

**Commit message**: `feat(ds): add BottomNavBar shell (canonical Figma 143:4685) (FOU-115)`

---

### Step 18: Build `Label/` (Informational + Status)

**Implements**: WHAT §4f D23, Figma `768:27628`.

**Files**: `src/components/ds/Label/{Label.tsx,styles.ts,index.ts,__tests__/}`.

**Approach**:
1. `variant: 'informational' | 'status-success' | 'status-warning' | 'status-error' | 'status-info'`; `size: 's' | 'm'`. Non-interactive.
2. `testID='ds-label'`; `accessibilityRole='text'`.
3. Snapshot matrix: full baseline (no states beyond `default`).

**Verification**: `yarn jest src/components/ds/Label`.

**Commit message**: `feat(ds): add Label family (Informational + Status) (FOU-115)`

---

### Step 19: Build `CategoryBadge/`

**Implements**: WHAT §4f D24.

**Files**: `src/components/ds/CategoryBadge/{...}`.

**Approach**:
1. `variant` enumerates the category palette (closed union — pick from existing PocketPal category list); `size: 's' | 'm'`. Non-interactive.
2. `testID='ds-category-badge'`; `accessibilityRole='text'`.

**Verification**: `yarn jest src/components/ds/CategoryBadge`.

**Commit message**: `feat(ds): add CategoryBadge family (FOU-115)`

---

### Step 20: Build `Dropdown/`

**Implements**: WHAT §4f D25.

**Files**: `src/components/ds/Dropdown/{...}`.

**Approach**:
1. Trigger Pressable + the existing `src/components/Menu` wrapper for the popup positioning (per D25). `variant: 'standard'`; `size: 's' | 'm' | 'l'`. Required props: `value`, `options: {value, label}[]`, `onChange`.
2. **Compose the sanctioned Menu wrapper, NOT Paper Menu directly.** Import: `import {Menu} from '../../Menu';` (relative path to `src/components/Menu/`). The Menu wrapper at `src/components/Menu/Menu.tsx` is the existing Paper-Menu wrapper used by `Selector.tsx` (and others); it is the sanctioned popup primitive. This keeps Dropdown inside the DS layer's "no direct Paper import" discipline — Step 31 therefore does NOT need a per-file override for Dropdown, preserving WHAT §4g #6's exact 3-file wrap-Paper exception list (`Switch`, `Checkbox`, `RadioButton`).
3. `testID='ds-dropdown'`; `accessibilityRole='button'` (trigger).
4. Snapshot matrix: trigger states only (open/closed via prop). Don't snapshot the Menu portal subtree (it's wrapper-owned and the wrapper itself owns its tests under `src/components/Menu/__tests__/`).
5. Note on I_DS2 (DS observation-free): `src/components/Menu/Menu.tsx` does not import `mobx`/`mobx-react` (verified — only React, react-native-paper, react-native-safe-area-context, plus a local `useTheme` hook). Composing it does not pull observation into the DS layer.

**Verification**: `yarn jest src/components/ds/Dropdown`. Additionally: `grep -n "from 'react-native-paper'" src/components/ds/Dropdown/` returns ZERO hits (proves the file does not import Paper directly — discipline preserved without an excludedFile carve-out).

**Commit message**: `feat(ds): add Dropdown family (Menu trigger, rebuild) (FOU-115)`

---

### Step 21: Build `MessageContent/` variants

**Implements**: WHAT §4f D26, Figma `128:3113`.

**Files**: `src/components/ds/MessageContent/{...}`.

**Approach**:
1. Token-bound message-bubble shell. `variant: 'user' | 'assistant' | 'system'`; `size: 'm'` only (messages don't have size axis in Figma). Content is `children`.
2. Existing `src/components/Message/*` continues to render — this is the additive DS variant for Phase 3 to wire.
3. `testID='ds-message-content'`; `accessibilityRole='none'`.

**Verification**: `yarn jest src/components/ds/MessageContent`.

**Commit message**: `feat(ds): add MessageContent variants (FOU-115)`

---

### Step 22: Build `Switch/` (Paper-wrap)

**Implements**: WHAT §4f D22, §4g #6, §4h.3, Scenario D.

**Files**: `src/components/ds/Switch/{Switch.tsx,styles.ts,index.ts,__tests__/}`.

**Approach**:
1. Thin wrapper around Paper `Switch`. Imports `Switch as PaperSwitch from 'react-native-paper'` — this is the file the per-file ESLint override allows (Step 31).
2. Props (per WHAT §4c.4): `value: boolean`, `onValueChange`, `disabled?`, `accessibilityLabel: string` (required — discriminated union: no `label` slot for Switch). `testID='ds-switch'`; `accessibilityRole='switch'`.
3. Token-bound color overrides via `theme.colors.*` passed to PaperSwitch's `color` prop. No bespoke layout on top.
4. Snapshot matrix per §4h.3: `variant × size × {default,disabled} × {light,dark} × value={true,false}`. NO pressed/focused snapshots (Paper internals).

**Verification**: `yarn jest src/components/ds/Switch`. Behaviour test: `accessibilityValue` reflects `value` (Paper auto-derives — Scenario D).

**Commit message**: `feat(ds): add Switch (Paper-wrap) (FOU-115)`

---

### Step 23: Build `Checkbox/` (Paper-wrap)

**Implements**: WHAT §4f D21, §4g #6, §4h.3.

**Files**: `src/components/ds/Checkbox/{...}`.

**Approach**:
1. Same shape as Switch: wraps Paper `Checkbox`. Props: `value: boolean`, `onValueChange`, `disabled?`, `accessibilityLabel: string`.
2. `testID='ds-checkbox'`; `accessibilityRole='checkbox'`.
3. Snapshot matrix: as Switch.

**Verification**: `yarn jest src/components/ds/Checkbox`.

**Commit message**: `feat(ds): add Checkbox (Paper-wrap) (FOU-115)`

---

### Step 24: Build `RadioButton/` + `RadioSection/`

**Implements**: WHAT §4f D20, §4g #6, §4h.3.

**Files**: `src/components/ds/RadioButton/{RadioButton.tsx,RadioSection.tsx,styles.ts,index.ts,__tests__/}`.

**Approach**:
1. `RadioButton`: wraps Paper `RadioButton`. Props: `value: string`, `groupValue: string`, `onSelect`, `disabled?`, `accessibilityLabel: string`. `testID` default `'ds-radio-<value>'` (templated per §4i). Role `'radio'`.
2. `RadioSection`: composite — label + helper + a list of `RadioButton`s + optional `Divider`. Rebuilt (composite of wrapped RadioButton). Per D20 "Rebuild on top of wrapped RadioButton".
3. Snapshot matrix: RadioButton baseline + value axis; RadioSection one snapshot per section variant.

**Verification**: `yarn jest src/components/ds/RadioButton`.

**Commit message**: `feat(ds): add RadioButton (Paper-wrap) + RadioSection (composite) (FOU-115)`

---

### Step 25: Build `Sheet/` (gorhom + Header composition)

**Implements**: WHAT §4e, D27, D7 (working pattern = `ChatPalModelPickerSheet`), I_DS3.

**Files**: `src/components/ds/Sheet/{Sheet.tsx,Actions.tsx,styles.ts,index.ts,__tests__/}`.

**Approach**:
1. Composes `@gorhom/bottom-sheet` (existing dependency; reuse the wrapping pattern from `src/components/Sheet/Sheet.tsx` — do NOT touch the legacy file).
2. API:
   ```tsx
   <DSSheet isVisible onDismiss title? subtitle? leading? trailing? align?>
     {children}        // body
     <DSSheet.Actions primary={...} secondary={...} />
   </DSSheet>
   ```
3. Internally renders `<Header title=... subtitle=... leading=... trailing=... align=... />` exactly once (I_DS3). Body is `children`. `Actions` is a sub-component (exported via `Sheet.Actions`).
4. `Actions` shape per §4e.4: `primary?: ActionConfig`, `secondary?: ActionConfig` where `ActionConfig = {label; onPress; loading?; disabled?; destructive?}`.
5. `testID='ds-sheet'`. No `accessibilityRole` (overlay; n/a per §4i).
6. Snapshot matrix: representative composition — one snapshot per `(align, mode)` matrix with Header (title+subtitle) + a mock body + Actions (primary only, primary+secondary, none).
7. Cross-overlay shape test (Scenario F): a small test renders `<DSSheet title='Hello'>` and a `<DSDialog title='Hello'>` and a `<DSModal title='Hello'>` (later steps) and asserts that the `ds-header` subtree shape (testID + child structure) is identical across the three (helper defined in Step 27 cross-overlay test file).
8. Working-pattern check (D7): render the body shape used by `ChatPalModelPickerSheet` (title + scrollable item list + action row); confirm snapshot. This is a behavioural anchor, not a literal port — the legacy file stays.

**Verification**: `yarn jest src/components/ds/Sheet`.

**Commit message**: `feat(ds): add Sheet composition (gorhom + Header) (FOU-115)`

---

### Step 26: Build `Modal/` (Portal + full-screen View + Header)

**Implements**: WHAT §4e, D28, I_DS3.

**Files**: `src/components/ds/Modal/{Modal.tsx,Actions.tsx,styles.ts,index.ts,__tests__/}`.

**Approach**:
1. Uses Paper's `Portal` (already in the locked thin set — not blocked by §4g.4). Wraps a full-screen `View` over the host.
2. Same API shape as Sheet (Header + body + Actions). Renders `<Header>` exactly once (I_DS3).
3. `testID='ds-modal'`.
4. Snapshot matrix: representative composition (same as Sheet).

**Verification**: `yarn jest src/components/ds/Modal`.

**Commit message**: `feat(ds): add Modal composition (Portal + Header) (FOU-115)`

---

### Step 27: Build `Dialog/` (Portal + centered Surface + Header) + cross-overlay shape test

**Implements**: WHAT §4e, D29, I_DS3, Scenario F.

**Files**:
- `src/components/ds/Dialog/{Dialog.tsx,Actions.tsx,styles.ts,index.ts,__tests__/}`
- `src/components/ds/Dialog/__tests__/CrossOverlayHeader.test.tsx` (cross-overlay shape assertion — Scenario F)

**Approach**:
1. Uses Paper `Portal` + a centered `DSSurface`. Same API shape as Sheet/Modal. Renders `<Header>` exactly once.
2. `testID='ds-dialog'`.
3. Cross-overlay test: render `<DSSheet>`, `<DSModal>`, `<DSDialog>` each with `title='Hello' subtitle='World'`. Use `getByTestId('ds-header')` against each rendered tree; assert `toJSON()` subtree under `ds-header` is structurally equal across the three (modulo outermost overlay surface) — proves Scenario F.

**Verification**: `yarn jest src/components/ds/Dialog`. Cross-overlay test asserts F.

**Commit message**: `feat(ds): add Dialog composition (Portal + Surface + Header) (FOU-115)`

---

### Step 28: Public DS barrel `src/components/ds/index.ts`

**Implements**: WHAT §4b last paragraph, §4k row "src/components/ds/index.ts".

**Files**: `src/components/ds/index.ts`.

**Approach**:
1. Named re-exports for every shipped family. Use `export {Surface} from './Surface'` form (not default exports per §4b.7).
2. Re-export `Surface as DSSurface` is not required at the barrel — consumers can `import {Surface} from '.../components/ds'` and alias at the call-site. (Steps 29–30 use `import {Surface as DSSurface}` to disambiguate from any leftover legacy import during the swap.)
3. Do NOT re-export `primitives/Pressable` (DS-internal per §4b last paragraph).
4. Do NOT re-export anything from `src/components/*` (legacy namespace — §4b.4).

**Verification**:
- `yarn typecheck` green.
- `grep -n "from '.*src/components/ds'" src/` should currently return zero hits (no consumers yet — Steps 29–30 add the first two).

**Commit message**: `feat(ds): add public DS barrel (FOU-115)`

---

### Step 29: Surface consumer swap #1 — `src/components/UsageStats/UsageStats.tsx`

**Implements**: WHAT §4g.7, Scenario I.

**Files**: `src/components/UsageStats/UsageStats.tsx`.

**Approach**:
1. Replace `import {Surface, Portal} from 'react-native-paper';` with two imports:
   - `import {Portal} from 'react-native-paper';` (Portal stays — locked thin set)
   - `import {Surface as DSSurface} from '../ds';` (relative path; barrel)
2. Replace the JSX usage `<Surface testID="memory-usage-tooltip" style={[...]}>` with `<DSSurface testID="memory-usage-tooltip" style={[...]}>` — props identical, no other changes. UsageStats does not pass `elevation`; DS Surface's default `elevation = 1` (committed in Step 7 per CONCERN 4 resolution) matches Paper's default, so the Android visual is preserved without an explicit override. The Step 7 elevation-parity unit test is the mechanical gate; the screen-level diff here is confirmation.
3. Update any related `__tests__/UsageStats.test.tsx` if it asserts on Surface's rendered tree.

**Verification**:
- `yarn jest src/components/UsageStats` — existing tests pass; if a snapshot exists, regenerate ONLY if visual diff is intentional (it should not be; the swap is meant to be a no-op).
- `yarn lint`, `yarn typecheck` green.

**Commit message**: `refactor(usage-stats): swap Paper Surface for DSSurface (FOU-115)`

---

### Step 30: Surface consumer swap #2 — `src/components/PalsHub/PalDetailSheet/PalDetailSheet.tsx`

**Implements**: WHAT §4g.7, Scenario I.

**Files**: `src/components/PalsHub/PalDetailSheet/PalDetailSheet.tsx`.

**Approach**:
1. Change `import {Text, Button, Surface, Divider} from 'react-native-paper';` to:
   - `import {Text, Button, Divider} from 'react-native-paper';` (these remain — `Text`/`Button` are in the locked thin set; `Divider` is in the to-be-blocked set but its replacement ships in Step 14 — call-site swap is deferred to Phase 3 per D5/D31).
   - `import {Surface as DSSurface} from '../../ds';` (relative; barrel).
2. Replace the JSX `<Surface style={styles.statsSection} elevation={0}>...</Surface>` with `<DSSurface style={styles.statsSection} elevation={0}>...</DSSurface>` — `elevation={0}` is passed explicitly, identical visual.
3. Update related tests if they assert on Surface tree.

**Verification**:
- `yarn jest src/components/PalsHub/PalDetailSheet` — green; snapshots if any unchanged.
- `yarn lint`, `yarn typecheck` green.

**Commit message**: `refactor(palshub): swap Paper Surface for DSSurface (FOU-115)`

---

### Step 31: ESLint `no-restricted-imports` Paper blocklist (seed `['Surface']`) + wrap-Paper overrides

**Implements**: WHAT §4g.1–§4g.7, D31, D32, I_DS4. Scenarios C, I'.

**Files**: `.eslintrc.js`.

**Approach**:
1. The existing `overrides` block (line 41 onward) restricts automation imports via `patterns:`. Add a SECOND `overrides` entry — distinct from the automation entry — keyed on `files: ['src/**/*.{ts,tsx}']` that adds a `paths:` rule for `react-native-paper`. Concretely:
   ```js
   {
     files: ['src/**/*.{ts,tsx}'],
     excludedFiles: [
       'src/__automation__/**',
       'src/components/ds/Switch/**',
       'src/components/ds/Checkbox/**',
       'src/components/ds/RadioButton/**',
     ],
     rules: {
       'no-restricted-imports': ['error', {
         paths: [{
           name: 'react-native-paper',
           importNames: ['Surface'],
           message:
             "Phase 2 DS replacement available: import 'Surface' from 'src/components/ds' instead. Locked thin Paper set: Text, Button, IconButton, Portal, Provider.",
         }],
         patterns: [
           {group: ['**/__automation__', '**/__automation__/**'],
            message: 'Do not import from src/__automation__/ outside the automation folder itself. See src/__automation__/README.md.'},
         ],
       }],
     },
   },
   ```

   IMPORTANT: This entry must combine BOTH the `paths` (new Paper rule) AND `patterns` (existing automation rule) into a single `no-restricted-imports` rule object — ESLint allows only one `no-restricted-imports` per scope. If two `overrides` blocks both target `src/**/*.{ts,tsx}`, the second's `rules.no-restricted-imports` REPLACES the first's (not merges). So: either (a) merge into the existing automation block (preferred — single source of truth) OR (b) keep the existing block targeted at `src/__automation__/`-related paths only and the new one for everything else. **Use (a)**: extend the existing block (lines 41–65 of `.eslintrc.js`) by adding `paths:` alongside `patterns:` and tightening `excludedFiles` to also exclude the DS wrap-Paper trio + Dropdown.
2. Verify the existing exception block `files: ['App.tsx', 'src/hooks/useDeepLinking.ts'], rules: {'no-restricted-imports': 'off'}` (lines 67–69) still functions — those two files keep their full exemption.
3. Confirm the per-file overrides re-allow the entire `react-native-paper` module import (not just specific symbols) by listing them under `excludedFiles`. Per WHAT §4g #6, the contract is "DS wrap-Paper files are the only legal place those Paper imports live by Phase 4" — an excludedFile-based exemption satisfies this.
4. **Add `no-restricted-syntax` rule banning raw hex literals inside `src/components/ds/**/styles.ts`** (mechanically enforces I_DS1's spirit — token-bound styles only, no raw hex). Concrete rule shape, added as a SECOND `overrides` entry distinct from the Paper rule:
   ```js
   {
     files: ['src/components/ds/**/styles.ts'],
     rules: {
       'no-restricted-syntax': ['error', {
         selector: "Literal[value=/^#[0-9a-fA-F]{3,8}$/]",
         message:
           'I_DS1: raw hex literal in DS styles.ts is banned — read the color through theme.colors.* (or theme.interaction.*) instead. If the value genuinely cannot come from a token, surface as a token-layer gap, not a styles.ts string.',
       }],
     },
   },
   ```
   Notes:
   - Selector matches AST `Literal` nodes whose `value` is a 3, 6, or 8 char hex string with leading `#` (covers `#fff`, `#ffffff`, `#ffffff80` alpha-hex forms). TypeScript string literals expose `value` to ESLint's AST.
   - Scope is intentionally narrow (`styles.ts` only) — DS test files / fixtures may still need literal hex for assertions; component `.tsx` files don't have inline styles in our convention.
   - Snapshot review remains the visual cross-check; this rule catches the common-case regression mechanically so the reviewer can focus on legitimate token-vs-design mismatches.
   - The rule applies to the empty DS tree on day one (no `styles.ts` exists at lint time of Step 31). Verify zero false positives by `yarn lint src/components/ds/` after Step 28 (barrel) lands and all family `styles.ts` files exist.

**Verification**:
- `yarn lint` passes overall.
- Negative test (Scenario C / I'): create a temp file at `src/components/SomeFile.tsx` with `import {Surface} from 'react-native-paper';` and run `yarn lint src/components/SomeFile.tsx`. Lint MUST error with the message "Phase 2 DS replacement available: import 'Surface' from 'src/components/ds' instead...". Delete the temp file.
- Positive test: `yarn lint src/components/ds/Switch/Switch.tsx` (or wherever Switch imports Paper) — no Paper-related error.
- `grep -rn "import.*\bSurface\b.*from 'react-native-paper'" src/` returns ZERO hits after Step 29–30 land (Scenario I' confirmation).

**Commit message**: `chore(eslint): seed Paper-import blocklist with Surface (FOU-115)`

---

### Step 32: Full test suite + lint + typecheck

**Implements**: WHAT §6 (every scenario), §4j (every invariant).

**Approach**:
1. `yarn typecheck` — 0 errors.
2. `yarn lint` — 0 errors. Pre-existing warnings allowed (e.g. those carried over from FOU-114).
3. `yarn jest` — full suite green. Snapshot count grows by the DS family matrices; review the new snapshot files in `git diff` to confirm no raw hex appears in any rendered style object (I_DS1 spot-check).
4. Confirm `grep -rn "import.*from 'mobx" src/components/ds/` returns ZERO hits (I_DS2).
5. Confirm every DS overlay (`Sheet/Modal/Dialog`) test asserts the rendered tree contains exactly one `testID='ds-header'` (I_DS3).
6. Confirm the snapshot file shape: every rebuilt family has `variant × size × {default,disabled} × {light,dark}` cells plus declared canaries; wrap-Paper trio has the value axis but no pressed/focused (I_DS5 scope boundary).

**Verification**:
- All three commands pass. Snapshot review is a manual spot-check (the tester stage owns the depth review).

**Commit message**: not a commit — runs locally.

---

### Step F1: Absorb Phase 2 delta into `context/architecture/theming.md`

**Implements**: WHAT Cleanup reminders #1–4, I_DS8 (architecture-doc drift forbidden), WHAT §4k row "context/architecture/theming.md".

**Files**: `context/architecture/theming.md` (dev-team repo).

**Approach**:
1. Add a new top-level section "**§N. Component layer (DS)**" (renumber subsequent sections if collision; otherwise append after the existing §N). The section absorbs:
   - §4b — DS layer directory layout + per-component file structure (**post-PD6 corrected tree** — `Surface/` is a top-level sibling, NOT under `primitives/`; verify the absorbed tree matches the shipped `src/components/ds/` layout exactly).
   - §4c — component API contract (CommonDSProps + a11y discriminated union).
   - §4d — Header building block (Figma `3011:23955`).
   - §4e — Sheet/Modal/Dialog composition pattern.
   - §4g.4 — final Paper-import blocklist (inversion-of-thin-set).
   - §4i — testID + a11y label freeze contract.
   - §4j — I_DS1 through I_DS8 invariants (added to the existing §4e "Hard invariants" or as a new "Hard invariants — DS" subsection).
2. Add the wrap-vs-rebuild matrix from §4f (D13–D30) to `theming.md` §8 ("Decisions") as a new sub-table titled "Phase 2 wrap-vs-rebuild (FOU-115)".
3. Convert every Phase-2 (P) marker in the absorbed text to (C); convert every (D) to plain prose with the decision text inlined (D-marker label may be kept inline for cross-reference, e.g. "(D13)").
4. Add to the §1a "What each component renders" table a row for `src/components/ds/*` per WHAT §4k.
5. Verify zero `(?)` markers remain anywhere in `theming.md`.
6. Append a "Promoted from FOU-115 / TASK-20260524-2320 — PR #<N>" entry to `theming.md`'s change-log section if it has one (matches the FOU-114 promotion pattern).

**Verification**:
- `grep -n "(?)" context/architecture/theming.md` — zero hits.
- `grep -n "src/components/ds" context/architecture/theming.md` — appears in the new section, the renders table, and at least one cross-reference.
- `git diff context/architecture/theming.md` reviewed end-to-end for accuracy against `what.md`.

**Commit message**: `docs(architecture): absorb FOU-115 Phase 2 DS layer + invariants I_DS1–8`

---

## Testable-Contract Coverage

Every canonical scenario in WHAT §6 maps to a test or manual verification step:

| Contract item (WHAT §6) | Verified by |
| --- | --- |
| A. Token rename absorbed, app renders identically | Step 1 verification (`scales.test.ts` 12 assertions + `yarn jest --testPathPattern='src/theme'` + manual smoke at Step 32) |
| B. DS Button renders all variants × sizes × states × modes | Step 10 snapshot matrix in `src/components/ds/Button/__tests__/__snapshots__/Button.test.tsx.snap` |
| C. Paper-import ESLint rule rejects banned `importNames` | Step 31 negative-test (temp file at `src/components/SomeFile.tsx`) — also covers Scenario I' |
| D. Wrap-Paper DS Switch preserves a11y semantics | Step 22 behaviour test (`accessibilityValue` reflects `value`; testID `ds-switch`; role `'switch'`) |
| E. Sheet composes Header + Body + Actions | Step 25 representative-composition snapshots; behaviour test asserts exactly one `ds-header` in the rendered tree (I_DS3) |
| F. DS overlay header is reused (cross-overlay shape) | Step 27 cross-overlay shape test (`CrossOverlayHeader.test.tsx`) |
| G. RTL canary (one per component) | Snapshot-matrix helper (Step 4) emits one `*-fa.snap` per family; consumed by every family test (Steps 7–27) |
| H. Dark canary (every variant) | Baseline matrix from Step 4 includes `mode='dark'` for every cell |
| I. Phase 2 ships zero screen changes (Surface excepted) | Steps 29–30 (only the two `Surface` consumers change); manual `git diff src/screens/` confirms zero hits |
| I'. Paper-`Surface` blocklist enforces immediately | Step 31 negative test + `grep -rn` post-swap (zero `Surface` imports from `react-native-paper` in `src/`) |
| J. Folded rename does not regress §1a invariants | Step 1 + Step 2 (theming.md `I1`–`I8` text unchanged; `grep` for the invariant labels confirms intact) |

Every invariant in WHAT §4j is enforced by a step:

| Invariant | Enforced by |
| --- | --- |
| I_DS1 (tokens only — no raw hex/px) | Step 32 manual snapshot review + per-family `styles.ts` review during impl |
| I_DS2 (DS observation-free) | Step 32 `grep -rn "from 'mobx"` returns zero hits in `src/components/ds/` |
| I_DS3 (Header is sole overlay header) | Steps 25–27 per-overlay test asserts exactly one `ds-header` |
| I_DS4 (blocklist monotonic) | Step 31 — the blocklist is one rule object; future PRs append; never remove |
| I_DS5 (Phase 3 swaps preserve DS snapshots) | Phase 3 contract; this PR establishes the baselines (Steps 7–27) |
| I_DS6 (testID freeze) | Phase 3 contract; this PR fixes defaults (Steps 7–27 per §4i table) |
| I_DS7 (canonical-variant choices recorded) | Step F1 absorbs D8/D9/D10 into `theming.md` §8 |
| I_DS8 (rename = one commit + same-PR doc update) | Steps 1 + 2 (separate atomic commits, same PR) |

---

## Native Verification

**NATIVE_CHANGES = NO.** No native verification required.

If during implementation any chosen font/icon asset registration or native dep is introduced (e.g. a Switch wrap that drags a new native module), STOP and re-route through the orchestrator per WHAT §0. The wrap-vs-rebuild matrix (§4f) does NOT introduce any new native dep — all rebuilds use RN primitives + existing tokens; all wraps use already-installed Paper components.

---

## Visual Confirmation

Visual Confirmation = YES, but in this slice the snapshots are the primary artefact. Manual capture is limited to the two `Surface` swap consumers because they're the only visible code-path change.

```json
[
  {
    "label": "UsageStats tooltip — pre-swap reference",
    "prompt": "Open the model selector / inference screen so the memory-usage tooltip appears. Capture before applying Step 29.",
    "look_for": "Tooltip surface with the memory-usage text; record background color + corner radius + elevation shadow (or lack thereof)."
  },
  {
    "label": "UsageStats tooltip — post-swap",
    "prompt": "Same scenario as above, after Step 29 commit lands.",
    "look_for": "Tooltip surface visually identical (same background color, same radius, same shadow) — proves the DS Surface rebuild matches Paper Surface for this consumer."
  },
  {
    "label": "PalDetailSheet stats section — pre-swap reference",
    "prompt": "Open a Pals Hub pal detail sheet that shows the stats section. Capture before applying Step 30.",
    "look_for": "Stats section background (elevation=0 — no shadow); record corner radius + spacing."
  },
  {
    "label": "PalDetailSheet stats section — post-swap",
    "prompt": "Same scenario as above, after Step 30 commit lands.",
    "look_for": "Stats section visually identical — same background, same lack of shadow, same radius/spacing."
  }
]
```

The remaining DS components have no live screen — their visual artefact is the Jest snapshot under `src/components/ds/<Family>/__tests__/__snapshots__/`. The pipeline-reviewer reviews those snapshots in the PR diff.

---

## Deferred Items

These items are explicitly in WHAT §0 / §5 as out-of-scope for this PR and stay deferred:

- Wiring any DS component into a real screen (Phase 3a–3g). Touching `src/screens/*` in this PR is forbidden per §9h.
- Deleting any `src/components/*` legacy file or its tests (Phase 3 swaps, then Phase 4 cleanup).
- Removing the comment "(currently withOpacity-derived, FOU-115)" from `theming.md` §1a — refers to a deferred FOU-115-suffix cleanup; NOT done here per WHAT §4a.2.
- Migrating `MD3Theme`/`MD3Colors`/`MD3Typescale` consumers (carried forward in `theming.md` §5 #5 — FOU-123).
- Migrating existing `src/components/Sheet/Sheet.tsx`, `src/components/Dialog/Dialog.tsx` call-sites to the new DS overlays (Phase 3 per WHAT §5 cleanup #7).
- Moving `stateLayerOpacity`/`hoverStateOpacity` into a dedicated `theme.interaction.*` namespace (WHAT §5 cleanup #8 — Pressable consumes via `theme.colors.*` for now).
- Adding non-canonical variants to Chips/Tabs/BottomNavBar (deferred per D8/D9/D10 to a designer-reconciliation pass).
- Adding ESLint `no-restricted-imports` entries beyond `Surface` (Phase 3 swap PRs per D31/D5).

---

## Review History

### Round 1 — plan-critic verdict: HAS_CONCERNS (4 CONCERNs, 2 SUGGESTIONs)

| # | Finding | Resolution | Notes |
| --- | --- | --- | --- |
| C1 | Dropdown step (20) adds 4th excludedFile entry, exceeds WHAT §4g #6 wrap-Paper exception list of exactly 3 | **FIXED (option a)** | Step 20 now composes `src/components/Menu` (the sanctioned Paper-Menu wrapper used by `Selector.tsx`) instead of importing Paper Menu directly. Verified the wrapper exists at `src/components/Menu/Menu.tsx`, exports `Menu` + sub-components (`Item`/`Separator`/`GroupSeparator`), is observation-free (no mobx import). Step 31 excludedFiles trimmed back to the exact §4g #6 trio (`Switch`, `Checkbox`, `RadioButton`). Step 20 verification adds a `grep` check confirming Dropdown has zero direct Paper imports. |
| C2 | Step 11 IconButton focused-snapshot policy dithered between two readings | **FIXED** | Locked to literal §4h.2 #4 reading — IconButton gets pressed canaries only, NO focused snapshots. Alternative paragraph deleted. Note added that an IconButton focused-snapshot need would re-enter the architect loop via a WHAT revision, not an in-place HOW edit. |
| C3 | Step 4 RTL canary picks `axes.variants[0]` non-deterministically; Chip's `display` (non-interactive) under-tests state-layer | **FIXED** | Added `rtlCanaryVariant?: V` axis override to the snapshot-matrix helper signature in Step 4; helper falls back to `variants[0]` when absent. Step 13 (Chip) now explicitly passes `rtlCanaryVariant: 'selectable'`. Tabs and other families left at default since their first variant exercises the state-layer. |
| C4 | Surface elevation parity gate is manual; Step 7 left default unspecified — Paper default 1 would visually diff on Android post-swap | **FIXED** | Step 7 commits DS Surface default `elevation = 1` to match Paper v5 default. Added two unit-test assertions (`defaults to 1` + `passes explicit value through`) as the mechanical parity gate. Step 29 simplified — no more "wait, re-check" paragraph; the screen-level diff is now confirmation, not the gate. UsageStats (no explicit elevation) retains Android shadow; PalDetailSheet (`elevation={0}`) remains unaffected by the default. |
| S5 | PD1 fix moves Surface to `src/components/ds/Surface/` but WHAT §4b tree still lists it under `primitives/` — Step F1 absorption would encode contradiction | **FIXED** | Added PD6 to Planner Decisions section. Step 2 sub-task 4 fixes WHAT §4b tree (doc-only edit, same class as PD3): removes `Surface/` from the `primitives/` block, adds it as a top-level sibling entry. Step F1 now explicitly notes the absorbed tree must match the shipped layout (post-PD6). Affected-files table + Progress-tracking row 2 updated. |
| S6 | I_DS1 enforcement (no raw hex) relies on manual snapshot review across 100+ files | **FIXED** | Step 31 adds an `no-restricted-syntax` ESLint rule scoped to `src/components/ds/**/styles.ts` banning hex-literal `Literal` nodes matching `/^#[0-9a-fA-F]{3,8}$/`. Concrete rule shape specified inline (selector + message). Snapshot review remains as visual cross-check; lint catches the common regression mechanically. Rule scope is narrow (styles.ts only) so DS test fixtures/assertions stay legal. |

No (?) markers introduced. All findings addressed in-place. No architectural changes to WHAT — the §4b tree fix is a doc-only correction (same class as PD3's "14→15" copy-edit) and the canary-variant override is an axis the helper exposes, not a change to the WHAT-stipulated bounded matrix.

---

## What this plan is NOT

- Not a design doc — design lives in `what.md`. WHAT §-references in every step.
- Not an exhaustive per-file code skeleton — the implementer writes idiomatic React Native + TypeScript following the patterns already in `src/components/*`. The HOW fixes the contract (props, defaults, snapshot axes, commit boundaries), not the line-by-line code.
- Not a justification — `intent-brief.md` is where the request lives.
- Not a screen migration plan — Phase 3 owns that, slice by slice, on top of the DS library this PR delivers.
