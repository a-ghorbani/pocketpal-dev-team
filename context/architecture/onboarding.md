# Onboarding

## Purpose

The first-launch flow: brand splash, four intro screens, a topic pick, and a pal + model pick, plus the persisted completion gate that switches `App.tsx` from the onboarding stack to the main navigator (`app-shell.md`). Tokens and DS components, `Stepper` included: `theming.md`. What a Pal is: `pals-and-talents.md`. How a registered HF model downloads: `model-loading.md`.

Design source: Figma file `RZxDJea4t6jnBZrV4YBacF`, Onboarding section `884:28223` (light) / `3011:25220` (dark).

## Code map

| Path | Role |
| --- | --- |
| `App.tsx` (`SwitchPoint`) | Reads `uiStore.hasCompletedOnboarding` and renders `OnboardingStack` or the Drawer |
| `src/store/UIStore.ts` | Gate + topic snapshot (persisted), `onboardingState` (in memory), `setOnboarding*`, `completeOnboarding`, `replayOnboarding`, `resetOnboarding` |
| `src/store/onboarding/types.ts` | `TopicKey`, `OnboardingState`, `INITIAL_ONBOARDING_STATE` |
| `src/store/onboarding/onboardingPals.ts` | The five pals (Pip, Codie, Sage, Echo, Muse), each with a quick / balanced / best tier; `TOPIC_TO_PAL`, `resolvePalForTopic`, `entryId` |
| `src/screens/OnboardingScreens/OnboardingStack.tsx` | `@react-navigation/stack` navigator (7 routes, names in `ROUTES.ONBOARDING`) with the persistent top chrome overlaid |
| `src/screens/OnboardingScreens/useOnboardingHandlers.ts` | Per-screen `next` / `goBack` / `selectTopic` / `finish` |
| `src/screens/OnboardingScreens/components/OnboardingTopChrome/` | Stepper + Skip overlay; step comes from the active route name |
| `src/screens/OnboardingScreens/SplashScreen/`, `Onboarding{1..6}Screen` | The screens |
| `src/screens/OnboardingScreens/components/` | Screen-local parts: scaffold, bottom bar, topic chip grid, model radio group, device chip, italic/highlight text |
| `src/components/ui/Stepper/` | DS stepper |
| `src/store/ModelStore.ts` (`registerOnboardingPalModel`) | Builds an HF model/file pair from an entry and delegates to `addHFModel` |
| `src/store/PalStore.ts` (`initializePipPal`) | Seeds Pip at boot |
| `src/screens/AboutScreen/AboutScreen.tsx` | "Show intro again" calls `uiStore.replayOnboarding()` |
| `src/__automation__/adapters/OnboardingBypass.tsx`, `babel.config.js` | E2E bypass and its build flag |

## How it works

1. `SwitchPoint`, an observer inside the single provider tree, renders `OnboardingStack` until the flag flips, then the Drawer. Only the navigator subtree remounts.
2. `SplashScreen` waits `SPLASH_MIN_DWELL_MS` (600 ms), then `navigation.replace(STEP_1)`.
3. Screens 1–4: the primary button calls `next()` (a fixed step→route map). Every screen calls `useOnboardingHandlers(step)`, which writes `currentStep` on mount.
4. Screen 5: tapping a `TopicChipGrid` chip calls `selectTopic` (`setOnboardingTopic` + navigate to step 6). No primary button, only a back-only bottom bar.
5. Screen 6 resolves the pal with `resolvePalForTopic(selectedTopic)` and lists its three tiers, pre-selecting the `recommended` entry when the selection isn't one of this pal's. The CTA reads "Download <pal> (<size>)", or "Use <pal>" when already downloaded.
6. `finish()`, in order: register the entry to get a `Model`; update the existing local pal of that name, or `createPal` with the def's prompt, colour and greeting; `completeOnboarding({topic, modelId})`; start `modelStore.checkSpaceAndDownload` without awaiting.
7. Skip lives in the top chrome on steps 1–6 ("Skip for now" on 6): `completeOnboarding({topic: selectedTopic, modelId: null})`, no pal or model.
8. The gate flips; `SwitchPoint` mounts the Drawer on its first route (Chat).

## Contracts and invariants

- **Gate writers:** `completeOnboarding` (finish, top-chrome Skip, E2E bypass), `replayOnboarding` (About), `resetOnboarding` (dev/E2E only, no production caller). See `UIStore.ts:210-243`.
- **Persistence:** only `hasCompletedOnboarding` and `onboardingTopicsSnapshot` are persisted (`UIStore.ts:123-124`). `onboardingState` is in memory, so a process kill mid-flow restarts at the splash.
- **Snapshot shape:** always a `TopicKey[]` of length 0 or 1, derived from the scalar topic. Replay keeps it and the next completion overwrites it. It has no reader yet.
- **Who writes what:** `completeOnboarding` writes only UIStore; pal and model effects belong to `finish`, ordered model → pal → gate → download. `finish` has `try/finally` but no `catch`, so a throw in registration or pal creation leaves the user on screen 6.
- **No double finish:** a ref blocks re-entry into `finish`, and `isFinishing` disables the CTA.
- **Pal identity:** `finish` finds an existing pal by `name === palDef.name && source === 'local'`. `initializePipPal` seeds Pip using the same key. Pip is defined twice, in `PalStore.initializePipPal` and `PAL_PIP`, and the two names must agree.
- **Model id:** `entryId` = `repo/filename`, which equals the `Model.id` that `addHFModel` produces. The screen-6 selection, the downloaded check and the e2e testID all key on it.
- **Registration:** every entry, preset repos included, goes through `registerOnboardingPalModel` → `addHFModel` (idempotent by id, so shared entries collapse), only in `finish`; Skip adds none. `siblings: []` means no projection model.
- **Top chrome step:** comes from the route name (`chromeStepFromRouteName`), not from `onboardingState.currentStep`, which nothing reads.
- **testIDs** (resolved by `e2e/pages/OnboardingPage.ts`, except `onboarding-device-chip`; extend, never rename):

  | testID | Where |
  | --- | --- |
  | `onboarding-splash` | splash |
  | `onboarding-screen-<N>` | each screen |
  | `onboarding-primary` | absent on 5 |
  | `onboarding-back` | 2–6 |
  | `onboarding-skip` | 1–6 |
  | `onboarding-topic-<key>` | topic chips |
  | `onboarding-pip-model-<entryId>` | every pal's tiers (the "pip" in the name is historical) |
  | `onboarding-device-chip` | device info chip |
  | `ui-stepper`, `ui-stepper-dot-<i>` | stepper |

## Traps and decisions

- **Upgraders see onboarding once.** The gate defaults to `false`, and an older build's persisted store has no key. Intended.
- **Back behaviour.** The stack is JS with `gestureEnabled: false`. The splash is *replaced*, so Onboarding1 is the root, and there is no `BackHandler`: Android back on screen 1 falls through to the OS; on 2–6 it pops.
- **The chrome is one overlay above the navigator,** so the Stepper and Skip stay put while bodies slide. A new route needs a case in `chromeStepFromRouteName`, or the chrome hides on it.
- **There are two skip paths.** `OnboardingTopChrome.onSkip` is the live one. `useOnboardingHandlers.skip` is returned but no screen uses it. Keep them in sync or delete the dead one.
- **The `else` chip is display-only** (a `View`, not a `Pressable`). The no-preference path is Skip. `resolvePalForTopic(null)` and `else` both give Pip.
- **The recommended tier is always Balanced, on every device.** There is no device-aware tier picker yet.
- **Replay** (About) unmounts the whole Drawer, losing its state. A second finish updates the existing pal, not a duplicate.
- **Renamed Pip.** `initializePipPal` looks up by the name `Pip`, so a user-renamed Pip is seeded again on the next launch.
- **Finish neither activates the pal nor loads the model.** The user lands on Chat, download in flight.
- **Deep links during onboarding** find no route. See `app-shell.md`, Traps and decisions.
- **Headline fonts.** `NON_LATIN_LOCALES` (`src/theme/tokens/typography.ts`) switch Fraunces to Inter by glyph coverage, not script; `pl` is listed because the bundled Fraunces lacks Latin Extended-A. Onboarding is the main Fraunces surface; its Polish screen-4 title is the canonical check.
- **Mirroring follows the device locale** (`I18nManager.isRTL`, read by `Stepper`, `OnboardingScaffold` and `OnboardingTopChrome`), not `uiStore.language`: choosing `he` in the app swaps strings and fonts but doesn't mirror.
- **Mid-flow state is not persisted** on purpose: the flow is short; restarting beats resuming.
- **E2E bypass.** `babel.config.js` sets `__E2E_SKIP_ONBOARDING__` in every e2e build unless `E2E_SKIP_ONBOARDING=false`; `OnboardingBypass` then completes onboarding after mount. `e2e/scripts/run-e2e.ts` builds a separate binary for `--spec onboarding`, so don't batch it with other specs.

## Verification

- **Unit tests:** `src/store/__tests__/UIStore.test.ts` (onboarding block), `src/store/__tests__/ModelStore.registerOnboardingPalModel.test.ts`, `src/store/onboarding/__tests__/onboardingPals.test.ts`, `src/screens/OnboardingScreens/{__tests__,Onboarding6Screen/__tests__,components/__tests__}/`, `src/__automation__/adapters/__tests__/OnboardingBypass.test.tsx`, `src/components/ui/Stepper/__tests__/`, `__tests__/App.test.tsx`.
- **E2E:** `e2e/specs/features/onboarding.spec.ts` with `e2e/pages/OnboardingPage.ts`; from `e2e/`, `yarn e2e:android --spec onboarding`. The spec's header comment says screens 5–6 have no Skip; its assertions (correctly) expect Skip.
- **By hand:** fresh install or About → "Show intro again". Check dark mode, an RTL device locale (mirroring) and `pl` (Inter fallback). Finish with a non-Pip topic and confirm the pal and its download appear.
