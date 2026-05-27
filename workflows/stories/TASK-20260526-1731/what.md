# FOU-116 Onboarding flow — WHAT (delta)

Story: TASK-20260526-1731 — Phase 3a slice of FOU-112 redesign rollout.

**This is the first FOU-112 slice that produces real screens against the FOU-114 token + FOU-115 DS layer.** It is a greenfield flow: the app has no onboarding today. The contents of this delta were initially promoted to `context/architecture/onboarding.md` in commit `a448d3f` (Round 2 LGTM). Round 3 changes the contract materially (see Review History) — the promoted flow doc MUST be updated in a paired follow-up commit using the I_UI8 cross-cite handshake (dev-team commit SHA ↔ app PR URL); see §10 cleanup reminder #1.

Consumer references only (do NOT modify in this slice except where I_OB11 / D11 explicitly amends `theming.md` §1a):
- `context/architecture/theming.md` — token + DS surface (FOU-114 / FOU-115). Two paired line edits required in §1a: Spacing axis gains `xxl` (D11 / I_OB11), Color axis gains `accent.peach` (D15 / I_OB12). Both via the I_UI8 cross-cite handshake.
- `context/architecture/chat-flow.md` — destination Chat session model after onboarding completes.
- `context/architecture/pals-and-talents.md` — `Pal` data model used by the seeded recommended pal.

Canonical inputs (LOCKED, per `context/redesign/FOU-112-rollout.md` §1):
- Figma file `RZxDJea4t6jnBZrV4YBacF`, page `0:1` "App design".
- Light frames: `884:28223` (Onboarding section, 6 screens + Splash + Homepage-first-time).
- Dark frames: `3011:25220` (Onboarding 7–12 = light 1–6 dark renders).
- Variable defs read for the section (verified 2026-05-26 via Figma MCP `get_variable_defs`; Round 3 re-confirmed 2026-05-27): every value used below resolves to a token name already present in `theme.colors.*`, `theme.typography.*`, `theme.spacing.*`, `theme.radius.*`, `theme.stroke.*` with one new exception subject to the I_UI8 cross-cite handshake: `Color/Accent/Peach` (I_OB12 / D15 — token + theming.md §1a both pending). The Round-2 `Spacing/XXL=40` handshake (I_OB11 / D11) is already satisfied on both sides — `src/theme/tokens/spacing.ts` ships `xxl: 40` and `context/architecture/theming.md` §1a Spacing axis lists it (commit `a448d3f`, 2026-05-26); I_OB11 / D11 are retained as historical anchors below but require no further action.

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
- Tokens / typography / DS-component changes beyond: (a) the new `Stepper` DS component (D10), (b) the new `HighlightText` DS primitive (I_OB12 / §4h), and (c) `colors.accent.peach` (I_OB12 / D15 — token + theming.md §1a both pending). `spacing.xxl=40` is already satisfied on both sides (commit `a448d3f`) — I_OB11 / D11 remain as historical anchors only. Otherwise the slice MUST consume the existing `theme.*` surface (theming.md §1a–§1d).
- Architecture-doc updates to `chat-flow.md`, `pals-and-talents.md`. `theming.md` §1a receives one paired line edit via the I_UI8 handshake: `accent.peach` (D15 / I_OB12). The `spacing.xxl` (D11 / I_OB11) paired edit already landed in commit `a448d3f` and is not redone here. The promoted `onboarding.md` flow doc (commit `a448d3f`) receives a Round-3 update covering all 14 corrections in the Review History.

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
  selectedTopic : TopicKey | null     // screen 5 single-select chip grid; tap = auto-advance to screen 6
  selectedModelId: string | null      // screen 6 radio selection (must resolve in ModelStore default catalogue)
```

```
TopicKey =
  | 'smartchat'        // speech-bubble icon — general everyday chat
  | 'coding'           // angle-bracket `<>` icon
  | 'education'        // books icon
  | 'roleplay'         // theater-masks icon
  | 'creative_writing' // feather icon
  | 'else'             // escape-hatch "Looking for something else?" — outlined chip, no icon, no preference recorded
  // (P) Closed union — verbatim from Figma frames 884:28282 (light) / 3011 dark band.
  // Labels + icons are designer-owned; engineering owns the union and the chip set.
  // The 'else' chip is rendered differently (outlined, no icon) and on tap auto-advances
  // to screen 6 WITHOUT writing a topic preference (selectedTopic stays null + the snapshot
  // is written as empty array on completion).
```

`selectedTopic` is captured but **not used to alter the recommended pal in this slice** — the recommended pal is always seeded `Pip` (see §4d). The pick persists into `uiStore.onboardingTopicsSnapshot` (P) on completion so the post-onboarding Homepage (FOU-117) can use it later as a future-pal-suggestion signal. The snapshot is written exactly once at completion and never edited after; if `selectedTopic === null` (user tapped 'else' or skipped screen 5) the snapshot is the empty array.

```
UIStore (P, persisted)
  hasCompletedOnboarding   : boolean
  onboardingTopicsSnapshot : TopicKey[]   // (P) frozen at completion; length 0 or 1 in this slice;
                                          //     kept as an array to leave headroom for FOU-117 multi-tag work
```

### 1b. PalStore additions

A new seeded system pal `Pip`, mirroring the existing `Lookie` seeding pattern (`src/store/PalStore.ts:739` `initializeLookiePal`).

```
SystemPip (P)
  type        : 'local'
  name        : 'Pip'
  description : <designer-owned copy>
  systemPrompt: <designer-owned starter prompt — friendly general-assistant tone>
  defaultModel: <Model — one of three quant variants of a single base model
                 from ModelStore.defaultModels; see RECOMMENDED_PAL_MODEL_SET below — D2>
  capabilities: {}                           // no video, no special
  color       : [<P: designer palette>]
  source      : 'local'
```

Pip is created idempotently from `PalStore.initialize()` after the database is loaded, by a private `initializePipPal()` paired with the existing `initializeLookiePal()` (matches the Lookie precedent — see Suggestion 1 resolution in Review History).

```
RECOMMENDED_PAL_MODEL_SET (P)
  // Three quant variants of a SINGLE base model (per Figma frame 885:29519 / 887:30011).
  // The radio rows render side-by-side as Quick / Balanced / Best.
  //
  //   Quick    : Q2_K       — smallest, fastest, lowest quality
  //   Balanced : Q4_K_M     — recommended (peach-tinted card + "Recommended" badge)
  //   Best     : Q8_0       — highest quality of the three
  //
  // Base model: Llama-3.2 1B Instruct. The Q8_0 variant already exists in
  // src/store/defaultModels.ts (id `hugging-quants/Llama-3.2-1B-Instruct-Q8_0-GGUF/llama-3.2-1b-instruct-q8_0.gguf`).
  // The Q2_K and Q4_K_M variants do NOT exist in defaultModels yet; the implementer
  // adds them at HOW time using the same shape (author/repo/filename/url pattern).
  //
  // D2 constraint: every member MUST resolve to a stable Model.id in defaultModels at
  // HOW time. If the implementer cannot source Q2_K / Q4_K_M Llama-3.2-1B GGUFs from
  // huggingface (e.g. only Q4_K_M exists), they pick the closest-quant variant that
  // does exist and update §4h's RECOMMENDED_PAL_MODEL_SET note in onboarding.md, NOT
  // re-architect the screen.
  //
  // Card metadata per row (rendered by screen 6, NOT by RadioSection):
  //   line 1 (title):    "Llama 3.2 1B · Q<N> · <size>"   (e.g. "Llama 3.2 1B · Q4_K_M · 770 MB")
  //   line 2 (subtitle): "≈<X> tok/s on your phone"        (OPTIONAL — see §9r;
  //                      no synchronous device-capability tok/s estimator
  //                      exists in the worktree today. If a synchronous hint is
  //                      added later, the subtitle includes it; otherwise the
  //                      subtitle ships without the "≈X tok/s" clause and
  //                      renders an empty second line or is omitted entirely —
  //                      no orphan "≈ tok/s" string.)
```

The "Recommended" middle-tier badge is a small pill drawn on the Balanced card only. Visual: peach-tinted background (see §4h / I_OB12), `theme.typography.captionM`, foreground `colors.text`. The badge is a sibling node of the RadioSection title row, NOT a RadioSection feature — RadioSection stays unchanged from FOU-115.

### 1c. Glossary

- **Hydration hold** — pre-`<PaperProvider>` neutral `View` rendered while `mobx-persist-store` is loading `UIStore` from AsyncStorage (theming.md §4c #4 / I10). NOT a splash screen. Stays neutral; reads from `Appearance.getColorScheme()`. Out of scope here; mentioned only to delineate.
- **Brand splash** (this slice) — the **post-hydration** branded screen at Figma `884:28349`. Rendered as the initial route of the Onboarding stack when `hasCompletedOnboarding === false`. Transitions to Onboarding-1 after a fixed minimum dwell (D6).
- **Stepper** — the 4-dot progress indicator on screens 1–4 (Figma `896:29130`-band). Note: screens 5 and 6 do NOT show a stepper in the Figma frames (screen 5 has a fullwidth header; screen 6 has the recommended-pal header). The stepper is therefore visually 1-of-4, 2-of-4, 3-of-4, 4-of-4 across screens 1–4 only.
- **Topic** — a category the user picks on screen 5. Closed union of 6 keys (`TopicKey`), single-select. Tapping a chip auto-advances to screen 6; there is no Continue button on screen 5 (D7).
- **Recommended tier** — the middle (Balanced / Q4_K_M) model card on screen 6. Renders with a peach-tinted background and a "Recommended" pill badge per Figma.
- **Audio button** — a 40×40 IconButton (headphones glyph) in the top-right of screens 5 and 6 (in the same slot that screens 1–4 use for Skip). On tap, the screen's title + body text is announced via `AccessibilityInfo.announceForAccessibility(text)`. Side-effect only; no app state.
- **HighlightText** — a Text primitive that renders one or more inline phrases against a peach pill background. Used inline within screen 2 / 3 / 4 body copy (see §4h).
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
              ─Next ("Show me Around →")→ navigate('Onboarding2')   (P)
              ─Next ("Next →")        → navigate('Onboarding3')     (P)
              ─Next ("Got it →")      → navigate('Onboarding4')     (P)
              ─Next ("Get Started →") → navigate('Onboarding5')     (P)
                 [Skip button on screens 1–4 → completeOnboarding({topic, modelId: null})]
                 [Back chevron on screens 2–6 → navigation.goBack()]
                 [Audio button on screens 5+6 → AccessibilityInfo.announceForAccessibility(screenText); D14]
              ─chip-tap (any of 6) → setOnboardingTopic(key) + navigate('Onboarding6')  (P; D7)
              ─Finish ("Download Pip (<size>) ⬇")
                    → uiStore.completeOnboarding({topic, modelId})    (P; topic: TopicKey | null, modelId: string | null)
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
  pre-stack ─dwell≥SPLASH_MIN_DWELL_MS→ 1
  1 ─Next→ 2 ─Next→ 3 ─Next→ 4 ─Next→ 5 ─chip-tap→ 6 ─Finish→ (completed; OnboardingStack unmounts)
       ↑                ↑                ↑                ↑
       └─Back←──────────┴─Back←──────────┴─Back←──────────┘
  Skip (any of 1–4) → (completed; OnboardingStack unmounts)
```

| State                          | User-visible feedback                                                                         |
| ------------------------------ | --------------------------------------------------------------------------------------------- |
| `pre-stack` (hasCompletedOnboarding=false, hydrated) | Brand splash visible for at least `SPLASH_MIN_DWELL_MS`.                                       |
| `Onboarding1`                  | Welcome screen; Stepper 1/4; primary action "Show me Around →" (Back: none — first screen; Skip: top-right).      |
| `Onboarding2`                  | "Anytime, Anywhere." screen; Stepper 2/4; Back chevron + primary "Next →"; Skip top-right.                       |
| `Onboarding3`                  | "Smaller, but yours." screen; Stepper 3/4; Back chevron + primary "Got it →"; Skip top-right.                    |
| `Onboarding4`                  | "Nothing leaves your phone." screen; Stepper 4/4; Back chevron + primary "Get Started →"; Skip top-right.        |
| `Onboarding5`                  | Topic chip grid (6 options, single-select); NO Stepper; NO bottom bar; **chip-tap auto-advances** (D7); Back chevron + Audio button in top header. |
| `Onboarding6`                  | Pip headline + 3 model radio cards (Quick / Balanced / Best); NO Stepper; Back chevron + primary "Download Pip (<size>) ⬇"; Finish enabled only when a radio is selected (D8); Audio button top-right (NO Skip — only completion path is download). |
| `completed`                    | OnboardingStack unmounts; Drawer.Navigator mounts in the same provider tree; Chat screen visible (FOU-117 first-time empty state — out of scope here, `ChatScreen` unchanged in this slice). |

Skip is allowed on steps 1–4 ONLY. Figma confirms: screens 1–4 carry a `Buttons` "Skip" instance in their top-right header slot; screens 5 and 6 replace that slot with a 40×40 headphones IconButton ("Audio button" — D14). On Skip, `selectedTopic` is `null` and `selectedModelId` is `null`; the user can pick later from Pals / Models drawer entries. Screen 6 has NO Skip — the only forward path on screen 6 is to pick a model and tap the download primary. Screen 5 has NO Continue button; chip-tap auto-advances to screen 6 (D7).

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
  Stepper        (only screens 1–4, at y=30)                       — Figma 896:29130
  Skip button    (only screens 1–4, at x=331,y=16)                 — Figma "Buttons" 46×28 instance
  Audio button   (only screens 5+6, at x=337,y=12)                 — 40×40 IconButton, headphones glyph
  Visual         (the illustration; per-screen geometry)
  Content        (title + description with inline italic + peach-pill accents)
Bottom (y=763, height=89 for screens 1–4 + screen 6; ABSENT on screen 5)
  Buttons row    (Back IconButton 48×48 + primary Button 305×48)   — Figma 888:33xxx
  Home Indicator (presentational, system)
```

Screen-specific deltas:

| Screen | Frame | Visual | Title (italic accents marked with `*…*`) | Body | Top-right | Bottom bar primary |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | `884:28224` | 112×112 hero (same artwork as splash mark — engineering verifies node equality in HOW) | "Meet your *pals*." | Figma-filled (port verbatim) | Skip | "Show me Around →" |
| 2 | `884:32529` | phone-with-pals illustration | "*Anytime, Anywhere.*" (both words italic) | Figma-filled, contains peach-highlighted phrase **"No internet, no signal"** | Skip | "Next →" |
| 3 | `885:29142` | phone-card + cloud-card pair | "*Smaller,* but yours." | Figma-filled, contains peach-highlighted phrase **"quick and private"** | Skip | "Got it →" |
| 4 | `885:29519` | phone + shield group | "Nothing *leaves* your phone." | Figma-filled, contains peach-highlighted phrase **"No accounts. No cloud. No tracking."** | Skip | "Get Started →" |
| 5 | `884:28282` | 6× chip in a 2-col grid (5 icon chips + 1 escape-hatch outlined chip) | "What's your pal for?" | Figma-filled (port verbatim) | **Audio** | NO bottom bar (D7 — chip-tap auto-advances) |
| 6 | `887:30011` | Pip mascot 66×62 + big italic "*Pip*" headline + device-info chip | "We found perfect pal for you - a friendly everyday companion. Smart enough for most things, light enough for any phone." (port from Figma verbatim — see §4j) | **Audio** | "Download Pip (<selected-model-size>) ⬇" (download glyph; primary disabled until a quant is selected) |

Notes:

1. Italic accents (the `*…*` segments above) render in Fraunces-Italic against `theme.typography.headlineH1` / `headlineH2` — per theming.md §4d.2 they fall back to `Inter-Medium` with `fontStyle: 'italic'` for the non-Latin language set (matches the existing D5 fallback for `styledXs`).
2. The peach-highlighted phrases on screens 2 / 3 / 4 use the new `HighlightText` primitive against the new `theme.colors.accent.peach` token (I_OB12 / §4h).
3. Screen 5's bottom bar is **physically absent** in the Figma frame — there is no Continue button drawn at all. Engineering ships it absent; chip-tap is the sole forward control (D7). The Audio + Back buttons live in the top header.
4. The Back chevron lives in the bottom bar's left slot on screens 2, 3, 4 and 6. On screen 5 (no bottom bar) the Back chevron lives in the top-left header slot (verified against Figma frame `884:28282`).
5. Screen 6's primary button uses a download icon (existing `IconButton` `icon="download"` glyph from the DS set) and renders the selected model's human-readable size in the visible label (e.g. "Download Pip (770 MB) ⬇"). The size is read from the same `Model` field the existing `ModelCard.tsx` row uses (`size` / `params` — engineering picks the existing field in HOW).
6. Screen 6 carries a real device-info chip (not the static "Local · on-device" placeholder shipped in the wireframe). Format: `${deviceName} · ${ramGB} GB RAM · ${freeGB} GB free`. Source: `react-native-device-info` (already a project dependency — `package.json:67`, used in `BenchmarkRunnerScreen.tsx`, `utils/index.ts`, `utils/deviceCapabilities.ts`, `AboutScreen.tsx`). The chip is presentational; if any of the three fields is unavailable at read time, the chip falls back to whichever subset is available (e.g. "iPhone 13 Pro · 6 GB RAM" — no `·` orphan).

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

(P) The recommended model on screen 6 is one of the three quants in `RECOMMENDED_PAL_MODEL_SET` (D2). The middle (Balanced / Q4_K_M) card is pre-rendered with a peach-tinted background and a "Recommended" pill badge, but it is NOT pre-selected — the user must tap a radio to enable the download primary (D8). Once picked, the chosen variant is registered in `ModelStore` (using existing model registration paths) AND its `id` is written to `Pip.defaultModel.id`. Pip thereby "knows" which model to use.

(P) The user-picked download is enqueued via `modelStore.checkSpaceAndDownload(modelId)` (existing public API; signature confirmed against `src/store/ModelStore.ts:990` and call sites `ModelCard.tsx:415`, `ChatPalModelPickerSheet.tsx:62`, `ProjectionModelSelector.tsx:108`, `ModelNotAvailable.tsx:52`). It accepts the model `id` string and resolves space/auth/destination internally. Onboarding does NOT block on the download completing; the user lands on Homepage with the download in-flight (visible via the existing Models screen).

(P) If the user picks no model (Skip path on screens 1–4 only — screen 6 has no Skip), Pip exists with `defaultModel=undefined`; the user must pick a model later via the Models screen. This matches the existing post-install state of the app. There is no "screen 6 Skip" path.

### 4e. Onboarding-skipped invariants

(P) Skipping at any step (screens 1–4 ONLY — screens 5 and 6 have no Skip):
- Always flips `hasCompletedOnboarding = true` via `completeOnboarding({topic: null, modelId: null})` (screen 5 has not been reached yet on any Skip-able step, so `selectedTopic` is `null`).
- Captures the topic snapshot in `uiStore.onboardingTopicsSnapshot` as the empty array.
- Does NOT seed Pip differently; Pip is seeded by `PalStore.initialize()` regardless of onboarding outcome.
- Does NOT enqueue any model download (no `checkSpaceAndDownload` call).

### 4f. Hard invariants

- **I_OB1 (single-shot flow)**: Onboarding mounts only when `uiStore.hasCompletedOnboarding === false` AND `mobx-persist-store` has hydrated `UIStore`. Once `hasCompletedOnboarding` flips to `true`, the `<SwitchPoint>` re-renders and the OnboardingStack subtree unmounts; it never re-mounts in this app lifetime.
- **I_OB2 (no Drawer overlap)**: While the OnboardingStack is mounted, `Drawer.Navigator` is NOT rendered by `<SwitchPoint>` and therefore does not mount its screens. The two are mutually exclusive children of the switch.
- **I_OB3 (token consumption only)**: Every onboarding screen consumes `theme.colors.*`, `theme.typography.*`, `theme.spacing.*`, `theme.radius.*`, `theme.stroke.*` from `useTheme()`. No raw hex, no raw px in `styles.ts` (lint-enforced by the existing `no-restricted-syntax` rule once the new files are inside `src/components/ui/**/styles.ts`; for screen-level `styles.ts` outside the DS namespace the lint rule does not apply, but tokens-only is still a soft contract enforced at code review).
- **I_OB4 (DS-only components)**: Onboarding screens consume only DS components (`Button`, `IconButton`, `Chip`, `RadioSection`, `Header`, `Stepper`, `HighlightText`, plus `Text` from RN Paper per the locked thin set). No legacy `src/components/*` import except where there is no DS equivalent (none expected in this slice). This is the first slice to put I_UI6 (testID freeze) into play at screen level.
- **I_OB5 (testID freeze)**: Every interactive element exposes a stable `testID` per §4l. Phase 4 / FOU-123 may extend but MUST NOT rename.
- **I_OB6 (no Drawer screens read OnboardingState)**: Because `Drawer.Navigator` is not rendered while onboarding is active (I_OB2), no Drawer screen can read `OnboardingState`. Conversely, once onboarding completes and the Drawer mounts, the only post-completion surfaces a Drawer screen reads are the two persisted UIStore fields (`hasCompletedOnboarding`, `onboardingTopicsSnapshot`); `OnboardingState` is the empty / reset shape by then.
- **I_OB7 (Pip seeding is idempotent and order-independent)**: `initializePipPal` MUST be safe to call multiple times in any order relative to `initializeLookiePal`; both must converge on the same `pals[]` regardless of arrival order.
- **I_OB8 (light + dark parity)**: Every screen renders against light tokens AND dark tokens with no visual regression vs the canonical Figma frame. Verified per screen in HOW.
- **I_OB9 (RTL + non-Latin verified per slice)**: On `language ∈ {he, fa}`, screen layout mirrors (RN `I18nManager` already enabled — verified by FOU-114) AND headlines fall back to Inter per theming.md §4d.2.
- **I_OB10 (no telemetry / no auth)**: No network call originates from any onboarding screen.
- **I_OB11 (`spacing.xxl = 40` cross-cite handshake — SATISFIED)**: Historical anchor only. Figma uses `Spacing/XXL=40` for onboarding screens; the token was added to `src/theme/tokens/spacing.ts` (Round-2 work) and the matching `context/architecture/theming.md` §1a Spacing-axis entry landed in dev-team commit `a448d3f` (2026-05-26). Both sides of the I_UI8 handshake are on disk; no further paired-edit step in HOW. Retained here so future readers can trace the original handshake against the FOU-115 I_UI8 precedent.
- **I_OB12 (`colors.accent.peach` cross-cite handshake)**: Figma uses a peach/beige accent fill for (a) the inline HighlightText pills on screens 2 / 3 / 4 body copy, and (b) the "Recommended" middle-tier card background + badge on screen 6. The new token addition in `src/theme/tokens/colors.ts` (light + dark bindings, sourced from the canonical Figma file `RZxDJea4t6jnBZrV4YBacF` per I2) and the matching amendment to `context/architecture/theming.md` §1a (extend the Color axis to list the `accent.peach` binding) follow the same I_UI8 paired-edit handshake as I_OB11. PR description cites dev-team-repo commit SHA; dev-team-repo commit message cites app PR URL. Splitting across review cycles is forbidden. The planner MUST emit this as a discrete paired-edit step in HOW alongside the `spacing.xxl` paired edit (D15).
- **I_OB13 (screen-5 single forward control)**: Screen 5 has exactly ONE forward control: tapping a topic chip. There is no Continue / primary button. The bottom bar is not rendered. The Back chevron and Audio button live in the top header (§4b note 4). E2E specs MUST assert the absence of `onboarding-primary` on screen 5.
- **I_OB14 (screen-6 has no Skip)**: Screen 6 has no Skip control. The only completion path off screen 6 is to pick a model radio (enabling the download primary) and tap the primary. Skip is only valid on screens 1–4. Pipeline-reviewer enforces this against §4i (no `onboarding-skip` testID on screen 6's tree).

### 4g. What each component / module renders

| Component / module | Renders / produces | Does NOT render / produce |
| --- | --- | --- |
| `AppWithMigrationWrapper` (unchanged from (C)) | (C) The hydration hold while `!isHydrated(uiStore)`; `<AppWithMigration><App/></AppWithMigration>` once hydrated. | (P) The onboarding switch — that moves down to `<App/>`. |
| `App` (extended) | (P) The provider tree (unchanged from (C)) followed by a single observed `<SwitchPoint>` child of `<BottomSheetModalProvider>`. `<SwitchPoint>` reads `uiStore.hasCompletedOnboarding` and renders either `<OnboardingStack/>` or `<Drawer.Navigator …>` (with the existing screens). | Theme construction (still in `useTheme()`); the hydration hold (lives one level up, unchanged from (C)). |
| `OnboardingStack` | (P) `createNativeStackNavigator()` with `headerShown: false` and 7 routes: `Splash`, `Onboarding1`…`Onboarding6`. Shares the `<NavigationContainer>` provided by `<App/>`. | A separate `<NavigationContainer>` / `<PaperProvider>` / `<BottomSheetModalProvider>` (it shares the App-level instances). Per-screen state (lives in `uiStore.onboardingState`); side effects (caller does that on Finish). |
| `SplashScreen` (P) | The brand mark at canvas centre per Figma `884:28349`. Triggers `navigate('Onboarding1')` after `SPLASH_MIN_DWELL_MS` (D6). | A neutral background hold (that's the FOU-114 hydration hold, pre-`<PaperProvider>`). |
| `Onboarding{N}Screen` (P, N=1..6) | The per-screen layout in §4b: header (Stepper on 1–4 + Skip on 1–4 + Audio on 5+6), Visual, Content, Bottom bar (absent on 5). Consumes DS components only. Italic title accents via `fontStyle: 'italic'` on `theme.typography.headlineH1/H2`; inline pill phrases via `HighlightText`. | Navigation logic beyond `navigation.navigate(prev|next)` and `uiStore.completeOnboarding`. State of any kind beyond the per-screen mount effect that writes `currentStep`. |
| `Stepper` (P, new DS) | A row of dot markers per `current/total`. Token-bound. | State (purely presentational). |
| `HighlightText` (P, new DS) | A `<Text>` (or `<Text>`-wrapping) primitive that renders one or more inline phrases against a peach pill background (`theme.colors.accent.peach`). Accepts a `phrases: string[]` prop (or a children + segments shape — engineering picks the cleaner API at HOW time) and finds-and-highlights occurrences in the body copy. Token-bound. | Layout reflow (the highlighted run is `display: inline` semantically — RN's `<Text>` nested-`<Text>` model). |
| `Audio button` (P, per-screen IconButton 40×40, screens 5+6) | A side-effect-only IconButton (headphones glyph). On press: `AccessibilityInfo.announceForAccessibility(screenText)` where `screenText` = title + body of the active screen, joined. No state, no store write. (D14) | Any text-to-speech engine — this uses the platform screen-reader queue, not the TTS feature flow. |
| `uiStore` (extended) | `hasCompletedOnboarding`, `onboardingTopicsSnapshot` (both persisted); `onboardingState` (in-memory). Single-writer methods: `setOnboardingStep(n)`, `setOnboardingTopic(key: TopicKey \| null)`, `setOnboardingModelId(modelId: string \| null)`, `completeOnboarding({topic, modelId})`, `resetOnboarding` (test-only). | Any read of `palStore` / `modelStore`. The onboarding completion fans out via direct calls from the screens; UIStore is not a router. |
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
| `Color/Accent/Peach` (or similar, per the inline HighlightText pills + the Recommended-tier card background) | `colors.accent.peach` (**NEW**, see I_OB12 — paired-edit handshake) |
| `Headline/H1` (Fraunces 36 / 1.4 mult) | `typography.headlineH1` (absolute lineHeight 50 — theming.md §4a #4) |
| `Title/sm` (Inter Medium 16/22) | `typography.titleS` (closest existing) — engineering verifies the size match in HOW |
| `Body/md` (Inter Regular 15/28) | `typography.bodyM` |
| `Body/sm` (Inter Regular 13/20) | `typography.bodyS` |
| `Caption/xs` (Inter 10/18) | `typography.captionS` |
| `Caption/sm` (Inter Medium 11/18) | `typography.captionM` |
| `Spacing/{None,XXS,XS,S,SM,M,ML,L,XL,XXL}` (0..40) | `spacing.{none,xxs,xs,s,sm,m,ml,l,xl,xxl}` — `xxl=40` landed under I_OB11; both sides satisfied (commit `a448d3f`) |
| `Radius/{XS,S,M,ML,L,XL,XXL}` (4..40) | `radius.{xs,s,m,ml,l,xl,xxl}` (per theming.md §1a Radius rename) |
| `Stroke/{xs,sm,md,lg}` | `stroke.{xs,sm,md,lg}` |

I_OB11 (`spacing.xxl`) — already satisfied on both sides (see §4f). No paired-edit step in HOW.

I_OB12 — paired-edit handshake (see §4f). The app PR adds the `accent.peach` binding to `src/theme/tokens/colors.ts` (light + dark values, sourced verbatim from the canonical Figma file per I2); the dev-team-repo commit amends `context/architecture/theming.md` §1a to list `accent.peach` in the Color axis. Uses the I_UI8 cross-cite mechanism (PR description cites dev-team commit SHA; dev-team commit message cites app PR URL; splitting across review cycles forbidden).

**Italic title accents (typography contract — Figma-faithful).** Each onboarding title carries a Fraunces-Italic accent fragment (the `*…*` spans in §4b's table). Implementation: a child `<Text style={{fontStyle: 'italic'}}>` nested inside the parent `<Text>` (which carries `theme.typography.headlineH1` / `headlineH2`). For the non-Latin locale set (`{fa, he, ja, ko, ru, uk, zh, zh_Hant}` per theming.md §4d.2), Fraunces-Italic falls back to `Inter-Medium` with `fontStyle: 'italic'` — same fallback shape as D5's existing handling for `styledXs`. No new font cuts ship in this slice.

**Body-copy pill highlights (HighlightText contract).** Per-screen highlighted phrases (Figma-verified, port verbatim):

| Screen | Phrase rendered in `colors.accent.peach` pill |
| --- | --- |
| 2 | "No internet, no signal" |
| 3 | "quick and private" |
| 4 | "No accounts. No cloud. No tracking." |

The highlighted phrase MUST be a contiguous slice of the body copy. The phrase is l10n-keyed (`onboarding.screen<N>.body.highlight`) and the rendering primitive walks the body copy to wrap the matching span. If the translated body does not contain the keyed substring at HOW time, the implementer falls back to rendering the body without a pill (§9p) rather than crash.

### 4i. testID surface (frozen here)

Per `context/redesign/FOU-112-rollout.md` §5 testID-freeze contract. This is what E2E observes; Phase 4 may extend at the leaves but MUST NOT rename.

| Surface | `testID` |
| --- | --- |
| Splash screen root | `onboarding-splash` |
| Onboarding screen root (N=1..6) | `onboarding-screen-<N>` |
| Stepper root (screens 1–4) | `ui-stepper` (DS default) |
| Stepper dot (i=1..total) | `ui-stepper-dot-<i>` |
| Skip button (screens 1–4 only) | `onboarding-skip` |
| Audio button (screens 5+6 only) | `onboarding-audio` |
| Back chevron (screens 2–6) | `onboarding-back` (same testID across slots — bottom-bar left on 2/3/4/6, top-left header on 5 per §4b note 4) |
| Primary button (screens 1–4 + screen 6 ONLY — screen 5 has no primary, I_OB13) | `onboarding-primary` |
| Topic chip (screen 5, key ∈ TopicKey) | `onboarding-topic-<key>` (keys: `smartchat`, `coding`, `education`, `roleplay`, `creative_writing`, `else`) |
| Recommended-quant model radio (screen 6, modelId) | `onboarding-pip-model-<modelId>` |
| Device-info chip (screen 6, presentational) | `onboarding-device-chip` |
| First-time homepage destination marker | (none — the homepage proper is FOU-117 scope and freezes its own testIDs there) |

`accessibilityLabel` defaults: every interactive element above gets an l10n-keyed label (see §4j). For the Stepper, see §4c #3.

### 4j. l10n contract

(P) New keys under `onboarding.*` in `src/locales/en.json` (English only — translators pick up via Weblate per the project's locale workflow).

```
onboarding.splash.title                  // optional brand subtitle (engineering may omit if Figma has no text node)
onboarding.screen1.title                 // "Meet your pals."           — accent: "pals"
onboarding.screen1.body                  // Figma-filled (port verbatim)
onboarding.screen1.cta                   // "Show me Around"
onboarding.screen2.title                 // "Anytime, Anywhere."        — entire title italic
onboarding.screen2.body                  // Figma-filled (port verbatim)
onboarding.screen2.body.highlight        // "No internet, no signal"   (peach pill)
onboarding.screen2.cta                   // "Next"
onboarding.screen3.title                 // "Smaller, but yours."       — accent: "Smaller,"
onboarding.screen3.body                  // Figma-filled (port verbatim)
onboarding.screen3.body.highlight        // "quick and private"        (peach pill)
onboarding.screen3.cta                   // "Got it"
onboarding.screen4.title                 // "Nothing leaves your phone." — accent: "leaves"
onboarding.screen4.body                  // Figma-filled (port verbatim)
onboarding.screen4.body.highlight        // "No accounts. No cloud. No tracking." (peach pill)
onboarding.screen4.cta                   // "Get Started"
onboarding.screen5.title                 // "What's your pal for?"
onboarding.screen5.body                  // Figma-filled (port verbatim)
onboarding.screen5.topic.smartchat       // "Smart Chat"
onboarding.screen5.topic.coding          // "Coding"
onboarding.screen5.topic.education       // "Education"
onboarding.screen5.topic.roleplay        // "Roleplay"
onboarding.screen5.topic.creative_writing// "Creative Writing"
onboarding.screen5.topic.else            // "Looking for something else?"  (escape hatch — outlined chip)
onboarding.screen6.title                 // "Pip"                       — big italic Fraunces headline
onboarding.screen6.body                  // "We found perfect pal for you - a friendly everyday companion. Smart enough for most things, light enough for any phone." (port from Figma verbatim)
onboarding.screen6.cta.template          // "Download Pip ({{size}})"   — {{size}} interpolated from selected model
onboarding.screen6.model.quick.title     // "Quick"        (Q2_K)
onboarding.screen6.model.balanced.title  // "Balanced"     (Q4_K_M)  — also bears the "Recommended" badge
onboarding.screen6.model.best.title      // "Best"         (Q8_0)
onboarding.screen6.model.<key>.subtitle  // 3 entries — format "Llama 3.2 1B · Q<N> · <size> · ≈<X> tok/s on your phone" (size + tok/s computed, not l10n)
onboarding.screen6.recommended.badge     // "Recommended"
onboarding.back                          // accessibility label for the back chevron
onboarding.skip                          // visible label + accessibility label for Skip (screens 1–4)
onboarding.audio                         // accessibility label for the Audio button (screens 5+6)
```

(P) **All body / title / CTA copy is Figma-filled** — engineering ports the strings verbatim in HOW from the canonical Figma frames (`884:28223` light band; verify against `3011:25220` dark band — identical text). The pre-Round-3 "designer-pending" wording is removed; bodies are NOT pending. The remaining designer-ask is the Audio button's intent (does it announce title-only, title+body, or something narrated by the designer?) — engineering implements the title+body default per D14 and the designer may revise via a copy-only delta later. This is the sole entry remaining in `workflows/stories/TASK-20260526-1731/designer-asks.md` after Round 3.

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
| `uiStore.hasCompletedOnboarding` | `uiStore.completeOnboarding({topic, modelId})` (P; sets to `true`); `uiStore.resetOnboarding()` (P; **test-only**, dev/E2E flag-gated). |
| `uiStore.onboardingTopicsSnapshot` | `uiStore.completeOnboarding({topic, modelId})` — derives the snapshot from `topic` (`topic === null` ⇒ `[]`; otherwise `[topic]`). Written once, never edited after. `modelId` is forwarded to the screen-side `checkSpaceAndDownload` call, not persisted on UIStore. |
| `uiStore.onboardingState.currentStep` | `uiStore.setOnboardingStep(n)`, called by the relevant screen's mount effect. |
| `uiStore.onboardingState.selectedTopic` | `uiStore.setOnboardingTopic(key: TopicKey \| null)` (P) — single mutation entry; called by screen 5 on chip tap (which also triggers `navigation.navigate('Onboarding6')` in the same handler). |
| `uiStore.onboardingState.selectedModelId` | `uiStore.setOnboardingModelId(modelId)` (P). |
| `palStore.pals` (Pip entry) | `PalStore.initializePipPal()` (P) — idempotent create. Pip is otherwise edited like any user pal via `PalSheet` (existing path; out of scope here). |
| `modelStore.models` / `modelStore.downloads` | Existing single-writers in `ModelStore`. Onboarding only **calls** `modelStore.checkSpaceAndDownload(modelId)` (existing public API). |

`completeOnboarding({topic, modelId})` signature (P): `topic: TopicKey | null`, `modelId: string | null`. The screen-side caller is responsible for invoking `palStore.initializePipPal()` (idempotent — already called from `PalStore.initialize`) and, when `modelId !== null`, `modelStore.checkSpaceAndDownload(modelId)`. UIStore derives the snapshot from `topic` (null → `[]`, else `[topic]`) and writes only its own fields.

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
5. Onboarding1: italic-accent title "Meet your *pals*." + Figma body.
   User taps "Show me Around →". → Onboarding2.
6. Onboarding2: italic title "*Anytime, Anywhere.*" + body with peach pill "No internet, no signal".
   User taps "Next →". → Onboarding3.
7. Onboarding3: title "*Smaller,* but yours." + body with peach pill "quick and private".
   User taps "Got it →". → Onboarding4.
8. Onboarding4: title "Nothing *leaves* your phone." + body with peach pill
   "No accounts. No cloud. No tracking.". User taps "Get Started →". → Onboarding5.
9. Onboarding5: 6-chip grid renders (smartchat / coding / education / roleplay /
   creative_writing icons + outlined 'else' chip). No bottom bar; Audio + Back live in
   the top header. User taps the 'smartchat' chip:
     - setOnboardingTopic('smartchat')
     - navigation.navigate('Onboarding6')        (same handler — single forward control, D7)
10. Onboarding6: big italic "*Pip*" headline + Pip mascot + device-info chip
    ("iPhone 13 Pro · 6 GB RAM · 24 GB free") + 3 radio cards (Quick / Balanced / Best).
    The Balanced card carries a peach background + "Recommended" pill. None pre-selected.
    Primary "Download Pip" is disabled. NO Skip on this screen.
11. User taps the Balanced radio (Llama-3.2 1B Q4_K_M). Primary label updates to
    "Download Pip (770 MB) ⬇" and becomes enabled.
12. User taps the primary. Screen handler runs:
     - uiStore.completeOnboarding({topic: 'smartchat', modelId: '<balanced-id>'})
        → hasCompletedOnboarding := true (persisted)
        → onboardingTopicsSnapshot := ['smartchat']
     - palStore.initializePipPal()  (idempotent; if needed, updates Pip.defaultModel.id)
     - modelStore.checkSpaceAndDownload('<balanced-id>')  (existing API; enqueues download)
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
2. User taps top-right "Skip" (visible on screens 1–4).
3. uiStore.completeOnboarding({topic: null, modelId: null}) runs.
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
1. User taps the "Download Pip (<size>) ⬇" primary on screen 6 with
   selectedModelId='<llama-3.2-1b-q4_k_m-id>' (Balanced — Recommended).
2. Screen handler runs:
   - uiStore.completeOnboarding({topic: <selected on screen 5 — possibly null if user tapped 'else'>,
                                  modelId: '<llama-3.2-1b-q4_k_m-id>'})
   - palStore.initializePipPal() (idempotent)
   - modelStore.checkSpaceAndDownload('<llama-3.2-1b-q4_k_m-id>') begins (existing API; resolves
     destination/auth internally).
3. <SwitchPoint> swaps to Drawer.Navigator; user lands on Chat. Chat shows the existing empty state.
4. User opens Models drawer item → sees the chosen model in 'downloading' state.
5. When download completes, Pip is usable in Chat (selected via the existing
   pal/model selection flows — out of scope here).
```

### G'. **DELETED in Round 3.** Figma confirms screen 6 has no Skip control (I_OB14). The closest analogue
is "user reaches screen 6 then taps the system Back gesture or onboarding-back chevron all the way back to a Skip-able screen"
— but that's a sequence of normal Back taps + a Skip on screen 1–4, which Scenarios C and F already cover. Implementer
MUST mirror this deletion in the E2E spec (`onboarding.spec.ts`) — remove the screen-6 Skip test.

### G''. Screen-5 escape-hatch — user taps 'Looking for something else?'

```
1. User reaches Onboarding5.
2. User taps the outlined 'else' chip (no icon, escape-hatch style).
3. Screen handler runs:
   - setOnboardingTopic(null)               (the 'else' tap is treated as "no preference")
   - navigation.navigate('Onboarding6')
4. User picks a model on screen 6 and taps the primary.
5. completeOnboarding({topic: null, modelId: <id>}).
   - onboardingTopicsSnapshot := [].
6. <SwitchPoint> swaps to Drawer.Navigator. Chat visible.
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
| `uiStore.hasCompletedOnboarding` | `completeOnboarding({topic, modelId})` (and `resetOnboarding()` test-only). | `<SwitchPoint>` inside `<App/>` (gates Drawer vs OnboardingStack). | User has finished or skipped onboarding once. |
| `uiStore.onboardingState.currentStep` | `setOnboardingStep(n)` via screen mount-effect. | Stepper (`current` prop on screens 1–4); E2E for state observation. | The corresponding screen is active. |
| `uiStore.onboardingState.selectedTopic !== null` (or chip-tap event) | `setOnboardingTopic(key)` (called inline with `navigation.navigate('Onboarding6')` in screen 5's chip handler) | Screen 5 itself does not need to read this (chip-tap auto-advances); screen 6 reads via the snapshot at completion. | The user has tapped any of the 5 icon chips on screen 5 (the 'else' chip writes `null`). |
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
- **D7 (Screen 5 has no Continue — chip-tap auto-advances)**: Figma frame `884:28282` draws no bottom bar on screen 5 (no primary, no Back at the bottom). The single forward control is tapping a topic chip; the chip handler writes `selectedTopic` AND navigates to Onboarding6 in the same call. The 'else' (escape-hatch) chip writes `null` but still navigates. Back chevron and Audio button live in the top header. Alternative considered (the Round 1–2 reading): always render a disabled bottom-bar primary that enables on selection. Rejected because Figma is the source of truth and ships no bottom bar on screen 5; rendering a disabled primary would contradict the visual. I_OB13 carries the invariant.
- **D8 (Screen 6 primary disabled until a model radio is selected)**: The primary on screen 6 is labelled "Download Pip (<size>) ⬇" — its label is data-bound to the selected model's size, which only exists after a radio tap. Disabling until selection prevents a label-without-size state. There is no Skip on screen 6 (I_OB14); the only forward path is selection + tap. Scenario G' is deleted; the closest equivalent is Scenarios C and F (Skip on a screen 1–4).
- **D9 (Removed in Round 3.)** Previously "render screen 5 bottom bar disabled". Figma confirms the bottom bar is physically absent on screen 5; chip-tap is the sole forward control. D7 now carries the rule; I_OB13 enforces no `onboarding-primary` on screen 5.
- **D10 (`Stepper` lives in DS layer from this slice)**: Per theming.md §4g rules, a presentational, tokens-only, observation-free component belongs in `src/components/ui/`. Putting it outside the DS layer would breach I_OB4 (DS-only components from screens). It will gain non-onboarding consumers as soon as setup-style flows appear; pre-placing it in the DS namespace prevents a later move.
- **D11 (`spacing.xxl = 40` added to tokens — theming.md §1a amended via the I_UI8 cross-cite handshake)**: Figma section explicitly defines `Spacing/XXL=40` for use on onboarding screens. Adding it is mechanical + source-of-truth-driven (theming.md I2). Because app code (`src/theme/tokens/spacing.ts`) and architecture docs (`context/architecture/theming.md`) live in **different repos** linked by submodule, literal same-PR atomicity is structurally impossible — same constraint that theming.md I_UI8 already addresses for the FOU-115 rename. Therefore: app PR cites the dev-team-repo commit SHA that amends theming.md §1a in its description; the dev-team-repo commit cites the app PR URL. Splitting them across review cycles is forbidden. The planner MUST emit this paired-edit step explicitly in HOW; the pipeline-reviewer enforces both citations before approving the draft PR. I_OB11 carries the invariant.
- **D12 (No analytics / no telemetry)**: I_OB10 is non-negotiable; PocketPal has no analytics today and FOU-116 is the wrong slice to introduce them.
- **D13 (Onboarding state lives inside `UIStore`, not a new `OnboardingStore`)**: Single flow, single-shot, in-memory, shares lifetime with a persisted UIStore flag. A separate store doubles the persistence surface for zero benefit at this stage. Deferred-cleanup item recorded in §5 if a second flow shows up.
- **D14 (Audio button announces title + body via `AccessibilityInfo.announceForAccessibility`)**: Side-effect only; no new TTS engine, no app state. The button is in the top-right slot on screens 5+6 (the slot screens 1–4 use for Skip). Rationale: Figma frames place a headphones icon there; the cheapest meaningful behaviour is to push the screen text into the platform screen-reader queue (works with VoiceOver / TalkBack out of the box; degrades to silent on devices without an active reader). Alternative: actual TTS playback via the existing rn-speech engine. Rejected for this slice because it pulls TTS-engine wiring into onboarding (cross-cuts FOU-117 + future work) and Figma does not specify a voice / speed contract. The Audio-button intent is logged as the single remaining `designer-asks.md` entry; copy can be revised by a delta later.
- **D15 (`colors.accent.peach` token added; theming.md §1a amended via the I_UI8 cross-cite handshake)**: Same shape as D11 / I_OB11. The peach accent is the only new color binding; light + dark values are read directly from the canonical Figma file (`RZxDJea4t6jnBZrV4YBacF`) per I2. I_OB12 carries the cross-cite invariant. The planner MUST emit this paired-edit as a discrete step in HOW (paired with the D11 spacing.xxl edit — they MAY share the same dev-team-repo commit if the editor groups them, but the citations remain separable for review-evidence purposes).
- **D16 (`RECOMMENDED_PAL_MODEL_SET` = 3 quants of one base model, not 3 different models)**: Figma screen 6 (`887:30011`) shows three radio cards labelled Quick / Balanced / Best — same base model, different quants. The pre-Round-3 wireframe diverged from Figma by listing 3 different models (Llama-3.2-1B / Qwen-2.5-1.5B / SmolLM2-1.7B). Round 3 corrects this: base model = Llama-3.2 1B Instruct; quants = Q2_K (Quick) / Q4_K_M (Balanced — Recommended) / Q8_0 (Best). The Q8_0 variant exists in `defaultModels.ts` (verified — line 245); the Q2_K and Q4_K_M variants do NOT and must be added by the implementer at HOW time. If a quant is unsourceable from huggingface at HOW time the implementer picks the closest available variant and updates `onboarding.md` §4h's RECOMMENDED_PAL_MODEL_SET note (D2 escape hatch).

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

Onboarding1 has NO Back chevron per Figma (it is the first onboarding screen). Pressing system back (Android) is intercepted by the stack's `gestureEnabled: false` + a no-op `BackHandler` listener while on the first route. Result: nothing happens; the splash does NOT re-appear.

### 9g. Two `initializePipPal` invocations race

`PalStore.initialize` is called once in the store constructor; idempotency check (`pals.find(p => p.name === 'Pip' && p.source === 'local')`) ensures a re-entry does not double-seed. I_OB7.

### 9h. User reaches screen 6 before the canonical `RECOMMENDED_PAL_MODEL_SET` is loaded into `ModelStore`

`ModelStore.defaultModels` is a static const (`src/store/defaultModels.ts`) — present in memory from app start. No async dependency. The three model rows render synchronously.

### 9i. RTL: stepper dot order

`flexDirection: 'row-reverse'` when `I18nManager.isRTL`. The wide "current" dot still represents the same logical step (1..4 in document order), just visually mirrored. Manual verification in `he` is required.

### 9j. `__E2E__` mode bypass

E2E specs run against fresh installs and may want to skip onboarding for non-onboarding tests. Mechanism: an existing AutomationBridge call (`__E2E__` flag) calls `uiStore.completeOnboarding({topic: null, modelId: null})` synchronously before navigation mounts. This is an additive E2E test-utility, NOT a runtime production path. The onboarding spec itself does NOT use this bypass.

### 9k. Existing-app upgrade (user installs the FOU-116 build over an older build)

`UIStore` already has persisted state from a prior install (e.g. `colorScheme = 'dark'`, `language = 'en'`). The new key `hasCompletedOnboarding` is `undefined` after hydration (not in the persisted store) → coerced to `false` → onboarding shows once for upgrade users. (P) This is the **intended** behaviour: existing users see the redesigned brand onboarding the first time after upgrade. Alternative considered: gate onboarding on a separate `hasUsedAppBefore` heuristic (e.g. any pal exists, any model is downloaded). Rejected because it adds complexity and the one-time onboarding for upgraders is the intent per FOU-98 brief.

### 9l. **Removed in Round 3.** (Was: multi-select chips with last-deselect re-disables Continue.) Screen 5 is now single-select with chip-tap auto-advance (D7); there is no "deselect" path and no Continue button. Tapping a chip writes `selectedTopic` and navigates to Onboarding6 in one handler call. The user can return to screen 5 via Back from Onboarding6 and tap a different chip — which simply overwrites `selectedTopic` and re-navigates.

### 9m. Empty Figma string at HOW time

After Round 3, every body / title / CTA slot is Figma-filled (§4j); empty slots are not expected. If the implementer encounters one in HOW, they do NOT invent placeholder copy — they pause, surface a designer ask analogous to the FOU-114 `designer-asks.md` precedent at `workflows/stories/TASK-20260519-2110/`, and proceed only after the slot is filled.

### 9n. The user installs a build that ships `Stepper` but no consumer exists

Stepper is exported from the DS barrel. Tree-shaking should remove it from the bundle when unused; even if not, it's a small presentational component. No runtime cost.

### 9o. Audio button on a device with no active screen reader

`AccessibilityInfo.announceForAccessibility(text)` pushes a string into the platform reader queue. If no reader is active (most users), the call is a silent no-op — no crash, no warning. Tested at HOW time on a simulator without VoiceOver enabled. The button itself remains visible/tappable; this is acceptable behaviour and matches RN's documented contract. Future delta WHAT may swap to a TTS engine if the designer specifies a voice / playback contract.

### 9p. HighlightText phrase does not occur in the (possibly translated) body copy

Per §4h's HighlightText contract: the highlighted phrase is l10n-keyed (`onboarding.screenN.body.highlight`) and the renderer searches for the keyed substring in the body. If a translation drift leaves the body without the substring, the renderer falls back to rendering the body without a pill — NOT a crash, NOT a thrown warning visible to the user (a `console.warn` in dev is acceptable). This protects against translator-side drift in screens 2 / 3 / 4 body copy.

### 9q. Device-info chip on a device where one or more fields are unavailable

`react-native-device-info` returns sentinel values (e.g. `'unknown'` for `getDeviceName` on simulators without configured names) and Promise-rejects on some platforms for `getFreeDiskStorage`. The chip handler MUST treat each field independently and concatenate only the fields that resolved successfully (e.g. "iPhone 13 Pro · 6 GB RAM" if free-disk read fails). No `·` orphan, no "undefined" string visible to the user. Fields refresh once per mount; no live update.

### 9r. Screen-6 model-card tok/s subtitle is unavailable

No synchronous device-capability tok/s estimator exists in the worktree today (verified 2026-05-27: `src/utils/deviceCapabilities.ts` has CPU-count gates only; benchmark screen reads from completed bench results, not a pre-bench estimator). The model-card subtitle ships **without** the "≈X tok/s on your phone" clause when no hint is available — the renderer MUST NOT print an orphan "≈ tok/s" string (mirror of §9q's no-orphan-separator pattern). If a synchronous estimator is added later (delta WHAT against `onboarding.md`), the subtitle gains the clause; in the meantime the subtitle is "Llama 3.2 1B · Q<N> · <size>"-only or is omitted entirely. Engineering picks the cheaper of the two at HOW time.

---

## 10. What this doc is NOT

- Not an implementation plan — file layout, refactor order, asset wiring live in `how.md`.
- Not a designer hand-off — Figma is the design source.
- Not a Homepage / Chat specification — those are FOU-117 scope. This doc references the first-time Homepage only as the destination state.
- Not a model-catalogue specification — the `RECOMMENDED_PAL_MODEL_SET` membership is HOW-time work against the current `defaultModels` content (D2).
- Not a designer-copy spec — onboarding copy is **filled** in Figma and ported verbatim in HOW (§4j). The single remaining designer-ask after Round 3 is the Audio button's intent (title + body announcement default per D14); the dev-team commit that absorbs the Round-3 `onboarding.md` update MUST also create-or-trim `designer-asks.md` to contain at most that one entry (§10 cleanup #1). Empty slots elsewhere are engineering errors at HOW time, not engineering invention.
- Not a Phase 4 cleanup plan — Stepper does not need a non-onboarding consumer to exist in DS, and the Paper-import blocklist is not extended by this slice.

**Cleanup reminders**:

1. The new flow doc `context/architecture/onboarding.md` was promoted from this delta in commit `a448d3f`. Round 3 changes the contract materially (Skip presence, screen-5 single-select + auto-advance, RECOMMENDED_PAL_MODEL_SET → quants, Audio button, HighlightText, italic accents, peach token, screen-6 no Skip, Pip title hierarchy). The promoted flow doc MUST be updated in a paired follow-up commit using the I_UI8 handshake (dev-team commit SHA ↔ app PR URL). The planner MUST surface this as a discrete step in HOW. The **same dev-team commit** that absorbs the Round-3 `onboarding.md` update MUST also create-or-trim `workflows/stories/TASK-20260526-1731/designer-asks.md` so it contains at most one entry: the Audio-button announcement intent (D14). All pre-Round-3 "body copy pending" / "title pending" framings are obsolete (Figma fills those slots — §4j).
2. The new `colors.accent.peach` token (I_OB12 / D15) requires a paired line edit in `context/architecture/theming.md` §1a (Color axis). I_UI8 cross-cite handshake: app PR description cites the dev-team-repo commit SHA; the dev-team-repo commit message cites the app PR URL. The planner MUST emit this as a discrete step in HOW. (The `spacing.xxl` paired edit landed in commit `a448d3f` and does NOT need to be redone.)
3. Once FOU-117 lands the real Homepage, this doc references it instead of "out of scope here".
4. The `Stepper` DS component is subject to the same snapshot freeze contract (I_UI5) as every other DS component starting next slice. `HighlightText` is similarly subject to I_UI5 starting next slice.

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

### Round 3 — Figma-faithful pass after user visual review (2026-05-27)

After PR #747 passed all pipeline gates, the user invoked Figma as the source of truth and flagged that the shipped implementation is a wireframe, not the actual design. Round 3 rewrites the WHAT contract to match Figma frame-for-frame at the contract level. **No findings from a critic — this is a user-driven correction pass.** The corrections below are all Figma-faithful, not designer-asks.

| # | Area | Pre-Round-3 (incorrect) | Round-3 (Figma-faithful) | Sections touched |
| - | ---- | ----------------------- | ------------------------ | ---------------- |
| A | Skip presence | Skip on screens 2–6 | Skip on screens 1–4 only; screens 5+6 carry an Audio (headphones) IconButton in the same top-right slot. New testID `onboarding-audio` added. | §3, §4b, §4d, §4e, §4i, I_OB13/I_OB14, Scenarios A/C |
| B | Scenario G' | "User skips on screen 6 → Chat without model bound" | **Deleted.** Figma has no Skip on screen 6 (I_OB14); the only forward path is pick + download. E2E spec must mirror the deletion. | §6 (G' → DELETED note), I_OB14 |
| C | TopicKey union + multi-select | `selectedTopics: TopicKey[]`, multi-select chips, Continue button to advance; keys `everyday / creative / learning / coding / productivity / roleplay` | `selectedTopic: TopicKey \| null`, single-select, chip-tap auto-advance (no Continue, no bottom bar on screen 5); keys `smartchat / coding / education / roleplay / creative_writing / else` (outlined escape-hatch). Method renamed `toggleOnboardingTopic` → `setOnboardingTopic`. | §1a, §2, §4b, §4d, §4i, §5, §7, §8 D7, §9l (deleted), Scenarios A/G''  |
| D | Model card framing | 3 different models (Llama-3.2-1B Q8_0 / Qwen-2.5-1.5B Q8_0 / SmolLM2-1.7B Q8_0) labelled by `size · description` | 3 quants of **one** base model: Llama-3.2 1B Q2_K (Quick) / Q4_K_M (Balanced — peach-tinted card + "Recommended" pill) / Q8_0 (Best). Card metadata `Llama 3.2 1B · Q<N> · <size> · ≈<X> tok/s on your phone`. Only Q8_0 is in `defaultModels.ts` today (line 245 verified); Q2_K / Q4_K_M are added at HOW time. | §1b RECOMMENDED_PAL_MODEL_SET, §4d, §4j, D2, D16 |
| E | Audio button | Did not exist | New 40×40 IconButton (headphones glyph) on screens 5+6, top-right. On tap: `AccessibilityInfo.announceForAccessibility(screenText)` — stub-but-real-behavior, not a no-op. Stateless. | §4b note 4, §4g new row, §4i testID, D14, §9o |
| F | Italic title accents | Not specified | Each title has a Fraunces-Italic accent fragment (or whole-title italic for screen 2 and screen 6 "*Pip*"). Implementation: nested `<Text style={{fontStyle: 'italic'}}>`; non-Latin locales fall back to `Inter-Medium + fontStyle:'italic'` per theming.md D5 (no new font cuts). | §4b screen table, §4h "Italic title accents" subsection |
| G | Peach inline pill highlights | Not specified ("accent rectangle" wording was vague) | New `HighlightText` primitive renders per-screen phrases in a peach pill: screen 2 "No internet, no signal"; screen 3 "quick and private"; screen 4 "No accounts. No cloud. No tracking.". Phrases are l10n-keyed; renderer falls back to plain body if phrase missing in translation. | §1c glossary, §4g new row, §4h "Body-copy pill highlights" subsection, §4j, I_OB12, D15, §9p |
| H | Body copy contract | "Designer-owned, possibly empty; placeholder forbidden, log designer-ask if empty" | **All bodies are Figma-filled.** Port verbatim. The "designer-pending" framing is removed. The only remaining designer-ask is the Audio button's announcement intent (D14). | §4j paragraph rewrite, §10 designer-copy bullet |
| I | CTA copy + arrow | Generic "Get started / Continue / Finish" | Per-screen CTAs verbatim from Figma: 1) "Show me Around →"; 2) "Next →"; 3) "Got it →"; 4) "Get Started →"; 5) no CTA (chip-tap); 6) "Download Pip (<size>) ⬇" with download icon and runtime-bound size. | §2 event-flow, §3 state machine table, §4b screen table, §4j l10n keys |
| J | Back chevron | "Back on screens 2–6" — placement unspecified | Bottom-bar left slot on screens 2/3/4/6; **top-left header slot on screen 5** (screen 5 has no bottom bar). | §4b note 4 |
| K | Illustration sources | Single fuzzy "illustration" per screen | 7 assets enumerated, all bundled under `src/assets/onboarding/` and exported via Figma MCP at HOW time (splash mark 112×112, screen-1 hero, screen-2 phone-with-pals, screen-3 phone-card + cloud-card pair, screen-4 phone+shield, screen-5 6× chip icons, screen-6 Pip mascot 66×62). Engineering verifies splash-mark = screen-1 hero in HOW. | §4b screen table |
| L | Device-info chip | Static "Local · on-device" placeholder | Real device-info chip: `${deviceName} · ${ramGB} GB RAM · ${freeGB} GB free` from `react-native-device-info` (already a project dep — package.json:67). Each field falls back independently if unavailable. | §4b screen 6 row + note 6, §9q |
| M | Screen-6 title hierarchy | "Pip" small caption + "We found a perfect pal for you." big heading | "Pip" is the big italic Fraunces headline (with Pip mascot above); the long description is the body. Inverted from the wireframe. | §4b screen 6 row, §4j keys |
| N | designer-asks.md | Multiple entries for "body copy pending" | One entry: Audio button announcement intent (D14). Bodies are NOT pending. | §4j paragraph, §10 designer-copy bullet |

**Drift re-check (Round 3).**

- `src/theme/tokens/spacing.ts` (worktree, re-read): `spacing.xxl = 40` is already present (committed under FOU-114 follow-up). No drift; I_OB11 still load-bearing because `theming.md` §1a has NOT yet listed `xxl` in the spacing axis enumeration — a paired-edit step remains.
- `src/theme/tokens/colors.ts` (worktree, re-read): no `accent.peach` binding today. I_OB12 + D15 are new and require the I_UI8 cross-cite paired edit.
- `src/store/defaultModels.ts` (worktree, re-read at line 245): Llama-3.2-1B Q8_0 is the only present quant. Q2_K and Q4_K_M variants must be added at HOW time per D16 / D2.
- `react-native-device-info` confirmed at `package.json:67`, in active use across `BenchmarkRunnerScreen.tsx`, `utils/deviceCapabilities.ts`, `AboutScreen.tsx`, `utils/index.ts` — no new dep required for the device-info chip.
- `context/architecture/onboarding.md` was promoted from this WHAT in commit `a448d3f` (Round 2 LGTM). Round 3 materially changes the contract — the promoted flow doc MUST be updated in a paired follow-up commit (added to §10 cleanup reminder #1).
- `context/architecture/theming.md` — no contradictions introduced. I_OB12 follows the I_UI8 mechanism that theming.md already documents (§4 I_UI8 wording). No structural change to theming.md required; only the §1a Color-axis and Spacing-axis enumerations gain one binding each.
- `context/architecture/chat-flow.md` — unchanged. Onboarding completion lands the user on the existing Drawer / Chat surface; no chat-side contract shifts.

**Round 3 — designer-asks scope collapse.** `workflows/stories/TASK-20260526-1731/designer-asks.md` should be reduced to one entry post-Round-3:

1. Audio button announcement intent — confirm D14's title+body default is acceptable, or specify alternate copy / engine.

All pre-Round-3 "body copy pending" / "title pending" entries are removed; Figma fills those slots.

**Quality checklist re-run.** Zero `(?)` markers. Every `(P)` carries a one-line rationale. Every `(D)` carries a rationale. Hard invariants now: I_OB1..I_OB14. Single-writer table updated for `setOnboardingTopic` and the snapshot derivation. Canonical scenarios A / C / G / G'' (replacing G') / H exercise the Round-3 contract. Edge cases 9o / 9p / 9q added. No implementation steps in the doc; no file paths beyond what's needed to identify a contract location. Doc is ~700 lines after Round 3 (still inside the 600-line guidance for a single flow, slightly over because the Round-3 review history is itself substantial — accepting the overrun because the contract is one flow).

### Round 3.5 — architect-critic, HAS_BLOCKERS (2026-05-27)

| # | Severity | Summary | Resolution |
| - | -------- | ------- | ---------- |
| BLOCKER 1 | BLOCKER | §0 / I_OB11 / §4h / §10 cleanup #2 misstate the `spacing.xxl=40` paired-edit state — `theming.md` §1a Spacing axis already lists `xxl: 40` (committed in `a448d3f`, same commit that promoted onboarding.md). Both sides of the I_UI8 handshake are on disk; no further paired-edit work belongs in HOW. | **FIXED.** Verified directly in `context/architecture/theming.md` §1a (line 95 already reads `none: 0, xxs: 2, xs: 4, s: 8, sm: 12, m: 16, ml: 20, l: 24, xl: 32, xxl: 40   // NEW: xl, xxl`). Verified the corresponding commit `a448d3f`: "docs(architecture): promote onboarding.md and extend Spacing axis with xxl". Collapsed I_OB11 to a historical anchor (`SATISFIED`); reworded §0 lines 16 and 52; reworded the final §0 architecture-doc bullet to single paired edit (`accent.peach` only); dropped the paired-edit paragraph in §4h; updated §4h binding-table row for spacing to reference commit `a448d3f`; removed §10 cleanup #2 (spacing) and renumbered subsequent items. I_OB12 / D15 / cleanup #2 for `accent.peach` remain load-bearing — verified via grep on the worktree's `src/theme/tokens/colors.ts` (0 hits) and on `context/architecture/theming.md` (0 hits). |
| BLOCKER 2 | BLOCKER | §3 ASCII state-machine reads `Skip (any of 2-6) → (completed)`, contradicting §3 table + I_OB14 + §4e + §4i, all of which agree Skip is screens 1-4 only (screen 5 has Audio, screen 6 has no Skip per I_OB14). Also missing the pre-stack → Onboarding1 dwell arrow (SUGGESTION 1). | **FIXED.** §3 ASCII now reads `Skip (any of 1–4) → (completed; OnboardingStack unmounts)`; added the dwell arrow `pre-stack ─dwell≥SPLASH_MIN_DWELL_MS→ 1` as the first line of the diagram; clarified the chip-tap transition on 5 in the same block. |
| CONCERN 1 | CONCERN | §4i row "Back chevron (screens 2–6)" doesn't note that screen 5 places the chevron in the top-left header per §4b note 4 — implementer could miss the header-vs-bottom-bar placement difference. | **FIXED.** Appended clarifier to the row: "same testID across slots — bottom-bar left on 2/3/4/6, top-left header on 5 per §4b note 4". testID itself unchanged. |
| CONCERN 2 | CONCERN | §10 #1 and Round-3 history N assert `designer-asks.md` should be reduced to ≤1 entry, but the file isn't trimmed yet (in fact, verified 2026-05-27 — the file does NOT exist at all). Either trim it or tighten the doc so HOW carries the work item explicitly. | **FIXED.** Tightened §10 cleanup #1: the same dev-team commit that absorbs the Round-3 `onboarding.md` update MUST also create-or-trim `workflows/stories/TASK-20260526-1731/designer-asks.md` to contain at most the Audio-button-intent entry (D14). Also updated the §10 paragraph "Not a designer-copy spec" to cite cleanup #1. Actual file create-or-trim is a planner/implementer step, not a WHAT step. |
| SUGGESTION 1 | SUGGESTION | §3 diagram should show the splash → Onboarding1 transition explicitly. | **FIXED** as part of BLOCKER 2 above (`pre-stack ─dwell≥SPLASH_MIN_DWELL_MS→ 1` line added). |
| SUGGESTION 2 | SUGGESTION | §4j / §1b's "≈<X> tok/s on your phone" subtitle cites "ModelStore device-capability hint; same source as benchmark screen's per-model perf hints" — verify the synchronous getter exists. | **FIXED.** Verified directly: no synchronous tok/s estimator exists in the worktree today. `src/utils/deviceCapabilities.ts` has only CPU-count gates (`cpuCount >= 6` at line 213). `BenchmarkScreen/BenchResultCard.tsx` reads `l10n.benchmark.benchmarkResultCard.results.tokensPerSecond` from **completed bench results**, not from a pre-bench device estimator. Updated §1b's RECOMMENDED_PAL_MODEL_SET subtitle comment to mark the tok/s clause as OPTIONAL, with explicit fallback when the estimator is absent. Added a new §9r edge case ("Screen-6 model-card tok/s subtitle is unavailable") to mirror §9q's no-orphan-separator pattern — subtitle ships without the "≈X tok/s" clause rather than emitting an orphan "≈ tok/s" string. Subtitle format becomes "Llama 3.2 1B · Q<N> · <size>" by default; tok/s is additive future work. |

**Drift re-check (Round 3.5).**

- `context/architecture/theming.md` §1a re-read at lines 80–115. Spacing axis already enumerates `xxl: 40` (line 95) with the `// NEW: xl, xxl` comment. No outstanding paired-edit for spacing. The Color axis (line 78–84) does NOT contain any `accent.peach` binding — I_OB12 / D15 / cleanup #2 stay load-bearing.
- `worktrees/TASK-20260526-1731/src/theme/tokens/colors.ts`: 0 hits for `accent.peach` (verified 2026-05-27). Token addition still required at HOW time.
- `worktrees/TASK-20260526-1731/src/utils/deviceCapabilities.ts`: no tok/s estimator. `BenchmarkScreen/BenchResultCard.tsx`: only renders bench-result tok/s, not a device estimate. SUGGESTION 2 fallback is correct.
- `workflows/stories/TASK-20260526-1731/`: directory contains `intent-brief.md`, `what.md`, `how.md`, `screenshots/`. `designer-asks.md` does **not** exist on disk — the dev-team commit that absorbs the Round-3 update must **create** the file with at most the Audio-button entry. §10 cleanup #1 now says this explicitly.

**Quality checklist re-run.** Zero `(?)` markers. Every `(P)` carries a one-line rationale; every `(D)` carries a rationale. Hard invariants: I_OB1..I_OB14 (I_OB11 retained as a satisfied historical anchor — no contract obligation remains). Single-writer table unchanged. Canonical scenarios unchanged. Edge cases gained §9r. Doc grew by the Round-3.5 review history entry; ASCII state diagram tightened (-/+ a line). No implementation steps; no file paths beyond contract identification. Re-routing to architect-critic.
