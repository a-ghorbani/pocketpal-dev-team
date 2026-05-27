# Implementation Plan: FOU-116 Phase 3a — Onboarding flow

Executable worklist that lands the WHAT delta in `workflows/stories/TASK-20260526-1731/what.md` and absorbs it into a new flow doc `context/architecture/onboarding.md` (and a single line into `context/architecture/theming.md` §1a) on PR landing. Every step traces to a WHAT section; no design content is invented here.

---

## Metadata

- **Task ID**: TASK-20260526-1731
- **Worktree**: `/Users/aghorbani/codes/pocketpal-dev-team/worktrees/TASK-20260526-1731`
- **Branch**: `feature/TASK-20260526-1731`
- **Native Changes**: NO
- **Visual Confirmation**: YES (per-screen light + dark capture; §4l)
- **Intent Brief**: `./workflows/stories/TASK-20260526-1731/intent-brief.md`
- **WHAT**: `./workflows/stories/TASK-20260526-1731/what.md`
- **Architecture doc(s) being updated**: `./context/architecture/onboarding.md` (promoted under Rounds 1–2 in dev-team commit `a448d3f`; Round-3 absorb in Step R19) AND `./context/architecture/theming.md` §1a (Spacing-axis `xxl=40` already landed in `a448d3f`; Round-3 adds Color-axis `accent.peach` in Step R18 — D15 / I_OB12 paired-edit handshake).
- **Status**: draft (Round-3 Figma-faithful retrofit appended on top of the Round-1/2 skeleton shipped in PR #747)

---

## Progress Tracking

| Step | Status | Commit | Notes |
| --- | --- | --- | --- |
| Step 1 — Token: spacing.xxl=40 | DONE | app `e205be1` | App-side half of D11 / I_OB11 |
| Step 2 — UIStore: persisted + ephemeral onboarding fields | DONE | app `a991d9c` | §1a / §5 |
| Step 3 — PalStore: initializePipPal seeded from initialize() | DONE | app `6761343` | §1b / §4d |
| Step 4 — RECOMMENDED_PAL_MODEL_SET constant + unit test | DONE | app `f11ea89` | D2 model-id stability test |
| Step 5 — DS Stepper component + tests + snapshots (8 cells via `variants=['2','3','4','5']`) | DONE | app `9c03290` | §4c / §4c.5 / §4l — 8 snapshots emitted |
| Step 6 — l10n keys under onboarding.* | DONE | app `247d106` | §4j — bodies logged as designer asks |
| Step 7 — Splash + Onboarding{1..6} screens | DONE | app `2932063` | §4b / §4h / §4i |
| Step 8 — OnboardingStack navigator | DONE | app `2932063` | §4a / §4g |
| Step 9 — SwitchPoint inside App.tsx | DONE | app `2932063` | §4a |
| Step 10 — Visual capture (per-screen light + dark) | PENDING-HUMAN | app `39da448` (placeholder dir) | Captures require running sim/emu — implementer left README + slot list |
| Step 11 — E2E onboarding spec + OnboardingPage | DONE | app `39da448` | §6 |
| Step 12 — AutomationBridge opt-IN onboarding bypass | DONE | app `df74063` | §9j |
| Step 13 — Lint + typecheck + Jest | DONE | app `1fca72f` | 3188/3190 passed; warnings pre-existing |
| Step 14 — Promote WHAT to `context/architecture/onboarding.md` | DONE | dev-team `a448d3f` | New flow doc |
| Step 15 — Amend `context/architecture/theming.md` §1a (xxl) | DONE | dev-team `a448d3f` | One-line edit |
| Step 16 — Paired-edit cross-cite handshake | DONE-PARTIAL | dev-team `a448d3f`; app PR URL pending | Pipeline-reviewer reconciles app PR URL after open |
| Cleanup reminders | pending | - | Track in WHAT §10 — none landing here |

---

## Affected Files

### App repo (`worktrees/TASK-20260526-1731`)

| Path | Change kind | WHAT reference |
| --- | --- | --- |
| `src/theme/tokens/spacing.ts` | edit (add `xxl: 40`) | §4h / §4f I_OB11 / D11 |
| `src/theme/tokens/types.ts` | edit (widen `TokenSpacing` with `xxl: 40`) | §4h (paired-edit handshake; literal-type widen) |
| `src/theme/tokens/__tests__/*` | edit (extend tokens contract test) | §4h |
| `src/store/UIStore.ts` | edit (fields + single-writer methods + `properties` array) | §1a / §5 / §7 |
| `src/store/__tests__/UIStore.test.ts` | edit (single-writer + reset semantics) | §5 / §6.A,C,F |
| `src/store/PalStore.ts` | edit (private `initializePipPal()`; call from `initialize()`) | §1b / §4d / §9g |
| `src/store/__tests__/PalStore.test.ts` | edit (idempotency + Lookie precedent + defaultModel-preservation re-init test) | §4d / I_OB7 / §9g |
| `src/store/onboarding/recommendedPalModelSet.ts` | new (`RECOMMENDED_PAL_MODEL_SET` const) | §1b / §4d / D2 |
| `src/store/onboarding/__tests__/recommendedPalModelSet.test.ts` | new (asserts each id exists in `defaultModels`) | D2 (model-id stability) |
| `src/components/ui/Stepper/Stepper.tsx` | new | §4c |
| `src/components/ui/Stepper/styles.ts` | new | §4c |
| `src/components/ui/Stepper/index.ts` | new | §4c |
| `src/components/ui/Stepper/__tests__/Stepper.test.tsx` | new (incl. snapshot matrix) | §4c.5 / §4l |
| `src/components/ui/index.ts` | edit (promote `Stepper`) | §4c.5 |
| `src/locales/en.json` | edit (new `onboarding.*` keys) | §4j |
| `src/screens/OnboardingScreens/SplashScreen.tsx` | new | §4b / §4g splash row / D6 |
| `src/screens/OnboardingScreens/Onboarding{1..6}Screen.tsx` | new (6 files) | §4b table |
| `src/screens/OnboardingScreens/components/TopicChipGrid.tsx` | new (internal — NOT DS) | §4b (screen 5) |
| `src/screens/OnboardingScreens/components/ModelRadioGroup.tsx` | new (internal — NOT DS) | §4b (screen 6) / §4d |
| `src/screens/OnboardingScreens/components/OnboardingBottomBar.tsx` | new (internal — NOT DS) | §4b (rows 2–6) |
| `src/screens/OnboardingScreens/OnboardingStack.tsx` | new (native stack, 7 routes, `headerShown: false`) | §4a / §4g |
| `src/screens/OnboardingScreens/index.ts` | new (barrel) | §4a |
| `src/screens/index.ts` | edit (re-export) | n/a (mechanical) |
| `src/utils/navigationConstants.ts` | edit (new `ROUTES.ONBOARDING_*` consts) | §4a #3 |
| `App.tsx` | edit (insert `<SwitchPoint>` under `<BottomSheetModalProvider>`) | §4a / §2 |
| `src/__automation__/AutomationBridge.tsx` (or adjacent helper) | edit (E2E opt-IN bypass; default OFF — see Step 12) | §9j |
| `e2e/specs/features/onboarding.spec.ts` | new | §6.A,C,G,G' |
| `e2e/pages/OnboardingPage.ts` | new | §4i (testIDs) |
| `workflows/stories/TASK-20260526-1731/screenshots/*.png` | new (12+ images: 6 screens × {light, dark} + splash) | §4l |
| `workflows/stories/TASK-20260526-1731/designer-asks.md` | new — created lazily IF any Figma copy slot is empty | §9m (see Step 6) |

The "Affected Files" rows under `src/screens/OnboardingScreens/components/` enumerate the three concrete internal components (TopicChipGrid, ModelRadioGroup, OnboardingBottomBar). No wildcard. A fourth file under that directory is a tracked scope deviation requiring an architect callback.

### Dev-team repo (`/Users/aghorbani/codes/pocketpal-dev-team`)

| Path | Change kind | WHAT reference |
| --- | --- | --- |
| `context/architecture/onboarding.md` | new (promoted from `what.md` minus story metadata + Review History) | WHAT preamble (line 5) |
| `context/architecture/theming.md` | edit (single line in §1a Spacing axis: add `xxl: 40`) | I_OB11 / D11 |
| `context/redesign/FOU-112-rollout.md` | edit (mark FOU-116 merged + add SHA) | rollout-doc convention |

---

## Implementation Steps

### Step 1: Add `spacing.xxl = 40` token + widen `TokenSpacing`

**Implements**: WHAT §4h (token-to-Figma table — Spacing axis row) / §4f I_OB11 / D11.

**Files**:

- `src/theme/tokens/spacing.ts` — append `xxl: 40` to the `spacing` const.
- `src/theme/tokens/types.ts` — widen the `TokenSpacing` interface (line 160) with `xxl: 40`. This step is mandatory and separate from the const edit because `TokenSpacing` is literal-typed: omitting it makes the const-edit a typecheck failure.
- `src/theme/tokens/__tests__/spacing.test.ts` (or whichever tokens contract test exists under `src/theme/tokens/__tests__/`) — extend to assert `spacing.xxl === 40`.

**Approach**: Mechanical token addition. `spacing.xxl` is a leaf-only addition; no consumer changes today. The architect-critic flagged the literal-type widen as the implicit second edit — both edits ship in the same commit so the typecheck never breaks.

**Verification**:

- `yarn typecheck` passes (widened interface accepts the const change).
- `yarn lint` passes.
- `yarn test --findRelatedTests src/theme/tokens/spacing.ts` passes.

### Step 2: UIStore — persisted flag + ephemeral onboarding state + single-writer methods

**Implements**: WHAT §1a / §5 / §7 / §9c.

**Files**:

- `src/store/UIStore.ts` — add fields:
  - persisted: `hasCompletedOnboarding: boolean = false`, `onboardingTopicsSnapshot: TopicKey[] = []`. Append both names to the `makePersistable.properties` array (line 91).
  - in-memory only (NOT persisted): `onboardingState: { currentStep: 1; selectedTopics: TopicKey[]; selectedModelId: string | null }` initialised to `{ currentStep: 1, selectedTopics: [], selectedModelId: null }`.
  - Define `TopicKey` (closed union of the 6 keys from §1a) in this file or co-locate under `src/store/onboarding/types.ts`.
  - Methods (each wraps a single `runInAction`):
    - `setOnboardingStep(n: 1|2|3|4|5|6)`
    - `toggleOnboardingTopic(key: TopicKey)`
    - `setOnboardingModelId(modelId: string | null)`
    - `completeOnboarding({topics, modelId}: {topics: TopicKey[]; modelId: string | null})` — sets `hasCompletedOnboarding=true`, snapshot, resets `onboardingState`.
    - `resetOnboarding()` — test/E2E-only (callers ensure `__DEV__ || __E2E__`).
- `src/store/__tests__/UIStore.test.ts` — cover: default flag is `false`, `completeOnboarding` flips the flag and freezes the snapshot, `resetOnboarding` returns to clean state, `toggleOnboardingTopic` adds + removes idempotently. No tests for resilience of persistence on hydration failure (already covered by theming.md §9k contract).

**Approach**: One field set, one method set, one place. Follow the existing `runInAction`/`makeAutoObservable` patterns already in this file (`setChatWarning` is the nearest shape). All onboarding state mutations live inside the methods above — screens never touch `uiStore.onboardingState` directly. This is the §5 single-writer rule.

**Verification**:

- `yarn test --findRelatedTests src/store/UIStore.ts` passes.
- `yarn typecheck` passes.

### Step 3: PalStore — `initializePipPal` seeded from `initialize()`

**Implements**: WHAT §1b / §4d / §9g / I_OB7.

**Files**:

- `src/store/PalStore.ts` — add private `initializePipPal()` next to `initializeLookiePal` (line 739). Idempotency check: `this.pals.find(p => p.name === 'Pip' && p.source === 'local')`. If absent, `addPal(palData)` with the §1b shape, `defaultModel: undefined` (no preset model — screen 6 binds the model when the user picks one). If present, **return immediately** — do NOT overwrite any field on the existing Pip record (this is the I_OB7 idempotency guarantee: a re-init never clobbers an existing `defaultModel` that screen 6 wrote on a prior session). Call from `initialize()` (line 76) immediately after `initializeLookiePal()`.
- `src/store/__tests__/PalStore.test.ts` — mirror the existing Lookie tests:
  1. First call seeds Pip; second call is a no-op; both Pip and Lookie coexist regardless of call order.
  2. **defaultModel-preservation re-init**: pre-seed Pip with `defaultModel = <some model>` directly via `addPal`, call `initializePipPal()`, assert `pip.defaultModel` is unchanged (same id, same object identity). This pins the I_OB7 contract: idempotency means "no-op when present, regardless of internal shape" (CONCERN 1 resolution).

**Approach**: Copy the Lookie precedent — same call site, same idempotency shape, same error-swallow. `defaultModel` is intentionally `undefined` on first seed; the screen-6 Finish path is what binds it via `palStore.updatePal({...pip, defaultModel: <chosenModel>})` (called by the Onboarding6 finish handler in Step 7). Pip seeding happens on every app start, independent of onboarding outcome (Skip path leaves Pip with no model — §4e). On a subsequent restart after the user picked a model, `initializePipPal()` MUST be a true no-op so the persisted Pip survives.

**Approach detail on model binding**: The screen-6 handler resolves the picked model object from `RECOMMENDED_PAL_MODEL_SET` against `modelStore.defaultModels`, then calls `palStore.updatePal({id: pip.id, defaultModel})` to persist the binding. The Onboarding6 component finds Pip via `palStore.pals.find(p => p.name === 'Pip' && p.source === 'local')` — no new public API on `PalStore`.

**Verification**:

- `yarn test --findRelatedTests src/store/PalStore.ts` passes (including the new defaultModel-preservation test).

### Step 4: `RECOMMENDED_PAL_MODEL_SET` + stability test

**Implements**: WHAT §1b / §4d / D2 — and architect-critic R2 SUGGESTION 2 (pick stable, existing ids; assert with a unit test).

**Files**:

- `src/store/onboarding/recommendedPalModelSet.ts` — new module exporting:
  ```ts
  export const RECOMMENDED_PAL_MODEL_SET: readonly string[] = [
    'hugging-quants/Llama-3.2-1B-Instruct-Q8_0-GGUF/llama-3.2-1b-instruct-q8_0.gguf', // ~1.32 GB
    'Qwen/Qwen2.5-1.5B-Instruct-GGUF/qwen2.5-1.5b-instruct-q8_0.gguf',                 // ~1.89 GB
    'bartowski/SmolLM2-1.7B-Instruct-GGUF/SmolLM2-1.7B-Instruct-Q8_0.gguf',            // ~1.82 GB
  ] as const;
  ```
- `src/store/onboarding/__tests__/recommendedPalModelSet.test.ts` — new test asserting:
  - `RECOMMENDED_PAL_MODEL_SET.length === 3`.
  - Every id in the set is present in `defaultModels` (`defaultModels.find(m => m.id === id)` returns defined).
  - Each entry has `origin === ModelOrigin.PRESET` (catches future catalogue refactors).
  - All three model `size` fields stay ≤ 2.5 GB (rough small-tier bound; flags catalogue replacement that drifts off the small-tier intent).

**Approach**: A closed const + a unit test that breaks loudly the moment a future catalogue change deletes or renames any of the three ids. This is the lock the architect-critic asked for — the E2E spec keys off `onboarding-pip-model-<modelId>` (§4i), so id stability is a testable contract item.

**Verification**:

- `yarn test --findRelatedTests src/store/onboarding/__tests__/recommendedPalModelSet.test.ts` passes.

### Step 5: DS `Stepper` component + tests + snapshot matrix

**Implements**: WHAT §4c / §4c.5 / §4l / D10 / I_OB4.

**Files**:

- `src/components/ui/Stepper/Stepper.tsx` — pure presentational. Reads `useTheme()`. Renders a horizontal row of dots; the dot at `current` is wider (48×4), the rest are 20×4. Reads `theme.colors.primary` / `theme.colors.outlineVariant`, `theme.radius.xs`, `theme.spacing.xs`. Clamps `current` to `[1,total]` and emits a dev `console.warn` if out of range. `accessibilityRole='progressbar'`, `accessibilityValue={{min:1,max:total,now:current}}`, default `accessibilityLabel` = `Step ${current} of ${total}` (overridable). Default `testID='ui-stepper'`; per-dot `testID='ui-stepper-dot-<i>'` (i = 1..total).
- `src/components/ui/Stepper/styles.ts` — token-only styles factory `createStyles(theme)`. No raw hex, no raw px.
- `src/components/ui/Stepper/index.ts` — named re-exports of `Stepper` + `StepperProps`.
- `src/components/ui/Stepper/__tests__/Stepper.test.tsx` — three logic tests (default a11y, clamp, RTL row-reverse) plus a **single `runSnapshotMatrix` invocation** that exactly satisfies WHAT §4c.5's `{2,3,4,5-step} × {light,dark}` = 8 snapshots requirement. The helper (`src/components/ui/__tests__/helpers/snapshotMatrix.tsx:96`) has no `total` axis; map the `total` axis onto the helper's `variants` axis (variant values `'2'`, `'3'`, `'4'`, `'5'`):
  ```ts
  runSnapshotMatrix(
    'Stepper',
    ({variant}) => <Stepper total={Number(variant)} current={1} />,
    {
      variants: ['2', '3', '4', '5'] as const,
      sizes: ['m'] as const,
      states: ['default'] as const,
      modes: ['light', 'dark'] as const,
      // langs omitted → no font-fallback canary cells emitted
    },
  );
  ```
  This yields `4 variants × 1 size × 1 state × 2 modes = 8 cells`, matching WHAT §4c.5 exactly. `current` is fixed at `1` because the visual contract is "dot widths and gaps render correctly across totals"; varying `current` adds nothing to the snapshot signal (the wide-dot position is symmetric across totals, exercised in the dedicated logic tests instead).
- `src/components/ui/index.ts` — add `export {Stepper} from './Stepper';` and `export type {StepperProps} from './Stepper';`.

**Approach**: Mirror the `Chip` folder shape and its `runSnapshotMatrix` integration at `src/components/ui/Chip/__tests__/Chip.test.tsx:28`. `RTL` row-reverse is the only conditional layout (read `I18nManager.isRTL` once at render time). Dot widths are token-derived (`spacing.s * 2.5` for narrow, `spacing.l * 2` for wide is approximate — pick values that match the Figma `896:29130` widths; do not invent new tokens).

**Verification**:

- `yarn test --findRelatedTests src/components/ui/Stepper/` passes; Jest reports exactly 8 snapshots emitted under the `Stepper — snapshot matrix > baseline …` describe block (labels: `2-m-default-light`, `2-m-default-dark`, `3-m-default-light`, …, `5-m-default-dark`).
- Snapshot files reviewed once and committed.
- `yarn lint` passes (new file is inside `src/components/ui/**/styles.ts` so the no-raw-hex / no-raw-px lint rule applies — must use tokens).

### Step 6: l10n keys under `onboarding.*` in `src/locales/en.json`

**Implements**: WHAT §4j / §9m.

**Files**:

- `src/locales/en.json` — add the `onboarding` top-level key with all sub-keys enumerated in WHAT §4j (eyebrow / title / body / cta per screen 1–6; `screen5.topic.<6 TopicKey entries>`; `screen6.model.<3 keys mirroring RECOMMENDED_PAL_MODEL_SET>.title`; `screen6.model.<...>.subtitle`; `back`; `skip`; `splash.title` optional).

**Approach**: Copy the strings verbatim from the canonical Figma frames (`884:28223`). The Weblate pipeline picks up `en.json` automatically; non-English locales follow on Weblate (no changes needed here).

**Empty-Figma fallback (per §9m)**: If any Figma string slot is empty at HOW execution time, the implementer takes this **expected exit path** (it is not a failure — §9m specifies this exact protocol):

1. Log a designer ask under `workflows/stories/TASK-20260526-1731/designer-asks.md` (new file; same shape as `workflows/stories/TASK-20260519-2110/designer-asks.md`). Record the screen #, the missing key, and the Figma node id that should have held the copy.
2. Continue building Steps 5/7/8 against placeholder testID-only renderings: render the `testID`-bearing element with an empty string text node (NOT invented copy). Visual captures in Step 10 are still produced, but with the empty text node visible — the pipeline-reviewer treats this as an architect-flagged designer ask, not an engineering omission.
3. The designer-asks file rides in the PR as a non-blocking surface; copy lands later via Weblate / a follow-up small PR.

**Verification**:

- `node scripts/validate-l10n.js` passes (existing CI gate; runs locally too).
- `yarn test --findRelatedTests src/locales/` passes.
- If any Figma string was empty: `workflows/stories/TASK-20260526-1731/designer-asks.md` exists and enumerates every missing key.

### Step 7: Splash + Onboarding{1..6} screens (light + dark)

**Implements**: WHAT §4b (per-screen layout) / §4h (token mapping) / §4i (testIDs) / §3 (state machine) / §4d (screen 6 model binding) / §4k (RTL).

**Files**:

- `src/screens/OnboardingScreens/SplashScreen.tsx` — renders the brand mark per Figma `884:28349`. On mount, schedules `navigation.navigate('Onboarding1')` after `SPLASH_MIN_DWELL_MS` (`= 600`, hoisted as a file-local const per D6). Disables back gesture (`gestureEnabled: false` via screen options or `BackHandler` listener). `testID='onboarding-splash'`. SUGGESTION 1 disposition: `SPLASH_MIN_DWELL_MS = 600` (constant value) — WHAT D6 leaves the exact value to HOW (`~600ms`); HOW pins it at `600` and ships it as a file-local const. No WHAT amendment needed.
- `src/screens/OnboardingScreens/Onboarding1Screen.tsx` through `Onboarding6Screen.tsx` — one file per screen. Each:
  1. Calls `uiStore.setOnboardingStep(N)` once on mount (use `useEffect(() => {…}, [])`).
  2. Renders header (Stepper for 1–4 only, Skip for 2–6 only), Visual, Content, Bottom bar per the §4b table.
  3. Uses DS components only: `Button`, `IconButton`, `Chip`, `RadioSection`, `Header`, `Stepper`, plus RN Paper `Text` (the thin Paper set allowed by theming.md).
  4. Reads tokens via `useTheme()`. No raw hex, no raw px. Use `start`/`end` for directional padding/margin (RTL contract §4k).
  5. Wires testIDs per §4i (`onboarding-screen-<N>`, `onboarding-skip`, `onboarding-back`, `onboarding-primary`, plus the per-screen ones for chips / radios / device-info chip).
  6. Reads / writes onboarding state through `uiStore.toggleOnboardingTopic` (screen 5) and `uiStore.setOnboardingModelId` (screen 6). Continue/Finish enable state derives from `uiStore.onboardingState.selectedTopics.length > 0` (screen 5; D7) and `uiStore.onboardingState.selectedModelId !== null` (screen 6; D8).
  7. Screen 6 Finish handler runs (in order, all inside one function):
     - resolve the picked `Model` from `defaultModels.find(m => m.id === uiStore.onboardingState.selectedModelId)`;
     - find `pip = palStore.pals.find(p => p.name === 'Pip' && p.source === 'local')` and call `palStore.updatePal({...pip, defaultModel: picked})`;
     - call `uiStore.completeOnboarding({topics: uiStore.onboardingState.selectedTopics, modelId: picked.id})`;
     - call `modelStore.checkSpaceAndDownload(picked.id)` (fire-and-forget; no `await` blocking screen unmount). The MobX reactivity on `hasCompletedOnboarding` will swap the navigator from this point.
  8. Screen 2–6 Skip handler runs `uiStore.completeOnboarding({topics: uiStore.onboardingState.selectedTopics, modelId: null})`. No Pip update, no download call (§4e).
- `src/screens/OnboardingScreens/components/TopicChipGrid.tsx` — internal 2-col chip layout for screen 5. Pure presentational; reads `Chip` from DS. NOT a DS export.
- `src/screens/OnboardingScreens/components/ModelRadioGroup.tsx` — internal 3-row radio group for screen 6. Uses `RadioSection` from DS. NOT a DS export.
- `src/screens/OnboardingScreens/components/OnboardingBottomBar.tsx` — internal back+primary row used by screens 2–6. Uses `IconButton` + `Button` from DS.
- `src/screens/index.ts` — re-export.
- `src/utils/navigationConstants.ts` — add `ROUTES.ONBOARDING = { SPLASH, STEP_1, ..., STEP_6 }` (or a flat namespace) to avoid magic strings.

**Approach**: Each screen is a thin layout file backed by `useTheme()` + DS components + the UIStore single-writer methods. No screen owns onboarding state — all reads go through `uiStore.onboardingState`. Designer copy is keyed via `useL10n()` (`L10nContext`). No `accessibilityLabel` invention — every interactive element labels itself via the existing l10n key (`onboarding.back`, `onboarding.skip`, `onboarding.screenN.cta`). Per §4l, the screen-level snapshot strategy is OUT — screens ship visual references, not Jest snapshots.

**Verification**:

- `yarn lint` passes.
- `yarn typecheck` passes.
- Manual run on iOS sim + Android emu — observe each screen renders, Back/Skip/Continue/Finish work, Continue/Finish disabled-until-selected on screens 5/6 (Scenarios §6.A, §6.C, §6.G, §6.G').

### Step 8: `OnboardingStack` navigator

**Implements**: WHAT §4a (#3) / §4g.

**Files**:

- `src/screens/OnboardingScreens/OnboardingStack.tsx` — `createNativeStackNavigator()` (`@react-navigation/native-stack`; confirm dependency is present; if not, fall back to `createStackNavigator` from `@react-navigation/stack`, whichever is already in the worktree's `package.json` — do NOT add a new dependency). 7 routes: `Splash`, `Onboarding1`…`Onboarding6`. `screenOptions={{ headerShown: false, gestureEnabled: false }}`. Initial route `Splash`.

**Approach**: A small file. No new dependency. The stack is a child of the existing `<NavigationContainer>` (sibling of `Drawer.Navigator` via the SwitchPoint in Step 9).

**Verification**:

- `yarn typecheck` passes.

### Step 9: `<SwitchPoint>` inside `App.tsx`

**Implements**: WHAT §4a (#1, #2, #4) / §2 / §4f I_OB1 / I_OB2 / I_OB6 / Scenarios §6.A, §6.B, §6.C.

**Files**:

- `App.tsx` — add a small `observer` component `<SwitchPoint>` defined either inline or in `src/components/SwitchPoint.tsx`. It reads `uiStore.hasCompletedOnboarding` and returns either `<OnboardingStack/>` or the existing `<Drawer.Navigator …>` block (lines 90–186 today). Insert `<SwitchPoint/>` as a sibling of `<TTSSetupSheet/>` directly under `<BottomSheetModalProvider>`, replacing today's `<Drawer.Navigator …>` block by moving its full JSX into `SwitchPoint`'s "no" branch. The `<TTSSetupSheet/>` stays as the second child of `<BottomSheetModalProvider>` (it should be reachable post-onboarding only — TTS is a Drawer-screen-driven concern, so co-mounting it during onboarding has no visible effect; it's a portal target rendered only when used).

**Approach**: A pure rewiring step. The provider tree above is unchanged. The Drawer block moves verbatim into the `false` branch of `<SwitchPoint>`'s ternary — diff should show "moved + added a wrapper", nothing else. The `<SwitchPoint>` body is ~15 lines.

**Verification**:

- `yarn typecheck` passes.
- Manual fresh-install run: app boots → hydration hold (existing) → Splash → Onboarding1.
- Manual "second-launch" run: kill + relaunch → no Splash, direct to Chat (Scenario §6.B).

### Step 10: Visual capture — light + dark per screen

**Implements**: WHAT §4l.

**Files**:

- `workflows/stories/TASK-20260526-1731/screenshots/<screen>-<mode>.png` — 12+ captures (Splash + 6 screens × {light, dark} on iOS sim + Android emu). The pipeline-reviewer diffs these against the canonical Figma frames `884:28223` and `3011:25220` by eye.

**Approach**: Same procedure as FOU-114 (`workflows/stories/TASK-20260519-2110/visual-diff-procedure.md`). Drive the screens manually via the running sim; flip `colorScheme` via OS settings; capture on each transition. RTL spot-check on screens 5 + 6 (Scenario §6.D) — add `<screen>-rtl-he.png` for screens 5 + 6.

**Verification**:

- All captures committed under the story dir.
- Pipeline-reviewer references them in the draft PR body.

### Step 11: E2E onboarding spec

**Implements**: WHAT §6.A, §6.B, §6.C, §6.G, §6.G', §6.H / §4i (testID surface) / §9j (`__E2E_SKIP_ONBOARDING__` left UNSET for this spec only).

**Files**:

- `e2e/pages/OnboardingPage.ts` — page object exposing accessors for: `splash`, `screen(N)`, `stepper`, `stepperDot(i)`, `skip`, `back`, `primary`, `topicChip(key)`, `pipModel(modelId)`. All driven by the §4i testIDs.
- `e2e/specs/features/onboarding.spec.ts` — covers:
  1. Fresh install → Splash → Onboarding1 → 1..5 → 1 chip → 6 → 1 radio → Finish lands on Chat (§6.A).
  2. **Cold-restart skips onboarding (§6.B)**: continuation of test 1 — after Finish, relaunch the app via the Appium relaunch primitive and assert the app boots straight to Chat (no Splash, no Onboarding1 visible). **Relaunch driver API (pinned)**: on iOS, use `driver.terminateApp(<bundleId>)` followed by `driver.activateApp(<bundleId>)`, where `<bundleId>` is read from the existing wdio capabilities (`appium:bundleId`). On Android, the UiAutomator2 equivalent is the same `terminateApp` / `activateApp` pair against `<appPackage>` (read from `appium:appPackage`). Both APIs are part of the WebDriver/Appium 2 surface already used in `e2e/specs/features/`; no new helper is added. Persisted `hasCompletedOnboarding=true` survives the kill (AsyncStorage is process-external) — this is what test 2 verifies.
  3. Skip on step 3 → lands on Chat with no pal/model bound (§6.C).
  4. Pick smallest model on step 6 → Finish → `pip` has `defaultModel.id === <chosen>` (introspection via existing AutomationBridge MemoryAdapter or via deep-link if present; otherwise verify by navigating to Models screen and seeing the model marked downloading) (§6.G).
  5. Skip on step 6 → no model bound, no download started (§6.G').
  6. Stepper dot count + active dot index across screens 1–4 (§6.H).
- `e2e/scripts/run-e2e.ts` (existing pipeline) — no change. Spec name `onboarding` slots into the existing matrix.

**Approach**: The `__E2E_SKIP_ONBOARDING__` bypass in `AutomationBridge` (see Step 12) auto-completes onboarding on app start IF the env var / capability is set — so the onboarding spec runs with the bypass OFF (the spec's wdio config does NOT set `e2eSkipOnboarding=true`), against a fresh install (clear app data on Android via `adb shell pm clear com.pocketpalai.e2e`; uninstall + reinstall on iOS sim). The bypass is opt-IN, not opt-OUT — onboarding is the default; every OTHER E2E spec sets the capability to true so they don't have to walk the flow.

**Verification**:

- `yarn e2e:ios --spec onboarding --skip-build` passes on the local sim (6 tests).
- `yarn e2e:android --spec onboarding --skip-build` passes on the local emu (6 tests).

### Step 12: `AutomationBridge` opt-IN onboarding bypass

**Implements**: WHAT §9j.

**Files**:

- `src/__automation__/AutomationBridge.tsx` (or a new `src/__automation__/adapters/OnboardingBypass.tsx`) — reads a build-time env var `__E2E_SKIP_ONBOARDING__` (added to `babel.config.js` env-var inject list); when truthy, calls `uiStore.completeOnboarding({topics: [], modelId: null})` synchronously on mount, before navigation mounts. Gated by `__E2E__`; tree-shaken out of prod builds via the existing AutomationBridge contract.
- `e2e/wdio.*.conf.ts` (existing wdio configs for non-onboarding specs) — add `capabilities['appium:processArguments'].env.E2E_SKIP_ONBOARDING = 'true'` (iOS) and equivalent extraOptions on Android, OR simply default-on via `babel.config.js` when `E2E_BUILD=true && E2E_SKIP_ONBOARDING !== 'false'`. The simplest path is: env-var defaults ON in E2E builds, the onboarding spec sets `E2E_SKIP_ONBOARDING=false` for its wdio config (single override). Pick whichever lands fewer wdio config edits; document the chosen direction in the spec file's top-of-file comment.

**Approach**: Mirror the existing MemoryAdapter pattern. Default off so the onboarding spec works against a clean state; flipped on by every other E2E spec via the wdio capability.

**Verification**:

- Existing AutomationBridge prod-bundle grep (`AUTOMATION_BRIDGE` marker) still triggers in dev/E2E and is absent from prod (CI sanity).
- All existing E2E specs (`quick-smoke`, `language`, `pal-greeting`, `thinking-pal-override`) pass with `E2E_SKIP_ONBOARDING=true` in their wdio config.

### Step 13: Lint + typecheck + Jest

**Implements**: repo-wide gates.

**Verification**:

- `yarn lint` passes (worktree-wide).
- `yarn typecheck` passes (worktree-wide).
- `yarn test` passes (full Jest suite — necessary because UIStore and PalStore are central).

### Step 14: Promote WHAT to new `context/architecture/onboarding.md`

**Implements**: per the architect's intent — WHAT is a flow-doc bootstrap, absorbed into the architecture library on the same PR pair. Per AGENTS.md and §10 cleanup-reminder #1.

**Files** (dev-team repo, not worktree):

- `context/architecture/onboarding.md` — new file. Copy `workflows/stories/TASK-20260526-1731/what.md` verbatim, then:
  - delete the front-matter line `Story: TASK-20260526-1731 — Phase 3a slice of FOU-112 …` and the Review History section.
  - convert every `(P)` marker to `(C)` (all proposals are now landed behaviour).
  - leave every `(D)` marker as `(D)` (decisions stay tagged for posterity).
  - confirm zero `(?)` markers remain.
  - update the preamble to reference the merged PR URL instead of the story.
- `context/architecture/README.md` — append `onboarding.md` to the flow-doc index (matching the pattern used for the other flow docs).

**Approach**: Mechanical promotion. The `(P)→(C)` conversion is the only semantic change; everything else is copy.

**Verification**:

- `grep -E '\(P\)|\(\?\)' context/architecture/onboarding.md` returns no matches.
- README index renders the new flow doc.

### Step 15: Amend `context/architecture/theming.md` §1a (Spacing axis adds `xxl`)

**Implements**: WHAT §4h paired-edit / I_OB11 / D11.

**Files** (dev-team repo, not worktree):

- `context/architecture/theming.md` — locate the Spacing axis line under §1a (currently ends `xl: 32   // NEW: xl`) and extend to `xxl: 40   // NEW: xxl (FOU-116 / TASK-20260526-1731)`. Leave the `// NEW: xl` annotation intact (the previous slice's marker). One-line edit.

**Approach**: One-line edit. The Spacing axis is the only section that changes.

**Verification**:

- The edited line matches the WHAT §4h Spacing-axis row.
- `git diff context/architecture/theming.md` shows exactly one inserted token name.

### Step 16: Paired-edit cross-cite handshake (I_UI8 analogue)

**Implements**: WHAT §4f I_OB11 / D11 / §10 cleanup-reminder #2.

**Files / artifacts** (cross-repo):

- Dev-team-repo commit message (the commit containing Steps 14 + 15): cite the **app PR URL** in the body, e.g. `Promotes onboarding.md and amends theming.md §1a — paired with app PR <URL>`.
- App PR description: cite the **dev-team-repo commit SHA** of the commit containing Steps 14 + 15, e.g. `Architecture absorbed in pocketpal-dev-team commit <SHA>`.
- Implementer keeps both citations visible in the final draft PR; the pipeline-reviewer enforces both before approving.

**Approach**: Mechanical. Same handshake FOU-115 used (theming.md I_UI8 line 499). Order: land dev-team-repo commit first (so the SHA exists) → push app PR with the SHA → amend dev-team-repo commit message in-place (or follow with a small `docs(architecture): note app PR #N` commit) to record the app PR number. The pipeline-reviewer accepts either ordering as long as both citations exist at draft-PR time.

**Verification**:

- App PR description grep matches the dev-team-repo commit SHA.
- Dev-team-repo commit message grep matches the app PR URL or number.

---

## Testable-Contract Coverage

Per template — standard/complex source is WHAT §6.

| Contract item (WHAT §6) | Verified by |
| --- | --- |
| §6.A — Fresh install, full onboarding flow → Drawer mounts | E2E `e2e/specs/features/onboarding.spec.ts` test 1 + Step 10 visual captures |
| §6.B — Cold restart after onboarding skips the flow | E2E `e2e/specs/features/onboarding.spec.ts` test 2 (relaunch via `driver.terminateApp` + `driver.activateApp`, bypass capability left unset) |
| §6.C — Skip on screen 3 → Drawer mounts, no model bound | E2E `e2e/specs/features/onboarding.spec.ts` test 3 |
| §6.D — RTL Hebrew layout mirrors | Manual RTL spot-check on screens 5/6 (Step 10 capture `<screen>-rtl-he.png`) + Stepper unit test (Step 5) |
| §6.E — Dark mode parity | Step 10 visual captures `<screen>-dark.png` diff against Figma `3011:25220` |
| §6.F — Mid-flow process kill → restart at Splash | Unit test `UIStore.test.ts` (in-memory state lost; persisted flag still `false`) |
| §6.G — Pick model + Finish → download enqueued | E2E `e2e/specs/features/onboarding.spec.ts` test 4 (post-Finish navigate to Models, observe downloading state) |
| §6.G' — Skip on screen 6 → no model bound, no download | E2E `e2e/specs/features/onboarding.spec.ts` test 5 |
| §6.H — Stepper dot count / active dot per screen | Unit test `Stepper.test.tsx` + Step 5 snapshot matrix (8 cells, `total ∈ {2,3,4,5} × {light,dark}`) + E2E test 6 |
| D2 — `RECOMMENDED_PAL_MODEL_SET` ids stable on `defaultModels` | Unit test `src/store/onboarding/__tests__/recommendedPalModelSet.test.ts` (Step 4) |
| I_OB1 / I_OB2 — single-shot flow, no Drawer overlap | E2E test 1 (Drawer absent during onboarding; present after Finish) |
| I_OB6 — no Drawer screens read OnboardingState | Static (Drawer not rendered during onboarding); implicitly verified by test 1 |
| I_OB7 — `initializePipPal` idempotent (incl. defaultModel preservation on re-init) | Unit tests `PalStore.test.ts` (Step 3 — two new tests: no-op-when-present AND defaultModel-preservation) |
| I_OB10 — no telemetry / no auth | Static (no network code in any onboarding screen — code-review gate) |
| I_OB11 — `spacing.xxl=40` paired-edit handshake | Step 16 — both citations present in PR description + dev-team-repo commit |

---

## Native Verification

NATIVE_CHANGES=NO. No `pod install`, no iOS build, no Android build required as a gate. (`yarn ios` / `yarn android` may still be used locally to drive the visual captures in Step 10, but they are not blocking review evidence.)

---

## Visual Confirmation

VISUAL_CAPTURES (driven manually by the pipeline-reviewer / implementer; no AutomationBridge prompts):

```json
[
  {
    "label": "Onboarding Splash — light",
    "prompt": "Fresh install on iOS sim. Observe boot from cold.",
    "look_for": "Brand splash at 884:28349 visible for ~600ms; light background; no nav header; testID onboarding-splash present."
  },
  {
    "label": "Onboarding Splash — dark",
    "prompt": "Fresh install on iOS sim with OS dark mode on.",
    "look_for": "Brand splash rendered against dark tokens; no FOUC between hydration hold and splash."
  },
  {
    "label": "Onboarding1 — light",
    "prompt": "After Splash transition.",
    "look_for": "Stepper 1/4 at top; 'Welcome to Pocket Pal' eyebrow + 'Meet your pals.' title + body; full-width primary 'Get started' button; NO Back, NO Skip."
  },
  {
    "label": "Onboarding1 — dark",
    "prompt": "Same as above with dark mode.",
    "look_for": "Dark render matches Figma 3011:25220 screen 7 (= dark of light screen 1)."
  },
  {
    "label": "Onboarding2 — light + dark",
    "prompt": "Tap 'Get started' on screen 1.",
    "look_for": "Stepper 2/4; 'The idea' / 'Anytime, Anywhere.' eyebrow + title; Back IconButton + primary Continue."
  },
  {
    "label": "Onboarding3 — light + dark",
    "prompt": "Tap Continue on screen 2.",
    "look_for": "Stepper 3/4; 'A heads-up' / 'Smaller, but yours.' eyebrow + title; cards stack visual."
  },
  {
    "label": "Onboarding4 — light + dark",
    "prompt": "Tap Continue on screen 3.",
    "look_for": "Stepper 4/4; 'Privacy promised' / 'Nothing leaves your phone.' eyebrow + title; shield visual."
  },
  {
    "label": "Onboarding5 — light + dark",
    "prompt": "Tap Continue on screen 4.",
    "look_for": "NO Stepper; 'What's your pal for?' header; 6 topic chips in 2-col grid; Continue disabled before selection, enabled after tapping one chip."
  },
  {
    "label": "Onboarding5 — RTL (he)",
    "prompt": "Switch language to Hebrew via Settings (post-onboarding), then trigger E2E reset of onboarding and re-enter.",
    "look_for": "Header text right-aligned; chip grid still 2-col but row order flips; Stepper row order mirrors; Inter (not Fraunces) renders the headline per theming.md §4d.2."
  },
  {
    "label": "Onboarding6 — light + dark",
    "prompt": "Select a chip on screen 5, tap Continue.",
    "look_for": "NO Stepper; Pip header (Pip icon + 'Pip' eyebrow + tagline + device-info chip); 3 model radio rows (Llama-3.2-1B, Qwen2.5-1.5B, SmolLM2-1.7B); Finish disabled until one radio picked."
  },
  {
    "label": "Onboarding6 — RTL (he)",
    "prompt": "Same flow under Hebrew locale.",
    "look_for": "Radio rows mirror; device-info chip and Skip button on the correct edge; model titles render in Inter."
  },
  {
    "label": "Onboarding complete → Chat empty",
    "prompt": "Tap Finish with a model selected.",
    "look_for": "OnboardingStack unmounts; Drawer.Navigator mounts; ChatScreen empty state visible (existing); no flash of Splash; Drawer hamburger visible top-left."
  }
]
```

---

## Deferred Items

WHAT §10 cleanup reminders #3 + #4 stay deferred — they refer to follow-on slices (FOU-117 for the real Homepage replacing the "out of scope here" note; next-slice Stepper snapshot-freeze contract).

WHAT §5 deferred-cleanups #1 (migrate `OnboardingState` to its own store) and #4 (widen `Stepper` variants on first non-onboarding consumer) — stay listed in WHAT; do NOT land here.

---

## What this plan is NOT

- Not a redesign of WHAT — WHAT §1–§9 is the design source; any decision required at execution time that isn't in WHAT routes back to the architect.
- Not a designer hand-off — Figma is the source for copy, illustrations, and exact dimensions.
- Not a Homepage / Chat specification — FOU-117 owns those. This slice stops at "Drawer mounts; ChatScreen empty state visible".
- Not a non-English copy delivery — `en.json` is the only locale touched; Weblate handles the rest.

---

## Review History

### Round 1 — plan-critic, LGTM (no findings recorded; round-1 verdict not preserved in handoff). Round-2 starts below.

### Round 2 — plan-critic, HAS_CONCERNS (2026-05-26)

| # | Severity | Summary | Resolution |
| - | -------- | ------- | ---------- |
| BLOCKER 1 | BLOCKER | Step 5 invoked `runSnapshotMatrix` with axes (`states`, `modes`, `total`-parametric closure) that don't match the helper's actual API at `src/components/ui/__tests__/helpers/snapshotMatrix.tsx:96` (no `states`/`modes` axes, no `total` axis). WHAT §4c.5 mandates `{2,3,4,5-step} × {light,dark}` = 8 snapshots. | **FIXED** (option c — single helper call with axis-mapping, no helper widen). Re-read the helper: it DOES accept `states` and `modes` as optional axes (lines 47–50, defaulted), but has no `total` axis. Mapped `total` onto the `variants` axis as string-encoded values `'2'`, `'3'`, `'4'`, `'5'`; the factory closure parses `Number(variant)` and passes it as Stepper's `total` prop with `current` fixed at `1`. Single `runSnapshotMatrix` call: `variants=['2','3','4','5'] as const`, `sizes=['m'] as const`, `states=['default'] as const`, `modes=['light','dark'] as const`, no `langs`. Yields exactly 8 cells `{2,3,4,5} × m × default × {light,dark}`. Step 5 Files block now shows the literal `ts` code block; Step 5 Verification specifies the exact 8 cell labels Jest will emit (`2-m-default-light`, …, `5-m-default-dark`); Progress Tracking row 5 amended to reflect the mapping; Testable-Contract row §6.H amended to cite the 8-cell shape. Helper API is NOT widened — kept untouched. |
| BLOCKER 2 | BLOCKER | Step 9b numbering bug: "Step 9b" was nested under Step 11; Progress Tracking listed 15 steps with no 9b row; Step 9 (SwitchPoint) made no mention of an AutomationBridge sub-step. | **FIXED** (option a — re-numbered to proper Step 12). Renamed "Step 9b: AutomationBridge opt-IN onboarding bypass" → standalone "Step 12: AutomationBridge opt-IN onboarding bypass". Shifted: old Step 12 (Lint + typecheck + Jest) → Step 13; old Step 13 (Promote WHAT) → Step 14; old Step 14 (Amend theming.md §1a) → Step 15; old Step 15 (Paired-edit handshake) → Step 16. Progress Tracking table updated (now 16 step rows). Testable-Contract Coverage updated for the new Step 12 / 14–16 numbers. Step 11 (E2E spec) Approach paragraph now points to Step 12 instead of "Step 9b below". I_OB11 row in Testable-Contract Coverage points to Step 16. |
| CONCERN 1 | CONCERN | Step 7's screen-6 Finish handler writes `pip.defaultModel` via `palStore.updatePal`. Test-only `resetOnboarding` could re-trigger `initializePipPal` on subsequent app boot — must guarantee re-init does not clobber. Step 3's PalStore.test.ts didn't cover "Pip exists with defaultModel; re-init no-op". | **FIXED**. Step 3's PalStore.test.ts gains a second test (the existing "first-call seeds; second-call no-op" test stays unchanged): pre-seed Pip via direct `addPal` with `defaultModel = <some model>`; call `initializePipPal()`; assert `pip.defaultModel` is preserved (same id AND same object identity). Step 3's Approach paragraph clarifies I_OB7's idempotency contract: "no-op when present, regardless of internal shape — never overwrite an existing Pip record". Affected-Files row for `PalStore.test.ts` extended to mention the new defaultModel-preservation test. Testable-Contract I_OB7 row updated to cite both tests. |
| CONCERN 2 | CONCERN | §6.B (cold-restart skips onboarding) — Test 2's relaunch mechanism was unspecified. | **FIXED**. Step 11's spec coverage list now has §6.B as a discrete test 2 (was implicitly merged into test 1 step-2). The relaunch driver API is pinned in Step 11: on iOS, `driver.terminateApp(<bundleId>)` then `driver.activateApp(<bundleId>)`, reading `<bundleId>` from `appium:bundleId`. On Android, same `terminateApp` / `activateApp` pair against `<appPackage>` from `appium:appPackage`. No new helper. Test numbering shifted (old tests 2..5 → 3..6). Testable-Contract §6.B row updated to cite test 2 and the API. |
| CONCERN 3 | CONCERN | Affected-Files row `src/screens/OnboardingScreens/components/*` used a wildcard, inviting scope drift. Step 7's Files list already enumerates three concrete files. | **FIXED**. Affected-Files row split into three concrete rows: `TopicChipGrid.tsx`, `ModelRadioGroup.tsx`, `OnboardingBottomBar.tsx` — each with its own WHAT reference. A paragraph below the Affected-Files table explicitly states "a fourth file under `src/screens/OnboardingScreens/components/` is a tracked scope deviation requiring an architect callback". |
| SUGGESTION 1 | SUGGESTION | D6 `SPLASH_MIN_DWELL_MS` value (`= 600`) was pinned in HOW but WHAT D6 only said "~600ms". | **DEFERRED-NO-OP** (acceptable latitude). WHAT D6 explicitly leaves the exact value to HOW ("Constant defined in HOW"), so HOW is the right place to pin `600`. Step 7's SplashScreen file description now states this disposition inline. No WHAT amendment requested. |
| SUGGESTION 2 | SUGGESTION | Topic-copy verification fallback path when Figma is empty wasn't fully spelled out — Step 6 said the implementer "stops" at §9m but didn't name it as an expected exit, didn't say to log a designer ask, didn't say to continue against placeholder testID-only renderings. | **FIXED**. Step 6 now has an "Empty-Figma fallback (per §9m)" sub-block with three explicit actions: (1) log the missing keys + Figma node ids in a new `workflows/stories/TASK-20260526-1731/designer-asks.md` (same shape as the FOU-114 precedent at `workflows/stories/TASK-20260519-2110/designer-asks.md`); (2) continue building Steps 5/7/8 against placeholder testID-only renderings — empty text nodes, NOT invented copy; (3) the file rides in the PR as a non-blocking surface. Step 6's Verification now lists "if any Figma string was empty: designer-asks.md exists and enumerates every missing key". Affected-Files table gains a row for `workflows/stories/TASK-20260526-1731/designer-asks.md` (lazy — created only if needed). |

### Revision summary for round-3 plan-critic

The two BLOCKERs are mechanical fact-fixes against the codebase:

1. The snapshot-matrix call now uses the actual `runSnapshotMatrix` API. The helper has no `total` axis but does accept `states`/`modes` as optional override axes (helper lines 47–50, defaulted to `['default','disabled']` and `['light','dark']`). The clean mapping is `total → variants` as string-encoded values `'2'..'5'` parsed back via `Number(variant)` in the factory; this is the same shape `Chip.test.tsx:28` uses (`variants` as a string axis), so the pattern is already in the codebase. Eight cells exactly, zero helper changes, no hand-rolled snapshot loop.
2. The AutomationBridge bypass is now a proper standalone Step 12; the surrounding steps shifted by one. Progress Tracking, Testable-Contract Coverage, and cross-step "see Step …" references all updated.

The three CONCERNs are testable-contract tightenings:

- I_OB7 grows a second PalStore test that explicitly verifies `defaultModel` survives a re-init — closes the "test-only `resetOnboarding` clobbers" trapdoor.
- §6.B's relaunch primitive is pinned to `driver.terminateApp` + `driver.activateApp` on both platforms (these are Appium 2 first-class APIs already used by the WDIO harness; no new helper).
- The components/* wildcard is replaced by three concrete file rows; a fourth is a tracked deviation, not free scope.

SUGGESTION 1 is a no-op — WHAT D6 explicitly defers the constant to HOW; pinning it at `600` in Step 7 is the contract-correct disposition. SUGGESTION 2 is the most user-visible revision: Step 6 now treats the empty-Figma exit as an _expected_ path with a named artefact (`designer-asks.md`) and a placeholder-rendering protocol, mirroring the FOU-114 precedent.

No design content was invented. No new invariants added. No deferred items from WHAT silently landed. Step count grew from 15 to 16 (the AutomationBridge bypass promotion). Plan still fits in one head.

---

## Round 3 — Figma-faithful retrofit (2026-05-27)

**Status**: open. The Rounds 1–2 skeleton shipped (commits `a44a949..2e324c7`, dev-team `a448d3f`+`d906cd8`+`cfe57a8`) ahead of a user visual review against the canonical Figma file `RZxDJea4t6jnBZrV4YBacF`. WHAT was rewritten to 14 Figma-faithful corrections (WHAT Round-3 history table A–N) and re-LGTM'd at Round 3.5. This section is the retrofit on top of the shipped skeleton. Each step is its own commit.

**Round-3 step ordering principle**: tokens + contract first (R1–R4), then primitives + scaffolding (R5–R8), then per-screen content (R9–R14), then tests/E2E (R15–R17), then dev-team paired-edit + flow-doc absorb (R18–R20). Asset exports (R5) gate everything visual but are independent of code edits R1–R4.

### Round-3 Progress Tracking

| Step | Status | WHAT trace | Commit (preview) |
| --- | --- | --- | --- |
| R1 — Token: `colors.accent.peach` (light + dark) + types widen | pending | §4h / §4f I_OB12 / D15 | `feat(theme): add accent.peach color binding` |
| R2 — TopicKey rename + single-select contract in UIStore | pending | §1a / §5 / §8 D7 | `refactor(onboarding): rename TopicKey union; switch to single-select` |
| R3 — `RECOMMENDED_PAL_MODEL_SET` quants of one base model | pending | §1b / D16 / §4d | `refactor(onboarding): replace recommended set with Llama-3.2-1B quants` |
| R4 — `defaultModels.ts` add Llama-3.2-1B Q2_K + Q4_K_M | pending | §1b / D16 / §9h | `feat(models): add Llama-3.2-1B Q2_K + Q4_K_M entries` |
| R5 — Asset exports (7 SVGs/PNGs from Figma) | pending | §4b (illustration column) / Round-3 history K | `chore(assets): add onboarding illustrations exported from Figma` |
| R6 — `HighlightText` internal primitive + tests | pending | §4g new row / §4h "Body-copy pill highlights" / §9p | `feat(onboarding): add HighlightText pill primitive` |
| R7 — `OnboardingAudioButton` internal primitive + tests | pending | §4b note 4 / §4g audio row / D14 / §9o | `feat(onboarding): add OnboardingAudioButton` |
| R8 — `DeviceInfoChip` internal primitive + tests | pending | §4b note 6 / §9q | `feat(onboarding): add DeviceInfoChip` |
| R9 — `ComparisonCards` screen-3 layout primitive + tests | pending | §4b screen 3 row | `feat(onboarding): add ComparisonCards primitive for screen 3` |
| R10 — `OnboardingScaffold` retrofit: Skip on 1–4, Audio on 5+6, italic titles, illustration slot | pending | §3 state table / §4b screen table + notes 1–6 / §4i | `refactor(onboarding): retrofit scaffold for Figma-faithful header + title` |
| R11 — Per-screen retrofit screens 1–4 (illustrations, italic accents, highlight pills, CTAs) | pending | §4b table rows 1–4 / §4h / §4j Round-3 keys | `feat(onboarding): retrofit screens 1-4 to Figma` |
| R12 — Screen 5 retrofit: chip-tap auto-advance, no bottom bar, header-slot Back+Audio | pending | §3 row 5 / §4b row 5 + note 4 / §4i / I_OB13 / D7 | `refactor(onboarding): single-select chip-tap auto-advance on screen 5` |
| R13 — Screen 6 retrofit: italic `*Pip*` headline, mascot, device chip, quant cards + Recommended badge, download CTA, no Skip | pending | §3 row 6 / §4b row 6 + notes 5–6 / §4d / §4j / I_OB14 / D8 / D16 | `feat(onboarding): retrofit screen 6 to Pip headline + quant picker` |
| R14 — l10n key delta (rename topic keys, new screen-6 keys, audio/highlight) | pending | §4j Round-3 keys | `feat(l10n): add Figma-faithful onboarding keys; rename topic keys` |
| R15 — UIStore + handlers + PalStore tests aligned to single-select + Round-3 contract | pending | §5 / §6 A,C,F,G,G'' (G' deleted) | `test(onboarding): align store/handler tests to single-select contract` |
| R16 — E2E spec + page-object update (drop G', add Audio assert, single-select tap-advance) | pending | §6.A,C,G,G'' + Round-3 history A,B,C / §4i | `test(e2e): align onboarding spec to Figma-faithful contract` |
| R17 — Lint + typecheck + Jest gates | pending | repo-wide gates | `chore: lint/typecheck/jest gates green` |
| R18 — Dev-team paired-edit: `theming.md` §1a Color axis adds `accent.peach` | pending | I_OB12 / D15 / §10 cleanup #2 | dev-team `docs(architecture): add accent.peach to Color axis` |
| R19 — Dev-team flow-doc absorb: `onboarding.md` Round-3 update + trim `designer-asks.md` | pending | §10 cleanup #1 / Round-3 history rows | dev-team `docs(architecture): absorb FOU-116 Round-3 corrections` |
| R20 — Dev-team rollout log: FOU-112 rollout entry for Round-3 | pending | rollout-doc convention | dev-team `docs(rollout): note FOU-116 Round-3 against PR #747` |
| R21 — Cross-cite handshake (app PR #747 ↔ dev-team SHAs) | pending | §4f I_OB12 / D15 / I_UI8 mechanism | (no code; PR description + commit-message edit) |

**Note on Round-1/2 retained work.** Every Round-1/2 step in the earlier Progress Tracking table that already shipped (Steps 1–16 above) stays as the load-bearing skeleton — the Round-3 retrofit edits files those steps created, it does NOT re-do them. The only exception is the model-set (R3 replaces the body of Round-2 Step 4) and the topic-key contract (R2 replaces the body of Round-2 Steps 2 + 6 + 7).

---

### Step R1 — Add `colors.accent.peach` token (light + dark) + widen `TokenColors`

**Implements**: WHAT §4h binding table (`Color/Accent/Peach` row), §4f I_OB12, D15, §10 cleanup #2.

**Files**:
- `src/theme/tokens/colors.ts` — add `accent: {peach: '<hex>'}` to both `lightColors` and `darkColors`. Hex values: read directly via Figma MCP `get_variable_defs` against the canonical file `RZxDJea4t6jnBZrV4YBacF` (peach pill on screens 2/3/4 body copy, Recommended-tier card background on screen 6).
- `src/theme/tokens/types.ts` — widen `TokenColors` with `accent: {peach: string}` (literal-typed; same handshake as `spacing.xxl` precedent in `a448d3f`).
- `src/theme/tokens/__tests__/colors.test.ts` (or the existing tokens contract test) — assert both binding paths resolve and differ between light/dark.

**Approach**: Mechanical token addition. Same shape as the `spacing.xxl` precedent. The `accent` namespace is new; alternative — flat `peach` at the top of the color map — was rejected because Figma groups it under `Color/Accent/*` (future peach/coral/etc. siblings land there).

**Verification**:
- `yarn typecheck && yarn test --findRelatedTests src/theme/tokens/colors.ts`.

**Commit preview**: `feat(theme): add accent.peach color binding`.

---

### Step R2 — Rename `TopicKey` union; switch to single-select in UIStore (persisted snapshot unchanged)

**Implements**: WHAT §1a, §5 single-writer table, §7, §8 D7, §9l (deleted), Round-3 history C.

**Files**:
- `src/store/UIStore.ts` (or `src/store/onboarding/types.ts` if `TopicKey` lives there):
  - Rename union members: `everyday → smartchat`, `creative → creative_writing`, `learning → education`, `productivity → else`. Keep `coding`, `roleplay`.
  - **Ephemeral state**: `selectedTopics: TopicKey[]` → `selectedTopic: TopicKey | null`. Default `null`.
  - **Persisted field UNCHANGED**: `onboardingTopicsSnapshot: TopicKey[]` stays as an array (per WHAT §1a comment "kept as an array to leave headroom for FOU-117 multi-tag work"; per WHAT §5 line 492 "derives the snapshot from `topic` (`topic === null` ⇒ `[]`; otherwise `[topic]`)"). NO field rename, NO hydrate-time migration, NO change to `makePersistable.properties` for this field — persisted shape is unchanged.
  - **Setter rename**: `toggleOnboardingTopic` → `setOnboardingTopic(key: TopicKey | null)`. Single mutation inside `runInAction`.
  - **Completion writer**: `completeOnboarding({topic, modelId})` signature: `topic: TopicKey | null`, `modelId: string | null`. Snapshot derivation (per WHAT §5): `topic === null ? [] : [topic]` — writes that array into the unchanged persisted `onboardingTopicsSnapshot`.
- `src/store/__tests__/UIStore.test.ts` — replace multi-select tests with single-select: `setOnboardingTopic('smartchat')` then `setOnboardingTopic(null)` then `setOnboardingTopic('coding')` (overwrite, no toggle). Assert post-`completeOnboarding` snapshot is `['smartchat']` for a non-null pick and `[]` for `null`. No hydrate-migration test (no migration needed).
- `src/screens/OnboardingScreens/useOnboardingHandlers.ts` — caller surface drops `toggleOnboardingTopic`; downstream Step R12 wires `setOnboardingTopic`.

**Approach**: Direct rename of the **ephemeral** state and setter only. The **persisted** snapshot field name and shape are unchanged — the WHAT explicitly keeps it as a `TopicKey[]` array to leave headroom for FOU-117 multi-tag work, and the completion writer derives `[topic]` or `[]` from the new scalar `selectedTopic`. The 'else' chip writes `null` per §8 D7's escape-hatch rule. No persistence migration is required by this slice (old union keys would still hydrate as strings; only members that were already removed from the union would surface as untyped — none of the renamed keys had shipped in any released build).

**Verification**:
- `yarn typecheck && yarn test --findRelatedTests src/store/UIStore.ts src/screens/OnboardingScreens/useOnboardingHandlers.ts`.

**Commit preview**: `refactor(onboarding): single-select topic state + TopicKey rename (persisted snapshot unchanged)`.
---

### Step R3 — Replace `RECOMMENDED_PAL_MODEL_SET` with 3 Llama-3.2-1B quants

**Implements**: WHAT §1b RECOMMENDED_PAL_MODEL_SET block, §4d, D16, D2 escape hatch, Round-3 history D.

**Files**:
- `src/store/onboarding/recommendedPalModelSet.ts` — replace the const with a typed shape that preserves quant tier labels:
  ```ts
  export type RecommendedQuantTier = 'quick' | 'balanced' | 'best';
  export interface RecommendedPalModelEntry {
    tier: RecommendedQuantTier;
    modelId: string;       // must exist in defaultModels with origin PRESET
    quant: 'Q2_K' | 'Q4_K_M' | 'Q8_0';
    recommended: boolean;  // true for 'balanced' only
  }
  export const RECOMMENDED_PAL_MODEL_SET: readonly RecommendedPalModelEntry[] = [
    {tier: 'quick',    modelId: '<llama-3.2-1b-q2_k-id>',   quant: 'Q2_K',   recommended: false},
    {tier: 'balanced', modelId: '<llama-3.2-1b-q4_k_m-id>', quant: 'Q4_K_M', recommended: true},
    {tier: 'best',     modelId: 'hugging-quants/Llama-3.2-1B-Instruct-Q8_0-GGUF/llama-3.2-1b-instruct-q8_0.gguf', quant: 'Q8_0', recommended: false},
  ] as const;
  ```
  Exact ids for Q2_K / Q4_K_M come from Step R4.
- `src/store/onboarding/__tests__/recommendedPalModelSet.test.ts` — retrofit existing tests:
  - Assert length 3, every `modelId` resolves in `defaultModels` with `origin === ModelOrigin.PRESET`.
  - Assert exactly one entry has `recommended: true` (the Balanced/Q4_K_M).
  - Assert tiers in `['quick','balanced','best']` order (positional contract — screen 6 renders in this order).
  - Drop the old "≤ 2.5 GB" size-bound test (the three Llama-3.2-1B quants are all well under 1 GB; the bound was a different-base-models safeguard).

**D2 escape hatch**: if Step R4 cannot source one of the GGUFs (huggingface 404), the implementer picks the closest-quant variant that does exist (e.g. Q3_K_M for Quick) AND updates the §4h note in `onboarding.md` (the Round-3 absorb in Step R19) — NOT a re-architect.

**Verification**:
- `yarn test --findRelatedTests src/store/onboarding/__tests__/recommendedPalModelSet.test.ts`.

**Commit preview**: `refactor(onboarding): replace recommended set with Llama-3.2-1B quants`.

---

### Step R4 — Add Llama-3.2-1B Q2_K + Q4_K_M entries to `defaultModels.ts`

**Implements**: WHAT §1b RECOMMENDED_PAL_MODEL_SET, D16, §9h, Round-3 history D.

**Files**:
- `src/store/defaultModels.ts` — duplicate the existing Q8_0 entry shape (line 245 — verified) twice, swap `id` / `name` / `url` / `filename` / `size` to Q2_K and Q4_K_M variants. Source paths from `hugging-quants/Llama-3.2-1B-Instruct-Q*-GGUF` repos (the Q8_0 already points there). Verify via huggingface that both filenames exist at the canonical url pattern; if not, fall back to `bartowski/Llama-3.2-1B-Instruct-GGUF` (existing alternate publisher for Llama-3.2 family — see `defaultModels.ts:290`'s Q6_K-3B entry).
- (Optional) `src/store/__tests__/defaultModels.test.ts` if such a test exists — extend.

**Approach**: Pure catalogue extension. No store / no UI change. The new ids feed Step R3's set.

**Verification**:
- `yarn test --findRelatedTests src/store/defaultModels.ts` (covers shape) and `yarn test --findRelatedTests src/store/onboarding/__tests__/recommendedPalModelSet.test.ts` (covers cross-reference).

**Commit preview**: `feat(models): add Llama-3.2-1B Q2_K + Q4_K_M entries`.

---

### Step R5 — Export 7 illustration assets from Figma into `src/assets/onboarding/`

**Implements**: WHAT §4b screen-table illustration column, Round-3 history K.

**Files** (new, under `src/assets/onboarding/`):
- `splash-mark.{svg,png,@2x,@3x}` — node `884:28349 > Frame 2608365` (112×112). Verify equality with screen-1 hero (`884:29310 Visual`) via Figma MCP; if identical, reuse one asset.
- `screen-2-illustration.svg` — node `884:32584 Visual` (~85×142 phone-with-pals).
- `screen-3-phone-card.svg` + `screen-3-cloud-card.svg` — extracted from node `885:29436 Cads` (export two visuals separately; "VS" divider is a presentational text rendered in `ComparisonCards` per R9, NOT a baked asset).
- `screen-4-shield.svg` — node `885:29601 Visual` (phone+shield group, Group 186).
- `screen-5-chip-icons/` directory containing 5 icons: `speech-bubble.svg` (smartchat), `code-brackets.svg` (coding), `books.svg` (education), `theater-masks.svg` (roleplay), `feather.svg` (creative_writing). 'else' chip has no icon (outlined). Source from node `890:29650 Options` (instances `890:29651..890:29656`).
- `pip-mascot.svg` — node `887:30085 Visuals` (66×62 smaller splash-mark variant).

**Approach**: Use Figma MCP `get_design_context` per node id (file `RZxDJea4t6jnBZrV4YBacF`, frames `884:28223` light + `3011:25220` dark for sanity), then asset-export via MCP. PNG @2x/@3x only needed for splash-mark (RN bundler requirement for raster); SVG is fine for the rest if the project already ships `react-native-svg` (it does — used in `src/components/Bubble`, `src/assets/icons`). Place under `src/assets/onboarding/index.ts` barrel for ergonomic import.

**Verification**:
- `ls src/assets/onboarding/*.svg | wc -l` ≥ 8 (or 9 if splash-mark and screen-1 hero differ).
- Manual visual diff against Figma frames at the next sim run.
- Implementer manually compares each exported asset against the source Figma node id at capture time before committing.

**Commit preview**: `chore(assets): add onboarding illustrations exported from Figma`.

---

### Step R6 — Add `HighlightText` internal primitive

**Implements**: WHAT §4g new row (HighlightText), §4h "Body-copy pill highlights", §1c glossary, §9p, I_OB12.

**Files** (new, NOT a DS export):
- `src/screens/OnboardingScreens/components/HighlightText.tsx` — props `{body: string; phrases: string[]}` (multi-phrase ready for screen 4's three-segment phrase). Walks `body`, splits on each phrase occurrence, wraps matched runs in a nested `<Text>` with `backgroundColor: theme.colors.accent.peach`, `borderRadius: theme.radius.xs`, and a horizontal padding pair. Uses `useTheme()`. Plain-body fallback when no phrase matches (§9p).
- `src/screens/OnboardingScreens/components/__tests__/HighlightText.test.tsx` — unit + snapshot. Cases: (a) single phrase wraps once; (b) multiple phrases each wrap; (c) translated body without the phrase renders plain; (d) light + dark snapshot via standard pattern (not the DS `runSnapshotMatrix` — screen-internal).

**Approach**: Internal primitive, NOT promoted to DS this slice. RN `<Text>` supports nested `<Text>` with its own backgroundColor — no `react-native-render-html` style hack needed. The split walker is a small reduce over `body.split(phrase)` repeated per phrase; order preserved by emitting segments alternately.

**Verification**:
- `yarn test --findRelatedTests src/screens/OnboardingScreens/components/HighlightText.tsx`.

**Commit preview**: `feat(onboarding): add HighlightText pill primitive`.

---

### Step R7 — Add `OnboardingAudioButton` internal primitive

**Implements**: WHAT §4b note 4, §4g audio row, §4i `onboarding-audio` testID, §8 D14, §9o.

**Files** (new):
- `src/screens/OnboardingScreens/components/OnboardingAudioButton.tsx` — wraps DS `IconButton` (size 40, icon `'headphones'`). Props: `{titleText: string; bodyText: string}`. On press: `AccessibilityInfo.announceForAccessibility(\`\${titleText} \${bodyText}\`)`. `testID='onboarding-audio'`. l10n `accessibilityLabel` via `onboarding.audio` key.
- `src/screens/OnboardingScreens/components/__tests__/OnboardingAudioButton.test.tsx` — mocks `AccessibilityInfo.announceForAccessibility`, asserts press fires with the concatenated string.

**Approach**: Side-effect only, stateless. Mirrors the DS IconButton shape; no new icon needed (Paper's MD icon set includes `headphones`).

**Verification**:
- `yarn test --findRelatedTests src/screens/OnboardingScreens/components/OnboardingAudioButton.tsx`.

**Commit preview**: `feat(onboarding): add OnboardingAudioButton`.

---

### Step R8 — Add `DeviceInfoChip` internal primitive

**Implements**: WHAT §4b screen-6 note 6, §9q.

**Files** (new):
- `src/screens/OnboardingScreens/components/DeviceInfoChip.tsx` — reads `getDeviceName()`, `getTotalMemorySync()`, `getFreeDiskStorage()` from `react-native-device-info` (`package.json:67` — verified). Composes `${deviceName} · ${ramGB} GB RAM · ${freeGB} GB free` with **independent per-field fallback**: if any single field is unavailable, skip it AND the `·` separator on its side (no orphan separator — §9q). Render via DS `Chip` (existing) with `mode='outlined'` + smartphone icon (`'cellphone'`).
- `src/screens/OnboardingScreens/components/__tests__/DeviceInfoChip.test.tsx` — mock `react-native-device-info`; cases: (a) all three fields → full string; (b) free-disk rejects → "name · ram"; (c) all three reject → empty chip (or icon-only).

**Approach**: One mount-time read (no live update — §4b note 6). Same mocking pattern as `BenchmarkRunnerScreen.tsx` (existing consumer of `react-native-device-info`).

**Verification**:
- `yarn test --findRelatedTests src/screens/OnboardingScreens/components/DeviceInfoChip.tsx`.

**Commit preview**: `feat(onboarding): add DeviceInfoChip`.

---

### Step R9 — Add `ComparisonCards` primitive for screen 3

**Implements**: WHAT §4b screen-3 row.

**Files** (new):
- `src/screens/OnboardingScreens/components/ComparisonCards.tsx` — two-card horizontal layout with a centred "VS" divider. Props `{leftAsset: ImageSource; leftLabel: string; rightAsset: ImageSource; rightLabel: string; vsLabel: string}`. Uses `theme.spacing.*`, `theme.radius.l` for card corners, `theme.colors.surface` for card bg, `theme.colors.outlineVariant` for border.
- `src/screens/OnboardingScreens/components/__tests__/ComparisonCards.test.tsx` — snapshot light + dark; asserts both labels render and VS divider is present between them.

**Approach**: Screen-3-only layout primitive; resists DS promotion (single consumer, very specific). Two `Image` (or `SvgUri`) children + a centred `<Text>`.

**Verification**:
- `yarn test --findRelatedTests src/screens/OnboardingScreens/components/ComparisonCards.tsx`.

**Commit preview**: `feat(onboarding): add ComparisonCards primitive for screen 3`.

---

### Step R10 — Retrofit `OnboardingScaffold` for Figma-faithful header + title

**Implements**: WHAT §3 state-machine table (Skip 1–4 / Audio 5+6), §4b table + notes 1–6, §4i, Round-3 history A,F,J.

**Files**:
- `src/screens/OnboardingScreens/components/OnboardingScaffold.tsx` — replace the existing wireframe scaffold to support:
  - Header right slot polymorphic: `topRight: 'skip' | 'audio' | 'none'` (Skip on 1–4, Audio on 5+6).
  - Header left slot polymorphic: `topLeft: 'back' | 'none'` (Back chevron lives in the top-left header on screen 5 only; bottom-bar Back on 2/3/4/6 — §4b note 4).
  - New `illustration?: ReactNode` prop (rendered between header and content).
  - `title` becomes `ReactNode` (allows nested italic accents per §4h "Italic title accents"); the per-screen wrappers compose `<Text>` with nested `<Text style={{fontStyle:'italic'}}>` for `*…*` spans.
  - Drop `eyebrow` (Figma has no eyebrow per Round-3 corrections; screens use `title` directly).
  - Pass-through `bottomBar?: ReactNode` — screen 5 passes `null` (no bottom bar, I_OB13); screens 2/3/4/6 pass an `OnboardingBottomBar` instance with `back` + `primary`.
  - Token-only: `theme.spacing.xxl` for the canvas y=54 zone offset (now possible via Round-2 `xxl=40` token).
- `src/screens/OnboardingScreens/components/__tests__/OnboardingScaffold.test.tsx` — extend coverage: Skip vs Audio top-right; Back-in-header vs Back-in-bottom-bar; illustration slot renders.

**Approach**: One scaffold, polymorphic slots. Keeps each screen file thin. Alternative — N scaffolds — rejected because the structural diff between screens is small (header slot + bottom bar presence).

**Verification**:
- `yarn typecheck && yarn test --findRelatedTests src/screens/OnboardingScreens/components/OnboardingScaffold.tsx`.

**Commit preview**: `refactor(onboarding): retrofit scaffold for Figma-faithful header + title`.

---

### Step R11 — Retrofit screens 1–4 (illustrations, italic titles, highlight pills, CTAs)

**Implements**: WHAT §4b table rows 1–4 + notes 1–2, §4h, §4j Round-3 keys, Round-3 history F,G,H,I,K.

**Files**:
- `src/screens/OnboardingScreens/Onboarding1Screen.tsx` — title `Meet your *pals*.` (Fraunces-Italic on `pals`), splash-mark hero illustration, Figma body verbatim (no highlight), CTA `Show me Around →` (`OnboardingArrowButton` if extracted, else inline arrow). topRight=`skip`, topLeft=`none`.
- `src/screens/OnboardingScreens/Onboarding2Screen.tsx` — title `*Anytime, Anywhere.*` (entire title italic), phone-with-pals illustration, body with `<HighlightText phrases={['No internet, no signal']}>`, CTA `Next →`. topRight=`skip`, topLeft=`back` (via bottom bar).
- `src/screens/OnboardingScreens/Onboarding3Screen.tsx` — title `*Smaller,* but yours.`, `<ComparisonCards>` illustration (phone vs cloud), body with `<HighlightText phrases={['quick and private']}>`, CTA `Got it →`. topRight=`skip`.
- `src/screens/OnboardingScreens/Onboarding4Screen.tsx` — title `Nothing *leaves* your phone.`, phone+shield illustration, body with `<HighlightText phrases={['No accounts. No cloud. No tracking.']}>`, CTA `Get Started →`. topRight=`skip`. Verify the existing test "promised" / "promiced" typo fix stays (Figma has the typo per task note).
- Each screen wires `setOnboardingStep(N)` on mount (unchanged from Round-1 skeleton).
- Optional new `src/screens/OnboardingScreens/components/OnboardingArrowButton.tsx` — thin wrapper around DS `Button` that appends a trailing arrow icon. If trivial enough, inline the arrow as a `<Text>` glyph after the label inside the existing DS `Button` `children`; do NOT change the DS API.

**Approach**: Each screen file is ~50–80 lines of layout. Title-italic uses nested `<Text>`; body-highlight uses `<HighlightText>` (R6). Bottom bar = `<OnboardingBottomBar back primary={...}/>` (existing internal from Round-1 skeleton).

**Verification**:
- `yarn typecheck && yarn lint`.
- Manual sim run: screens 1–4 visually match Figma frames `884:28224`, `884:32529`, `885:29142`, `885:29519` light + `3011:25220` dark band.

**Commit preview**: `feat(onboarding): retrofit screens 1-4 to Figma`.

---

### Step R12 — Screen 5 retrofit: chip-tap auto-advance, no bottom bar, header-slot Back + Audio

**Implements**: WHAT §3 row 5, §4b row 5 + notes 3–4, §4i, I_OB13, D7, §9l (deleted), Round-3 history A,C,J.

**Files**:
- `src/screens/OnboardingScreens/Onboarding5Screen.tsx`:
  - Scaffold props: `topRight={<OnboardingAudioButton ... />}`, `topLeft={<BackButton ... />}` (header-slot Back per §4b note 4), `bottomBar={null}`, `title` center-aligned, body verbatim from Figma.
  - `TopicChipGrid` retrofit: render 5 icon chips (smartchat/coding/education/roleplay/creative_writing) with per-Figma icons + sub-line + label, plus 1 outlined 'else' chip (no icon, "Looking for something else?"). On chip tap: `uiStore.setOnboardingTopic(key)` (or `null` for 'else'), then `navigation.navigate('Onboarding6')` in the same handler — single forward control (D7, I_OB13).
  - Remove the Round-1 "Continue" primary button; assert no `onboarding-primary` testID exists on screen 5 in the test.
- `src/screens/OnboardingScreens/components/TopicChipGrid.tsx` — rework: single-select, no toggle semantics. Pass `onSelect(key)` callback up to the screen.
- `src/screens/OnboardingScreens/useOnboardingHandlers.ts` — `onTopicTap(key)` is now `(key) => { uiStore.setOnboardingTopic(key); navigation.navigate('Onboarding6'); }`. Drop the old `onContinueFrom5` handler.

**Approach**: Screen 5 is the most contract-altered screen. The chip handler now both writes state AND navigates — collapsed into one call to match D7's "single forward control" invariant. Back chevron lives in the top-left header (the only screen where it does — §4b note 4).

**Verification**:
- `yarn typecheck`.
- Unit test in R15.

**Commit preview**: `refactor(onboarding): single-select chip-tap auto-advance on screen 5`.

---

### Step R13 — Screen 6 retrofit: italic Pip headline, mascot, device chip, quant cards, download CTA, no Skip

**Implements**: WHAT §3 row 6, §4b row 6 + notes 5–6, §4d, §4j Round-3 keys, §1b RECOMMENDED_PAL_MODEL_SET tier shape, I_OB14, D8, D16, Round-3 history B,D,E,L,M.

**Files**:
- `src/screens/OnboardingScreens/Onboarding6Screen.tsx`:
  - Scaffold: `topRight={<OnboardingAudioButton ... />}`, `topLeft={<BackButton ... />}` via bottom bar (Back chevron in bottom-bar left slot per §4b note 4 — screen 6 is in the "back lives in bottom bar" cohort with 2/3/4).
  - Hero: `<PipMascot/>` (66×62 PNG/SVG from R5) above the title.
  - Title: big italic `*Pip*` (Fraunces-Italic, `theme.typography.headlineH1`) — replaces the Round-1 wireframe's small caption + big "We found..." heading (history M inversion).
  - Body: verbatim from Figma — "We found perfect pal for you - a friendly everyday companion. Smart enough for most things, light enough for any phone."
  - `<DeviceInfoChip/>` from R8 directly under body.
  - `ModelRadioGroup` retrofit: render 3 cards from `RECOMMENDED_PAL_MODEL_SET` (R3 shape) in tier order — Quick / Balanced / Best. Each card shows:
    - Tier label (Quick/Balanced/Best) — from `onboarding.screen6.model.<tier>.title`.
    - Per-row computed subtitle `Llama 3.2 1B · Q<N> · <size>` (size from `defaultModels[].size` lookup); tok/s clause OPTIONAL per §9r — drop entirely (no synchronous estimator exists per WHAT §9r drift re-check).
    - Recommended pill badge on Balanced only (`entry.recommended === true`); peach-tinted card background (`theme.colors.accent.peach` with reduced opacity OR a paired `accent.peachSubtle` if Figma defines one — verify in R1).
    - testID `onboarding-pip-model-<modelId>`.
  - None pre-selected (D8). Primary "Download Pip (<size>) ⬇" disabled until selection.
  - Primary uses download icon (`'download'` Paper MD glyph) trailing the label. Size = `defaultModels.find(m => m.id === selectedModelId)?.size` rendered human-readable (MB / GB).
  - **No Skip control** (I_OB14). Pipeline-reviewer enforces.
- `src/screens/OnboardingScreens/components/ModelRadioGroup.tsx` — rework: input type changes from string-id array to `RecommendedPalModelEntry[]`. Reads from `RECOMMENDED_PAL_MODEL_SET` (R3) directly.
- Finish handler in `useOnboardingHandlers.ts` (unchanged logic from Round-1 skeleton, but signature follows R2's new `completeOnboarding({topic, modelId})`).

**Approach**: Most-changed screen. The card metadata is computed in JSX (not l10n) because `size` and `quant` come from the model object; titles ("Quick"/"Balanced"/"Best") are l10n. The Recommended badge is a small `<View>` with `accent.peach` background — NOT a `RadioSection` API change.

**Verification**:
- `yarn typecheck`.
- Unit test in R15.

**Commit preview**: `feat(onboarding): retrofit screen 6 to Pip headline + quant picker`.

---

### Step R14 — l10n key delta (rename topic keys, screen-6 keys, audio/highlight)

**Implements**: WHAT §4j Round-3 keys, Round-3 history H,I,N.

**Files**:
- `src/locales/en.json` — delta:
  - Rename topic keys: `onboarding.screen5.topic.{everyday,creative,learning,productivity}` → `{smartchat,creative_writing,education,else}` (keep `coding`, `roleplay`). String values per §4j table.
  - Add `onboarding.screen2.body.highlight = "No internet, no signal"`, `onboarding.screen3.body.highlight = "quick and private"`, `onboarding.screen4.body.highlight = "No accounts. No cloud. No tracking."`.
  - Add `onboarding.audio` (accessibility label), keep `onboarding.skip`, `onboarding.back`.
  - Update `onboarding.screen6.title = "Pip"`, body to the Figma-verbatim string.
  - Add `onboarding.screen6.model.quick.title|balanced.title|best.title` ("Quick", "Balanced", "Best"). Drop the old per-key model titles if they shipped under different keys in Round-1.
  - Add `onboarding.screen6.recommended.badge = "Recommended"`.
  - Update `onboarding.screen6.cta.template = "Download Pip ({{size}})"`.
  - Fill in bodies for screens 1–4 verbatim from Figma (no more empty bodies — Round-3 history H clears `designer-asks.md`).
  - Per-screen CTAs verbatim: `"Show me Around"`, `"Next"`, `"Got it"`, `"Get Started"` (arrow glyph rendered in JSX, not l10n).
- `workflows/stories/TASK-20260526-1731/designer-asks.md` — trim to a single entry: Audio button announcement intent (D14). All other entries removed (bodies filled per §4j Round-3).
- `src/components/ui/__tests__/snapshotMatrix.tsx` / `src/locales/__tests__/*` — re-run; no API change expected, only string additions.

**Approach**: Strict l10n key delta. Weblate picks up en.json on next sync (translators pick up Round-3 keys naturally — old keys are removed and surface as untranslated).

**Translator heads-up (PR body / R21 handshake)**: Note in the PR body that this change removes old topic keys (`everyday`, `creative`, `learning`, `productivity`) and old per-model l10n keys from `en.json`; Weblate translators will see them surface as untranslated until they re-translate the new keys.

**Verification**:
- `node scripts/validate-l10n.js` passes.
- `yarn test --findRelatedTests src/locales/`.

**Commit preview**: `feat(l10n): add Figma-faithful onboarding keys; rename topic keys`.

---

### Step R15 — Align store/handler tests to Round-3 contract

**Implements**: WHAT §5, §6 A,C,F,G,G'' (G' deleted), §9l deletion, Round-3 history C.

**Files**:
- `src/store/__tests__/UIStore.test.ts` — already partially updated in R2; final pass to remove multi-select assertions and add hydrate-migration coverage.
- `src/screens/OnboardingScreens/__tests__/useOnboardingHandlers.test.ts` — replace multi-select chip handler tests with single-select tap-advance; remove the deleted Scenario G' "screen 6 Skip" test; assert finish-handler passes `topic: TopicKey | null` to `completeOnboarding`.
- `src/store/__tests__/PalStore.test.ts` — no contract change (R-step PalStore unchanged); only verify the existing `defaultModel`-preservation test still passes after R4 catalogue additions.

**Approach**: Test-only follow-through; no production-code changes here. Catches contract drift between R2 / R12 / R13 wiring and the unit-test layer.

**Verification**:
- `yarn test --findRelatedTests src/store src/screens/OnboardingScreens`.

**Commit preview**: `test(onboarding): align store/handler tests to single-select contract`.

---

### Step R16 — E2E spec + page-object alignment

**Implements**: WHAT §6.A, C, G, G'' (G' deleted), Round-3 history A, B, C, §4i, §3 state-table.

**Files**:
- `e2e/specs/features/onboarding.spec.ts`:
  - Add screen-1 Skip presence assertion (Round-3 history A — Skip now on screens 1–4).
  - Remove the "Skip on screen 6" test (G' deletion — I_OB14).
  - Update topic-tap behavior: tap a chip → assert direct landing on Onboarding6 (no Continue button visible on screen 5 — single forward control per I_OB13).
  - Add Audio button visibility assertions on screens 5 + 6 (`onboarding-audio` testID).
  - Update §6.G test to verify `Download Pip (<size>) ⬇` label updates when a quant radio is tapped.
  - Verify the screen-6 title is the big italic "Pip" (the test asserts `accessibilityLabel` or visible text; no Round-1 "We found..." string anywhere on screen 6).
- `e2e/pages/OnboardingPage.ts`:
  - Update `tapTopic(key)`: after tap, `await chat.waitForReady()` (or the equivalent page-readiness wait used elsewhere) because the tap auto-advances to Onboarding6 — there is no Continue press.
  - Add `audio` accessor for the headphones button.
  - Update `topicChip(key)` to use the new TopicKey values.
  - Remove any `screen6.skip` accessor (no Skip on 6).

**Approach**: E2E follows the contract changes mechanically. The relaunch primitive from Round-2 (driver.terminateApp/activateApp) is unchanged.

**Verification**:
- `yarn e2e:ios --spec onboarding --skip-build` on local sim (target spec only).
- `yarn e2e:android --spec onboarding --skip-build` on local emu.

**Commit preview**: `test(e2e): align onboarding spec to Figma-faithful contract`.

---

### Step R17 — Repo-wide gates

**Implements**: lint / typecheck / Jest invariants.

**Verification**:
- `yarn lint && yarn typecheck && yarn test --silent`.
- Expect 0 errors; snapshot updates for new components (R6/R7/R8/R9, and updated R10/R12/R13 snapshots if the existing scaffold/group snapshots cover them).
- Review and commit snapshot deltas in this single repo-gate commit.

**Commit preview**: `chore: lint/typecheck/jest gates green`.

---

### Step R18 — Dev-team paired-edit: add `accent.peach` to `theming.md` §1a Color axis

**Implements**: WHAT I_OB12 / D15 / §10 cleanup #2 / I_UI8 cross-cite handshake.

**Files** (dev-team repo, NOT worktree):
- `context/architecture/theming.md` — locate the Color axis enumeration in §1a and append `accent.peach` (or a `Accent` sub-namespace if the existing axis structure has one). One-line addition mirroring the `spacing.xxl` precedent in `a448d3f`.

**Approach**: Single-line edit. The cross-cite handshake (Step R21) wires the SHA into the app PR and the app PR URL into the commit message.

**Verification**:
- `git diff context/architecture/theming.md` shows exactly one binding-name addition.
- `grep -n "accent.peach" context/architecture/theming.md` returns 1+ hit.

**Commit preview** (dev-team): `docs(architecture): add accent.peach to Color axis`.

---

### Step R19 — Dev-team flow-doc absorb: `onboarding.md` Round-3 update + trim `designer-asks.md`

**Implements**: WHAT §10 cleanup #1 (Round-3 absorb on the promoted flow doc), §10 cleanup-#1 designer-asks trim.

**Files** (dev-team repo):
- `context/architecture/onboarding.md` — rewrite to reflect Round-3 contract:
  - Skip presence: screens 1–4 only; Audio on 5+6.
  - TopicKey union: `smartchat / coding / education / roleplay / creative_writing / else`.
  - `selectedTopic: TopicKey | null` (single-select).
  - `setOnboardingTopic` method name.
  - `RECOMMENDED_PAL_MODEL_SET` as quants of one base model (3 tiers).
  - Audio button + HighlightText + DeviceInfoChip rows in §4g.
  - I_OB13 / I_OB14 invariants.
  - Screen-6 title = big italic Pip, body = "We found..." (inverted).
  - All `(P)` markers stay `(C)` (flow doc is current-state); `(D)` markers tagged with Round number where they originated.
  - Zero `(?)` markers (assert via grep).
- `workflows/stories/TASK-20260526-1731/designer-asks.md` (in worktree — but the trim is best done by the dev-team-absorb commit per WHAT §10 cleanup #1): reduce to a single entry — Audio button announcement intent (D14). Delete the empty-body entries.

**Approach**: This is the flow-doc that was promoted in `a448d3f` and is now stale relative to the Round-3 WHAT. Absorb the corrections row-by-row from the Round-3 history table (A–N) in the WHAT.

**Verification**:
- `grep -E "\(P\)|\(\?\)" context/architecture/onboarding.md` returns no matches.
- `wc -l workflows/stories/TASK-20260526-1731/designer-asks.md` ≤ ~20 lines (single entry).

**Commit preview** (dev-team): `docs(architecture): absorb FOU-116 Round-3 corrections`.

---

### Step R20 — Dev-team rollout log: FOU-112 rollout entry for Round-3

**Implements**: rollout-doc convention (paired-PR tracking).

**Files** (dev-team repo):
- `context/redesign/FOU-112-rollout.md` — add a Round-3 line to the FOU-116 entry citing PR #747 and the dev-team SHAs (R18 + R19).

**Approach**: Mechanical bookkeeping; the same pattern earlier rollout entries use.

**Verification**:
- Diff shows one or two added lines under the FOU-116 row.

**Commit preview** (dev-team): `docs(rollout): note FOU-116 Round-3 against PR #747`.

---

### Step R21 — Cross-cite handshake (I_UI8 mechanism)

**Implements**: WHAT I_OB12 / D15 / §10 cleanup #2 / I_UI8.

**Files / artifacts** (cross-repo):
- PR #747 description (app) — append a line `Architecture absorbed in pocketpal-dev-team commits <SHA-R18>, <SHA-R19>, <SHA-R20>`.
- Dev-team commit messages (R18 + R19): cite `paired with app PR #747` in the body.

**Approach**: Same mechanism as the Round-2 spacing-xxl handshake (`a448d3f`). No code change; PR-description + commit-message edits only. Pipeline-reviewer enforces both citations before re-approving the draft.

**Verification**:
- `gh pr view 747 --json body | grep "pocketpal-dev-team commit"`.
- `cd dev-team-repo && git log -1 --format=%B <SHA-R18>` contains `app PR #747`.

**Commit preview**: (no code commit; PR-description + commit-message edits across both repos).

---

## Round-3 Affected Files (delta on top of Rounds 1–2)

### App repo

| Path | Round-3 change kind | Step |
| --- | --- | --- |
| `src/theme/tokens/colors.ts` | edit (add `accent.peach` light + dark) | R1 |
| `src/theme/tokens/types.ts` | edit (widen `TokenColors.accent.peach`) | R1 |
| `src/theme/tokens/__tests__/colors.test.ts` | edit | R1 |
| `src/store/UIStore.ts` | edit (TopicKey rename + single-select + setter rename + hydrate migration) | R2 |
| `src/store/onboarding/types.ts` (if present) | edit (TopicKey union) | R2 |
| `src/store/__tests__/UIStore.test.ts` | edit | R2, R15 |
| `src/screens/OnboardingScreens/useOnboardingHandlers.ts` | edit (single-select handler + screen-5 auto-advance) | R2, R12 |
| `src/screens/OnboardingScreens/__tests__/useOnboardingHandlers.test.ts` | edit | R15 |
| `src/store/onboarding/recommendedPalModelSet.ts` | rewrite (typed tier shape; 3 quants of Llama-3.2-1B) | R3 |
| `src/store/onboarding/__tests__/recommendedPalModelSet.test.ts` | edit | R3 |
| `src/store/defaultModels.ts` | edit (add Q2_K + Q4_K_M entries) | R4 |
| `src/assets/onboarding/*` | new (7+ illustration assets + barrel) | R5 |
| `src/screens/OnboardingScreens/components/HighlightText.tsx` (+ test) | new | R6 |
| `src/screens/OnboardingScreens/components/OnboardingAudioButton.tsx` (+ test) | new | R7 |
| `src/screens/OnboardingScreens/components/DeviceInfoChip.tsx` (+ test) | new | R8 |
| `src/screens/OnboardingScreens/components/ComparisonCards.tsx` (+ test) | new | R9 |
| `src/screens/OnboardingScreens/components/OnboardingScaffold.tsx` (+ test) | edit | R10 |
| `src/screens/OnboardingScreens/Onboarding{1..4}Screen.tsx` | edit (illustration + italic title + highlight + CTA + Skip) | R11 |
| `src/screens/OnboardingScreens/components/OnboardingArrowButton.tsx` | new (optional) | R11 |
| `src/screens/OnboardingScreens/Onboarding5Screen.tsx` | edit (header-slot Back+Audio, no bottom bar, chip-tap auto-advance) | R12 |
| `src/screens/OnboardingScreens/components/TopicChipGrid.tsx` | edit (single-select, icons, sub-lines) | R12 |
| `src/screens/OnboardingScreens/Onboarding6Screen.tsx` | edit (Pip headline + mascot + DeviceInfoChip + quant cards + download CTA, no Skip) | R13 |
| `src/screens/OnboardingScreens/components/ModelRadioGroup.tsx` | edit (tier shape; Recommended badge; peach tint) | R13 |
| `src/locales/en.json` | edit (Round-3 key delta) | R14 |
| `e2e/specs/features/onboarding.spec.ts` | edit (drop G', add Audio, single-select) | R16 |
| `e2e/pages/OnboardingPage.ts` | edit (selectors + auto-advance wait) | R16 |
| `workflows/stories/TASK-20260526-1731/designer-asks.md` | trim (down to 1 entry — Audio intent) | R19 |
| Snapshot files under affected `__tests__/__snapshots__` | edit (commit deltas) | R17 |

### Dev-team repo

| Path | Round-3 change kind | Step |
| --- | --- | --- |
| `context/architecture/theming.md` | edit (Color axis adds `accent.peach`) | R18 |
| `context/architecture/onboarding.md` | edit (Round-3 absorb — A–N) | R19 |
| `context/redesign/FOU-112-rollout.md` | edit (Round-3 note) | R20 |

---

## Round-3 Testable-Contract Coverage (delta)

| Contract item (WHAT §6 + Round-3 history) | Verified by |
| --- | --- |
| Round-3 history A — Skip on screens 1–4; Audio on 5+6 | E2E test (R16) asserts `onboarding-skip` visible on screens 1–4 and absent on 5+6; `onboarding-audio` visible on 5+6 |
| Round-3 history B — Scenario G' deleted (no Skip on screen 6) | E2E spec drops the corresponding test (R16); pipeline-reviewer enforces I_OB14 |
| Round-3 history C — single-select TopicKey + auto-advance | Unit (R15) + E2E (R16) — tapping a chip transitions directly to Onboarding6 with no Continue |
| Round-3 history D — 3 quants of one base model + Recommended badge | Unit (R3) — `RECOMMENDED_PAL_MODEL_SET` tier shape + Recommended invariant; visual diff on R13 sim run |
| Round-3 history E — Audio button announces title+body | Unit (R7) — `AccessibilityInfo.announceForAccessibility` mock asserts concatenation |
| Round-3 history F — italic title accents | Visual diff per screen on R11 sim run + dark-mode parity (§6.E) |
| Round-3 history G — peach pill highlights | Unit (R6) — phrase wrap + plain-body fallback; visual diff on R11 |
| Round-3 history H — bodies filled, no empty l10n slots | `node scripts/validate-l10n.js` in R17; `designer-asks.md` trimmed to 1 entry (R19) |
| Round-3 history I — per-screen CTAs verbatim with trailing arrow | R11 visual diff |
| Round-3 history J — Back chevron header-slot on 5; bottom-bar on 2/3/4/6 | E2E (R16) asserts `onboarding-back` present in both header and bottom-bar slots; visual diff on R10/R11 |
| Round-3 history K — 7 illustration assets bundled | R5 ls verification + visual diff |
| Round-3 history L — DeviceInfoChip with independent per-field fallback | Unit (R8) — mock `react-native-device-info` |
| Round-3 history M — screen-6 title hierarchy inverted | R13 visual diff + R16 E2E text-presence assertion |
| Round-3 history N — `designer-asks.md` ≤ 1 entry | R19 verification (`wc -l`) |
| I_OB12 — `accent.peach` paired-edit handshake | R21 — both citations present (app PR + dev-team commit) |
| I_OB13 — screen-5 single forward control (no primary) | E2E (R16) asserts `onboarding-primary` absent on screen 5 |
| I_OB14 — no Skip on screen 6 | E2E (R16) asserts `onboarding-skip` absent on screen 6 |

---

## Visual Confirmation (Round 3)

Round-2 captured screenshots are stale (they show the wireframe). After R11–R13 land, **the user prefers their own visual diff against Figma** (per task instructions). The implementer SHOULD still drop fresh light + dark captures into `workflows/stories/TASK-20260526-1731/screenshots/` for the PR record, but the user is the source of truth on the verdict — no AutomationBridge auto-capture, no critic call between the captures landing and user sign-off.

Frames to compare per screen (light / dark):
- Splash → `884:28349` / `3011:25220`-band splash
- Screen 1 → `884:28224` / dark equivalent
- Screen 2 → `884:32529` / dark equivalent
- Screen 3 → `885:29142` / dark equivalent
- Screen 4 → `885:29519` / dark equivalent
- Screen 5 → `884:28282` / dark equivalent
- Screen 6 → `887:30011` / dark equivalent

---

## Review History — Round 3 entry

### Round 3 — plan-critic, pending (2026-05-27)

Round-3 is a Figma-faithful retrofit on top of the Round-1/2 skeleton that shipped in PR #747. WHAT was rewritten across 14 corrections (Round-3 history A–N) and re-LGTM'd at Round 3.5. HOW absorbs the deltas into 21 atomic Round-3 steps (R1–R21) layered on the existing skeleton:

- Tokens + contract (R1–R4): `accent.peach`, TopicKey rename, single-select, RECOMMENDED_PAL_MODEL_SET → quants of Llama-3.2-1B (Q2_K + Q4_K_M added to `defaultModels`).
- Assets + primitives (R5–R9): 7 Figma exports, `HighlightText`, `OnboardingAudioButton`, `DeviceInfoChip`, `ComparisonCards`.
- Scaffold + screens (R10–R13): polymorphic header slots (Skip vs Audio, header-slot Back), italic titles, illustration slot, screen 5 chip-tap auto-advance, screen 6 Pip headline + quant cards + download CTA.
- Copy + tests (R14–R17): l10n key delta, store/handler/E2E alignment, repo gates.
- Dev-team absorb + handshake (R18–R21): `theming.md` `accent.peach` paired-edit, `onboarding.md` Round-3 absorb, `designer-asks.md` trim, rollout note, I_UI8 cross-cite handshake.

Every Round-3 step traces to a WHAT §X reference and ships as its own commit. No design content invented; deferred items still deferred (§5 #1, #4; §10 #3, #4). The Round-2 progress-tracking table is preserved so the load-bearing skeleton remains visible. Visual diff verdict belongs to the user (per task instructions).

Routing back to plan-critic.


### Round 3.5 — plan-critic, HAS_CONCERNS (2026-05-27)

| # | Severity | Summary | Resolution |
| - | -------- | ------- | ---------- |
| BLOCKER 1 | BLOCKER | R2 over-applied the rename to the **persisted** snapshot field (`onboardingTopicsSnapshot: TopicKey[]` → `onboardingTopicSnapshot: TopicKey \| null`) and added a hydrate-time migration. WHAT §1a is explicit that the persisted field stays as `TopicKey[]` ("kept as an array to leave headroom for FOU-117 multi-tag work"); WHAT §5 line 492 says the completion writer "derives the snapshot from `topic` (`topic === null` ⇒ `[]`; otherwise `[topic]`)". | **FIXED**. Step R2 rewritten: scope reduced to (a) ephemeral state rename `selectedTopics: TopicKey[]` → `selectedTopic: TopicKey \| null`, (b) setter rename `toggleOnboardingTopic` → `setOnboardingTopic(key: TopicKey \| null)`, (c) `TopicKey` union member rename. The persisted `onboardingTopicsSnapshot: TopicKey[]` is untouched — no field rename, no `makePersistable.properties` edit, no hydrate-time migration. Completion writer derives `[topic]` or `[]` from the new scalar and writes that array into the unchanged persisted field. UIStore.test.ts loses the hydrate-migration test; gains a snapshot-derivation assertion (`['smartchat']` for a non-null pick, `[]` for `null`). Step heading + commit-preview both updated to make the unchanged-persistence scope explicit. |
| CONCERN 1 | CONCERN | R14 lacked a one-liner about translator impact when old topic keys + old per-model keys disappear from `en.json`. | **FIXED**. R14 Approach gained a "Translator heads-up (PR body / R21 handshake)" paragraph stating that removed keys surface as untranslated on Weblate until re-translated. The R21 cross-cite step already touches the PR body — that is where the heads-up lands. |
| CONCERN 2 | CONCERN | R5 asset verification was implicit ("Manual visual diff at next sim run"); no explicit pre-commit check that each exported asset matches its source Figma node id. | **FIXED**. R5 Verification gained one line: "Implementer manually compares each exported asset against the source Figma node id at capture time before committing." Same shape as the per-screen visual-diff line above it. |
| SUGGESTION 1 | SUGGESTION | R17 unified lint+typecheck+Jest gate could be split into per-step snapshot commits for finer atomicity. | **DEFERRED**. User wants speed; per-step snapshot commits would inflate the commit count without changing the verification surface (the snapshot diff is one commit anyway). R17 stays as one gate. |

### Revision summary for round-3.5 → implementer

The single BLOCKER was a mechanical fact-fix: I had over-applied the topic rename to the persisted field even though WHAT §1a / §5 explicitly keep it as `TopicKey[]` for FOU-117 headroom. The persisted shape is now unchanged; only the ephemeral state and setter change. No migration code, no `makePersistable.properties` churn.

The two CONCERNs are surface tightenings (translator note in PR body via R21; explicit Figma-node compare line in R5). SUGGESTION 1 is deferred as a no-op.

No design content invented. No invariants added. No deferred items silently landed. Round 3.5 changes touch 3 step bodies (R2, R5, R14) and add this history entry — nothing else.

Routing to implementer.
