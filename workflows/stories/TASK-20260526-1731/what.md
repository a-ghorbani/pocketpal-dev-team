# FOU-116 Onboarding flow — WHAT (delta)

Story: TASK-20260526-1731 — Phase 3a slice of FOU-112 redesign rollout.

**This is the first FOU-112 slice that produces real screens against the FOU-114 token + FOU-115 DS layer.** It is a greenfield flow: the app has no onboarding today. On PR merge the contents of this delta are promoted to `context/architecture/onboarding.md` (a new flow doc) in the same PR that lands the code.

Consumer references only (do NOT modify in this slice except where I_OB11 / D11 explicitly amends `theming.md` §1a):
- `context/architecture/theming.md` — token + DS surface (FOU-114 / FOU-115). One paired line edit required (spacing.xxl); see D11.
- `context/architecture/chat-flow.md` — destination Chat session model after onboarding completes.
- `context/architecture/pals-and-talents.md` — `Pal` data model used by the seeded recommended pal.

Canonical inputs (LOCKED, per `context/redesign/FOU-112-rollout.md` §1):
- Figma file `RZxDJea4t6jnBZrV4YBacF`, page `0:1` "App design".
- Light frames: `884:28223` (Onboarding section, 6 screens + Splash + Homepage-first-time).
- Dark frames: `3011:25220` (Onboarding 7–12 = light 1–6 dark renders).
- Variable defs read for the section (verified 2026-05-26 via Figma MCP `get_variable_defs`): every value used below resolves to a token name already present in `theme.colors.*`, `theme.typography.*`, `theme.spacing.*`, `theme.radius.*`, `theme.stroke.*` (with the single exception `Spacing/XXL=40` — see I_OB11 / D11).

---

## Conventions

- **(C)** = current behaviour, documented from code (the FOU-114 / FOU-115 surface this story builds on).
- **(P)** = proposal, this story.
- **(D)** = decision, this story.
- (No **(?)** entries — all clarifications resolved at intent stage or below.)

---

## 0. Scope & non-scope

In scope (P):

- Onboarding flow as a **new top-level navigator branch** rendered as an alternative to the existing Drawer **inside** `<App/>` (below all providers — see §4a), gated on a single persisted `uiStore.hasCompletedOnboarding` flag. On first launch the user sees Onboarding; on every subsequent launch the user sees the Drawer (today's app, unchanged).
- 6 onboarding screens implemented from canonical frames `884:28223` (light) / `3011:25220` (dark), parity verified per slice.
- Splash screen `884:28349` — the **post-hydration brand splash** that runs from `<PaperProvider>` mount until the Onboarding-1 transition. Distinct from the FOU-114 hydration hold (which is pre-`<PaperProvider>` and stays neutral; theming.md §4c #4 / I10).
- "First-time Homepage" `888:34414` is the **destination state** at end of onboarding: a Homepage shell with `Pip` selected, an empty "previous chats" list, and the Chat-with-your-pals tile strip. Functional Homepage proper is FOU-117; this slice ships only the empty-state surface plus its first-time copy. Any home-page behaviour beyond initial empty render (search, chat resume, model load triggers) is explicitly NOT in this slice.
- A new seeded system pal "Pip" (the "perfect pal" the recommended-pal screen names — Figma `887:30011`). Seeded by the same mechanism as `Lookie` (`PalStore.initialize`); ships with a small default model reference (no auto-download — see §9d).
- One new DS component: `Stepper` (the 4-dot progress indicator used on screens 1–4 — Figma `896:29130`-band). Promoted into the DS layer in this slice because it has zero non-onboarding consumers but is bounded, presentational, and meets the §4g rules of `context/architecture/theming.md`.
- E2E `onboarding` spec covering the happy path + skip + back + topic-chip selection + recommended-pal model picker.
- testID surface frozen here (§4l).
- RTL (`he`, `fa`) layout + non-Latin/CJK typography fallback verified on at least one screen with non-trivial content alignment (screen 5 chip grid, screen 6 radio-section list).
- Light + dark parity verified per screen.
- New l10n keys (English only — Weblate picks up translations later) under `onboarding.*`.

Explicitly NOT in scope:

- Functional Homepage (search, recent chats, model loader, FAB) → FOU-117.
- Functional Chat screen swap → FOU-117.
- Migration of users who already have the app — there is no migration; on first install of the build with this slice, the user sees onboarding. On second-and-later launches the persisted `hasCompletedOnboarding === true` skips the flow.
- Server-side user accounts, sign-in, Palshub auth — never present in onboarding (Figma confirms; no auth surface anywhere in screens 1–6).
- Model download UI / progress UI inside onboarding. Screen 6 selects a model for `Pip` and **enqueues** the download via the existing `modelStore.checkSpaceAndDownload(modelId)` API; the actual download surface is the existing Models flow.
- Tokens / typography / DS-component changes beyond the new `Stepper` and the single `spacing.xxl=40` addition (I_OB11). The slice MUST consume the existing `theme.*` surface (theming.md §1a–§1d).
- Architecture-doc updates to `chat-flow.md`, `pals-and-talents.md`. `theming.md` §1a receives a single paired line edit for `spacing.xxl` (see D11 / I_OB11). The new flow doc `onboarding.md` is the other architecture-library change.

---

## 1. Data model

### 1a. UIStore additions

```
UIStore (additions to (C) src/store/UIStore.ts)
  hasCompletedOnboarding : boolean    // (P) persisted; default false on fresh install
  onboardingState : OnboardingState   // (P) NOT persisted; in-memory only; reset on completion
```

`OnboardingState` is per-session, in-memory, and lives **inside** `UIStore` rather than its own store because (a) it is intrinsically tied to the same lifetime as `hasCompletedOnboarding`, (b) it never persists across launches, and (c) it has no cross-store dependencies — keeping it co-located with the persisted flag puts the single-writer rule in one file.

```
OnboardingState (P)
  currentStep   : 1 | 2 | 3 | 4 | 5 | 6
  selectedTopics: TopicKey[]          // screen 5 selection (multi-select chip grid)
  selectedModelId: string | null      // screen 6 radio selection (must resolve in ModelStore default catalogue)
```

```
TopicKey = 'everyday' | 'creative' | 'learning' | 'coding' | 'productivity' | 'roleplay'
  // (P) Closed union — matches the 6 chip slots in Figma 884:28282 / 890:29650.
  // Exact final labels + icons are designer-owned; engineering owns the union.
```

`selectedTopics` is captured but **not used to alter the recommended pal in this slice** — the recommended pal is always seeded `Pip` (see §4d). Topics persist into `palStore` only as a future-pal-suggestion signal, recorded under `uiStore.onboardingTopicsSnapshot` (P) on completion so the post-onboarding Homepage (FOU-117) can use it later. Persisting topics is **not** the same as persisting `OnboardingState.selectedTopics`; the snapshot is a one-write flat array.

```
UIStore (P, persisted)
  hasCompletedOnboarding   : boolean
  onboardingTopicsSnapshot : TopicKey[]   // (P) frozen at completion, never re-edited
```

### 1b. PalStore additions

A new seeded system pal `Pip`, mirroring the existing `Lookie` seeding pattern (`src/store/PalStore.ts:739` `initializeLookiePal`).

```
SystemPip (P)
  type        : 'local'
  name        : 'Pip'
  description : <designer-owned copy>
  systemPrompt: <designer-owned starter prompt — friendly general-assistant tone>
  defaultModel: <Model — the small default model in ModelStore.defaultModels;
                 chosen below from the closed RECOMMENDED_PAL_MODEL_SET — D2>
  capabilities: {}                           // no video, no special
  color       : [<P: designer palette>]
  source      : 'local'
```

Pip is created idempotently from `PalStore.initialize()` after the database is loaded, by a private `initializePipPal()` paired with the existing `initializeLookiePal()` (matches the Lookie precedent — see Suggestion 1 resolution in Review History).

### 1c. Glossary

- **Hydration hold** — pre-`<PaperProvider>` neutral `View` rendered while `mobx-persist-store` is loading `UIStore` from AsyncStorage (theming.md §4c #4 / I10). NOT a splash screen. Stays neutral; reads from `Appearance.getColorScheme()`. Out of scope here; mentioned only to delineate.
- **Brand splash** (this slice) — the **post-hydration** branded screen at Figma `884:28349`. Rendered as the initial route of the Onboarding stack when `hasCompletedOnboarding === false`. Transitions to Onboarding-1 after a fixed minimum dwell (D6).
- **Stepper** — the 4-dot progress indicator on screens 1–4 (Figma `896:29130`-band). Note: screens 5 and 6 do NOT show a stepper in the Figma frames (screen 5 has a fullwidth header; screen 6 has the recommended-pal header). The stepper is therefore visually 1-of-4, 2-of-4, 3-of-4, 4-of-4 across screens 1–4 only.
- **Topic** — a category the user picks on screen 5. Closed union of 6 keys (`TopicKey`).
- **Recommended pal** — the system-seeded `Pip` shown on screen 6.

---

## 1d. External shape

No wire format. The flow is purely client-side; no Palshub call, no telemetry, no auth.

---

## 2. Event flow

```
AppWithMigrationWrapper (C; unchanged: gates hydration via HydrationHold)
  hydrated → renders <AppWithMigration><App/></AppWithMigration>     (C)

<App/> (extended) constructs its full provider tree
  GestureHandlerRootView → SafeAreaProvider → KeyboardProvider →
  PaperProvider → L10nContext → MarkdownProvider → NavigationContainer →
  BottomSheetModalProvider → <SwitchPoint>                            (P)

<SwitchPoint> reads uiStore.hasCompletedOnboarding (MobX observer)
  → uiStore.hasCompletedOnboarding === false?
       yes → render <OnboardingStack initialRoute='Splash'>           (P)
              ─Splash dwell→ navigate('Onboarding1')                  (P)
              ─Next→ navigate('Onboarding2')                          (P)
              ─Next→ navigate('Onboarding3')                          (P)
              ─Next→ navigate('Onboarding4')                          (P)
              ─Next→ navigate('Onboarding5')                          (P)
                 [Skip button on every step except 1 → completeOnboarding({topics, modelId: null})]
                 [Back button on every step except 1 + Splash → navigation.goBack()]
              ─Next→ navigate('Onboarding6')                          (P)
              ─Finish→ uiStore.completeOnboarding({topics, modelId})  (P; modelId: string | null)
                       palStore.initializePipPal()                    (P; idempotent; also called from PalStore.initialize)
                       if (modelId) modelStore.checkSpaceAndDownload(modelId)  (P)
                       (MobX reactivity in <SwitchPoint> swaps to Drawer.Navigator;
                        ChatScreen displays the FOU-117 first-time empty state —
                        for this slice the ChatScreen is unchanged from (C))
       no  → render <Drawer.Navigator …> (existing tree, unchanged)   (C)
```

The onboarding branch and the Drawer are sibling children of the **same** provider tree inside `<App/>`. The switch is a navigator-choice (Drawer vs OnboardingStack), not a Drawer screen — onboarding never appears as a drawer entry and the Drawer never mounts while onboarding is active. MobX reactivity on `hasCompletedOnboarding` (read inside the observed switch component) re-renders only the navigator subtree on completion; providers above the switch do not remount.

---

## 3. State machine

```
OnboardingState.currentStep
  1 ─Next→ 2 ─Next→ 3 ─Next→ 4 ─Next→ 5 ─Next→ 6 ─Finish→ (completed; OnboardingStack unmounts)
       ↑                ↑                ↑                ↑
       └─Back←──────────┴─Back←──────────┴─Back←──────────┘
  Skip (any of 2–6) → (completed; OnboardingStack unmounts)
```

| State                          | User-visible feedback                                                                         |
| ------------------------------ | --------------------------------------------------------------------------------------------- |
| `pre-stack` (hasCompletedOnboarding=false, hydrated) | Brand splash visible for at least `SPLASH_MIN_DWELL_MS`.                                       |
| `Onboarding1`                  | Welcome screen; Stepper 1/4; primary action "Get started" (no Back, no Skip — per Figma).      |
| `Onboarding2`                  | "The idea" screen; Stepper 2/4; Back + Continue.                                              |
| `Onboarding3`                  | "Smaller, but yours" screen; Stepper 3/4; Back + Continue.                                    |
| `Onboarding4`                  | "Privacy promised" screen; Stepper 4/4; Back + Continue.                                      |
| `Onboarding5`                  | Topic chip grid (6 options); no Stepper; Back + Continue; Continue enabled only when ≥1 chip selected (D7). |
| `Onboarding6`                  | Recommended pal "Pip" + 3 model radio sections; no Stepper; Back + Finish; Finish enabled only when a radio is selected (D8). |
| `completed`                    | OnboardingStack unmounts; Drawer.Navigator mounts in the same provider tree; Chat screen visible (FOU-117 first-time empty state — out of scope here, `ChatScreen` unchanged in this slice). |

Skip is allowed on steps 2–6 (Figma "Skip" lives in the top-right `Buttons` instance on every Body header except Onboarding-1, which has no Skip — verified from the structure dump). On Skip, `selectedTopics` and `selectedModelId` are persisted as empty: the user can pick later.

---

## 4. Contract

### 4a. Where onboarding lives in the navigation tree

1. (P) The switch lives **inside** `<App/>` (`App.tsx`), below the entire provider tree (`GestureHandlerRootView` → `SafeAreaProvider` → `KeyboardProvider` → `PaperProvider` → `L10nContext.Provider` → `MarkdownProvider` → `NavigationContainer` → `BottomSheetModalProvider`). At the position currently occupied by `<Drawer.Navigator …>` (App.tsx:90), an observed component branches: if `uiStore.hasCompletedOnboarding === false`, render `<OnboardingStack/>`; otherwise render `<Drawer.Navigator …>` as today. `AppWithMigrationWrapper` is **unchanged** — it still gates on `isHydrated(uiStore)` and renders `<AppWithMigration><App/></AppWithMigration>` once hydrated.
2. (P) The branch shares the **single** provider tree above with the Drawer; no second `PaperProvider` / `NavigationContainer` / `L10nContext.Provider` / `BottomSheetModalProvider` is constructed. `<OnboardingStack/>` is a `createNativeStackNavigator()` (or `createStackNavigator()` — whichever library is already a dependency; engineering picks the one whose API is simplest for "no header, no gesture-back on Splash"). Because the onboarding stack is a sibling of `Drawer.Navigator` under the same `<NavigationContainer>`, no second navigation container is created.
3. (P) The stack's `screenOptions` set `headerShown: false` for every route (each screen draws its own header per Figma). The stack has 7 routes: `Splash`, `Onboarding1`…`Onboarding6`.
4. (P) Drawer mounting is gated by the same `<SwitchPoint>`: while `hasCompletedOnboarding === false`, `Drawer.Navigator` is **not** rendered and therefore does not mount its screens. This is what gives I_OB6 — the Drawer subtree (and every Drawer screen) is invisible during onboarding, so no Drawer screen can read `OnboardingState`.

### 4b. Per-screen layout contract (from Figma metadata)

Every onboarding screen is a 393×852pt canvas with three vertical zones (verified from `884:28223` metadata):

```
Body  (y=54, height=709 for screens 1–4; 798 for screens 5–6)
  Stepper        (only screens 1–4, at y=30)            — Figma 896:29130
  Skip button    (only screens 2–6, at x=331,y=16)      — Figma "Buttons" 46×28 instance
  Visual         (the illustration; per-screen geometry)
  Content        (title + description, vertical-aligned)
Bottom (y=763, height=89 for screens 1–4 and 5/6 except 5 hides it)
  Buttons row    (Back IconButton 48×48 + primary Button 305×48)   — Figma 888:33xxx
  Home Indicator (presentational, system)
```

Screen-specific deltas:

| Screen | Visual node | Content node | Bottom bar |
| --- | --- | --- | --- |
| 1 | `884:29310` 112×112 illustration | "Welcome to Pocket Pal" / "Meet your pals." / 1-line body | full-width primary Button only (no Back, no Skip) |
| 2 | `884:32584` 85×142 illustration | "The idea" / "Anytime, Anywhere." / body + accent rectangle | Back 48 + primary 305 |
| 3 | `885:29436` 369×217 cards stack | "A heads-up" / "Smaller, but yours." / body + accent rectangle | Back 48 + primary 305 |
| 4 | `885:29601` 85×142 illustration + shield group | "Privacy promised" / "Nothing leaves your phone." / body + accent rectangle | Back 48 + primary 305 |
| 5 | header text 369×80 + 6× Chip 177×160 in a 2-col grid | "What's your pal for?" / "Pick what you'd like to discuss…" | hidden (Figma marks `hidden="true"` on `884:28302`) — user advances via a fixed FAB-style continue or chip-tap-continue (D9) |
| 6 | header 361×196 (Pip icon + "Pip" + tagline) + device-chip 226×42 | "Pip thinks using a small AI model on your phone — pick one that fits." + 3 RadioSection 335×84 each | Back 48 + primary 305 |

(P) Screen 5's bottom bar (Figma flagged `hidden`) is interpreted as **continue is enabled only when ≥1 chip is selected, and is rendered as the same Back+primary bottom bar as other screens but starts disabled**. The Figma hidden flag is read as "designer hasn't decided whether to show the row before any selection"; engineering picks "always show, disable when no selection" because it preserves screen reachability invariants and matches FOU-98's brief. (D9)

### 4c. Stepper (NEW DS component)

(P) `src/components/ui/Stepper/Stepper.tsx`.

```ts
type StepperProps = CommonDSProps & {
  total: number;                  // 1..n
  current: number;                // 1..total
  // Visuals fixed per Figma 896:29130:
  //   inactive dot:  20×4 width, Radius/XS
  //   active   dot:  48×4 width (wider), Radius/XS
  //   gap:           Spacing/XS (=4)
  //   inactive color: theme.colors.outlineVariant
  //   active   color: theme.colors.primary
};
```

Rules:

1. (P) Pure presentational, no state. Reads tokens through `useTheme()` only.
2. (P) `current` clamped to `[1, total]`; out-of-range is logged via `warnIfNoA11yLabel`-style dev-only warning AND clamped to the nearest valid index.
3. (P) `accessibilityRole='progressbar'`; `accessibilityValue={{min: 1, max: total, now: current}}`. Default `accessibilityLabel` is computed (`Step ${current} of ${total}`); consumers may override.
4. (P) Default `testID='ui-stepper'`. Each dot's testID is `ui-stepper-dot-<index>` for E2E discoverability.
5. (P) Lives under `src/components/ui/Stepper/`, follows the §4g.7 folder shape (`Stepper.tsx` + `styles.ts` + `index.ts` + `__tests__/Stepper.test.tsx` + snapshots). Promoted in `src/components/ui/index.ts`.

This component is the only DS-layer addition. Per theming.md §4g, it MUST:
- Be tokens-only (I_UI1).
- Be observation-free (I_UI2).
- Not import `src/components/*` legacy.
- Be subject to the visual-parity snapshot strategy (§4k.2): `variant × size × {default, disabled} × {light, dark}` reduces to `{2-step, 3-step, 4-step, 5-step} × 1 × {default} × {light, dark}` because there is no variant or disabled state; emit 8 snapshots.

### 4d. The `Pip` seeded pal

(P) `PalStore.initializePipPal()` is a private method, called from `PalStore.initialize()` after `initializeLookiePal()`. Idempotent: looks up `{ name: 'Pip', source: 'local' }`; if present, returns; if absent, creates with the data shape in §1b.

(P) The recommended model on screen 6 is the user-pickable model from `RECOMMENDED_PAL_MODEL_SET` (D2). Once picked, the model is registered in `ModelStore` (using existing model registration paths) AND its `id` is written to `Pip.defaultModel.id`. (Pip then "knows" which model to use.)

(P) The user-picked download is enqueued via `modelStore.checkSpaceAndDownload(modelId)` (existing public API; signature confirmed against `src/store/ModelStore.ts:990` and call sites `ModelCard.tsx:415`, `ChatPalModelPickerSheet.tsx:62`, `ProjectionModelSelector.tsx:108`, `ModelNotAvailable.tsx:52`). It accepts the model `id` string and resolves space/auth/destination internally. Onboarding does NOT block on the download completing; the user lands on Homepage with the download in-flight (visible via the existing Models screen).

(P) If the user picks no model (Skip path on any of screens 2–6, or screen 6 Skip), Pip exists with `defaultModel=undefined`; the user must pick a model later via the Models screen. This matches the existing post-install state of the app. Screen 6 Finish before picking is disabled (D8), so the only no-model completion paths are the Skip buttons.

### 4e. Onboarding-skipped invariants

(P) Skipping at any step:
- Always flips `hasCompletedOnboarding = true` via `completeOnboarding({topics, modelId: null})` (where `topics` is whatever the user has accumulated in `OnboardingState.selectedTopics` — empty array if screen 5 not reached).
- Captures the partial state in `uiStore.onboardingTopicsSnapshot` (empty array if screen 5 not reached or no chip tapped).
- Does NOT seed Pip differently; Pip is seeded by `PalStore.initialize()` regardless of onboarding outcome.
- Does NOT enqueue any model download (no `checkSpaceAndDownload` call).

### 4f. Hard invariants

- **I_OB1 (single-shot flow)**: Onboarding mounts only when `uiStore.hasCompletedOnboarding === false` AND `mobx-persist-store` has hydrated `UIStore`. Once `hasCompletedOnboarding` flips to `true`, the `<SwitchPoint>` re-renders and the OnboardingStack subtree unmounts; it never re-mounts in this app lifetime.
- **I_OB2 (no Drawer overlap)**: While the OnboardingStack is mounted, `Drawer.Navigator` is NOT rendered by `<SwitchPoint>` and therefore does not mount its screens. The two are mutually exclusive children of the switch.
- **I_OB3 (token consumption only)**: Every onboarding screen consumes `theme.colors.*`, `theme.typography.*`, `theme.spacing.*`, `theme.radius.*`, `theme.stroke.*` from `useTheme()`. No raw hex, no raw px in `styles.ts` (lint-enforced by the existing `no-restricted-syntax` rule once the new files are inside `src/components/ui/**/styles.ts`; for screen-level `styles.ts` outside the DS namespace the lint rule does not apply, but tokens-only is still a soft contract enforced at code review).
- **I_OB4 (DS-only components)**: Onboarding screens consume only DS components (`Button`, `IconButton`, `Chip`, `RadioSection`, `Header`, `Stepper`, plus `Text` from RN Paper per the locked thin set). No legacy `src/components/*` import except where there is no DS equivalent (none expected in this slice). This is the first slice to put I_UI6 (testID freeze) into play at screen level.
- **I_OB5 (testID freeze)**: Every interactive element exposes a stable `testID` per §4l. Phase 4 / FOU-123 may extend but MUST NOT rename.
- **I_OB6 (no Drawer screens read OnboardingState)**: Because `Drawer.Navigator` is not rendered while onboarding is active (I_OB2), no Drawer screen can read `OnboardingState`. Conversely, once onboarding completes and the Drawer mounts, the only post-completion surfaces a Drawer screen reads are the two persisted UIStore fields (`hasCompletedOnboarding`, `onboardingTopicsSnapshot`); `OnboardingState` is the empty / reset shape by then.
- **I_OB7 (Pip seeding is idempotent and order-independent)**: `initializePipPal` MUST be safe to call multiple times in any order relative to `initializeLookiePal`; both must converge on the same `pals[]` regardless of arrival order.
- **I_OB8 (light + dark parity)**: Every screen renders against light tokens AND dark tokens with no visual regression vs the canonical Figma frame. Verified per screen in HOW.
- **I_OB9 (RTL + non-Latin verified per slice)**: On `language ∈ {he, fa}`, screen layout mirrors (RN `I18nManager` already enabled — verified by FOU-114) AND headlines fall back to Inter per theming.md §4d.2.
- **I_OB10 (no telemetry / no auth)**: No network call originates from any onboarding screen.
- **I_OB11 (`spacing.xxl = 40` cross-cite handshake)**: Figma uses `Spacing/XXL=40` for onboarding screens. The token addition in `src/theme/tokens/spacing.ts` and the architecture-doc amendment to `context/architecture/theming.md` §1a live in **different repos** (linked by submodule), so literal same-PR atomicity is structurally impossible. Instead, per the I_UI8 analogue established by FOU-115 (theming.md §4 I_UI8): the app PR cites the dev-team-repo commit SHA that amends theming.md §1a in its description; the dev-team-repo commit cites the app PR URL. Splitting them across review cycles is forbidden. The pipeline-reviewer enforces both citations before approving the draft PR.

### 4g. What each component / module renders

| Component / module | Renders / produces | Does NOT render / produce |
| --- | --- | --- |
| `AppWithMigrationWrapper` (unchanged from (C)) | (C) The hydration hold while `!isHydrated(uiStore)`; `<AppWithMigration><App/></AppWithMigration>` once hydrated. | (P) The onboarding switch — that moves down to `<App/>`. |
| `App` (extended) | (P) The provider tree (unchanged from (C)) followed by a single observed `<SwitchPoint>` child of `<BottomSheetModalProvider>`. `<SwitchPoint>` reads `uiStore.hasCompletedOnboarding` and renders either `<OnboardingStack/>` or `<Drawer.Navigator …>` (with the existing screens). | Theme construction (still in `useTheme()`); the hydration hold (lives one level up, unchanged from (C)). |
| `OnboardingStack` | (P) `createNativeStackNavigator()` with `headerShown: false` and 7 routes: `Splash`, `Onboarding1`…`Onboarding6`. Shares the `<NavigationContainer>` provided by `<App/>`. | A separate `<NavigationContainer>` / `<PaperProvider>` / `<BottomSheetModalProvider>` (it shares the App-level instances). Per-screen state (lives in `uiStore.onboardingState`); side effects (caller does that on Finish). |
| `SplashScreen` (P) | The brand mark at canvas centre per Figma `884:28349`. Triggers `navigate('Onboarding1')` after `SPLASH_MIN_DWELL_MS` (D6). | A neutral background hold (that's the FOU-114 hydration hold, pre-`<PaperProvider>`). |
| `Onboarding{N}Screen` (P, N=1..6) | The per-screen layout in §4b: header (Stepper for 1–4 + Skip for 2–6), Visual, Content, Bottom bar. Consumes DS components only. | Navigation logic beyond `navigation.navigate(prev|next)` and `uiStore.completeOnboarding`. |
| `Stepper` (P, new DS) | A row of dot markers per `current/total`. Token-bound. | State (purely presentational). |
| `uiStore` (extended) | `hasCompletedOnboarding`, `onboardingTopicsSnapshot` (both persisted); `onboardingState` (in-memory). Single-writer methods: `setOnboardingStep`, `setOnboardingTopics` / `toggleOnboardingTopic`, `setOnboardingModelId`, `completeOnboarding({topics, modelId})`, `resetOnboarding` (test-only). | Any read of `palStore` / `modelStore`. The onboarding completion fans out via direct calls from the screens; UIStore is not a router. |
| `PalStore` (extended) | `initializePipPal()` invoked from `initialize()` (mirrors `initializeLookiePal`). | Onboarding state. |
| `ModelStore` | No additions — existing `checkSpaceAndDownload(modelId)` is the public API screen 6 calls. | Onboarding state. |

### 4h. The token-to-Figma mapping (verified)

Per the `get_variable_defs` dump on `884:28223`, every visual property in onboarding screens 1–6 resolves to an existing token already in `theme.*`, with the single exception flagged by I_OB11:

| Figma binding | Resolves to (theme.*) |
| --- | --- |
| `Color/Foreground/Primary` (#181715) | `colors.text` / `colors.onBackground` |
| `Color/Foreground/Secondary` (#474747) | `colors.textSecondary` |
| `Color/Foreground/Tertiary` (#81807e) | `colors.onSurfaceVariant` (used for the device-chip text on screen 6) |
| `Color/Foreground/Subtle` (#c4c2c0) | `colors.outline` / `colors.placeholder` |
| `Color/Background/Card` (#ffffff) | `colors.surface` |
| `Color/Background/Muted` (#fafafa) | `colors.surfaceVariant` |
| `Color/Background/Top layer` (#ffffff) | `colors.background` |
| `Color/Primary/Default` (#0e0d0c) | `colors.primary` |
| `Color/Primary/Foreground` (#fafafa) | `colors.onPrimary` |
| `Color/Border/Light Grey` / `Color/Border/Subtle` / `Color/Border/Strong` | `colors.outlineVariant`, `colors.border`, `colors.outline` (existing surface) |
| `Color/Yellow/*` (subtle/strong/accent) | `colors.bgStatus*` family (existing) |
| `Headline/H1` (Fraunces 36 / 1.4 mult) | `typography.headlineH1` (absolute lineHeight 50 — theming.md §4a #4) |
| `Title/sm` (Inter Medium 16/22) | `typography.titleS` (closest existing) — engineering verifies the size match in HOW |
| `Body/md` (Inter Regular 15/28) | `typography.bodyM` |
| `Body/sm` (Inter Regular 13/20) | `typography.bodyS` |
| `Caption/xs` (Inter 10/18) | `typography.captionS` |
| `Caption/sm` (Inter Medium 11/18) | `typography.captionM` |
| `Spacing/{None,XXS,XS,S,SM,M,ML,L,XL,XXL}` (0..40) | `spacing.{none,xxs,xs,s,sm,m,ml,l,xl,xxl}` — note `xxl=40` is **new**, see I_OB11 |
| `Radius/{XS,S,M,ML,L,XL,XXL}` (4..40) | `radius.{xs,s,m,ml,l,xl,xxl}` (per theming.md §1a Radius rename) |
| `Stroke/{xs,sm,md,lg}` | `stroke.{xs,sm,md,lg}` |

I_OB11 — paired-edit handshake (see §4f for the invariant text). The app PR adds `spacing.xxl = 40` to `src/theme/tokens/spacing.ts`; a dev-team-repo commit amends `context/architecture/theming.md` §1a to list `xxl` in the Spacing axis. PR description cites dev-team-repo commit SHA; dev-team-repo commit message cites the app PR URL. This is a discrete paired-edit task the planner MUST surface as a step in HOW; the pipeline-reviewer enforces both citations.

### 4i. testID surface (frozen here)

Per `context/redesign/FOU-112-rollout.md` §5 testID-freeze contract. This is what E2E observes; Phase 4 may extend at the leaves but MUST NOT rename.

| Surface | `testID` |
| --- | --- |
| Splash screen root | `onboarding-splash` |
| Onboarding screen root (N=1..6) | `onboarding-screen-<N>` |
| Stepper root (screens 1–4) | `ui-stepper` (DS default) |
| Stepper dot (i=1..total) | `ui-stepper-dot-<i>` |
| Skip button (screens 2–6) | `onboarding-skip` |
| Back button (screens 2–6) | `onboarding-back` |
| Primary button (screens 1–6) | `onboarding-primary` |
| Topic chip (screen 5, key=TopicKey) | `onboarding-topic-<key>` |
| Recommended-pal model radio (screen 6, modelId) | `onboarding-pip-model-<modelId>` |
| Device-info chip (screen 6, presentational) | `onboarding-device-chip` |
| First-time homepage destination marker | (none — the homepage proper is FOU-117 scope and freezes its own testIDs there) |

`accessibilityLabel` defaults: every interactive element above gets an l10n-keyed label (see §4j). For the Stepper, see §4c #3.

### 4j. l10n contract

(P) New keys under `onboarding.*` in `src/locales/en.json` (English only — translators pick up via Weblate per the project's locale workflow).

```
onboarding.splash.title                  // optional brand subtitle (engineering may omit if Figma has no text node)
onboarding.screen1.title                 // "Meet your pals."
onboarding.screen1.body                  // "Smart little friends that live inside your phone…"
onboarding.screen1.eyebrow               // "Welcome to Pocket Pal"
onboarding.screen1.cta                   // "Get started"
onboarding.screen2.eyebrow / .title / .body / .cta
onboarding.screen3.eyebrow / .title / .body / .cta
onboarding.screen4.eyebrow / .title / .body / .cta
onboarding.screen5.title                 // "What's your pal for?"
onboarding.screen5.body                  // "Pick what you'd like to discuss…"
onboarding.screen5.cta                   // "Continue"
onboarding.screen5.topic.<key>           // 6 entries (one per TopicKey)
onboarding.screen6.eyebrow               // "Pip"
onboarding.screen6.title                 // "We found a perfect pal for you…"
onboarding.screen6.body                  // "Pip thinks using a small AI model on your phone — pick one that fits."
onboarding.screen6.cta                   // "Finish"
onboarding.screen6.model.<modelKey>.title       // 3 entries (one per RECOMMENDED_PAL_MODEL_SET member)
onboarding.screen6.model.<modelKey>.subtitle    // size + RAM hint
onboarding.back                          // accessibility label for the back IconButton
onboarding.skip                          // visible label + accessibility label for Skip
```

(P) **Designer-owned copy** for every screen body / title is captured in the Figma frames; engineering ports the strings verbatim in HOW. Empty `onboarding.*.body` keys are forbidden — if a Figma string is missing at HOW time, the architect-critic flags it as a designer ask, not a placeholder.

### 4k. RTL + non-Latin contract

(P) Per `FOU-112-rollout.md` §5 + theming.md §4d:

1. RTL (`he`, `fa`): Layout mirrors via RN's `I18nManager.isRTL` flag, which the FOU-114 wiring already toggles per `uiStore.language`. Screens use `start`/`end` semantics (RN built-in), not `left`/`right`, on every container that has directional padding/margin. The Stepper itself reads LTR → RTL by reversing its dot order via `flexDirection: 'row-reverse'` when `I18nManager.isRTL`. Per-screen sanity check: screens 5 and 6 (the two most layout-sensitive) MUST be verified manually in `he` (or `fa`) in HOW.
2. Non-Latin / CJK: Headlines using `theme.typography.headlineH1` (which is Fraunces in Latin locales) automatically fall back to Inter for `language ∈ {fa, he, ja, ko, ru, uk, zh, zh_Hant}` per theming.md §4d.2. No per-screen handling required — onboarding inherits the token-level swap.

### 4l. Visual-parity snapshot strategy for onboarding (additive)

(P) Onboarding screens are **screen-level** (not DS-component-level). Per theming.md §4k, the visual-parity snapshot strategy is a DS-component contract — screens do not ship snapshots in the same matrix shape.

However, this slice introduces the first screens designed against the new tokens. The HOW MUST produce **light + dark visual references per screen**, captured as iOS-simulator and Android-emulator screenshots stored alongside the story directory (`workflows/stories/TASK-20260526-1731/screenshots/`). These are diffed by hand against the canonical Figma frames at the architect-critic / pipeline-reviewer stage. This procedure is the same one used by FOU-114 (`workflows/stories/TASK-20260519-2110/visual-diff-procedure.md`) and is referenced in HOW, not duplicated here.

The new `Stepper` DS component DOES ship the standard variant×size×state×mode matrix per theming.md §4k.2.

---

## 5. Layer ownership (single-writer rule)

| Field | Single writer |
| --- | --- |
| `uiStore.hasCompletedOnboarding` | `uiStore.completeOnboarding({topics, modelId})` (P; sets to `true`); `uiStore.resetOnboarding()` (P; **test-only**, dev/E2E flag-gated). |
| `uiStore.onboardingTopicsSnapshot` | `uiStore.completeOnboarding({topics, modelId})` — `topics` is written once, never edited after. `modelId` is forwarded to the screen-side `checkSpaceAndDownload` call, not persisted on UIStore. |
| `uiStore.onboardingState.currentStep` | `uiStore.setOnboardingStep(n)`, called by the relevant screen's mount effect. |
| `uiStore.onboardingState.selectedTopics` | `uiStore.toggleOnboardingTopic(key)` (P) — single mutation entry. |
| `uiStore.onboardingState.selectedModelId` | `uiStore.setOnboardingModelId(modelId)` (P). |
| `palStore.pals` (Pip entry) | `PalStore.initializePipPal()` (P) — idempotent create. Pip is otherwise edited like any user pal via `PalSheet` (existing path; out of scope here). |
| `modelStore.models` / `modelStore.downloads` | Existing single-writers in `ModelStore`. Onboarding only **calls** `modelStore.checkSpaceAndDownload(modelId)` (existing public API). |

`completeOnboarding({topics, modelId})` signature (P): `topics: TopicKey[]` (possibly empty), `modelId: string | null`. The screen-side caller is responsible for invoking `palStore.initializePipPal()` (idempotent — already called from `PalStore.initialize`) and, when `modelId !== null`, `modelStore.checkSpaceAndDownload(modelId)`. UIStore writes only its own fields.

Recent bugs / past pain: onboarding is greenfield, so no prior bugs. The single-writer table is *prescriptive* — the resolver pattern from `ChatSessionStore` (chat-flow.md §5) is the model: ephemeral state lives in one place, fanned out via one method on completion, never persisted piecewise.

**Deferred cleanups**:

1. Migrate `OnboardingState` out of `UIStore` into its own store if a second flow ever needs similar transient state. Not now — single-flow, single-shot, in-memory keeps the cost low.
2. Once FOU-117 lands a real Homepage, `onboardingTopicsSnapshot` becomes a read-source for pal suggestions. Keep `snapshot` immutable; never re-derive at runtime.
3. Once translators ship `onboarding.*` keys, audit per-locale render manually (screens 5 + 6 are the most layout-sensitive).
4. When `Stepper` finds a non-onboarding consumer, widen its variant axis only via a delta WHAT against theming.md.

---

## 6. Canonical scenarios

Each scenario is manually verifiable in HOW.

### A. Fresh install — full onboarding flow

```
initial state: hasCompletedOnboarding=undefined, no Pip pal in DB

1. App launches. Hydration hold (neutral View) → hydrated. UIStore.hasCompletedOnboarding === false.
   AppWithMigrationWrapper renders <AppWithMigration><App/></AppWithMigration>.
2. <App/> mounts its provider tree. PalStore.initialize() seeds Pip via initializePipPal()
   (idempotent; no defaultModel yet).
3. <SwitchPoint> observes hasCompletedOnboarding === false → renders <OnboardingStack initialRoute='Splash'>.
4. SplashScreen renders for SPLASH_MIN_DWELL_MS, then navigates to Onboarding1.
5. User taps "Get started". → Onboarding2.
6. User taps "Continue" → Onboarding3 → Onboarding4 → Onboarding5.
7. Onboarding5: Continue is disabled.
8. User taps topic chip 'everyday' (or any). Continue enables.
9. User taps Continue → Onboarding6.
10. Onboarding6: Finish is disabled. Pip header + 3 model radios visible.
11. User picks the smallest model radio. Finish enables.
12. User taps Finish. Screen handler runs:
     - uiStore.completeOnboarding({topics: ['everyday'], modelId: <chosenId>})
        → hasCompletedOnboarding := true (persisted)
        → onboardingTopicsSnapshot := ['everyday']
     - palStore.initializePipPal()  (idempotent; if needed, updates Pip.defaultModel.id)
     - modelStore.checkSpaceAndDownload(<chosenId>)  (existing API; enqueues download)
13. MobX reactivity in <SwitchPoint> re-renders: OnboardingStack unmounts, Drawer.Navigator
    mounts inside the same provider tree. Chat screen visible (FOU-117 work; this slice does
    NOT alter ChatScreen visuals).
```

### B. Cold restart after onboarding

```
initial state: hasCompletedOnboarding=true (persisted from prior session)

1. App launches. Hydration hold → hydrated. AppWithMigrationWrapper renders <App/>.
2. <App/> mounts its provider tree. <SwitchPoint> observes hasCompletedOnboarding=true
   → renders <Drawer.Navigator …>.
3. SplashScreen NEVER renders. OnboardingStack NEVER mounts. The post-FOU-114 launch
   sequence is identical to today.
```

### C. User skips on screen 3

```
1. Splash → Onboarding1 → Onboarding2 → Onboarding3.
2. User taps top-right "Skip".
3. uiStore.completeOnboarding({topics: [], modelId: null}) runs.
   - hasCompletedOnboarding := true.
   - onboardingTopicsSnapshot := [].
4. palStore.initializePipPal() is a no-op (Pip already seeded by PalStore.initialize on app start) —
   Pip exists with defaultModel=undefined because the user picked none.
5. NO modelStore.checkSpaceAndDownload call (modelId is null).
6. <SwitchPoint> swaps to Drawer.Navigator. ChatScreen empty state visible.
```

### D. RTL language (Hebrew) — full onboarding mirrored

```
preconditions: uiStore.language = 'he', I18nManager.isRTL=true (persisted)

For each screen: header alignment, stepper dot order, bottom-bar Back/primary
ordering all mirror correctly. Headlines render in Inter-Regular (Fraunces
fallback per theming.md §4d.2). Body text reads right-to-left.
```

### E. Dark mode — full onboarding parity

```
preconditions: uiStore.colorScheme = 'dark'

For each screen: light-mode token usage → dark token usage produces the
canonical Figma dark renders at 3011:25220. Verified by side-by-side
screenshot in HOW.
```

### F. App killed mid-onboarding (state loss)

```
1. User reaches Onboarding4. Process killed (cold restart).
2. App launches. hasCompletedOnboarding=false (still). Onboarding restarts at Splash → Onboarding1.
3. The in-memory `onboardingState` from the prior session is gone (by design — D5).
```

This is a deliberate design call (D5): mid-flow state does not persist. The flow is short; resuming halfway is more friction than restart.

### G. User reaches screen 6, picks model, completes; download proceeds in background

```
1. User taps Finish on screen 6 with selectedModelId='gemma-3-1b'.
2. Screen handler runs:
   - uiStore.completeOnboarding({topics: <whatever was picked>, modelId: 'gemma-3-1b'})
   - palStore.initializePipPal() (idempotent)
   - modelStore.checkSpaceAndDownload('gemma-3-1b') begins (existing API; resolves
     destination/auth internally).
3. <SwitchPoint> swaps to Drawer.Navigator; user lands on Chat. Chat shows the existing empty state.
4. User opens Models drawer item → sees the chosen model in 'downloading' state.
5. When download completes, Pip is usable in Chat (selected via the existing
   pal/model selection flows — out of scope here).
```

### G'. User skips on screen 6 after seeing the recommended-pal picker (no model picked)

```
preconditions: user has reached Onboarding6 and may have selected topics on screen 5
               (e.g. ['everyday']), or may have arrived having picked nothing.

1. User taps top-right "Skip" on Onboarding6 (no model radio selected — or selected
   one but chose to skip anyway via the Skip button instead of Finish).
2. Screen handler runs:
   - uiStore.completeOnboarding({topics: <whatever was picked>, modelId: null})
      → hasCompletedOnboarding := true.
      → onboardingTopicsSnapshot := <topics> (possibly empty, possibly e.g. ['everyday']).
   - palStore.initializePipPal() is a no-op (Pip already seeded by PalStore.initialize
     on app start) — Pip exists with defaultModel=undefined. This exercises §4d line 253
     (Skip path → Pip seeded with no defaultModel).
   - NO modelStore.checkSpaceAndDownload call (modelId is null).
3. <SwitchPoint> swaps to Drawer.Navigator. ChatScreen empty state visible.
4. The user can later open the Models screen, download any model, and bind it to Pip
   via the existing PalSheet — out of scope here.
```

### H. Stepper renders correctly across screens 1–4

```
Screen 1: <Stepper total=4 current=1/> → dot 1 wide, dots 2–4 narrow.
Screen 2: <Stepper total=4 current=2/> → dot 2 wide.
Screen 3: <Stepper total=4 current=3/> → dot 3 wide.
Screen 4: <Stepper total=4 current=4/> → dot 4 wide.
Screens 5 + 6: NO Stepper rendered (per Figma).
```

---

## 7. State signals

| Signal | Set by | Read by | True when |
| --- | --- | --- | --- |
| `uiStore.hasCompletedOnboarding` | `completeOnboarding({topics, modelId})` (and `resetOnboarding()` test-only). | `<SwitchPoint>` inside `<App/>` (gates Drawer vs OnboardingStack). | User has finished or skipped onboarding once. |
| `uiStore.onboardingState.currentStep` | `setOnboardingStep(n)` via screen mount-effect. | Stepper (`current` prop on screens 1–4); E2E for state observation. | The corresponding screen is active. |
| `uiStore.onboardingState.selectedTopics.length > 0` | `toggleOnboardingTopic` | Screen 5 (enable Continue). | At least one topic chip is selected. |
| `uiStore.onboardingState.selectedModelId !== null` | `setOnboardingModelId` | Screen 6 (enable Finish). | A model radio has been picked. |
| `isHydrated(uiStore)` (from `mobx-persist-store`) | `makePersistable` lifecycle. | `AppWithMigrationWrapper` (gates first mount of `<App/>`, which in turn contains `<SwitchPoint>`). | UIStore has finished loading from AsyncStorage (already (C) per theming.md). |

---

## 8. Decisions

- **D1 (Onboarding switch is INSIDE `<App/>`, below the providers, branching `OnboardingStack` vs `Drawer.Navigator`)**: Keeps the entire provider tree (`PaperProvider`, `NavigationContainer`, `L10nContext`, `BottomSheetModalProvider`, `MarkdownProvider`, `KeyboardProvider`, `SafeAreaProvider`, `GestureHandlerRootView`) single-instance and shared between onboarding and the rest of the app. Avoids leaking onboarding into `headerLeft` / `SidebarContent` / drawer screen options (the branch is a navigator-choice, not a Drawer screen). Trivially satisfies I_OB6 since `Drawer.Navigator` simply isn't rendered while onboarding is active. Rejected alternative (Interp A — switch at `AppWithMigrationWrapper`): would require either pushing all providers up out of `<App/>` (cross-cutting refactor) or duplicating them on the onboarding side (two `PaperProvider`s, two `NavigationContainer`s — fragile and wrong).
- **D2 (`RECOMMENDED_PAL_MODEL_SET` = closed list of 3 small models)**: Engineering picks 3 small-RAM-budget models from `ModelStore.defaultModels` (e.g. one ~500MB tier, one ~1GB tier, one ~2GB tier). The exact list is HOW-time work (the architect doesn't pick model IDs from a moving catalogue; the planner sees the latest defaults). Constraint: every member MUST exist in `defaultModels` at HOW time, with a stable `id`. Adding a recommendation later is a delta WHAT against `onboarding.md`.
- **D3 (Pip seeded by `PalStore.initialize`, not by onboarding completion)**: Mirrors the existing Lookie precedent (`initializeLookiePal` at `src/store/PalStore.ts:739`). Pip exists on every install (independent of onboarding) so the post-skip state is sane. The method is named `initializePipPal` (matching the Lookie precedent), not `ensurePipPal` — see Suggestion 1 resolution in Review History.
- **D4 (Topic selection captured but not used to alter recommendation)**: The recommended pal is always Pip in this slice. Per-topic recommendations are a future FOU work item. Capturing the snapshot now means FOU-117 has the data when it lands. Alternative considered: hide screen 5 entirely until topic-driven recs exist. Rejected because screen 5 is in the canonical Figma frames and is part of the locked "first flow slice".
- **D5 (Mid-flow state does NOT persist across launches)**: `onboardingState` is in-memory. Rationale: flow is short, partial-progress surfaces are not in Figma, and recovering from kill at exactly the right step is more code than worth.
- **D6 (`SPLASH_MIN_DWELL_MS = ~600ms`)**: Constant defined in HOW. Rationale: long enough for the brand to read; short enough not to feel like a load screen. The hydration hold (pre-`<PaperProvider>`) is on top — total user-visible "splash" time is `max(hydration_actual_ms, SPLASH_MIN_DWELL_MS)` because we want the brand splash to show for a minimum even when hydration is instant.
- **D7 (Screen 5 Continue disabled until ≥1 topic selected)**: Without selection, advancing has no purpose; the screen has a clear "pick what you'd like to discuss" call to action. Alternative: allow zero selection to fast-skip. Rejected because Skip already covers fast-exit; this control should mean what it says.
- **D8 (Screen 6 Finish disabled until a model radio is selected)**: Same logic. Skip is the no-model path (see Scenario G').
- **D9 (Screen 5 bottom bar shown disabled, not hidden, despite Figma `hidden="true"` on `884:28302`)**: The Figma `hidden` flag is interpreted as "design-time hidden because no selection in the example mock", not "production-time hidden". Always-show-with-disabled state preserves screen-reachability invariants and the testID-freeze surface (`onboarding-primary` exists on every onboarding screen).
- **D10 (`Stepper` lives in DS layer from this slice)**: Per theming.md §4g rules, a presentational, tokens-only, observation-free component belongs in `src/components/ui/`. Putting it outside the DS layer would breach I_OB4 (DS-only components from screens). It will gain non-onboarding consumers as soon as setup-style flows appear; pre-placing it in the DS namespace prevents a later move.
- **D11 (`spacing.xxl = 40` added to tokens — theming.md §1a amended via the I_UI8 cross-cite handshake)**: Figma section explicitly defines `Spacing/XXL=40` for use on onboarding screens. Adding it is mechanical + source-of-truth-driven (theming.md I2). Because app code (`src/theme/tokens/spacing.ts`) and architecture docs (`context/architecture/theming.md`) live in **different repos** linked by submodule, literal same-PR atomicity is structurally impossible — same constraint that theming.md I_UI8 already addresses for the FOU-115 rename. Therefore: app PR cites the dev-team-repo commit SHA that amends theming.md §1a in its description; the dev-team-repo commit cites the app PR URL. Splitting them across review cycles is forbidden. The planner MUST emit this paired-edit step explicitly in HOW; the pipeline-reviewer enforces both citations before approving the draft PR. I_OB11 carries the invariant.
- **D12 (No analytics / no telemetry)**: I_OB10 is non-negotiable; PocketPal has no analytics today and FOU-116 is the wrong slice to introduce them.
- **D13 (Onboarding state lives inside `UIStore`, not a new `OnboardingStore`)**: Single flow, single-shot, in-memory, shares lifetime with a persisted UIStore flag. A separate store doubles the persistence surface for zero benefit at this stage. Deferred-cleanup item recorded in §5 if a second flow shows up.

---

## 9. Edge cases

### 9a. User flips colorScheme during onboarding

`uiStore.setColorScheme('dark')` is reachable only from Settings, which is in the Drawer — and the Drawer is unmounted during onboarding. So the only way to flip colorScheme mid-flow is system-level (OS dark-mode toggle). RN/Paper re-renders correctly via the existing reactive hook; no special handling.

### 9b. User flips language during onboarding

Same as 9a — Language picker is in Settings, in the Drawer, unmounted. System-language change is observable but rare. The theme reactivity covers it.

### 9c. `mobx-persist-store` hydration fails

Per theming.md §9k, `mobx-persist-store` proceeds with in-memory defaults on hydration failure → `hasCompletedOnboarding` reads its initial value `false` → onboarding shows. On next successful boot, the persisted value (if any) is honoured. No new error UI invented.

### 9d. Pip is seeded but no model is available

Pip exists with `defaultModel=undefined`. Selecting Pip later (Pals screen) and trying to use it surfaces the existing "no model loaded" path — out of scope here.

### 9e. The user enqueued model download fails

Onboarding doesn't observe the download. `modelStore.checkSpaceAndDownload` surfaces failure via the existing error path (per `ModelStore.ts:1011`); the Models screen renders the resulting snackbar / failure state. Pip remains seeded with the intended `defaultModel.id`, which will resolve to "not downloaded" until the user retries.

### 9f. User taps Back from Onboarding1

Onboarding1 has NO Back button per Figma. Pressing system back (Android) is intercepted by the stack's `gestureEnabled: false` + a no-op `BackHandler` listener while on the first route. Result: nothing happens; the splash does NOT re-appear.

### 9g. Two `initializePipPal` invocations race

`PalStore.initialize` is called once in the store constructor; idempotency check (`pals.find(p => p.name === 'Pip' && p.source === 'local')`) ensures a re-entry does not double-seed. I_OB7.

### 9h. User reaches screen 6 before the canonical `RECOMMENDED_PAL_MODEL_SET` is loaded into `ModelStore`

`ModelStore.defaultModels` is a static const (`src/store/defaultModels.ts`) — present in memory from app start. No async dependency. The three model rows render synchronously.

### 9i. RTL: stepper dot order

`flexDirection: 'row-reverse'` when `I18nManager.isRTL`. The wide "current" dot still represents the same logical step (1..4 in document order), just visually mirrored. Manual verification in `he` is required.

### 9j. `__E2E__` mode bypass

E2E specs run against fresh installs and may want to skip onboarding for non-onboarding tests. Mechanism: an existing AutomationBridge call (`__E2E__` flag) calls `uiStore.completeOnboarding({topics: [], modelId: null})` synchronously before navigation mounts. This is an additive E2E test-utility, NOT a runtime production path. The onboarding spec itself does NOT use this bypass.

### 9k. Existing-app upgrade (user installs the FOU-116 build over an older build)

`UIStore` already has persisted state from a prior install (e.g. `colorScheme = 'dark'`, `language = 'en'`). The new key `hasCompletedOnboarding` is `undefined` after hydration (not in the persisted store) → coerced to `false` → onboarding shows once for upgrade users. (P) This is the **intended** behaviour: existing users see the redesigned brand onboarding the first time after upgrade. Alternative considered: gate onboarding on a separate `hasUsedAppBefore` heuristic (e.g. any pal exists, any model is downloaded). Rejected because it adds complexity and the one-time onboarding for upgraders is the intent per FOU-98 brief.

### 9l. Onboarding screen 5 with all 6 chips deselected after one was selected

Once a chip is selected then deselected, Continue returns to disabled. This is intentional: D7 — selection is a precondition for Continue.

### 9m. Empty Figma string at HOW time

If a copy slot in the Figma frames is empty when HOW reads it, the planner does NOT invent placeholder copy. The architect-critic flags it as a designer ask logged on FOU-116 (analogous to the FOU-114 `designer-asks.md` precedent at `workflows/stories/TASK-20260519-2110/`).

### 9n. The user installs a build that ships `Stepper` but no consumer exists

Stepper is exported from the DS barrel. Tree-shaking should remove it from the bundle when unused; even if not, it's a small presentational component. No runtime cost.

---

## 10. What this doc is NOT

- Not an implementation plan — file layout, refactor order, asset wiring live in `how.md`.
- Not a designer hand-off — Figma is the design source.
- Not a Homepage / Chat specification — those are FOU-117 scope. This doc references the first-time Homepage only as the destination state.
- Not a model-catalogue specification — the `RECOMMENDED_PAL_MODEL_SET` membership is HOW-time work against the current `defaultModels` content (D2).
- Not a designer-copy spec — onboarding copy is ported verbatim from Figma in HOW. Empty slots are designer asks, not engineering invention (§9m).
- Not a Phase 4 cleanup plan — Stepper does not need a non-onboarding consumer to exist in DS, and the Paper-import blocklist is not extended by this slice.

**Cleanup reminders**:

1. The new flow doc `context/architecture/onboarding.md` is promoted from this delta on the same PR that lands the code.
2. The `spacing.xxl = 40` token (I_OB11 / D11) requires a paired line edit in `context/architecture/theming.md` §1a. Because the two files live in different repos, the I_UI8 cross-cite handshake applies: app PR description cites the dev-team-repo commit SHA; the dev-team-repo commit message cites the app PR URL. The planner MUST emit this as a discrete step in HOW.
3. Once FOU-117 lands the real Homepage, this doc references it instead of "out of scope here".
4. The `Stepper` DS component is subject to the same snapshot freeze contract (I_UI5) as every other DS component starting next slice.

---

## Review History

### Round 1 — architect-critic, HAS_BLOCKERS (2026-05-26)

| # | Severity | Summary | Resolution |
| - | -------- | ------- | ---------- |
| BLOCKER 1 | BLOCKER | §4a contradiction: switch at `AppWithMigrationWrapper` (above providers) vs "no separate provider tree" (which requires being below them). | **FIXED**. Adopted Interp B (critic's recommendation). Verified against `App.tsx` (worktree): all providers — `GestureHandlerRootView`, `SafeAreaProvider`, `KeyboardProvider`, `PaperProvider`, `L10nContext.Provider`, `MarkdownProvider`, `NavigationContainer`, `BottomSheetModalProvider` — are constructed inside `<App/>` (App.tsx:79–192). Switch now lives inside `<App/>` as `<SwitchPoint>`, a child of `<BottomSheetModalProvider>`, branching between `<OnboardingStack/>` and `<Drawer.Navigator …>`. `AppWithMigrationWrapper` is unchanged. Updated: §0 scope wording, §2 event flow diagram, §4a #1–#4, §4f I_OB1 + I_OB2 + I_OB6, §4g rows for `AppWithMigrationWrapper` (now describes only the hydration hold) and new `App` row, §7 signal table, Scenarios A/B/C/G/G' rewritten to step through the in-App `<SwitchPoint>`, D1 rationale rewritten with the alternative explicitly considered and rejected. |
| CONCERN 1 | CONCERN | D11 / I_OB11 said `spacing.xxl=40` lands "in the SAME PR" with `theming.md` §1a edit. App code and theming.md are in different repos — structurally impossible (same problem theming.md I_UI8 already addressed). | **FIXED**. Replaced "same PR" language with the I_UI8 analogue in both D11 and I_OB11: app PR cites dev-team-repo commit SHA in description; dev-team-repo commit message cites app PR URL; splitting across review cycles forbidden; pipeline-reviewer enforces both citations. Also lifted as a discrete paired-edit instruction the planner MUST surface in HOW (§4h paragraph after the table; §10 Cleanup reminder #2). |
| CONCERN 2 | CONCERN | Method drift: §2 used `enqueueDownload(modelId)`; §4d / §4g / Scenarios used `startDownload()`. The actual public API screens call is unverified. | **FIXED**. Verified against source: `src/store/ModelStore.ts:990` defines `checkSpaceAndDownload = async (modelId: string) => …`. Call sites: `ModelCard.tsx:415`, `ChatPalModelPickerSheet.tsx:62`, `ProjectionModelSelector.tsx:108`, `ModelNotAvailable.tsx:52`. (`downloadManager.startDownload(model, destinationPath, authToken)` is the **internal** call inside `checkSpaceAndDownload`.) Chose `modelStore.checkSpaceAndDownload(modelId)` everywhere. Updated §0 (scope), §2 (event flow), §4d (paragraph + source citation), §4g (ModelStore row), §5 (single-writer table), §9e (failure path with source line), Scenarios A/C/G/G'. |
| SUGGESTION 1 | SUGGESTION | Three name drifts: `ensurePipPal` vs `initializePipPal`, download method (Concern 2), `completeOnboarding` signature (`{topics}` vs `{topics, modelId}`). | **FIXED**. (a) `initializePipPal` everywhere — matches Lookie precedent (`initializeLookiePal` at `PalStore.ts:739`). Updated §1b (paragraph), §2, §4d, §4g, §5, §9g, Scenarios A/C/G/G', D3 rationale. (b) Download method resolved by Concern 2. (c) `completeOnboarding({topics, modelId})` where `modelId: string \| null` everywhere. Updated §2, §4e, §5 (single-writer table + new explicit signature paragraph), §9j, Scenarios A/C/G/G'. |
| SUGGESTION 2 | SUGGESTION | No scenario covers Skip on screen 6 (exercises §4d Skip path → Pip seeded with no defaultModel). | **FIXED**. Added Scenario G' (paragraph-length): user reaches Onboarding6, taps Skip, `completeOnboarding({topics, modelId: null})`, `initializePipPal` is a no-op (Pip pre-seeded by `PalStore.initialize`), Pip stays `defaultModel=undefined`, no `checkSpaceAndDownload` call, `<SwitchPoint>` swaps to Drawer. |

### Drift re-check on touched files

- `App.tsx` (worktree) read at full length. Provider tree confirmed: `GestureHandlerRootView → SafeAreaProvider → KeyboardProvider → PaperProvider → L10nContext.Provider → MarkdownProvider → NavigationContainer → BottomSheetModalProvider → Drawer.Navigator`. `AppWithMigrationWrapper` confirmed unchanged: hydration-only gate (App.tsx:251–260). `<App/>` is observer (App.tsx:61). Interp B fits cleanly under `<BottomSheetModalProvider>` with no provider duplication.
- `ModelStore.ts` (worktree) read for the download API surface. Public method is `checkSpaceAndDownload(modelId: string)` (line 990); internal `downloadManager.startDownload(model, dest, authToken)` is wrapped at line 1007. All 4 production call sites in the worktree (ModelCard, ChatPalModelPickerSheet, ProjectionModelSelector, ModelNotAvailable) use `checkSpaceAndDownload(modelId)`. WHAT updated to match.
- `PalStore.ts` (worktree) read for the seed-pal pattern. `initialize()` (line 76) calls `initializeLookiePal()` (line 89, defined private at line 739). `initializePipPal` named to match.
- `context/architecture/theming.md` I_UI8 (line 499) read for the cross-repo handshake language. D11 / I_OB11 wording aligned with it verbatim in spirit.
- No drift detected against the three reference architecture files; this WHAT is still a clean delta on top of them and amends only `theming.md` §1a (one line: `xxl=40` added to the Spacing axis) via the I_UI8 handshake.

### Revision summary for round-2 critic

The structural ambiguity in §4a is resolved — the onboarding switch is firmly **inside** `<App/>`, below the single provider tree, branching between `OnboardingStack` and `Drawer.Navigator`. No provider duplication, no two-NavigationContainer hazard. I_OB6 is trivially satisfied because the Drawer simply isn't rendered while onboarding is active. The spacing-xxl handshake now uses the same cross-cite mechanism FOU-115 established in theming.md I_UI8 and is called out as a discrete paired-edit step the planner must emit in HOW. The model-download call uses `modelStore.checkSpaceAndDownload(modelId)` everywhere, matching the public API used by every other screen in the worktree. Pip seeding uses `initializePipPal` matching the Lookie precedent. `completeOnboarding({topics, modelId})` is the single signature (modelId: string | null) used consistently across §2, §4e, §5, §9j, Scenarios A/C/G/G'. Scenario G' covers the Skip-on-screen-6 path and exercises the §4d "Pip seeded with no defaultModel" leaf. No new (?) markers; quality checklist re-run; no drift introduced against the three reference architecture files.
