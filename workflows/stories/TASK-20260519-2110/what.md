# Theming & Design Tokens — Architecture & Flow Board

**Story:** TASK-20260519-2110 (FOU-114, Phase 1 of FOU-112)
**Status:** delta — no prior `context/architecture/*.md` covers this surface. On merge, this WHAT is promoted to `context/architecture/theming.md` as the cumulative truth for the theme / token / typography layer.

This doc defines the contract the new design-token layer must obey. It is the contract any future restyle slice (FOU-115 through FOU-123) implements against. The intent brief locks the high-level decisions; this doc translates them into invariants, single-writer rules, and canonical shapes.

---

## Revision history

- **Round 1 revisions (2026-05-19, addressing architect-critic round 1):**
  - **B1 (FIXED)** — §0, I7, §4c.3, §4f, D10: replaced fictitious six-item Paper surface (`Text/Button/IconButton/Portal/Provider/Card via Selector`) with the actual current surface enumerated from `grep -rh "from 'react-native-paper'" src/`. I7 reworded: this slice does NOT add any new Paper import; the thin-set reduction is FOU-115/123 work.
  - **B2 (FIXED)** — §1a, §9e, §11: corrected `MMKV` → `AsyncStorage` for UIStore persistence (verified at `src/store/UIStore.ts:5,73-84`). Added cold-start hydration design (gate first render on `isHydrated`) rather than asserting no-flash.
  - **C1 (FIXED, via DEFER)** — Removed `I9 (no MD3 import in components)` from §4e invariants; moved to §5 deferred cleanup #5 with file list (`src/utils/types.ts:4,9,289`, `src/utils/index.ts:6`, `src/components/SidebarContent/styles.ts:3`, `src/components/RenameModal/styles.ts:2`). Migrating these in this slice would force per-file edits across MD3-typed style factories — out of scope for an invisible foundation slice. Belongs to FOU-123 (or a small precursor) once aliases are removed.
  - **C2 (FIXED)** — Added "Considered alternatives" sub-block under D1 listing two slice-shape alternatives (one-shot rewrite to direct token reads; defer-tokens, ship fonts + theme decoupling only) with one-line trade-offs and rejection rationales.
  - **C3 (FIXED)** — §1d row 2 rewritten: legacy MD3 typescale alias names (`bodyMedium`, `titleSmall`, `bodyLarge`, `displaySmall`, etc.) are **pinned to today's MD3 `configureFonts` values** (`fontFamily/fontSize/lineHeight/letterSpacing/fontWeight` unchanged). New typography reads `theme.typography.*`. The two surfaces do NOT cross-feed.
  - **C4 (FIXED)** — Added Scenario H (cold start with persisted `language='ja'`, no Fraunces flash). Added §4c.4 hydration gate at PaperProvider level. Added §9e design (gate on `isHydrated`).
  - **S1 (ADOPTED)** — D6 amended with disagreement-resolution rule (current dark Theme value wins on I1 conflict; disagreement logged as designer ask on FOU-112).
  - **S2 (ADOPTED)** — Scenario E softened to "PaperProvider re-renders with a new `theme` prop (no remount, same instance)".

- **Round 2 revisions (2026-05-21, hydration/splash rework after four PR-732 review rounds):**
  - **REWORK** — Added the "Hydration / splash rework" section (lead recommendation + rationale). Root cause: the Round-1 branded JS splash *impersonates* the iOS native launch screen and diverges from native per-platform (iOS has a branded storyboard; Android has NO native launch screen at all — verified in `android/.../styles.xml` + `package.json`). Four review rounds (R2 branding, R3 safe-area, R4 `initialMetrics`) each fixed a native-matching axis the prior round exposed.
  - **REVISED I10 / D11 / §4c.4 / §9e / §9k / Scenario H / §2 / §4f / §7** — splash hold is now **neutral background-only** (flat colored `View`, no branding, no `Text`, no `SafeAreaProvider`/insets/`initialWindowMetrics`). Gate semantics (defer `<PaperProvider>` on `isHydrated(uiStore)`) unchanged. Recommendation: Part A (neutral hold) lands in FOU-114; no new dependency, no scope change.
  - **ADDED D12 (deferred, HUMAN DECISION)** — the architecturally-correct end state is holding the *native* launch screen until hydration (`react-native-bootsplash`/RN core API). NATIVE_CHANGES=YES, adds a native Android splash that never existed; recorded as a separate task, NOT a FOU-114 deliverable.
  - **ADDED §9l** — documents the per-platform launch-screen divergence (iOS branded storyboard vs Android none) that the rework addresses.
  - **NOTE for orchestrator/human:** scope/dependency decision required only if Part B (D12) is chosen. Part A keeps FOU-114 scope and dependency surface unchanged.

- **Round 2 critic fold-in (2026-05-21, LGTM + 1 CONCERN, no re-round):** Reworded §10 cleanup-reminder-1 and §11 to separate the two artifacts — App.tsx *code* (branded `Text`/`SafeAreaProvider`/insets/`initialWindowMetrics` to strip) vs theming.md *doc* (already neutral; change is *positive* tightening — state no-branding/no-`Text`/no-`SafeArea`/no-insets/no-`initialWindowMetrics` explicitly + add §9l + record D12, not a strip). Added an axis-separation note to the net-effect summary (neutral hold is independent of the Round-3 `useTheme` subscription path; Scenarios E/F unaffected).

---

## Hydration / splash rework (Round 2 revision, 2026-05-21)

**Status of this section:** This supersedes the hydration-gate design as originally written in **I10 / D11 / Scenario H / §4c.4** (Round 1). The clauses below are revised in place; this section is the lead summary and rationale. Where this section and a Round-1 clause disagree, **this section wins**.

### Why the rework

The hydration gate was added in Round 1 to prevent a cold-start FOUC: a user with a persisted non-Latin `language` (e.g. `ja`) could see a headline render in Fraunces for one frame before `mobx-persist-store` hydrates `uiStore` from AsyncStorage and the §4d typography fallback swaps the family to Inter. The mechanism chosen — a **JS-rendered splash that impersonates the iOS native launch screen** — has now churned across four PR review rounds, each round fixing a native-matching axis the previous round exposed:

- R2 (CONCERN): blank `View` → reviewers asked for the branded `PocketPal` / `LLM Ventures` labels to match the iOS storyboard.
- R3 (CONCERN): static `bottom: 24` → safe-area-aware tagline (`insets.bottom + 20`) to match the storyboard constraint.
- R4 (CONCERN, still open): the dedicated `<SafeAreaProvider>` had no `initialMetrics`, so the first frame could render blank until the native inset event arrived → seed `initialWindowMetrics`.

**Root cause (C, verified this round):** a JS splash that *impersonates* a native launch screen will always diverge from native on some axis, and the divergence is **per-platform**:

- **iOS (C):** has a branded native launch screen. `ios/PocketPal/Info.plist` sets `UILaunchStoryboardName = LaunchScreen`; `ios/PocketPal/LaunchScreen.storyboard` renders `PocketPal` (bold system 36pt) + `LLM Ventures` (system 17pt) on `systemBackgroundColor`, tagline pinned to safe-area-bottom + 20pt. The JS splash was hand-matched to *this*.
- **Android (C):** has **no** native launch screen at all. `android/app/src/main/res/values/styles.xml` defines only `AppTheme` (`parent="Theme.AppCompat.DayNight.NoActionBar"`) with no `windowBackground` drawable; there is no launch/splash theme, no launch drawable, and no splash dependency in `package.json` (`grep -i splash package.json` → none). Pre-FOU-114 Android had **no startup splash whatsoever**.

So on Android the Round-1 JS splash is a **novel, unmatched branded screen** that did not exist before this slice — and `initialWindowMetrics` can be `null` on Android, re-exposing the R4 blank-frame risk. Hand-matching a JS splash to native on both platforms indefinitely is a losing game: every future native-launch tweak (storyboard label, Android-12 splash API, dark-mode background) re-opens the same review thread.

### Recommendation (lead)

**Two-part decision. Part A is a no-native-dependency change I recommend landing in FOU-114 now. Part B is a native-dependency follow-up I recommend the human schedule as its own task, NOT in FOU-114.**

**Part A — keep the hydration gate, but replace the impersonating branded splash with a NEUTRAL background-only hold. (P, recommended, no new dependency, no scope change.)**

Keep I10 (gate `<PaperProvider>` mount on `mobx-persist-store` hydration of `UIStore`) — it is the minimum that guarantees Scenario H and it is cheap. **But stop impersonating the native launch screen.** The gate renders a full-screen `View` whose only property is `backgroundColor` resolved from `Appearance.getColorScheme()` (system light/dark). **No `PocketPal` / `LLM Ventures` labels, no `Text`, no `SafeAreaProvider`, no `useSafeAreaInsets`, no `initialWindowMetrics`.** Rationale:

- A background-only `View` has **nothing to match** against either native launch screen — no labels to position, no tagline, no safe-area constraint. The entire R2/R3/R4 churn axis disappears by construction.
- On **iOS**, the native storyboard paints first (its background is `systemBackgroundColor`); the JS background-only `View` continues that same flat background, so the native→JS handoff is a same-color continuation rather than a label cross-fade that can jump. The branded labels stay where they belong — on the native launch screen, painted by the OS before JS starts.
- On **Android**, there is no native launch screen, so a flat colored hold is exactly what the OS already shows between process start and first frame; the JS background-only hold extends that flat color. It does **not** introduce a novel branded screen (the Round-1 regression).
- The gate is sub-frame in the common case (one AsyncStorage key read); the neutral hold is only ever visible as "app launching" flat color, which is acceptable on both platforms (see revised §9k).

**Part A satisfies the FOU-114 acceptance criterion (no Fraunces flash, Scenario H) with zero new dependency and zero added per-platform native config, and removes all four rounds' worth of native-matching obligations.**

**Part B — for true native-launch continuity, hold the NATIVE launch screen until hydration via `react-native-bootsplash` (or RN core splash API). (P, recommended as a SEPARATE task; NATIVE_CHANGES=YES; scope-expanding; HUMAN DECISION REQUIRED.)**

The architecturally-correct end state is: the **real native launch screen IS the splash on both platforms**, held programmatically until JS has hydrated, with nothing for JS to impersonate. `react-native-bootsplash` (or React Native's built-in splash-hide API) gives `BootSplash.hide()` / `hideAsync()` that JS calls *after* the hydration gate resolves. This means:

- iOS keeps its storyboard; Android gains a real native splash theme (Android-12 `windowSplashScreen*` API or a `windowBackground` launch theme) — the gap that makes Android the odd platform out today is closed natively, where it belongs.
- JS renders **no splash at all**; it just calls `hide()` once `isHydrated(uiStore)` is true and the first themed frame is ready.
- The branding lives once, in native config, designed correctly per platform by the platform's own splash mechanism — not re-implemented in JS and re-reviewed every round.

**Why Part B is NOT in FOU-114:** It is a native-dependency addition (`react-native-bootsplash` + iOS `pod install` + Android theme/drawable config + `react-native.config.js` / native linking) and it adds a new branded-screen surface on Android (a *native* one this time). That is a deliberate product/design decision (Android now gets a launch splash it never had) and a native-build-surface expansion — both of which the human should confirm and which deserve their own task with its own visual sign-off, not a rider on an "invisible token foundation" slice. **Flagging explicitly: adopting Part B in this PR would change FOU-114's scope and native-dependency surface.**

### Considered and rejected for FOU-114

- **Keep the branded JS splash but design it correctly for BOTH iOS and Android.** Rejected: this is the status quo that produced four review rounds. It permanently couples a JS component to two diverging native launch surfaces; every native-launch change re-opens it. It also forces a *new* branded screen onto Android, which is a product decision masquerading as a foundation-slice implementation detail.
- **Drop the hydration gate from FOU-114 entirely; ship pure token foundation and address the font-flash separately (Option: "extract the gate to its own task").** Rejected as the *default*, accepted as a *fallback* (see Decision D11 revised). The Fraunces flash is a **new** regression that FOU-114 itself introduces (today's app uses Inter unconditionally for headlines, so there is no race to lose; the §4d fallback rule creates the race). Shipping the font dimension without the gate would land a known new FOUC and rely on a follow-up task to fix a regression this slice caused — undesirable. The colorScheme-flash class is genuinely pre-existing (C, `App.tsx` renders `<PaperProvider>` immediately today) and is **not** FOU-114's to fix; it is fixed only incidentally by the gate. If the human prefers to keep FOU-114 strictly invisible-and-no-gate, the clean split is: FOU-114 ships tokens+fonts+decoupling, and a *fast follow* task ships the gate (Part A) before any later slice actually renders a Fraunces headline. This is acceptable only because no in-scope screen in FOU-114 renders a headline token yet (§9j-style reasoning: the token exists but no current consumer uses it). **Recommendation remains: keep Part A in FOU-114**, because the gate is small, dependency-free, and closes the regression in the same PR that opens it.
- **Pre-resolve persisted `language` synchronously before MobX hydrates** (read AsyncStorage manually / switch `colorScheme`+`language` to a synchronous store like MMKV). Rejected: duplicates the persistence layer (manual AsyncStorage read) or changes the persistence backend (MMKV migration) — both far larger blast radius than a background-only gate, and a backend swap is its own task with its own data-migration review.
- **Gate only first-frame headline rendering** (let the app mount, but suppress headline `Text` until hydrated). Rejected: spreads the gate across every headline consumer (a cross-cutting per-component concern), re-introduces the colorScheme flash for everything that is not a headline, and is more fragile than one gate at the root.

### Net effect on the contract

Part A is adopted into the clauses below. I10 keeps its meaning (gate exists) but its splash contract is rewritten to "neutral background-only, no native impersonation". D11 gains the rejected-alternatives and the extract-to-own-task fallback. Scenario H's mechanism block is rewritten. §4c.4, §9e, §9k are rewritten. A new §9l covers the Android no-native-launch case explicitly. Part B is recorded as **D12 (deferred, human decision)** and as a forward cleanup reminder; it is **not** a FOU-114 deliverable. **Note (axis separation):** this neutral-hold rework is independent of the Round-3 `useTheme` subscription path — the reactive mode/language swap behaviour (Scenarios E/F) is unaffected by it. Reviewers should not conflate the two open axes (splash-hold neutrality vs. reactive theme subscription).



---

## Conventions

- **(C)** = current behaviour, documented from code
- **(P)** = proposal in this delta
- **(?)** = open question (must be empty before routing to critic)
- **(D)** = decision (resolved trade-off, with one-line rationale)

This is a story-scoped delta. It is mostly **(P)** + **(D)**. On promotion, **(P)** → **(C)**.

---

## 0. Scope & non-scope

In scope (FOU-114 / this WHAT):

- Token module shape (color / typography / spacing / radius / stroke), light + dark, mode-aware.
- Font assets: add Fraunces, Fraunces-Italic, JetBrains Mono — static cuts only. Wire iOS (`UIAppFonts`) + Android (`android/app/src/main/assets/fonts/`) via `react-native.config.js`.
- Theme refactor: decouple the consumed shape from MD3 internals while keeping `PaperProvider` / `Portal` and `useTheme()` working.
- RTL + non-Latin/CJK fallback rules at the token layer (no per-component handling in this slice).
- Mapping of current component visuals onto the new tokens so the build is **visually unchanged**.
- Hydration gate at `<PaperProvider>` to guarantee no FOUC for persisted `language` (cold start, non-Latin locales). The hold rendered while unhydrated is a **neutral background-only `View`** — NOT a branded native-launch impersonation (REVISED Round 2; see "Hydration / splash rework"). Holding the *native* launch screen (D12) is explicitly out of scope (NATIVE_CHANGES, separate task).

Explicitly NOT in scope:

- Any visible restyle of any screen / component (Phase 1 is invisible — see I1).
- Per-component restyle work — that belongs to FOU-117–122.
- Sheet/Modal/ConfirmationDialog rework — that belongs to FOU-115 (Phase 2). Headers live in canonical Figma at node `3011:23955` and will be reused there.
- Per-language locale UI direction switching beyond what the token layer needs (full RTL screen mirroring may land in later slices; this slice guarantees the token / typography layer respects it).
- Reducing the current `react-native-paper` import surface. The intent brief's "keep Paper thin: Text/Button/IconButton/Portal/Provider" is the **end-state for future slices (FOU-115/123)**, not a deliverable here. This slice **preserves** the current Paper import surface (see I7).
- Migrating components that import `MD3Theme` / `MD3Colors` / `MD3Typescale` to a Paper-free type. Belongs to FOU-123 (or a focused precursor); see §5 deferred cleanup #5.

---

## 1. Data model

### 1a. Token module shape

The new token layer is a pure-data module rendered into a typed `Tokens` shape. `Tokens` is mode-resolved (light or dark binding chosen once per render based on `uiStore.colorScheme`). Token names below mirror the canonical Figma collection.

```
Tokens
  colors: TokenColors           // every key has a light and dark binding
    background: string          // canvas (was: MD3 background)
    surface: string             // raised surface
    surfaceVariant: string      // secondary raised surface
    onBackground: string        // text on canvas
    onSurface: string           // text on raised surface
    onSurfaceVariant: string    // muted text
    primary: string             // brand / accent fill
    onPrimary: string           // text on primary fill
    primaryContainer: string
    onPrimaryContainer: string
    secondary: string
    onSecondary: string
    secondaryContainer: string
    onSecondaryContainer: string
    tertiary: string
    onTertiary: string
    tertiaryContainer: string
    onTertiaryContainer: string
    border: string              // hairline / outline
    outline: string             // strokes on solid fills
    outlineVariant: string      // strokes on muted fills
    error: string
    onError: string
    errorContainer: string
    onErrorContainer: string
    // semantic extras already in (C) — see §1c for migration
    ...semanticColors            // see Migration table 1c

  typography: TokenTypography
    // each named style is a fully-resolved RN TextStyle ready for spread
    bodyM:    { fontFamily, fontSize, lineHeight, fontWeight, letterSpacing? }
    bodyS:    { ... }
    uiM:      { ... }
    uiS:      { ... }
    titleL:   { ... }    // Inter
    titleM:   { ... }
    titleS:   { ... }
    captionM: { ... }
    captionS: { ... }
    headlineH1: { ... }  // Fraunces — Latin/Cyrillic; falls back via family list
    styledXs:   { ... }  // Fraunces-Italic accent
    codeM:    { ... }    // JetBrains Mono
    codeS:    { ... }
    // Exact list is finalised against the canonical Figma file in `how.md`,
    // but every type style in canonical `789:19792` must have a named entry.

  spacing: TokenSpacing
    none: 0
    xxs: 2
    xs: 4
    s: 8
    sm: 12
    m: 16
    ml: 20
    l: 24

  radius: TokenRadius
    none: 0
    xxs: 2
    xs: 4
    s: 8
    sm: 12
    m: 16
    ml: 20
    l: 32
    xl: 40

  stroke: TokenStroke
    hairline: 0.5
    s: 1
    m: 1.5
    l: 3
```

Stored on disk: nothing. Tokens are pure code. Mode selection is read from `uiStore.colorScheme` (C — persisted by `mobx-persist-store` with **AsyncStorage** backend, see `src/store/UIStore.ts:5,73-84`). Locale selection is read from `uiStore.language` (same store, same backend).

Computed at render: the resolved `Theme` consumed by components (see §1b) is built per-render by `useTheme()` from the active `Tokens` binding.

### 1b. Consumed `Theme` shape (the public surface)

Components consume `useTheme()` and receive a `Theme` that is a **superset** of `Tokens` plus the Paper-compatibility fields needed for `react-native-paper` to keep rendering identically. The MD3 alignment is an **implementation detail of the `Theme` builder**, not a contract components depend on.

```
Theme
  colors:     TokenColors & MD3-compat aliases  // see §1c
  fonts:      MD3 typescale (pinned to today's values) + composite TextStyles  // see §1d
  typography: TokenTypography                    // new surface; new code reads this
  spacing:    TokenSpacing & { default: number } // `default` retained for backward-compat (= spacing.m = 16)
  radius:     TokenRadius
  stroke:     TokenStroke
  borders:    { inputBorderRadius, messageBorderRadius, default }  // retained (C); values map to radius scale
  insets:     { messageInsetsHorizontal, messageInsetsVertical }   // retained (C)
  icons?:     ThemeIcons   // retained (C)
  isV3:       true        // (C) — needed by Paper
  dark:       boolean     // (C) — needed by Paper
  roundness:  number      // (C) — Paper-internal
```

The intent of this superset is single-direction migration: **new code reads tokens directly** (`theme.spacing.m`, `theme.colors.primary`, `theme.typography.bodyM`); **legacy code keeps working** via the existing `Theme.fonts.*` MD3 typescale, `Theme.spacing.default`, etc. The legacy surfaces are the migration layer, not a permanent dual API — they shrink to zero in FOU-123.

### 1c. Color migration table (current → token)

Every color reference in current `Theme` (from `src/utils/theme.ts` + `src/utils/types.ts`) must continue to resolve. The new token module is the source; aliases preserve current names.

| Current name | Source in new model | Migration |
| --- | --- | --- |
| MD3 base colors (`primary`, `onPrimary`, `primaryContainer`, etc.) | `tokens.colors.*` (same key names, sourced from canonical Figma) | direct rename; values may differ — see I2 |
| `SemanticColors.surface*` (Highest/High/Container/Low/Lowest/Dim/Bright) | `tokens.colors.surface*` (mode-resolved bindings, not derived via opacity math) | move from computed `withOpacity` math to explicit token bindings; see §5 deferred #4 for fallback |
| `SemanticColors.text` / `textSecondary` / `inverseText` / `inverseTextSecondary` | `tokens.colors.{text,textSecondary,inverseText,inverseTextSecondary}` | direct rename |
| `border`, `placeholder` | `tokens.colors.{border,placeholder}` | direct rename |
| Menu colors (`menuBackground`, `menuBackgroundActive`, `menuSeparator`, etc.) | `tokens.colors.menu*` | direct rename |
| Message colors (`authorBubbleBackground`, `receivedMessage*`, `sentMessage*`, `userAvatar*`, `searchBarBackground`) | `tokens.colors.*` (same names) | direct rename |
| Thinking-bubble colors | `tokens.colors.thinkingBubble*` | direct rename |
| Status / button / icon-model-type colors (`bgStatus*`, `btn*`, `iconModelType*`) | `tokens.colors.*` | direct rename |
| `stateLayerOpacity`, `hoverStateOpacity`, `pressedStateOpacity`, `draggedStateOpacity`, `focusStateOpacity` | `tokens.colors.*` (kept under `colors` for source-compat, not moved to a new namespace in this slice) | direct rename |

### 1d. Typography migration table (current → token)

The Theme exposes **two parallel typography surfaces** during the migration window:

1. **`theme.typography.*`** — the new token shape (`bodyM`, `titleL`, `headlineH1`, `codeM`, etc.). Sourced from the canonical Figma file. Locale-aware (Fraunces → Inter swap for non-Latin per §4d). **New code reads this.**
2. **`theme.fonts.*`** — the existing MD3 typescale + PocketPal-custom TextStyles. Used by ~18 consumer files today (verified by `grep -rh "theme\.fonts\.(bodyMedium|titleSmall|bodyLarge|displaySmall|headlineLarge|headlineMedium|labelLarge)" src/`). **Pinned to today's MD3 values, unchanged.** Removed in FOU-123 once consumers migrate.

The two surfaces **do not cross-feed**. New tokens do not derive from legacy MD3 values; legacy MD3 values are not re-sourced from new tokens. This is what guarantees I1 for legacy consumers.

| Current name | New token surface | Behaviour in this slice |
| --- | --- | --- |
| `fontStyles.regular` / `medium` / `bold` / `thin` / `light` / `semibold` / `extraBold` | n/a (legacy module export at `src/utils/theme.ts`) | exported `fontStyles` object **preserved verbatim** (used by `ChatInput/styles.ts:4,145,152,157,162` and others). Removed in FOU-123. |
| MD3 typescale on `theme.fonts.*` (`displaySmall`, `headlineLarge`, `headlineMedium`, `bodyMedium`, `bodyLarge`, `titleSmall`, `labelLarge`, etc.) | n/a | **values pinned to today's `configureFonts` output** — same `fontFamily / fontSize / lineHeight / letterSpacing / fontWeight`. No change to legacy consumer rendering. |
| `theme.fonts.titleMediumLight` (custom, used in `Selector`, `ModelSettings`) | n/a | **preserved verbatim**. Removed in FOU-123. |
| `theme.fonts.dateDividerTextStyle` / `emptyChatPlaceholderTextStyle` / `inputTextStyle` / `receivedMessage*` / `sentMessage*` / `userAvatarTextStyle` / `userNameTextStyle` | n/a | **preserved verbatim** as composite TextStyles in the theme builder. Removed in FOU-123. |
| (new) | `theme.typography.{bodyM,bodyS,uiM,uiS,titleL,titleM,titleS,captionM,captionS,headlineH1,styledXs,codeM,codeS}` | new surface; values sourced from canonical Figma; new code reads this directly. |

### Glossary

- **Tokens** — pure-data, no React imports, the source of truth for color / typography / spacing / radius / stroke values. Mode-aware: every token has a light and dark binding.
- **Theme** — the runtime object consumed via `useTheme()`. A superset of resolved tokens plus MD3/Paper-compat aliases. Built per-render.
- **Mode** — `'light' | 'dark'`. Sourced from `uiStore.colorScheme`. (x1 is removed — see D4.)
- **MD3-compat alias** — a key on `Theme` whose name matches an MD3 / current-code identifier and whose value is preserved verbatim (color) or pinned to today's value (typography). Migration layer, not a permanent API.
- **Latin script-set** — `latin extended + cyrillic`. The serif accent (Fraunces) is restricted to this set; non-Latin/CJK falls back to Inter (and Inter falls back to system).
- **Non-Latin locale** — any language whose primary script falls outside the Latin script-set. For PocketPal's supported languages (`en/fa/he/id/ja/ko/ms/ru/uk/zh/zh_Hant`), the non-Latin set is `{fa, he, ja, ko, zh, zh_Hant}`. (`ru`, `uk` are Cyrillic — Latin script-set; `id`, `ms` are Latin.)
- **RTL locale** — `{he, fa}`. RTL mirroring is handled by RN's `I18nManager`; tokens are RTL-safe (no directional values baked in).

---

## 1e. External shape

No wire format. The token layer is internal. The only external touchpoint is the **bundled font binary set** (TTF files):

- iOS: registered via `UIAppFonts` in `ios/PocketPal/Info.plist`.
- Android: dropped in `android/app/src/main/assets/fonts/`.
- React Native: declared once in `react-native.config.js` (`assets: ['./src/assets/fonts']`); native-side registration is handled by `npx react-native-asset` (or equivalent linking) and currently already exists for Inter.

The font family **name** as referenced in code (e.g. `'Fraunces-Regular'`) must match the iOS PostScript name and the Android filename (sans extension). Mismatches are silent — RN falls back to system. See I8.

---

## 2. Event flow

No event flow changes. The theme layer is stateless apart from `uiStore.colorScheme` and `uiStore.language` (both already in (C)) and is read synchronously via `useTheme()`.

The one new addition is the **hydration gate** at `App.tsx` (§4c.4, REVISED Round 2): before the first render of `<PaperProvider>`, the app awaits `mobx-persist-store`'s `isHydrated(uiStore)` so the persisted `language` / `colorScheme` values are observed by the theme builder on first frame. While unhydrated it renders a **neutral background-only hold** (no branding, no native-launch impersonation — see "Hydration / splash rework"). This is a one-time gate at app startup, not a runtime event.

---

## 3. State machine

No state-machine changes. Theme selection is a function of `uiStore.colorScheme`:

```
colorScheme = 'light'  →  Theme(tokens.light)
colorScheme = 'dark'   →  Theme(tokens.dark)
```

| State                  | User-visible feedback                                  |
| ---------------------- | ------------------------------------------------------ |
| `colorScheme = light`  | App renders against light tokens; matches today's pixels (I1). |
| `colorScheme = dark`   | App renders against dark tokens; matches today's pixels (I1). |

No `'x1'` state — x1Theme is removed in this slice (D4). UIStore's `colorScheme` type is already `'light' | 'dark'` (C, `src/store/UIStore.ts:32`); the type was narrowed earlier than the theme cleanup.

---

## 4. Contract

### 4a. The tokens module (`src/theme/tokens` — exact path is the planner's call)

1. Exports a single named binding per mode: `lightTokens: Tokens` and `darkTokens: Tokens`, and a helper `resolveTokens(mode: 'light' | 'dark'): Tokens`.
2. Contains no React, no Paper, no MobX imports. Pure data + types.
3. Color values, spacing scale, radius scale, stroke scale are sourced verbatim from the canonical Figma file (`RZxDJea4t6jnBZrV4YBacF`, node `789:19792`). Light values are already verified (intent brief); dark values are pulled in `how.md` step 0 via `get_variable_defs` on `989:*` or the variable collection's dark binding.
4. Typography values use **absolute px line-heights only** (no multipliers, no percentage strings). The two known offenders from the canonical file are normalised:
   - `Headline/H1` (Fraunces, 36px, line-height 1.4 multiplier) → `lineHeight: 50` (= 36 × 1.4, rounded to integer).
   - `Styled/xs` (line-height 100%) → `lineHeight = fontSize` (1.0 multiplier resolved to px).
5. Weight mappings are static: token weight `400` → family `*-Regular`; token weight `500` → family `*-Medium`. No variable-axis weights (RN cannot consume them on iOS / Android consistently).
6. The non-Latin fallback rule is encoded as a function on the module: `typographyForLocale(style: keyof TokenTypography, locale: AvailableLanguage): TextStyle`. See §4d.
7. Aliases (`Gap/*` → `Spacing/*`, `radius/radius-xs` → `Radius/XS`) are resolved at token-module level, not at consumer level. Consumers see one scale per dimension.

### 4b. The theme builder (`useTheme()` hook and `lightTheme` / `darkTheme` exports)

1. `useTheme()` returns a `Theme` (§1b) — token superset + MD3-compat aliases + pinned legacy typography.
2. The builder reads `uiStore.colorScheme` (MobX-reactive) and selects the active token binding.
3. The builder is the **only** place that maps token keys to MD3-compat alias names. No component is allowed to know which fields are aliases.
4. The builder may continue to spread `baseTheme` (`MD3DarkTheme` / `PaperLightTheme`, C at `src/utils/theme.ts`) for **non-color, non-font** fields (`isV3`, `dark`, `roundness`, `animation`) that Paper itself reads but PocketPal does not override.
5. **The legacy `theme.fonts.*` MD3 typescale + custom TextStyles surface is constructed exactly as today** (preserving `configureFonts` output + the custom keys at `src/utils/theme.ts`). It is **not** derived from `theme.typography.*`. This is what gives I1 to the 18+ existing consumers.
6. `lightTheme` and `darkTheme` are also exported as plain values (no hook needed) so jest fixtures and any non-React code (e.g. test-utils) can use them. (C: same exports exist today.) These exports are en-locale snapshots.

### 4c. Paper integration (`App.tsx`)

1. `PaperProvider theme={theme}` continues to wrap the app. `theme` is whatever `useTheme()` returns.
2. The Paper-compat alias surface is shaped so every Paper component currently in use continues to render identically to today (I1).
3. **No new `react-native-paper` import is added in this slice**, and no existing import is removed. The current Paper import surface (verified by `grep -rh "from 'react-native-paper'" src/`) is: `ActivityIndicator, Button, Card, Checkbox, Chip, Dialog, Divider, DividerProps, Drawer, FAB, Icon, IconButton, List, MD3Theme, Menu, Paragraph, Portal, ProgressBar, SegmentedButtons, Snackbar, Surface, Switch, Text, TextInput, Tooltip, useTheme` (~23 distinct components + types). Reducing to the locked thin set (`Text/Button/IconButton/Portal/Provider`) is FOU-115/123 work.
4. **(P, REVISED Round 2 — see "Hydration / splash rework") Hydration gate, neutral background-only splash:** the app must observe persisted `uiStore.language` and `uiStore.colorScheme` on first render. Implementation contract: `App` defers rendering `<PaperProvider>` (or anything that consumes `useTheme()`) until `mobx-persist-store`'s hydration of `UIStore` completes (`isHydrated(uiStore)`). While hydrating, render a **neutral background-only hold**: a single full-screen `View` whose only meaningful style is `backgroundColor` resolved from `Appearance.getColorScheme()` (system light/dark). **The splash MUST NOT contain any branding (`PocketPal` / `LLM Ventures` labels), any `Text`, any `SafeAreaProvider`, any `useSafeAreaInsets`, or any `initialWindowMetrics` dependency.** It does NOT impersonate the iOS launch storyboard and it does NOT introduce a branded screen on Android (which has no native launch screen — see §9l). Rationale: I1 + no-flash for persisted non-Latin language (see §9e, Scenario H); a background-only `View` has nothing to match against either native launch surface, so it cannot diverge from native on any axis (this is the design that ends the four-round native-matching churn). Without the gate, the first paint uses the in-memory defaults (`colorScheme = system`, `language = 'en'`) and a persisted `language = 'ja'` user sees Fraunces for one frame before the AsyncStorage promise resolves.

### 4d. RTL & non-Latin fallback at the typography layer

1. For each `TokenTypography` style, the resolved `fontFamily` is a single string today (RN limitation: `fontFamily: 'Fraunces-Regular'`). RN does not honour CSS-style font-family fallback lists.
2. The non-Latin fallback is therefore a **per-style selection function**:
   - If the style is Fraunces-family AND the active locale is in the non-Latin set → swap the family for the Inter equivalent at the same weight (e.g. `Fraunces-Regular` → `Inter-Regular`).
   - If the style is Fraunces-Italic AND active locale is non-Latin → swap to `Inter-Medium` with `fontStyle: 'italic'`. (Decision: see D5.)
   - If the style is Inter or JetBrains Mono → no swap (Inter covers Latin + Cyrillic; JetBrains Mono is for code blocks regardless of locale).
3. The selection function is invoked **inside the theme builder**, not at component-call sites. Components remain locale-agnostic: they read `theme.typography.headlineH1` and get the right family for the active locale.
4. RTL mirroring (`I18nManager.isRTL`, `writingDirection: 'rtl'`) is **not** encoded in tokens. Tokens contain no directional values (no `marginLeft`, no `textAlign`). Components handle direction with RN's built-in `start`/`end` semantics in later slices.
5. The active locale is read from `uiStore.language` (MobX-reactive, same store and access pattern as `colorScheme`). The theme builder subscribes to both signals.

### 4e. Hard invariants

- **I1 (no visual regression)**: For every screen of the app, light AND dark, on iOS AND Android, the rendered output is pixel-identical (or visually indistinguishable to a designer's eye) to the pre-refactor build. The only allowed differences are sub-pixel font-rendering shifts on text that did not change family/size/weight. Any screen that fails this invariant is a bug in the migration tables (§1c, §1d), not a new design choice.
- **I2 (token-source consistency)**: Every color / typography / spacing / radius / stroke value in the new tokens module is sourced from the canonical Figma file `RZxDJea4t6jnBZrV4YBacF` (light: confirmed light render; dark: dark binding of the same variable collection). Non-canonical Figma files (`fyC1zC0eq0nJjG5SFDexbY`, `szXSjMGisopPpjgmVjovoB`) are forbidden as sources. (Intent-brief decision.)
- **I3 (single scale per dimension)**: Spacing has one scale, radius has one scale, stroke has one scale. `Gap/*` and lowercase `radius/radius-xs` from the canonical file are resolved at the token module via alias, not exposed as parallel scales.
- **I4 (absolute line-heights)**: No `TokenTypography` entry uses a non-numeric or multiplier line-height. The Figma multipliers are converted to px in the token module.
- **I5 (single writer for `colorScheme`)**: `uiStore.setColorScheme()` remains the single writer. The theme builder is read-only. (C — see §5.)
- **I6 (single writer for `language`)**: `uiStore.setLanguage()` remains the single writer. The theme builder is read-only. (C, defined in `src/store/UIStore.ts`.)
- **I7 (Paper surface is preserved, not reduced)**: This slice does NOT add any new `react-native-paper` component import in any file, and does NOT remove any existing one. The current Paper import surface (~23 components + types: `ActivityIndicator, Button, Card, Checkbox, Chip, Dialog, Divider, DividerProps, Drawer, FAB, Icon, IconButton, List, MD3Theme, Menu, Paragraph, Portal, ProgressBar, SegmentedButtons, Snackbar, Surface, Switch, Text, TextInput, Tooltip, useTheme`) is preserved as-is. Reducing the surface to the locked thin set (`Text/Button/IconButton/Portal/Provider`) is FOU-115/123 work, not this slice.
- **I8 (font family names match registered names)**: For every `fontFamily` string in `Tokens.typography.*`, a matching font asset is bundled and registered: iOS `UIAppFonts` (PostScript name) and Android `assets/fonts/{Name}.ttf`. CI / a script verifies this at build time (planner's call where this lives).
- **I9 (x1 is gone)**: No code path in `src/` references `x1Theme`, `AppTheme.X1`, or `'x1'` as a `colorScheme` value. (D4.)
- **I10 (hydration gate on first render, neutral splash)**: `<PaperProvider>` and any subtree that reads `useTheme()` are not mounted until `mobx-persist-store` has hydrated `UIStore`. Persisted `language` and `colorScheme` are observed on first frame. The hold rendered while unhydrated is a **neutral background-only `View`** (no branding, no `Text`, no safe-area provider/inset/`initialWindowMetrics`); it does not impersonate any native launch screen. (P, REVISED Round 2 — see "Hydration / splash rework", §4c.4, Scenario H.)

(Previous I9 — "no MD3 import in components" — has been deferred to §5 cleanup #5. It is not a slice deliverable.)

### 4f. What each component / module renders

| Component / module | Renders / produces | Does NOT render / produce |
| --- | --- | --- |
| `src/theme/tokens` (P) | Pure-data `lightTokens`, `darkTokens`, `Tokens` type. Family-name strings only — no font loading. | No React, no MobX, no Paper, no derived styles, no MD3 aliases. |
| `src/theme/builder` (P) — or whatever path the planner picks | The `Theme` superset for a given (mode, locale). MD3-compat aliases + pinned legacy `theme.fonts.*`. | Token data (sourced from the tokens module). Components do not call this directly. |
| `useTheme()` (refactored from `src/hooks/useTheme.ts`) | The reactive `Theme` for the current (`colorScheme`, `language`) pair. | No state of its own. Pure reader. |
| `lightTheme`, `darkTheme` exports | Pre-built `Theme` snapshots for the default locale (`en`). Used by jest fixtures and non-React code. | No locale-aware swaps — these are the en-locale snapshots. Locale-swapped values are only available via the hook. |
| `App.tsx` | (a) Hydration gate (I10): renders a **neutral background-only hold** (flat colored `View`, no branding/`Text`/safe-area) while `mobx-persist-store` hydrates `UIStore`. (b) `<PaperProvider theme={theme}>` — wraps app with `useTheme()` output once hydrated. | No theme construction logic. **No branded splash, no native-launch impersonation, no `SafeAreaProvider`/`initialWindowMetrics` in the hold.** |
| Existing component `styles.ts` files | Continue to read `theme.colors.*`, `theme.fonts.*` (MD3 typescale + custom), `theme.spacing.default`, `theme.borders.*`, `theme.insets.*`. (C — preserved by the unchanged legacy surface.) | Direct font-file imports, raw hex values, or MD3 internals. |
| `src/utils/types.ts`, `src/utils/index.ts`, `src/components/SidebarContent/styles.ts`, `src/components/RenameModal/styles.ts` | Continue to import `MD3Theme` / `MD3Colors` / `MD3Typescale` (C, unchanged). | Migration to a Paper-free type is deferred — see §5 #5. |

---

## 5. Layer ownership (single-writer rule)

For each mutable field the change touches:

| Field | Single writer | Notes |
| --- | --- | --- |
| `uiStore.colorScheme` | `uiStore.setColorScheme()` (C, `src/store/UIStore.ts:104`) | Settings toggle is the only caller. (C, `src/screens/SettingsScreen/SettingsScreen.tsx:934`.) |
| `uiStore._language` | `uiStore.setLanguage()` (C) | Read via `uiStore.language` getter. |
| `Tokens.{colors,typography,spacing,radius,stroke}` | The tokens module exports — values are `const`, never mutated at runtime. | No runtime mutation; mode swap is binding selection, not mutation. |
| `Theme.colors.*` / `Theme.fonts.*` / `Theme.typography.*` / etc. | The theme builder is the **only** code path that constructs a `Theme`. (P) | Components must never mutate the returned object. |
| Bundled font file set | `react-native.config.js` + `ios/PocketPal/Info.plist` `UIAppFonts` + `android/app/src/main/assets/fonts/` (P) | Single source = `src/assets/fonts/`. iOS plist and Android assets are linked outputs. CI must verify drift (I8). |

Recent / past pain related to multi-writer races for these fields: none. `colorScheme` is set only in Settings; `language` is set only in Settings + persistence rehydration. No new writer is introduced here.

**Deferred cleanups** (recorded, not done in this slice):

1. Migrate component `styles.ts` files from `theme.spacing.default` → `theme.spacing.m` and from `theme.fonts.bodyMedium` → `theme.typography.bodyM` etc. Belongs to per-screen restyle slices (FOU-117–122).
2. Remove MD3-compat aliases (`theme.spacing.default`, MD3 typescale on `theme.fonts`) once all consumers are migrated. Belongs to FOU-123.
3. Move `stateLayerOpacity` family out of `colors` and into a dedicated `interaction` namespace. Belongs to FOU-115 or later.
4. Migrate `withOpacity`-computed semantic surface colors (`surfaceContainer*`, `surfaceDim`, `surfaceBright`) from their current opacity-math derivations to explicit tokens once the canonical Figma file confirms direct bindings. The migration table §1c assumes explicit bindings exist; if a key is missing in the canonical file, we fall back to the (C) `withOpacity` math at the builder layer and flag it in the tokens-module comments — but the per-key decision is HOW work, not WHAT.
5. **Eliminate `MD3Theme` / `MD3Colors` / `MD3Typescale` imports from `src/`.** Today these are imported by:
   - `src/utils/types.ts:4,9` — `Theme extends MD3Theme`; `MD3BaseColors extends MD3Colors`; `ThemeFonts extends MD3Typescale`.
   - `src/utils/index.ts:6` — `getThemeColorsAsArray(theme: MD3Theme)`.
   - `src/components/SidebarContent/styles.ts:3` — `createStyles(theme: MD3Theme)`.
   - `src/components/RenameModal/styles.ts:2` — `createStyles(theme: MD3Theme)`.
   Migrating these requires replacing `MD3Theme` with our own `Theme` type (or a narrower interface) and re-validating that all consumers of `getThemeColorsAsArray` / the two `createStyles` factories still typecheck. Belongs to FOU-123 (or a small precursor) once the alias surface is stable. Not in this slice — out of scope for an invisible foundation.

---

## 6. Canonical scenarios

Each scenario is manually verifiable. Visual diffing is the primary acceptance check.

### A. Light mode, en locale, unchanged pixels

```
Input
  uiStore.colorScheme = 'light'
  uiStore.language    = 'en'
  Pre-merge baseline screenshots: Chat, Pals, Models, Settings, Benchmark, About, screens of all 6 drawer routes
─────────────────────────────────────────
Post-merge build produces screenshots indistinguishable from the baseline.
- Backgrounds, surfaces, text colors match.
- All Inter weights render in correct slots.
- Borders, radii, padding identical.
- No layout reflow.
```

### B. Dark mode, en locale, unchanged pixels

```
Input
  uiStore.colorScheme = 'dark'
  uiStore.language    = 'en'
  Pre-merge baseline dark-mode screenshots of all 6 drawer routes.
─────────────────────────────────────────
Post-merge dark-mode screenshots indistinguishable from baseline.
- All dark-mode color tokens resolve to the dark binding (sourced from canonical Figma `989:*`).
- No screen flickers light during mount.
```

### C. Headline rendered in Fraunces for a Latin locale

```
Input
  uiStore.language = 'en'  (or 'id', 'ru', 'ms', 'uk' — any Latin script-set locale)
  Any screen using tokens.typography.headlineH1
─────────────────────────────────────────
Text renders in Fraunces-Regular at 36px, line-height 50px (I4).
- iOS: PostScript name 'Fraunces-Regular' resolves.
- Android: 'Fraunces-Regular.ttf' resolves.
- No system-font fallback observed.
```

### D. Headline falls back to Inter for a non-Latin locale

```
Input
  uiStore.language ∈ { 'fa', 'he', 'ja', 'ko', 'zh', 'zh_Hant' }
  Any screen using tokens.typography.headlineH1
─────────────────────────────────────────
Text renders in Inter-Regular at 36px, line-height 50px.
- Same metrics (size, line-height, letter-spacing) as the Fraunces version (kerning may differ slightly).
- Inter glyphs cover the locale's primary script (Inter has full CJK fallback via system on iOS / Android — that is RN-default behaviour).
- No Fraunces glyphs visible.
```

### E. Mode swap is reactive

```
Input
  Settings → toggle "Dark mode" on
─────────────────────────────────────────
Every visible component re-renders with dark tokens within one frame.
- Mode swap triggers a re-render via MobX reactivity in useTheme().
- PaperProvider re-renders with a new `theme` prop (no remount, same React instance).
- NavigationContainer not remounted.
- Behavior is unchanged from today's app.
```

### F. Language swap is reactive (typography fallback applies)

```
Input
  Settings → change Language from 'en' to 'fa'
─────────────────────────────────────────
Every component reading a Fraunces-family typography token re-renders with Inter-Regular.
- PaperProvider re-renders with a new `theme` prop (no remount).
- NavigationContainer not remounted.
- MobX reactivity in useTheme() (or its inner subscription to uiStore.language) is the only re-render trigger.
```

### G. JetBrains Mono renders for code blocks

```
Input
  Any chat message containing a fenced code block (` ``` ` block) in any locale
─────────────────────────────────────────
Code renders in JetBrains-Mono-Regular (or -Medium where the existing markdown component asks for emphasis), at the size defined by tokens.typography.codeM / codeS.
- Locale fallback does NOT apply to code (§4d.2).
```

### H. Cold start with persisted non-Latin language — no Fraunces flash (NEW)

```
Input
  Prior session: uiStore.setLanguage('ja') was called and persisted.
  AsyncStorage now contains the 'ja' language entry under the 'UIStore' key.
  App is force-killed and re-launched.
─────────────────────────────────────────
On the very first painted frame that contains a headline (e.g. an onboarding header, a screen title using tokens.typography.headlineH1):
- The text is rendered in Inter-Regular, NOT Fraunces.
- No flash of Fraunces (the family-mismatch glyph silhouette) is observable.

Mechanism (per §4c.4 / I10, REVISED Round 2):
- App.tsx defers <PaperProvider> mount until mobx-persist-store has hydrated UIStore.
- During hydration, a NEUTRAL background-only splash View renders (backgroundColor from
  Appearance.getColorScheme(); NO branding, NO Text, NO safe-area provider/insets).
- After hydration completes (typically <1 frame, but bounded), the theme builder reads
  uiStore.language === 'ja' and produces headline tokens with the Inter family.
- First paint of any theme-consuming subtree therefore has the correct family already.
- The neutral hold does not impersonate the iOS storyboard; on iOS it continues the
  storyboard's flat system-background, on Android it continues the OS's flat launch color
  (Android has no native launch screen — §9l). There is nothing for the hold to match,
  so there is no native-divergence axis to review.

Acceptance:
- Manual: launch app on iOS sim with prior persisted Japanese setting; observe no Fraunces flash on screens with headline text.
- Automated (preferred): a Jest unit test asserts that the gate host renders its neutral
  hold (testID present, NO branded "PocketPal"/"LLM Ventures" text, NO PaperProvider) when
  isHydrated(uiStore) is false, and renders the PaperProvider subtree only when true. A
  second test flips hydration false->true after mount and asserts the hold unmounts and a
  post-hydration app element appears (closes the round-1 "permanent splash" gap).
```

---

## 7. State signals

| Signal | Set by | Read by | True when |
| --- | --- | --- | --- |
| `uiStore.colorScheme === 'dark'` | `uiStore.setColorScheme('dark')` | Theme builder; any direct consumer | User opted into dark mode (or system default was dark at first launch). (C.) |
| `uiStore.language` ∈ non-Latin set | `uiStore.setLanguage(lang)` | Theme builder (typography fallback selector, §4d) | User's selected language is in `{fa, he, ja, ko, zh, zh_Hant}`. (P.) |
| `I18nManager.isRTL` | RN platform / locale change at app launch | Components (later slices) | App is in RTL layout direction. Not consumed by this slice. (C — RN built-in.) |
| `isHydrated(uiStore)` (from `mobx-persist-store`) | `makePersistable` lifecycle | `App.tsx` (gates `<PaperProvider>` mount; neutral hold while false) | UIStore has finished loading from AsyncStorage. (P — see I10, §4c.4, "Hydration / splash rework".) |

---

## 8. Decisions

- **D1**: Introduce a new `Tokens` data shape distinct from `Theme`, with `Theme` as a superset alias surface. Rationale: lets new code read tokens directly while legacy code keeps its current keys; gives FOU-123 a clean removal line ("delete the alias layer").

  **Considered alternatives:**
  - *One-shot rewrite: replace `theme.fonts.bodyMedium` / `theme.spacing.default` / etc. with direct token reads across all ~94 Paper-touching files + ~50+ `theme.*.default` consumers in this slice.* Rejected: violates I1 risk surface — a per-file edit of every consumer in one PR is incompatible with the "invisible foundation slice" framing. The blast radius is too large to validate via visual diff alone, and the slice ceases to be reviewable.
  - *Defer tokens entirely: ship only fonts + theme decoupling (MD3 removal), leave token shape for FOU-115.* Rejected: leaves the token source open, splits the "design system foundation" into two PRs without a coherent boundary, and loses the single mode-aware token collection that the FOU-112 rollout plan depends on. The rollout plan (`context/redesign/FOU-112-rollout.md` §2,4) treats the token module as the Phase 1 deliverable; deferring it pushes all later slices.

- **D2**: Keep `useTheme()` as the single consumer entry point (no parallel `useTokens()`). Rationale: every consumer already calls `useTheme()`; adding a second hook doubles the migration surface and risks two hooks drifting.
- **D3**: Continue spreading Paper's `MD3DarkTheme` / `PaperLightTheme` for non-color non-font fields in the `Theme` builder. Rationale: those fields (`isV3`, `dark`, `roundness`, `animation`) are Paper-internal and must stay Paper-compatible; PocketPal does not override them today.
- **D4**: Remove `x1Theme` in this slice (not deferred to FOU-123). Rationale: x1 is already dead code (the export is unused; `UIStore.colorScheme` is already typed `'light' | 'dark'`); cleanup is one file change with zero behavioral risk; deferring it leaves a stale third theme in `src/utils/theme.ts` that future readers will keep asking about.
- **D5**: For Fraunces-Italic on non-Latin locales, fall back to `Inter-Medium` with `fontStyle: 'italic'` rather than shipping a separate `Inter-Italic` font cut. Rationale: RN's `fontStyle: 'italic'` synthesises italics on Inter acceptably on both platforms; shipping `Inter-Italic` adds ~200KB per cut for an accent style used in one place (`Styled/xs`).
- **D6**: Source dark tokens by reading the canonical Figma file's variable collection dark binding at the **start of HOW** (planner's step 0), NOT inferred / hand-derived from the light tokens. Rationale: dark mode in the canonical file is a designer decision; inference risks systematic mismatch. The intent brief explicitly defers this extraction to the architect/planner. **Disagreement-resolution rule:** if the canonical dark binding for a token disagrees with the current dark `Theme` value at a key that needs visual parity for I1 (i.e. the disagreement would produce a visible pixel difference on a screen that is in scope), the current dark value wins (I1 takes precedence), and the disagreement is logged as a designer ask on FOU-112. Consistent with §5 deferred cleanup #4.
- **D7**: No new flow doc is created in this PR until the WHAT is approved and the implementer absorbs the delta as `context/architecture/theming.md` in the same PR. Rationale: standard library lifecycle (see `context/architecture/README.md`); avoids creating a flow file that may not match the merged code.
- **D8**: The `language` signal is read **inside** the theme builder, not on every component. Rationale: keeps components locale-agnostic and concentrates the (small) set of locale-aware swaps to one place; future RTL refinements happen in one file.
- **D9**: Add the new Fraunces, Fraunces-Italic, and JetBrains Mono font weights `400` and `500` only (`*-Regular` and `*-Medium`) for each family in this slice. Rationale: the canonical Figma file only uses these weights; ship the minimum cuts; additional weights are added per future slice if a token demands them. Final per-family weight list is finalised in `how.md` against the resolved set of typography token weights (canonical file may also use 600/700 for one or two styles — that's a HOW-level confirmation, not a WHAT decision).
- **D10**: The legacy `theme.fonts.*` MD3 typescale + custom TextStyles + `theme.spacing.default` + `theme.borders.*` + `theme.insets.*` are **preserved verbatim** in this slice — same `configureFonts` output, same custom keys, same values. Rationale: this is what guarantees I1 (no visual regression) for the ~18 existing consumers of MD3 typescale keys + ~4 `theme.spacing.default` consumers + every legacy color consumer. Selective preservation would force per-file edits in this slice, which is out of scope for an invisible foundation slice. The legacy surfaces are deleted in FOU-123 once consumers migrate to `theme.typography.*` + `theme.spacing.*` token keys.
- **D11 (REVISED Round 2)**: Gate the first render of `<PaperProvider>` on `mobx-persist-store` hydration of `UIStore`, rendering a **neutral background-only hold** (NOT a branded native-launch impersonation) while unhydrated. Rationale: AsyncStorage hydration is async (`src/store/UIStore.ts:5,73-84`); without the gate, the first paint uses in-memory defaults (`colorScheme = Appearance.getColorScheme()`, `_language = 'en'`), and a persisted non-Latin language user would see Fraunces for one frame before hydration completes. This is a **new** visible regression introduced by the §4d typography fallback rule (today's app uses Inter unconditionally for headlines, so there's no race to lose), which is why FOU-114 owns fixing it. The gate + neutral hold is the minimum design that guarantees Scenario H with **no new dependency and no native-matching obligation** (see "Hydration / splash rework" Part A). Alternatives considered:
  - *Branded JS splash impersonating the iOS launch storyboard (the Round-1 design)*: Rejected this round. Caused four review rounds of native-matching churn (branding, safe-area, initialMetrics) and introduces a novel branded screen on Android, which has no native launch screen (§9l). A neutral hold has nothing to match and ends the churn.
  - *Hold the NATIVE launch screen via `react-native-bootsplash` / RN core splash API* (the architecturally-correct end state): deferred to **D12** — it is NATIVE_CHANGES=YES, scope-expanding (adds a native Android splash that never existed), and a human decision. Not in FOU-114.
  - *Pre-resolve a "safe" headline family if `language` is unhydrated but a persisted value exists*: requires reading AsyncStorage manually before MobX hydrates — duplicates the persistence layer. Rejected.
  - *Accept the one-frame flash and document it*: violates I1 spirit (the flash is a new behavior not present in today's build). Rejected.
  - *Extract the gate to its own task and ship FOU-114 as pure tokens+fonts (no gate)*: Acceptable fallback, NOT the recommendation. Tolerable only because no in-scope FOU-114 screen renders a headline token yet (the token exists but no current consumer uses it, §9j-style), so the Fraunces race cannot fire until a later slice. But it lands a known regression's fix in a follow-up rather than in the PR that opens the regression. Recommendation: keep the gate (Part A) in FOU-114. If the human chooses the strict-invisible split, the gate MUST land before any later slice renders a Fraunces headline.
- **D12 (new, DEFERRED — HUMAN DECISION)**: The architecturally-correct long-term mechanism is to **hold the native launch screen until hydration** via `react-native-bootsplash` (or RN's built-in splash-hide API): JS calls `hide()` once `isHydrated(uiStore)` is true, the real native launch screen IS the splash on both platforms, and JS renders no splash at all. This closes the Android gap natively (Android gains a real native splash theme, where branding belongs) and removes the JS splash entirely. **Not adopted in FOU-114** because it is NATIVE_CHANGES=YES (new dependency + iOS `pod install` + Android splash theme/drawable + native linking) AND it adds a *new branded launch surface on Android* that never existed — a product/design decision plus a native-build expansion that both warrant their own task and visual sign-off, not a rider on an invisible token-foundation slice. Recorded as a forward cleanup reminder (§10) and a designer/PM ask. Rationale for deferring rather than adopting now: FOU-114's acceptance is fully met by D11+I10 (Part A) with zero scope/dependency change; Part B is an enhancement, not a requirement of this slice.

---

## 9. Edge cases

### 9a. Missing dark binding for a token

A token has a light value in the canonical Figma file but no dark binding (e.g. a designer oversight). Builder behavior: the dark `Tokens` falls back to the corresponding light value AND the tokens module flags the key in a `// TODO: dark binding missing` comment. The token is **not** invented from `withOpacity` math. Rationale: prefers visible "this looks wrong in dark mode" as a designer-fixable bug over a silent invention. (Hits I2; see also D6 disagreement-resolution rule for the I1-conflict case.)

### 9b. Font asset present but PostScript name mismatch (iOS)

A font file is dropped into `src/assets/fonts/` and listed in `react-native.config.js` and `Info.plist`, but the iOS PostScript name differs from the filename (e.g. file is `Fraunces-Regular.ttf` but PostScript name is `Fraunces-Regular_Foundation`). RN renders the system font instead. Mitigation: a manual verification step in `how.md` (open each TTF in Font Book or `otfinfo --postscript-name`) **and** an iOS smoke screen that renders one Fraunces sample for visual confirmation in build verification (intent brief acceptance criterion).

### 9c. Font asset missing on Android only

The font is listed in `react-native.config.js` and present in `src/assets/fonts/` but native linking did not copy it into `android/app/src/main/assets/fonts/`. RN renders the system font. Mitigation: the implementer runs `npx react-native-asset` (or equivalent) and the planner adds a step that verifies the file lands in `android/app/src/main/assets/fonts/` before claiming the build is ready. (I8.)

### 9d. User switches language mid-session

`uiStore.setLanguage('fa')` fires while a screen is mounted. Expected: MobX reactivity propagates through `useTheme()` → `theme.typography.headlineH1` resolves to Inter on the next render frame. No state to migrate. (Scenario F.)

### 9e. Cold start with persisted non-Latin language

**Problem:** App restarts with persisted `language = 'ja'`. `mobx-persist-store` hydrates `UIStore` from AsyncStorage asynchronously (verified at `src/store/UIStore.ts:73-84`, `storage: AsyncStorage`). There is no current code path that gates first render on hydration completion (verified: `grep -rn "isHydrated\|hasHydrated" src/` returns no hits). Without intervention, first paint would render with the in-memory defaults (`_language = 'en'`, headline = Fraunces), then re-render with Inter once hydration resolves — a visible flash.

**Design (REVISED Round 2):** App.tsx adds a hydration gate per §4c.4 / D11 / I10. The gate uses `mobx-persist-store`'s `isHydrated(uiStore)` accessor and renders a **neutral background-only hold** (a single `View` with `backgroundColor` resolved from `Appearance.getColorScheme()`; no branding, no `Text`, no safe-area provider/insets, no `initialWindowMetrics`) while `false`. Once `true`, `<PaperProvider>` mounts. First theme-consuming paint therefore reads the persisted `language` value. (Scenario H.) The neutral hold is the design that ends the four-round native-matching churn: a flat colored `View` has nothing to match against the iOS storyboard or the (absent) Android launch screen, so there is no per-platform divergence to review (§9l).

**Note on `colorScheme` flash:** today's app already exhibits a colorScheme flash on cold start (the in-memory default is `Appearance.getColorScheme()`, which may differ from the persisted value). The new hydration gate fixes that too as a side effect — but the gate's primary purpose is the language race, since the colorScheme race was already present and tolerated in (C).

**Note on scope (Round 2):** The colorScheme race is **pre-existing** (C — `App.tsx` renders `<PaperProvider>` immediately today) and is NOT FOU-114's to fix; the gate fixes it only incidentally. FOU-114 owns only the **font** race, which the §4d fallback rule newly introduces. If the human elects to extract the gate to its own task (D11 fallback), FOU-114 ships strictly invisible (tokens+fonts, no gate) and the gate lands before any later slice renders a Fraunces headline.

### 9f. RTL locale without RTL screen mirroring

User picks `he` or `fa`. App reading direction does NOT mirror in this slice (RTL screen mirroring is later-slice work). Typography fallback still applies (headlines render in Inter). Expected: text alignment may look wrong; **this is acknowledged and out of scope**. The intent brief locks RTL screen mirroring as engineering's responsibility "at the typography / token layer" only for FOU-114. Visual mirroring is FOU-117+ work.

### 9g. A consumer still uses a not-aliased name

A consumer reads `theme.someThingNew` that exists in `Tokens` but the alias layer didn't preserve. Expected: TypeScript compile error (we own `Theme`'s type). Mitigation: D10 (every current name preserved as alias) eliminates this in practice; the type system catches any residual.

### 9h. PaperProvider passes a theme Paper doesn't recognise

Paper's `Provider` validates its theme shape minimally — it reads `dark`, `colors.primary`, `colors.background`, `fonts.bodyMedium`, etc. The builder must preserve all the Paper-required fields. Expected: I7 catches this — Paper continues to render `Button` / `Text` / `IconButton` (and the broader Paper surface enumerated in I7) identically. Verified by scenario A + B (the entire UI uses Paper indirectly).

### 9i. New font added but only on one platform (iOS plist updated, Android assets/fonts/ not)

CI / `how.md` step verifies both targets are in sync. If a build slips with the iOS plist updated and Android assets missing, the Android scenario C / D fails visibly (system-font fallback). I8 + scenario tests guard this.

### 9j. JetBrains Mono not yet asked for by any current style

No (C) code today references JetBrains Mono explicitly. Code blocks in markdown render via `react-native-render-html` with default `<code>` styling. The new tokens module defines `codeM` / `codeS` but **no current consumer is updated in this slice to use it**. Expected: code blocks continue to render exactly as today (system monospace). The new token is available for the markdown / code-block restyle slice (FOU-117+) to opt into. This is consistent with I1: invisible foundation.

### 9k. Hydration hold visible for too long

`mobx-persist-store` hydration normally completes within a few microtasks (AsyncStorage read of one key). If it takes longer (slow device, cold disk cache), the neutral hold `View` is visible for that duration. Expected: the hold is a flat colored `View` matching the system color scheme, so a longer-than-microtask delay reads as plain "app launching" flat color on both platforms — acceptable. No spinner, no branding, no `Text` is required or permitted in this slice (per revised §4c.4 / I10). If hydration ever fails outright (AsyncStorage error), `mobx-persist-store` proceeds with in-memory defaults — accept the (C) behavior, do not invent error UI in this slice.

### 9l. Android has no native launch screen (the per-platform divergence the rework addresses)

(C, verified this round.) iOS has a branded native launch screen (`ios/PocketPal/Info.plist` `UILaunchStoryboardName = LaunchScreen`; `ios/PocketPal/LaunchScreen.storyboard` renders `PocketPal` + `LLM Ventures` on `systemBackgroundColor`). **Android has none**: `android/app/src/main/res/values/styles.xml` defines only `AppTheme` (`parent="Theme.AppCompat.DayNight.NoActionBar"`) with no `windowBackground` launch drawable, no Android-12 `windowSplashScreen*` theme, and there is no splash dependency in `package.json`. The OS shows a flat window background between process start and first JS frame, nothing more.

Consequence for this slice: a branded JS splash (Round-1 design) would be a **novel branded screen on Android** that did not exist pre-FOU-114, and `initialWindowMetrics` can be `null` on Android, re-exposing the round-4 blank-frame risk. The revised neutral background-only hold (§4c.4 / I10) sidesteps both: it continues the OS's flat launch color on Android and the storyboard's flat background on iOS, matching neither's *content* because it has none. Closing the Android gap with a *real native* launch screen (so Android stops being the odd platform out) is the D12 deferred follow-up — explicitly NOT a FOU-114 deliverable because it adds a native dependency and a new branded surface.

---

## 10. What this doc is NOT

- Not an implementation plan — file layout, refactor order, and migration scripts live in `how.md`.
- Not a designer hand-off — Figma is the design source; this doc reflects the slice of it that engineering owns.
- Not a record of what hard-codes exist today — those are migration entries in §1c / §1d, not the long tail of every literal hex in the codebase.
- Not a long-term API design — the Paper-compat alias surface and the legacy `theme.fonts.*` MD3 typescale are explicitly migration layers (D10) with a removal line in FOU-123.
- Not a per-language a11y / l10n review — RTL screen mirroring, IME, dynamic text scaling are later-slice concerns.
- Not a Paper-surface-reduction plan — that is FOU-115/123. This slice preserves the current Paper imports.

**Cleanup reminders** (for the implementer / next architects to track):

1. After this PR lands, **promote this WHAT to `context/architecture/theming.md`** (architect step on the same PR, per library lifecycle). **Round-2 note — two distinct artifacts, do not conflate them:**

   - **`App.tsx` *code* change (this PR):** the live code renders a *branded* hold (`HydrationSplashContent` with `PocketPal` / `LLM Ventures` `Text` labels, wrapped in a dedicated `SafeAreaProvider` reading `useSafeAreaInsets` / `initialWindowMetrics`). Strip it down to a single flat-`backgroundColor` `View` keyed off `Appearance.getColorScheme()` — remove the branded `Text` labels and the `SafeAreaProvider` / `useSafeAreaInsets` / `initialWindowMetrics` usage entirely (exact edits are HOW/implementer work, not this WHAT). The branding lives in *code*, not in theming.md.

   - **`context/architecture/theming.md` *doc* change (SAME PR):** theming.md today (§4c.4 line ~229, I10 line ~253, §9k line ~401) already describes a *neutral* "minimal splash (a `View` with `backgroundColor` from the system color scheme)" — it never described branding, `Text`, `SafeAreaProvider`, or `initialWindowMetrics`, so there is **nothing to strip from the doc**. The doc change is *positive tightening*: make §4c.4 / I10 / §9k state the neutral constraints **explicitly** — no branding (`PocketPal` / `LLM Ventures` labels), no `Text`, no `SafeAreaProvider`, no `useSafeAreaInsets`, no `initialWindowMetrics` — so a future reader cannot re-add them; add the new §9l Android-no-native-launch note; and record D12 (native-launch hold) as a deferred follow-up. These three additions are genuinely absent from theming.md today.
2. The deferred-cleanups list in §5 must be carried forward in the promoted doc until each item lands.
3. If `how.md` step 0 (dark-token extraction) finds tokens with no dark binding in the canonical file, those are designer asks logged on FOU-112 — not invented at the engineering side.
4. The Paper-surface reduction to the thin set (`Text/Button/IconButton/Portal/Provider`) tracked under FOU-115/123.
5. **D12 (native launch-screen hold) — deferred, human decision.** The startup hold should eventually move from a JS neutral `View` to holding the *native* launch screen until hydration (`react-native-bootsplash` / RN core splash-hide API). This is NATIVE_CHANGES=YES, adds a real native splash to Android (which has none today — §9l), and is a product/design + native-build decision. Track as its own task with visual sign-off; do NOT fold into FOU-114.

---

## 11. Drift check

I read `src/utils/theme.ts`, `src/utils/types.ts`, `src/hooks/useTheme.ts`, `src/store/UIStore.ts`, `App.tsx`, `react-native.config.js`, `ios/PocketPal/Info.plist`, the contents of `android/app/src/main/assets/fonts/`, `src/locales/index.ts`, `src/components/Selector/Selector.tsx`, `src/components/SidebarContent/styles.ts`, `src/components/RenameModal/styles.ts`, `src/utils/index.ts`, `src/components/ChatInput/styles.ts`, and `src/screens/SettingsScreen/SettingsScreen.tsx` to verify the (C) claims. No prior `context/architecture/*.md` covers the theme / token surface, so there is no existing doc to drift against. The (C) statements in §1c, §1d, §3, §4c.3, §4f, §5, §9e, §9j reflect the code as of this branch.

Verified specifics (round-1 re-check):

- **Persistence backend.** `UIStore` calls `makePersistable(this, { ..., storage: AsyncStorage })` (`src/store/UIStore.ts:5,73-84`). NOT MMKV. There is no MMKV import anywhere in `src/store/`.
- **No hydration gate exists today.** `grep -rn "isHydrated\|hasHydrated" src/` returns no hits. `App.tsx` renders `<PaperProvider>` immediately (`App.tsx:82`); the colorScheme race is already present and tolerated.
- **Paper import surface (~23 components + types).** From `grep -rh "from 'react-native-paper'" src/`: `ActivityIndicator, Button, Card, Checkbox, Chip, Dialog (and PaperDialog alias), Divider (and PaperDivider alias), DividerProps, Drawer, FAB, Icon, IconButton, List, MD3Theme, Menu (as PaperMenu), Paragraph, Portal, ProgressBar, SegmentedButtons, Snackbar, Surface, Switch, Text, TextInput (and PaperTextInput alias), Tooltip, useTheme (and usePaperTheme alias)`. Card is used in `BenchmarkScreen`, `BenchResultCard`, `DeviceInfoCard`, `SquarePalCard`, `DevToolsScreen`, `DatabaseInspectorScreen`, `TestCompletionScreen`, `ModelCard`, `ModelSettings`, `SettingsScreen`, `SkillsDisplay` — NOT by `Selector`. `Selector` uses `Button, Text, Icon` (`src/components/Selector/Selector.tsx:4`).
- **MD3 imports in `src/`.** `MD3Theme` / `MD3Colors` / `MD3Typescale` are imported by `src/utils/types.ts:4,9,289`, `src/utils/index.ts:6`, `src/components/SidebarContent/styles.ts:3`, `src/components/RenameModal/styles.ts:2`, and `src/hooks/useTheme.ts`. Migrating these to a Paper-free type is deferred to §5 cleanup #5.
- **MD3 typescale consumer count.** `grep -rh "theme\.fonts\.(bodyMedium|titleSmall|bodyLarge|displaySmall|headlineLarge|headlineMedium|labelLarge)" src/ | wc -l` returns 18. These are pinned in this slice per §1d row 2 and D10.
- **`theme.spacing.default` consumer count.** `grep -rln "theme.spacing.default" src/ | wc -l` returns 4. Same migration strategy.
- **x1 deadness.** `src/utils/theme.ts:422` exports `x1Theme` but the type of `uiStore.colorScheme` is already `'light' | 'dark'` (`src/store/UIStore.ts:32`), meaning x1 has been dead code since UIStore was narrowed. D4 removes the stale export.
- **`fontStyles` legacy module export.** `src/components/ChatInput/styles.ts:4,145,152,157,162` imports `fontStyles` from `'../../utils/theme'`. Preserved verbatim per §1d.

Verified specifics (round-2 re-check, native launch screens):

- **iOS native launch screen exists and is branded.** `ios/PocketPal/Info.plist` sets `UILaunchStoryboardName = LaunchScreen`; `ios/PocketPal/LaunchScreen.storyboard` renders `PocketPal` (boldSystem 36pt) + `LLM Ventures` (system 17pt) on `systemBackgroundColor`, tagline pinned to safe-area-bottom + 20pt.
- **Android has NO native launch screen.** `android/app/src/main/res/values/styles.xml` defines only `AppTheme` (`parent="Theme.AppCompat.DayNight.NoActionBar"`) with no `windowBackground` launch drawable and no Android-12 `windowSplashScreen*` theme. `AndroidManifest.xml` `application android:theme="@style/AppTheme"`; no splash dependency in `package.json` (`grep -i splash package.json` → none). The current Round-1 branded JS splash is therefore a novel branded screen on Android.
- **`useTheme()` subscription path is stable as of round 4.** `src/hooks/useTheme.ts` retains `usePaperTheme()` as the React-context subscription path for non-`observer` consumers and caches by Paper-theme identity then `${mode}:${language}` (WeakMap). This rework does NOT touch the hook; it touches only the `App.tsx` startup hold.

Minor drift observed: none beyond the items already enumerated above. No `context/architecture/theming.md` drift to reconcile against code at the splash surface — the doc has not yet been promoted from this WHAT (D7). theming.md today (§4c.4 ~line 229, I10 ~line 253, §9k ~line 401) already describes a **neutral** minimal splash (a `View` with `backgroundColor` from the system color scheme); it has never described branding, `Text`, `SafeAreaProvider`, or `initialWindowMetrics`. The Round-1 branded design lives only in App.tsx *code*. In the same PR the implementer therefore (a) strips the branded `Text` + `SafeAreaProvider`/insets/`initialWindowMetrics` from App.tsx *code*, and (b) makes a *positive* doc edit to theming.md — stating the neutral constraints explicitly + adding §9l + recording D12 (see §10 cleanup reminder 1). The doc edit adds constraints, it does not strip a branded design that was never in the doc.
