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
- **Architecture doc(s) being updated**: NEW `./context/architecture/onboarding.md` (promote WHAT delta) AND single-line edit to `./context/architecture/theming.md` §1a (`xxl=40` added to the Spacing axis — D11 / I_OB11 paired-edit handshake).
- **Status**: draft (round-2 revision applied)

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
