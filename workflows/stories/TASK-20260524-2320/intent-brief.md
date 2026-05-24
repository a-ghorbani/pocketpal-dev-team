# Intent: FOU-115 — Phase 2 new shared component library (parent FOU-112)

## Metadata

- **Task ID**: TASK-20260524-2320
- **Source**: [FOU-115](https://linear.app/pocketpal/issue/FOU-115/redesign-phase-2-new-shared-component-library) (parent [FOU-112](https://linear.app/pocketpal/issue/FOU-112), follows merged FOU-114 / PR #732)
- **Worktree**: `./worktrees/TASK-20260524-2320`
- **Branch**: `feature/TASK-20260524-2320`
- **Complexity**: complex
- **Native Changes**: NO (expected; flip to YES if a chosen font icon or asset registration requires native linking)
- **Visual Confirmation**: YES (component library — snapshots required for visual parity, light + dark)
- **Created**: 2026-05-24
- **Status**: approved

---

## Request

FOU-115 — Phase 2: New shared component library (parent FOU-112; follows merged FOU-114 / PR #732).

Canonical Figma file: `RZxDJea4t6jnBZrV4YBacF` (page "App design" / DS section `789:19792` + Icons `746:26281`).
Rollout plan: `context/redesign/FOU-112-rollout.md` (Phase 2 row).

**Scope (canonical, from the Linear ticket):**
Build the new component set against the Phase 1 token layer, in parallel with existing components. Same component API where possible so screens swap in place during Phase 3. Components per Figma DS:

- Buttons (`746:26337/26338`), Inputs (`161:9020`), Chips (`890:29153`, `768:29722`), Cards / Card-List (`764:27682`), Tabs (`764:27807`, `408:11226`), Bottom nav bar (`143:4685`, `764:28530`), Radio button (`888:30130`) + Radio sections (`888:30157`), Checkbox (`224:17932`), Switch, Informational & Status labels (`768:27628`), Category badges / dropdowns, Message content variants (`128:3113`). Pick canonical variant where duplicated (Chips×3 / Tabs×3 / nav×2 — no canonical marker in DS).
- Sheet / Modal / Confirmation-Dialog: design our own, do NOT block on a delivered component. Headers are available as components at node `3011:23955` — reuse them as the header building block. Pick one representative bespoke sheet from the design as the working pattern and standardize the existing Sheet/Dialog wrappers onto it.
- Light + dark verified (dark band lives at `3011:*` — same screens).

**Architectural decision to record (Phase 2 deliverable, from ticket):** wrap-vs-rebuild per component. Likely answer: rebuild Buttons / IconButton / Cards / Chips / Surface / Divider from RN primitives (`Pressable` + token-bound styles); closer call for a11y-heavy form controls (Switch / Checkbox / RadioButton — wrapping `react-native-paper` there keeps a11y / state for free). Once decided, encode Paper-import discipline via ESLint `no-restricted-imports` `importNames` blocklist that grows entry-by-entry as each DS component ships its Paper replacement. Replaces the retired `verify-paper-surface.js` snapshot guard.

**Done when (canonical):** new components implemented, token-bound, with visual-parity snapshots; no screen wired yet (Phase 3 swaps); iOS + Android builds green.

**Pre-existing work to fold in (first commit of this PR):**
There is a 236-line patch at `/tmp/fou-114-token-rename-leftover.patch` that was meant to ship with FOU-114 / PR #732 but was left uncommitted in worktree `TASK-20260519-2110`. It is a foundation-layer rename to align token keys with canonical Figma names BEFORE Phase 2 components consume them — folding it here is the cleanest landing spot. The patch touches only:

- `src/theme/tokens/spacing.ts` (+`xl: 32`)
- `src/theme/tokens/radius.ts` (rename to None/XXS/XS/S/M/ML/L/XL/XXL — drops `sm` step since Figma jumps S(8)→M(12); `l` renumbers 32→20; adds `xxl: 40`)
- `src/theme/tokens/stroke.ts` (rename `hairline`/`s`/`m`/`l` → `xs`/`sm`/`md`/`lg`)
- `src/theme/tokens/types.ts` (mirror the above)
- `src/theme/tokens/__tests__/scales.test.ts` (updated assertions, 12 tests passing)

Apply this patch as the FIRST commit in the new worktree before any Phase 2 components are designed against the renamed keys.

**Cross-cutting rules (every redesign slice, from rollout doc §5):**

- `testID` + accessibility-label freeze (restyling changes the a11y tree Appium queries — keep selectors stable as a migration contract).
- RTL + non-Latin verified per slice, not deferred to Phase 4.
- Light + dark parity per slice (dark = the `3011:*` render).
- Update the relevant `context/architecture/*.md` flow doc in the same PR as any behavior change.
- Keep `react-native-paper` THIN (Text / Button / IconButton / Portal / Provider only). Token layer stays decoupled from MD3.

---

## Clarifications

The orchestrator-side preconditions for the "fold the patch in" instruction were verified before classification:

- **Q1**: Does `/tmp/fou-114-token-rename-leftover.patch` still apply cleanly against current `origin/main` (HEAD `82ada65`, with PR #732 merged)?
  - **A1**: Yes. `git apply --check` in the new worktree returns success.
- **Q2**: The patch renames `radius.sm`, `radius.l`, and `stroke.{hairline,s,m,l}`. Are there any consumers of those keys outside the token module itself that would break with a pure-rename commit?
  - **A2**: No. `grep -rn "radius\.sm\|radius\.l\b\|stroke\.\(hairline\|s\|m\|l\)\b" src/` in the worktree returns zero hits. The architecture doc (`context/architecture/theming.md` §1a) still shows the old key set (`spacing` without `xl`, `radius` with `sm`, `stroke` with `hairline`/`s`/`m`/`l`) — the first commit of this PR will need a doc delta to match. That delta is downstream work for the architect / planner; it does not block this brief.

---

## What this brief is NOT

- Not a design doc — the architect produces `what.md` (wrap-vs-rebuild contract, per-component canonical variant choices, sheet/modal pattern selection, Paper-import-discipline mechanism, semantic-surface explicit-binding work flagged in `theming.md` §5 #3–#4).
- Not an implementation plan — the planner produces `how.md` (file layout for `src/components/`, snapshot-test infrastructure, ESLint `no-restricted-imports` config, per-component build order, the token-rename patch commit as Step 1, the `theming.md` §1a key-set delta as part of the same PR).
- Not a place for invented acceptance criteria, performance budgets, coding conventions, or design constraints — those are downstream work or already covered by `context/patterns.md` and `context/redesign/FOU-112-rollout.md` §5.
