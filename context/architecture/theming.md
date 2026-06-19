# Theming & Design Tokens — Architecture & Flow Board

Promoted from `workflows/stories/TASK-20260519-2110/what.md` on merge of
FOU-114 (Phase 1 of the FOU-112 redesign rollout). Extended on merge of
FOU-115 / TASK-20260524-2320 (Phase 2 — DS component layer + Paper-
import blocklist seed + token key rename to mirror Figma).

This is the cumulative truth for the theme / token / typography layer.
Any future restyle slice (FOU-115 through FOU-123) implements against
this doc; deltas are drafted as story-scoped WHATs and merged back here
on PR landing.

---

## Conventions

- **(C)** = current behaviour, documented from code
- **(D)** = decision (resolved trade-off, with one-line rationale)

(Story-scoped WHATs may carry **(P)** for proposals; this doc resolves
them to **(C)** at promotion time. No **(P)** or **(?)** entries
should remain here.)

---

## 0. Scope & non-scope

In scope:

- Token module shape (color / typography / spacing / radius / stroke), light + dark, mode-aware.
- Font assets: Inter (Bold / ExtraBold / Light / Medium / Regular / SemiBold / Thin), Fraunces (Regular / Medium / Italic / MediumItalic), JetBrains Mono (Regular / Medium) — static cuts only. Wired iOS (`UIAppFonts` + `link-assets-manifest.json` + pbxproj Resources phase) + Android (`android/app/src/main/assets/fonts/` + `android/link-assets-manifest.json`).
- Theme builder: `buildTheme({mode, language})` decoupled from MD3 internals where the new system diverges, while keeping `PaperProvider` / `Portal` and `useTheme()` working.
- RTL + non-Latin/CJK fallback rules at the token layer (no per-component handling).
- Mapping of current component visuals onto the new tokens so the build is **visually unchanged**.
- Hydration gate at `AppWithMigrationWrapper` to guarantee no FOUC for persisted `language` (cold start, non-Latin locales).

Also in scope (added by FOU-115 / Phase 2):

- A new namespace `src/components/ui/` holding the Phase 2 shared component library, built against the tokens layer in parallel with the legacy `src/components/*` namespace (which keeps working through Phase 3 swaps and is removed in Phase 4 / FOU-123).
- A per-component wrap-vs-rebuild matrix (D13–D32): rebuild visually-defining families from RN primitives + Pressable; wrap `react-native-paper` for a11y-heavy form controls (`Switch`, `Checkbox`, `RadioButton`).
- A Header building block (Figma `3011:23955`) reused by every DS overlay (Sheet/Modal/Dialog) — see §4i.
- Paper-import discipline enforced via ESLint `no-restricted-imports` `importNames` blocklist that grows entry-by-entry as DS replacements ship (replaces the retired `verify-paper-surface.js`). Phase 2 seed: `['Surface']`.
- `testID` + accessibility-label freeze contract on every DS component (§4l).
- Visual-parity snapshot strategy: every DS component ships a bounded `variant × size × state × mode` snapshot matrix as the Phase 3 comparison baseline (§4k).

Explicitly NOT in scope:

- Any visible restyle of any screen / component (FOU-114 was invisible). Phase 2 ships library + snapshots + the two `Surface` consumer swaps only; no new screen wiring.
- Per-component restyle work (FOU-117–122).
- Sheet/Modal/ConfirmationDialog **call-site migration** beyond the two `Surface` consumers (`UsageStats`, `PalDetailSheet`). The DS `Sheet`/`Modal`/`Dialog` exist; the existing `src/components/Sheet/Sheet.tsx` and `src/components/Dialog/Dialog.tsx` stay in place and Phase 3 slices migrate call-sites incrementally.
- Per-language locale UI direction switching beyond what the token layer needs.
- Reducing the current `react-native-paper` import surface beyond the seed Surface entry (FOU-115 Phase 3 / FOU-123).
- Migrating components that import `MD3Theme` / `MD3Colors` / `MD3Typescale` to a Paper-free type (FOU-123).

---

## 1. Data model

### 1a. Token module shape

The token layer is a pure-data module (under `src/theme/tokens/`) rendered into a typed `Tokens` shape. `Tokens` is mode-resolved (light or dark binding chosen once per render based on `uiStore.colorScheme`). Token names mirror the canonical Figma collection (`RZxDJea4t6jnBZrV4YBacF`, node `789:19792`).

```
Tokens
  colors: TokenColors           // every key has a light and dark binding
    background, surface, surfaceVariant
    onBackground, onSurface, onSurfaceVariant
    primary, onPrimary, primaryContainer, onPrimaryContainer
    secondary, onSecondary, secondaryContainer, onSecondaryContainer
    tertiary, onTertiary, tertiaryContainer, onTertiaryContainer
    border, outline, outlineVariant
    error, onError, errorContainer, onErrorContainer
    // semantic surface variants (currently withOpacity-derived, FOU-115)
    surfaceContainerHighest / High / / Low / Lowest, surfaceDim, surfaceBright
    // text variants
    text, textSecondary, inverseText, inverseTextSecondary
    // interactive state opacities
    stateLayerOpacity, hoverStateOpacity, pressedStateOpacity,
    draggedStateOpacity, focusStateOpacity
    // PocketPal extras
    menu*, authorBubbleBackground, receivedMessage*, sentMessage*,
    userAvatar*, searchBarBackground, thinkingBubble*,
    bgStatus*, btn*, iconModelType*
    accent.peach                      // NEW (FOU-116): peach pill highlight + Recommended-tier card background
    accent.yellowSubtle, accent.yellowMute  // NEW (POC-30): floating-tab active pill fill + border
    yellowAccent, yellowHighestContrast     // NEW (POC-30): pal-carousel active card border + label
    foregroundPrimary, foregroundTertiary, foregroundSubtle  // NEW (POC-30): canonical Figma Color/Foreground/* greys
    midnightHigh, midnightLow               // NEW (POC-30): composer send-button gradient stops

  typography: TokenTypography
    bodyM, bodyS                       // Inter
    uiM, uiS                           // Inter Medium
    titleL, titleM, titleS             // Inter Medium
    captionM, captionS                 // Inter
    headlineH1                         // Fraunces (Latin-only subset); Cyrillic + non-Latin → Inter
    styledXs                           // Fraunces-Italic
    codeM, codeS                       // JetBrains Mono

  spacing: TokenSpacing
    none: 0, xxs: 2, xs: 4, s: 8, sm: 12, m: 16, ml: 20, l: 24, xl: 32, xxl: 40   // NEW: xl, xxl

  radius: TokenRadius
    none: 0, xxs: 2, xs: 4, s: 8, m: 12, ml: 16, l: 20, xl: 32, xxl: 40
    //  ↑ no `sm` step (Figma jumps S(8)→M(12));
    //    `m` is 12 (was 16), `ml` is 16 (was 20), `l` is 20 (was 32),
    //    `xl` is 32 (was 40), `xxl` is 40 (new).
    //    Mirrors canonical Figma Radius/None|XXS|XS|S|M|ML|L|XL|XXL.

  stroke: TokenStroke
    xs: 0.5, sm: 1, md: 1.5, lg: 3
    // Renamed from {hairline, s, m, l} to mirror canonical Figma Stroke/*.
```

Two key correctness facts that motivate the rename:

- **Single source of truth = Figma name.** A Phase 3 designer spec saying "Radius/L" maps directly to `theme.radius.l = 20`. Before the rename, that spec would have read `theme.radius.l = 32`, which is the Figma value for `Radius/XL`. The rename closes a silent visual-regression vector.
- **No `radius.sm` exists** — Figma's `Radius/*` collection has no SM step (it jumps S(8) → M(12)). Code that previously typed `theme.radius.sm` had no canonical meaning; the rename surfaces that as a compile error.

Stored on disk: nothing. Tokens are pure code. Mode selection is read from `uiStore.colorScheme` (C — persisted by `mobx-persist-store` with **AsyncStorage** backend, `src/store/UIStore.ts:5,73-84`). Locale selection is read from `uiStore.language` (same store, same backend).

Computed at render: the resolved `Theme` consumed by components (see §1b) is built per-render by `useTheme()` from the active `Tokens` binding via `buildTheme({mode, language})`.

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
  borders:    { inputBorderRadius, messageBorderRadius, default }  // retained values
  insets:     { messageInsetsHorizontal, messageInsetsVertical }   // retained values
  icons?:     ThemeIcons   // retained
  isV3:       true        // Paper-internal
  dark:       boolean     // Paper-internal
  roundness:  number      // Paper-internal
```

The intent is single-direction migration: **new code reads tokens directly** (`theme.spacing.m`, `theme.colors.primary`, `theme.typography.bodyM`); **legacy code keeps working** via the existing `Theme.fonts.*` MD3 typescale, `Theme.spacing.default`, etc. The legacy surfaces are the migration layer, not a permanent dual API — they shrink to zero in FOU-123.

### 1c. Color migration table (legacy → token)

Every color reference in the current `Theme` continues to resolve. The new token module is the source; aliases preserve current names.

| Current name | Source in new model | Migration |
| --- | --- | --- |
| MD3 base colors (`primary`, `onPrimary`, `primaryContainer`, etc.) | `tokens.colors.*` (same key names, sourced from canonical Figma) | direct rename |
| `SemanticColors.surface*` (Highest/High/Container/Low/Lowest/Dim/Bright) | `tokens.colors.surface*` (currently withOpacity-derived; FOU-115 explicit bindings) | move from computed `withOpacity` math to explicit token bindings |
| `SemanticColors.text` / `textSecondary` / `inverseText` / `inverseTextSecondary` | `tokens.colors.{text,textSecondary,inverseText,inverseTextSecondary}` | direct rename |
| `border`, `placeholder` | `tokens.colors.{border,placeholder}` | direct rename |
| Menu colors (`menuBackground`, `menuBackgroundActive`, `menuSeparator`, etc.) | `tokens.colors.menu*` | direct rename |
| Message colors (`authorBubbleBackground`, `receivedMessage*`, `sentMessage*`, `userAvatar*`, `searchBarBackground`) | `tokens.colors.*` (same names) | direct rename |
| Thinking-bubble colors | `tokens.colors.thinkingBubble*` | direct rename |
| Status / button / icon-model-type colors (`bgStatus*`, `btn*`, `iconModelType*`) | `tokens.colors.*` | direct rename |
| `stateLayerOpacity`, `hoverStateOpacity`, `pressedStateOpacity`, `draggedStateOpacity`, `focusStateOpacity` | `tokens.colors.*` (kept under `colors` for source-compat) | direct rename |

### 1d. Typography migration table (legacy → token)

The Theme exposes **two parallel typography surfaces** during the migration window:

1. **`theme.typography.*`** — the new token shape (`bodyM`, `titleL`, `headlineH1`, `codeM`, etc.). Sourced from the canonical Figma file. Locale-aware (Fraunces → Inter swap for non-Latin per §4d). **New code reads this.**
2. **`theme.fonts.*`** — the existing MD3 typescale + PocketPal-custom TextStyles. **Pinned to today's MD3 values, unchanged.** Removed in FOU-123 once consumers migrate.

The two surfaces **do not cross-feed**. New tokens do not derive from legacy MD3 values; legacy MD3 values are not re-sourced from new tokens. This is what guarantees I1 for legacy consumers.

| Current name | New token surface | Behaviour |
| --- | --- | --- |
| `fontStyles.regular` / `medium` / `bold` / `thin` / `light` / `semibold` / `extraBold` | n/a (legacy module export at `src/utils/theme.ts`) | exported `fontStyles` object **preserved verbatim** (`ChatInput/styles.ts` consumes it). Removed in FOU-123. |
| MD3 typescale on `theme.fonts.*` (`displaySmall`, `headlineLarge`, `headlineMedium`, `bodyMedium`, `bodyLarge`, `titleSmall`, `labelLarge`, etc.) | n/a | **values pinned to today's `configureFonts` output** — same `fontFamily / fontSize / lineHeight / letterSpacing / fontWeight`. |
| `theme.fonts.titleMediumLight` (custom) | n/a | **preserved verbatim**. Removed in FOU-123. |
| `theme.fonts.dateDividerTextStyle` / `emptyChatPlaceholderTextStyle` / `inputTextStyle` / `receivedMessage*` / `sentMessage*` / `userAvatarTextStyle` / `userNameTextStyle` | n/a | **preserved verbatim** as composite TextStyles in the theme builder. Removed in FOU-123. |
| (new) | `theme.typography.{bodyM,bodyS,uiM,uiS,titleL,titleM,titleS,captionM,captionS,headlineH1,styledXs,codeM,codeS}` | new surface; values sourced from canonical Figma; new code reads this directly. |

### Glossary

- **Tokens** — pure-data, no React imports, the source of truth for color / typography / spacing / radius / stroke values. Mode-aware: every token has a light and dark binding. Lives at `src/theme/tokens/`.
- **Theme** — the runtime object consumed via `useTheme()`. A superset of resolved tokens plus MD3/Paper-compat aliases. Built per-render by `buildTheme({mode, language})`.
- **Mode** — `'light' | 'dark'`. Sourced from `uiStore.colorScheme`. (x1 is gone.)
- **MD3-compat alias** — a key on `Theme` whose name matches an MD3 / current-code identifier and whose value is preserved verbatim (color) or pinned to today's value (typography). Migration layer, not a permanent API.
- **Fraunces-fallback set** — locales whose primary script is not covered by the **bundled Fraunces subset**, which is Latin-only (Fontsource's Latin cut — no Cyrillic codepoints). For these, Fraunces tokens fall back to Inter (which ships Latin + Cyrillic; for scripts Inter doesn't cover, the platform falls back to system fonts). For PocketPal's supported languages (`en/fa/he/id/ja/ko/ms/ru/uk/zh/zh_Hant`) the set is `{fa, he, ja, ko, ru, uk, zh, zh_Hant}` — note `ru`/`uk` are included **because the bundled Fraunces has no Cyrillic glyphs**, not because Cyrillic is non-Latin in principle. The code constant is `NON_LATIN_LOCALES` (kept for name stability; the comment there explains the Cyrillic inclusion).
- **RTL locale** — `{he, fa}`. RTL mirroring is handled by RN's `I18nManager`; tokens are RTL-safe (no directional values baked in).

---

### 1f. DS component layer (added by FOU-115 / Phase 2)

The DS layer is a sibling of the tokens layer:

```
src/components/ui/
  index.ts                          // public barrel — DS surface for Phase 3
  types.ts                          // CommonDSProps + WithRequiredA11yLabel + warnIfNoA11yLabel
  primitives/
    Pressable/                      // RN Pressable + state-layer overlay; the building block for every interactive DS component
  Surface/                          // background + radius + optional elevation; Paper-free
  Header/                           // Figma 3011:23955; the header building block for Sheet/Modal/Dialog
  Button/                           // §4j matrix
  IconButton/                       //   "
  Input/                            //   "
  Chip/                             //   "
  Card/  + CardList/                //   "
  Divider/                          //   "
  Tabs/                             //   "
  BottomNavBar/                     //   "
  Label/                            //   "
  CategoryBadge/                    //   "
  Dropdown/                         //   "
  MessageContent/                   //   "
  Switch/                           // Paper-wrap
  Checkbox/                         // Paper-wrap
  RadioButton/  + RadioSection/     // Paper-wrap + composite
  Sheet/                            // gorhom + Header composition
  Modal/                            // Portal + Header composition
  Dialog/                           // Portal + Surface + Header composition
```

Each `<Component>/` folder owns:

```
<Component>.tsx                     // implementation
styles.ts                           // token-bound styles only (no raw hex, no raw px)
index.ts                            // re-export
__tests__/
  <Component>.test.tsx              // behaviour + a11y assertions
  __snapshots__/
    <Component>.test.tsx.snap       // variant × size × state × mode snapshots
```

Public DS surface is `src/components/ui/index.ts`. Phase 3 imports from `'src/components/ui'`. No DS-internal file is imported across components except via `primitives/`.

Stored on disk: nothing new. The DS layer is pure code. Computed at render: every style is a function of the resolved `Theme` from `useTheme()`.

**Glossary additions:**

- **DS layer** — `src/components/ui/`. The Phase 2 shared component library. Built against `useTheme()`. Distinct from `src/components/*` (the legacy components, which keep working through Phase 3 swaps and are removed in Phase 4 / FOU-123).
- **Header building block** — the DS `Header` component at `src/components/ui/Header/`. Figma node `3011:23955`. Reused as the header primitive by `Sheet`, `Modal`, and `Dialog`.
- **State layer** — the token-defined opacity overlay (`stateLayerOpacity`, `pressedStateOpacity`, `focusStateOpacity`, `hoverStateOpacity`) applied by the `Pressable` primitive on `pressed`. `focusStateOpacity` and `hoverStateOpacity` remain token-level constants for future consumer-driven focus/hover branches; the Pressable primitive itself only resolves `pressed` on mobile.
- **Visual-parity snapshot** — a serialized React tree of a DS component for a specific `(variant, size, state, mode)` tuple. Used by Phase 3 swaps to detect unintended visual change (§4k).

---

## 1e. External shape

No wire format. The token layer is internal. The only external touchpoint is the **bundled font binary set** (TTF files):

- iOS: registered via `UIAppFonts` in `ios/PocketPal/Info.plist`, AND wired into the Xcode project's PBXResourcesBuildPhase via `ios/link-assets-manifest.json` + `ios/PocketPal.xcodeproj/project.pbxproj` (npx react-native-asset writes both manifest and pbxproj entries).
- Android: dropped in `android/app/src/main/assets/fonts/`, tracked in `android/link-assets-manifest.json`.
- React Native: declared once in `react-native.config.js` (`assets: ['./src/assets/fonts']`).

The font family **name** as referenced in code (e.g. `'Fraunces-Regular'`) must match the iOS PostScript name and the Android filename (sans extension). Mismatches are silent — RN falls back to system. Enforced at CI by `scripts/verify-fonts.js` (see I8).

---

## 2. Event flow

No event flow changes. The theme layer is stateless apart from `uiStore.colorScheme` and `uiStore.language` (both already in (C)) and is read synchronously via `useTheme()`.

The one new addition is the **hydration gate** at `App.tsx`: before the first render of `<PaperProvider>`, the app awaits `mobx-persist-store`'s `isHydrated(uiStore)` so the persisted `language` / `colorScheme` values are observed by the theme builder on first frame. This is a one-time gate at app startup, not a runtime event. Implemented in `AppWithMigrationWrapper` (App.tsx). While unhydrated it renders a **neutral background-only hold** — a single full-screen `View` whose only meaningful style is `backgroundColor` from `Appearance.getColorScheme()`, with no branding, no `Text`, no `SafeAreaProvider`, no insets, and no `initialWindowMetrics`; it does not impersonate any native launch screen (see §4c #4, §9k, §9l).

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

No `'x1'` state — x1Theme was removed in FOU-114. UIStore's `colorScheme` type is `'light' | 'dark'` (C, `src/store/UIStore.ts:32`).

---

## 4. Contract

### 4a. The tokens module (`src/theme/tokens/`)

1. Exports a single named binding per mode: `lightTokens: Tokens` and `darkTokens: Tokens`, and a helper `resolveTokens(mode: 'light' | 'dark'): Tokens`.
2. Contains no React, no Paper, no MobX imports. Pure data + types (the only external dep is `src/utils/colorUtils`, a pure utility).
3. Color values, spacing scale, radius scale, stroke scale are sourced verbatim from the canonical Figma file (`RZxDJea4t6jnBZrV4YBacF`, node `789:19792`). Light values are the verbatim port of pre-FOU-114 `createBaseColors`/`createSemanticColors` (D10); dark values are sourced from `dark-tokens.json` (extracted from canonical dark band `3011:*`).
4. Typography values use **absolute px line-heights only** (I4):
   - `Headline/H1` (Fraunces, 36px, line-height 1.4 multiplier) → `lineHeight: 50` (= 36 × 1.4, rounded to integer).
   - `Styled/xs` (line-height 100%) → `lineHeight = fontSize` (1.0 multiplier resolved to px).
5. Weight mappings are static: token weight `400` → family `*-Regular`; token weight `500` → family `*-Medium`.
6. The non-Latin fallback rule is encoded as a function on the module: `typographyForLocale(style, locale)`. See §4d.
7. Aliases (`Gap/*` → `Spacing/*`, `radius/radius-xs` → `Radius/XS`) are resolved at token-module level, not at consumer level. Consumers see one scale per dimension.

### 4b. The theme builder (`buildTheme()`, `useTheme()`, `lightTheme` / `darkTheme` exports)

1. `useTheme()` returns a `Theme` (§1b) — token superset + MD3-compat aliases + pinned legacy typography. Subscribes via MobX to `uiStore.colorScheme` and `uiStore.language`.
2. `buildTheme({mode, language})` is the pure function consumed by the hook and by jest fixtures. It reads neither MobX nor React.
3. The builder is the **only** place that maps token keys to MD3-compat alias names. No component is allowed to know which fields are aliases.
4. The builder spreads `baseTheme` (`MD3DarkTheme` / `PaperLightTheme`) for **non-color, non-font** fields (`isV3`, `dark`, `roundness`, `animation`) that Paper itself reads but PocketPal does not override.
5. **The legacy `theme.fonts.*` MD3 typescale + custom TextStyles surface is constructed exactly as today** (preserving `configureFonts` output + the custom keys). It is **not** derived from `theme.typography.*`. This is what gives I1 to the existing consumers.
6. `lightTheme` and `darkTheme` are also exported as plain values (no hook needed) so jest fixtures and any non-React code (test-utils) can use them. These exports are en-locale snapshots.

### 4c. Paper integration (`App.tsx`)

1. `PaperProvider theme={theme}` continues to wrap the app. `theme` is whatever `useTheme()` returns.
2. The Paper-compat alias surface is shaped so every Paper component currently in use continues to render identically to today (I1).
3. The current `react-native-paper` import surface (~35 distinct identifiers including types — `ActivityIndicator, Button, Card, Checkbox, Chip, Dialog, Divider, DividerProps, Drawer, FAB, Icon, IconButton, List, MD3Theme, MD3DarkTheme, DefaultTheme, Menu, MenuItemProps, MenuProps, Paragraph, Portal, ProgressBar, RadioButton, SegmentedButtons, Snackbar, Surface, Switch, Text, TextInput, TextInputProps, Tooltip, TouchableRipple, configureFonts, HelperText, useTheme`) is preserved as-is. Reducing to the locked thin set (`Text/Button/IconButton/Portal/Provider`) is FOU-115/123 work. Post-merge enforcement of Paper-import discipline is deferred to FOU-115, once the wrap-vs-rebuild architectural call is made (likely as an ESLint `no-restricted-imports` rule that grows entry-by-entry as DS replacements ship).
4. **Hydration gate, neutral background-only hold:** the app defers rendering `<PaperProvider>` until `mobx-persist-store`'s hydration of `UIStore` completes. While hydrating, it renders a **neutral background-only hold**: a single full-screen `View` whose only meaningful style is `backgroundColor`, resolved from the **system color scheme** via `Appearance.getColorScheme()`. The hold MUST contain **no branding (`PocketPal` / `LLM Ventures` labels), no `Text`, no `SafeAreaProvider`, no `useSafeAreaInsets`, and no `initialWindowMetrics`** — and it does NOT impersonate the iOS launch storyboard nor introduce any branded screen on Android (which has no native launch screen — see §9l). A flat colored `View` has nothing to match against either native launch surface, so it cannot diverge from native on any axis. Implemented in `AppWithMigrationWrapper` (App.tsx). Holding the *native* launch screen instead is the deferred D12 alternative.

### 4d. RTL & non-Latin fallback at the typography layer

1. For each `TokenTypography` style, the resolved `fontFamily` is a single string (RN limitation: no CSS-style font-family fallback lists).
2. The non-Latin fallback is a **per-style selection function**:
   - If the style is Fraunces-family AND the active locale is in the non-Latin set → swap the family for the Inter equivalent at the same weight (e.g. `Fraunces-Regular` → `Inter-Regular`).
   - If the style is Fraunces-Italic AND active locale is non-Latin → swap to `Inter-Medium` with `fontStyle: 'italic'` (D5).
   - If the style is Inter or JetBrains Mono → no swap. Inter ships Latin + Cyrillic so it renders `ru`/`uk` directly; for scripts Inter doesn't cover the platform falls back to system fonts. JetBrains Mono is for code blocks regardless of locale.
3. The selection function is invoked **inside the theme builder**, not at component-call sites. Components remain locale-agnostic.
4. RTL mirroring (`I18nManager.isRTL`, `writingDirection: 'rtl'`) is **not** encoded in tokens. Tokens contain no directional values. Components handle direction with RN's built-in `start`/`end` semantics in later slices.
5. The active locale is read from `uiStore.language`. The theme builder subscribes to both signals.

### 4e. Hard invariants

- **I1 (no visual regression)**: For every screen of the app, light AND dark, on iOS AND Android, the rendered output is pixel-identical (or visually indistinguishable to a designer's eye) to the pre-FOU-114 build. Any screen that fails this invariant is a bug in the migration tables (§1c, §1d), not a new design choice.
- **I2 (token-source consistency)**: Every color / typography / spacing / radius / stroke value in the new tokens module is sourced from the canonical Figma file `RZxDJea4t6jnBZrV4YBacF`. Non-canonical Figma files are forbidden as sources.
- **I3 (single scale per dimension)**: Spacing has one scale, radius has one scale, stroke has one scale. `Gap/*` and lowercase `radius/radius-xs` from the canonical file are resolved at the token module via alias.
- **I4 (absolute line-heights)**: No `TokenTypography` entry uses a non-numeric or multiplier line-height. The Figma multipliers are converted to px in the token module.
- **I5 (single writer for `colorScheme`)**: `uiStore.setColorScheme()` is the single writer. The theme builder is read-only.
- **I6 (single writer for `language`)**: `uiStore.setLanguage()` is the single writer. The theme builder is read-only.
- **I7 (Paper surface is preserved, not reduced)**: This was a slice-scoped invariant for the foundation slice — the current Paper import surface was preserved as-is, confirmed by code review at merge time. Post-merge enforcement of Paper-import discipline is deferred to FOU-115 (the wrap-vs-rebuild decision determines the right enforcement vector). Reducing the surface to the locked thin set is FOU-115/123 work.
- **I8 (font family names match registered names)**: For every `fontFamily` string in `Tokens.typography.*`, a matching font asset is bundled and registered: iOS `UIAppFonts` (PostScript name) and Android `assets/fonts/{Name}.ttf`. Enforced by `scripts/verify-fonts.js`.
- **I9 (x1 is gone)**: No code path in `src/` references `x1Theme`, `AppTheme.X1`, or `'x1'` as a `colorScheme` value.
- **I10 (hydration gate on first render, neutral hold)**: `<PaperProvider>` and any subtree that reads `useTheme()` are not mounted until `mobx-persist-store` has hydrated `UIStore`. Persisted `language` and `colorScheme` are observed on first frame. The hold rendered while unhydrated is a neutral background-only `View` (no branding, no `Text`, no safe-area provider/insets, no `initialWindowMetrics`); it does not impersonate any native launch screen (see §4c #4, §9k, §9l, D12).

### 4f. What each component / module renders

| Component / module | Renders / produces | Does NOT render / produce |
| --- | --- | --- |
| `src/theme/tokens` | Pure-data `lightTokens`, `darkTokens`, `Tokens` type. Family-name strings only — no font loading. | No React, no MobX, no Paper, no derived styles, no MD3 aliases. |
| `src/utils/theme.ts` (`buildTheme`) | The `Theme` superset for a given (mode, locale). MD3-compat aliases + pinned legacy `theme.fonts.*`. | Token data (sourced from the tokens module). Components do not call this directly. |
| `useTheme()` (`src/hooks/useTheme.ts`) | The reactive `Theme` for the current (`colorScheme`, `language`) pair. | No state of its own. Pure reader. |
| `lightTheme`, `darkTheme` exports | Pre-built `Theme` snapshots for the default locale (`en`). Used by jest fixtures and non-React code. | No locale-aware swaps — these are the en-locale snapshots. |
| `App.tsx` | (a) Hydration gate (I10) in `AppWithMigrationWrapper`: renders a **neutral background-only hold** (flat colored `View`, no branding/`Text`/safe-area) while `mobx-persist-store` hydrates `UIStore`. (b) `<PaperProvider theme={theme}>` — wraps app with `useTheme()` output once hydrated. | No theme construction logic. **No branded splash, no native-launch impersonation, no `SafeAreaProvider`/`useSafeAreaInsets`/`initialWindowMetrics` in the hold.** |
| Existing component `styles.ts` files | Continue to read `theme.colors.*`, `theme.fonts.*` (MD3 typescale + custom), `theme.spacing.default`, `theme.borders.*`, `theme.insets.*`. | Direct font-file imports, raw hex values, or MD3 internals. |
| `src/utils/types.ts`, `src/utils/index.ts`, `src/components/SidebarContent/styles.ts`, `src/components/RenameModal/styles.ts` | Continue to import `MD3Theme` / `MD3Colors` / `MD3Typescale`. | Migration to a Paper-free type is deferred — see §5 #5. |
| `src/components/ui/primitives/Pressable` | A `Pressable` wrapper that resolves `pressed` and renders the token-bound state-layer overlay. | `focused`/`hovered` resolution (RN's `Pressable` does not surface these on mobile — consumers wrap `onFocus`/`onBlur` themselves). Any visual outside the state layer (no padding, no radius). |
| `src/components/ui/<Component>` (rebuild families) | A token-bound, observation-free presentational component. | Store reads. Raw hex / raw px. MD3 typescale references. |
| `src/components/ui/{Switch,Checkbox,RadioButton}` | A thin Paper wrapper exposing the DS API contract (§4h). Forwards a11y props on the wrapping View. | Custom state machinery. Custom a11y. |
| `src/components/ui/Header` | The shared overlay header building block (Figma `3011:23955`). | Sheet/Modal/Dialog mechanics. |
| `src/components/ui/{Sheet,Modal,Dialog}` | Composition of `Header + Body + Actions` around an existing presentation primitive (gorhom for Sheet, Paper Portal for Modal/Dialog). Renders exactly one Header per overlay (I_UI3). | New animation primitives. |
| `src/components/ui/*/styles.ts` | `createStyles(theme, {variant, size, state})` returning a `StyleSheet`. | Direct token-module imports. Raw values (hex literals banned by lint). |
| `src/components/ui/index.ts` | The public DS barrel. | Re-exports from `src/components/*` (legacy namespace). |
| `.eslintrc.js` | `no-restricted-imports` Paper `importNames` blocklist (seed `['Surface']`, grows per Phase 3 slice). Per-file override (`excludedFiles`) re-allowing Paper imports inside `src/components/ui/{Switch,Checkbox,RadioButton}/**`. Plus the `no-restricted-syntax` hex-literal ban scoped to `src/components/ui/**/styles.ts`. | Bulk Paper bans (entries accrue slice-by-slice, I_UI4). |

### 4g. DS component layer (`src/components/ui/`) — added by FOU-115 / Phase 2

1. Every DS component reads tokens through `useTheme()` only — no direct token-module imports, no raw hex (lint-enforced by `no-restricted-syntax` on `src/components/ui/**/styles.ts`), no raw px in `styles.ts`.
2. Every interactive DS component is built on the `Pressable` primitive in `primitives/Pressable/`. The primitive is the single writer of `pressed` state-layer overlays (the only interactive state RN's `Pressable` exposes via its `style` callback on mobile). Focus, where it applies, is consumer-driven (e.g. `Input` owns its `onFocus`/`onBlur` render branch); hover is web-only and out of mobile scope.
3. DS components are **observation-free**: they do not import `mobx-react`, `observer`, or any store. Stateful integration is the caller's responsibility in Phase 3 (I_UI2).
4. DS components do not import from `src/components/*` (the legacy namespace). The wrap-Paper families (`Switch`, `Checkbox`, `RadioButton`, `Dropdown`) import `react-native-paper` directly; their folders are the only legal place those Paper symbols live by Phase 4.
5. The `Header` component is the single source of structural truth for all DS overlay headers. A DS overlay that needs a header MUST compose `<Header>`; bespoke headers are forbidden inside the DS layer (I_UI3).
6. DS component public APIs follow the `variant` + `size` + `state` axis convention (§4h). New variants are added to the existing axis, not as new components.
7. Every DS component file exports a single named React component (no default exports).

### 4h. Component API contract (semantic shape)

Every DS component exposes the same shape, varying only in which axes apply:

```ts
type CommonDSProps = {
  testID?: string;
  accessibilityLabel?: string;
  accessibilityHint?: string;
  accessibilityRole?: AccessibilityRole;
  style?: StyleProp<ViewStyle>;
  disabled?: boolean;
};
```

Rules:

1. `variant` and `size` are **closed string unions per component**, not free strings. Adding a variant widens the union in `Component.tsx`.
2. Defaults declared in JSDoc above each component.
3. Token-binding pattern: `styles.ts` exposes `createStyles(theme, {variant, size, state})` and is the only place that maps a `(variant, size, state)` triple to token reads.
4. State model: `Pressable` resolves `pressed` (the only state RN's `Pressable` exposes via its `style` callback on mobile) and the primitive overlays the state-layer accordingly. `disabled` is part of the same state model. Wrap-Paper families (Switch/Checkbox/RadioButton/Dropdown) delegate `pressed`/`focused` to Paper. Focus on rebuilt families (e.g. Input's focus ring) is consumer-driven via `onFocus`/`onBlur`, not resolved by the primitive.
5. **`accessibilityLabel` is required** for interactive components. Primary enforcement = TypeScript discriminated-union constraint (`WithRequiredA11yLabel<P>` in `src/components/ui/types.ts`): consumers must supply `label` (which doubles as the spoken label) OR an explicit `accessibilityLabel`. Dev-only `__DEV__` runtime fallback (`warnIfNoA11yLabel`) catches type bypasses (D34).
6. `accessibilityRole` defaults: `Button`/`IconButton`/`Chip` (interactive) → `'button'`; `Chip` (display) → `'text'`; `Switch` → `'switch'`; `Checkbox` → `'checkbox'`; `RadioButton` → `'radio'`; `Tabs`/`BottomNavBar` root → `'tablist'`, item → `'tab'`; `Header` → `'header'` (D35 — desired landmark collision with native nav headers); `Label`/`CategoryBadge` → `'text'`; `Card`/`Surface`/`Divider` → `'none'`.

### 4i. The Header building block (Figma `3011:23955`)

`Header` is a single component:

```ts
type HeaderProps = CommonDSProps & {
  title?: string;
  subtitle?: string;
  leading?: ReactNode;
  trailing?: ReactNode;
  align?: 'leading' | 'center';   // default 'leading'
};
```

Reads `theme.typography.titleM` for title, `theme.typography.captionS` for subtitle. Horizontal padding = `theme.spacing.m`; vertical padding = `theme.spacing.s`. `testID` default `'ui-header'`; `accessibilityRole` default `'header'` (D35).

### 4j. Wrap-vs-rebuild matrix (the central architectural decision of FOU-115)

Per-family decisions:

| Family | Decision | Decision marker |
| --- | --- | --- |
| `Button`, `IconButton` | Rebuild | D13, D14 |
| `Input` | Rebuild (RN TextInput + token-bound bottom divider) | D15 |
| `Chip` (canonical `890:29153`) | Rebuild | D16, D8 |
| `Card` / `CardList` | Rebuild (View + tokens) | D17 |
| `Tabs` (canonical `764:27807`) | Rebuild | D18, D9 |
| `BottomNavBar` (canonical `143:4685`) | Rebuild — presentational shell only; `variant: 'default' \| 'floating'` | D19, D10, D36 |
| `Label` (Informational + Status) | Rebuild | D23 |
| `CategoryBadge` | Rebuild | D24 |
| `Dropdown` | Wrap Paper `Menu` directly; trigger rebuilt against tokens | D25 |
| `MessageContent` | Rebuild | D26 |
| `Divider` | Rebuild | (final blocklist §4n) |
| `Surface` | Rebuild — primitive backing the Phase 2 blocklist seed | D32 |
| `Header` | Rebuild | D30 |
| `Sheet` | Compose existing `@gorhom/bottom-sheet` + Header + Body + Actions | D27, D7 |
| `Modal` | Compose Paper `Portal` + Header + Body + Actions | D28 |
| `Dialog` | Compose Paper `Portal` + centered DS Surface + Header + Body + Actions | D29 |
| `Switch`, `Checkbox`, `RadioButton` | **Wrap Paper** (a11y-heavy form controls) | D20, D21, D22 |
| `RadioSection` | Rebuild composite on top of wrapped `RadioButton` | D20 |

Summary: 14 rebuilt families, 4 wrap-Paper families (`Switch`, `Checkbox`, `RadioButton`, `Dropdown`).

### 4k. Visual-parity snapshot strategy (bounded matrix)

#### 4k.1 Mechanism
Each DS component ships a Jest snapshot test using `@testing-library/react-native`'s `render().toJSON()` + `toMatchSnapshot()`. A shared helper `src/components/ui/__tests__/helpers/snapshotMatrix.tsx` generates the per-family matrix.

#### 4k.2 Rebuild-family matrix (bounded)
- Baseline: `variant × size × {default, disabled} × {light, dark}` — every (variant, size) under both static states under both modes. The `disabled` cell is rendered by passing `disabled` through to the component (not by labelling alone) — the snapshot factory consumes `cell.state` and forwards `disabled={state === 'disabled'}`.
- Pressed / focused: NOT snapshotted in Phase 2. Jest's `render()` cannot trigger Pressable's `pressed` via the style callback path, and Input's focused state needs `fireEvent.focus`. Emitting these cells produced misleading byte-identical-to-default coverage in the initial Phase 2 ship; pressed/focused signal is deferred to Phase 3 via a per-component `fireEvent`-driven harness that lands with each call-site swap.
- Non-Latin font-fallback canary: ONE snapshot at `canaryVariant × <default> × default × light × <lang='fa'>` — exercises the typography-fallback path through `buildTheme` (Fraunces → Inter for non-Latin). `Chip` passes `rtlCanaryVariant: 'selectable'` so the canary exercises the state-layer interactive path. This canary does NOT exercise `I18nManager.isRTL` layout direction (deferred to Phase 3 with a per-test isolation harness, since `forceRTL` is irreversible in the same process).
- Hover is NOT snapshotted (mobile-first; same overlay code path as pressed).

#### 4k.3 Wrap-Paper families (Switch/Checkbox/RadioButton/Dropdown)
Restricted matrix: `variant × {default, disabled} × {light, dark} × value={true, false}` for the trio (`Switch`/`Checkbox`/`RadioButton`) — `size` axis dropped because Paper owns sizing and the DS layer does not widen it; the trio's public `size` prop is also dropped accordingly. `Dropdown` keeps the `size` axis (its rebuilt trigger has a size variant). **Pressed/focused are NOT snapshotted** — they are Paper internals; testing them would test Paper, not the DS layer.

#### 4k.4 Theme construction in tests
Each snapshot renders against a real `Theme` from `themeFixtures.byMode(mode).byLocale(language)` (D33 — `jest/fixtures/theme.ts` extended with the `byMode().byLocale()` factory).

#### 4k.5 Phase 3 swap contract
Snapshots are the Phase 3 comparison baseline. When a Phase 3 slice swaps a screen, the relevant DS snapshots MUST NOT change in that PR — any DS-side visual change must be a separate, intentional commit (I_UI5).

### 4l. `testID` + accessibility-label freeze contract

Defaults table (the migration handshake Phase 3 relies on):

| Component | Default `testID` | `accessibilityRole` |
| --- | --- | --- |
| `Button` | `'ui-button'` | `'button'` |
| `IconButton` | `'ui-icon-button'` | `'button'` |
| `Input` | `'ui-input'` | `'none'` (RN TextInput owns its own a11y) |
| `Chip` | `'ui-chip'` | `'button'` (interactive) / `'text'` (display) |
| `Tabs` (root) | `'ui-tabs'` | `'tablist'` |
| `Tabs` (item) | `'ui-tab-item-<value>'` | `'tab'` |
| `BottomNavBar` (root) | `'ui-bottom-nav'` | `'tablist'` |
| `BottomNavBar` (item) | `'ui-bottom-nav-item-<value>'` | `'tab'` |
| `RadioButton` | `'ui-radio-<value>'` | `'radio'` |
| `Checkbox` | `'ui-checkbox'` | `'checkbox'` |
| `Switch` | `'ui-switch'` | `'switch'` |
| `Header` | `'ui-header'` | `'header'` (D35) |
| `Card` | `'ui-card'` | `'none'` |
| `Surface` | `'ui-surface'` | `'none'` |
| `Sheet` | `'ui-sheet'` | n/a (overlay) |
| `Modal` | `'ui-modal'` | n/a |
| `Dialog` | `'ui-dialog'` | n/a |
| `Divider` | `'ui-divider'` | `'none'` |
| `Label` | `'ui-label'` | `'text'` |
| `CategoryBadge` | `'ui-category-badge'` | `'text'` |
| `Dropdown` | `'ui-dropdown'` | `'button'` |
| `MessageContent` | `'ui-message-content'` | `'none'` |

Naming policy: `ui-<kebab-component-name>` and `ui-<kebab-component-name>-<discriminator>` for repeated items. Phase 3 swap PRs MUST pass the legacy testID at each call-site so Appium selectors continue to resolve (I_UI6).

### 4m. Paper-import discipline (`no-restricted-imports` blocklist)

1. `.eslintrc.js` extends its existing `src/**/*.{ts,tsx}` `overrides` entry with a `paths` rule for `'react-native-paper'` carrying an `importNames` blocklist.
2. **Phase 2 seed = `['Surface']`** (D31 proof-of-life). Both pre-existing `Surface` consumers (`UsageStats.tsx`, `PalDetailSheet.tsx`) swap to `Surface` in the same PR (Scenario I' / WHAT §4g.7).
3. The blocklist grows entry-by-entry as each Phase 3 swap lands its DS replacement and migrates all call-sites (I_UI4 monotonic growth).
4. Wrap-Paper DS components (`Switch`, `Checkbox`, `RadioButton`) are listed in `excludedFiles` so they keep their direct Paper imports — the only legal place those imports live by Phase 4.
5. Final-state blocklist (when Phase 4 / FOU-123 lands) = inversion of the locked thin set: `'ActivityIndicator', 'Card', 'Checkbox', 'Chip', 'Dialog', 'Divider', 'DividerProps', 'Drawer', 'FAB', 'List', 'MD3Theme', 'Menu', 'Paragraph', 'ProgressBar', 'RadioButton', 'SegmentedButtons', 'Snackbar', 'Surface', 'Switch', 'TextInput', 'Tooltip', 'useTheme'`. Locked thin set (never banned): `Text, Button, IconButton, Portal, Provider`.
6. The ESLint rule is the only enforcement vector for Paper-import discipline post-FOU-114 (the snapshot guard `verify-paper-surface.js` is gone).

### 4n. Hard invariants — DS layer (added by FOU-115)

- **I_UI1 (DS components are tokens-only)**: No DS component reads a raw hex, raw px, MD3 typescale key, or `theme.fonts.*` legacy alias. All visual values flow through `theme.colors.*`, `theme.typography.*`, `theme.spacing.*`, `theme.radius.*`, `theme.stroke.*`. Mechanically enforced for hex literals by `no-restricted-syntax` scoped to `src/components/ui/**/styles.ts`.
- **I_UI2 (DS layer is observation-free)**: No file under `src/components/ui/` imports `mobx`, `mobx-react`, or any store.
- **I_UI3 (Header is the sole overlay header)**: No DS overlay (`Sheet`, `Modal`, `Dialog`) renders inline header markup; they MUST compose `<Header>`. Each overlay's behaviour test asserts the rendered tree contains exactly one `testID='ui-header'`.
- **I_UI4 (Paper-import discipline grows monotonically)**: Once a Paper `importName` is added to the blocklist, it MUST NOT be removed (other than the per-file `excludedFiles` re-allow for the four wrap-Paper folders: `Switch`/`Checkbox`/`RadioButton`/`Dropdown`).
- **I_UI5 (Phase 3 swaps preserve DS snapshots)**: A Phase 3 slice PR may change a screen's snapshot, but MUST NOT change any DS component's snapshot. DS visual changes are separate, intentional commits.
- **I_UI6 (testID freeze)**: The Appium-observable testID tree at any screen MUST be identical pre- and post-Phase-3-swap. New DS testIDs are additive at the leaves, never replacing.
- **I_UI7 (canonical-variant choices are recorded)**: For each duplicated DS family (Chips×3, Tabs×3, nav×2), the canonical variant choice (D8/D9/D10) is recorded here. Phase 3 implements against the canonical choice; other variants are explicit dead designs until a designer-sourced reconciliation.
- **I_UI8 (folded rename + architecture doc absorption are cross-linked in the same review cycle)**: The token-rename patch lands as the FIRST commit of the FOU-115 app-PR; §1a is updated in a paired dev-team-repo commit referenced from the PR description (app PR cites dev-team commit SHA; dev-team commit cites app PR URL). Same-PR-atomicity is not literally enforceable because app code and architecture docs live in different repos by submodule structure. Splitting them across review cycles is forbidden. (Promoted to (C) on this merge; wording reflects round-1 pipeline-reviewer C8 — original I_UI8 text implied same-PR which is structurally impossible.)

---

## 5. Layer ownership (single-writer rule)

| Field | Single writer | Notes |
| --- | --- | --- |
| `uiStore.colorScheme` | `uiStore.setColorScheme()` (`src/store/UIStore.ts:104`) | Settings toggle is the only caller. |
| `uiStore._language` | `uiStore.setLanguage()` | Read via `uiStore.language` getter. |
| `Tokens.{colors,typography,spacing,radius,stroke}` | The tokens module exports — values are `const`, never mutated at runtime. | No runtime mutation; mode swap is binding selection, not mutation. |
| `Theme.colors.*` / `Theme.fonts.*` / `Theme.typography.*` / etc. | The theme builder (`buildTheme`) is the **only** code path that constructs a `Theme`. | Components must never mutate the returned object. |
| Bundled font file set | `react-native.config.js` + `ios/PocketPal/Info.plist` `UIAppFonts` + `ios/link-assets-manifest.json` + `android/link-assets-manifest.json` + `android/app/src/main/assets/fonts/` | Single source = `src/assets/fonts/`. iOS plist + pbxproj and Android assets are linked outputs from `npx react-native-asset`. CI verifies drift (I8). |

**Deferred cleanups** (recorded, not done in FOU-114 or FOU-115 Phase 2):

1. Migrate component `styles.ts` files from `theme.spacing.default` → `theme.spacing.m` and from `theme.fonts.bodyMedium` → `theme.typography.bodyM` etc. Belongs to per-screen restyle slices (FOU-117–122).
2. Remove MD3-compat aliases (`theme.spacing.default`, MD3 typescale on `theme.fonts`) once all consumers are migrated. Belongs to FOU-123.
3. Move `stateLayerOpacity` family out of `colors` and into a dedicated `interaction` namespace. Belongs to FOU-115 or later. (FOU-115 Phase 2: `Pressable` primitive consumes via `theme.colors.*` for now; when the namespace move lands, the primitive's `styles.ts` is the only DS file that needs to change.)
4. Migrate `withOpacity`-computed semantic surface colors (`surfaceContainer*`, `surfaceDim`, `surfaceBright`) from their current opacity-math derivations to explicit Figma tokens. FOU-115 (deferred from Phase 2; a later FOU-115-suffix slice).
5. **Eliminate `MD3Theme` / `MD3Colors` / `MD3Typescale` imports from `src/`.** Today these are imported by:
   - `src/utils/types.ts:4,9` — `Theme extends MD3Theme`; `MD3BaseColors extends MD3Colors`; `ThemeFonts extends MD3Typescale`.
   - `src/utils/index.ts:6` — `getThemeColorsAsArray(theme: MD3Theme)`.
   - `src/components/SidebarContent/styles.ts:3` — `createStyles(theme: MD3Theme)`.
   - `src/components/RenameModal/styles.ts:2` — `createStyles(theme: MD3Theme)`.
   Belongs to FOU-123.
6. Remove the comment "(currently withOpacity-derived, FOU-115)" from §1a `colors.surfaceContainer*` once item #4 lands.
7. Migrate `src/components/Sheet/Sheet.tsx`, `src/components/Dialog/Dialog.tsx` call-sites from the legacy wrappers to the DS `Sheet`/`Modal`/`Dialog`. Per-screen Phase 3 work (FOU-117+).
8. Grow the Paper-import blocklist (`.eslintrc.js` `no-restricted-imports` `importNames`) per Phase 3 slice. Each Phase 3 slice that ships a DS replacement for a Paper family adds that family's `importName` and migrates all call-sites in the same PR (I_UI4 monotonic growth).

---

## 6. Canonical scenarios

Each scenario is manually verifiable. Visual diffing is the primary acceptance check.

### A. Light mode, en locale, unchanged pixels

App renders against light tokens; pixel-identical to pre-FOU-114 baseline. Verified by manual visual diff against `origin/main` reference (Step 14 of how.md).

### B. Dark mode, en locale, unchanged pixels

App renders against dark tokens; pixel-identical to pre-FOU-114 baseline. No light flash on mount (hydration gate).

### C. Headline rendered in Fraunces for a Latin locale

`uiStore.language ∈ {en, id, ms}` → `theme.typography.headlineH1.fontFamily === 'Fraunces-Regular'`, 36 / 50 / 400. Verified by `src/theme/tokens/__tests__/typography.test.ts`.

### D. Headline falls back to Inter (Fraunces-fallback set)

`uiStore.language ∈ {fa, he, ja, ko, ru, uk, zh, zh_Hant}` → `theme.typography.headlineH1.fontFamily === 'Inter-Regular'`, same metrics. `ru`/`uk` are in this set because the bundled Fraunces subset is Latin-only. Same test file.

### E. Mode swap is reactive

Settings → toggle "Dark mode" on → every visible component re-renders with dark tokens within one frame. `PaperProvider` re-renders with a new `theme` prop (no remount, same React instance).

### F. Language swap is reactive (typography fallback applies)

Settings → change Language from `en` to `fa` → every component reading a Fraunces-family typography token re-renders with Inter-Regular.

### G. JetBrains Mono renders for code blocks

Code blocks render in `JetBrainsMono-Regular`/`-Medium`. Locale fallback does NOT apply to code (§4d.2).

### H. Cold start with persisted non-Latin language — no Fraunces flash

Prior session: `uiStore.setLanguage('ja')` was called and persisted. App restarts. First painted frame containing a headline renders in Inter-Regular, NOT Fraunces. Mechanism: `AppWithMigrationWrapper` defers `<PaperProvider>` mount until `mobx-persist-store` has hydrated `UIStore`. During hydration, a minimal splash View renders (`testID="hydration-splash"`, `backgroundColor` from `Appearance.getColorScheme()`). Verified by `__tests__/App.test.tsx`.

---

## 7. State signals

| Signal | Set by | Read by | True when |
| --- | --- | --- | --- |
| `uiStore.colorScheme === 'dark'` | `uiStore.setColorScheme('dark')` | Theme builder; any direct consumer | User opted into dark mode (or system default was dark at first launch). |
| `uiStore.language` ∈ Fraunces-fallback set | `uiStore.setLanguage(lang)` | Theme builder (typography fallback selector, §4d) | User's selected language is in `{fa, he, ja, ko, ru, uk, zh, zh_Hant}` (`ru`/`uk` included — bundled Fraunces is Latin-only). |
| `I18nManager.isRTL` | RN platform / locale change at app launch | Components (later slices) | App is in RTL layout direction. |
| `isHydrated(uiStore)` (from `mobx-persist-store`) | `makePersistable` lifecycle | `AppWithMigrationWrapper` (gates `<PaperProvider>` mount) | UIStore has finished loading from AsyncStorage. |

---

## 8. Decisions

- **D1**: A new `Tokens` data shape distinct from `Theme`, with `Theme` as a superset alias surface. Rationale: lets new code read tokens directly while legacy code keeps its current keys; gives FOU-123 a clean removal line.
- **D2**: `useTheme()` is the single consumer entry point (no parallel `useTokens()`). Rationale: every consumer already calls `useTheme()`; adding a second hook doubles the migration surface.
- **D3**: Continue spreading Paper's `MD3DarkTheme` / `PaperLightTheme` for non-color non-font fields. Rationale: those fields (`isV3`, `dark`, `roundness`, `animation`) are Paper-internal and must stay Paper-compatible.
- **D4**: x1Theme removed in FOU-114. Rationale: x1 was dead code (the export was unused; `UIStore.colorScheme` was already typed `'light' | 'dark'`).
- **D5**: For Fraunces-Italic on non-Latin locales, fall back to `Inter-Medium` with `fontStyle: 'italic'` rather than shipping a separate `Inter-Italic` font cut. Rationale: RN's synthesised italic is acceptable for an accent style used in one place (`Styled/xs`); shipping `Inter-Italic` adds ~200KB.
- **D6**: Dark tokens are sourced by reading the canonical Figma file's variable collection dark binding, NOT inferred / hand-derived from the light tokens. Disagreement-resolution rule: if the canonical dark binding disagrees with the current dark `Theme` value at a key with visible consumers, **the current dark value wins for I1**, and the disagreement is logged as a designer ask on FOU-112. See `workflows/stories/TASK-20260519-2110/dark-tokens.json` and `designer-asks.md`.
- **D7**: This doc was promoted from `workflows/stories/TASK-20260519-2110/what.md` in the SAME PR that landed FOU-114 code.
- **D8**: The `language` signal is read **inside** the theme builder, not on every component. Rationale: keeps components locale-agnostic.
- **D9**: Fraunces, Fraunces-Italic, and JetBrains Mono weights `400` and `500` only (`*-Regular` and `*-Medium`) for each family. Rationale: the canonical Figma file uses these weights; ship the minimum cuts.
- **D10**: The legacy `theme.fonts.*` MD3 typescale + custom TextStyles + `theme.spacing.default` + `theme.borders.*` + `theme.insets.*` are **preserved verbatim** in FOU-114 — same `configureFonts` output, same custom keys, same values. Rationale: I1 (no visual regression) for the ~18 existing consumers of MD3 typescale keys + ~4 `theme.spacing.default` consumers. The legacy surfaces are deleted in FOU-123.
- **D11**: The first render of `<PaperProvider>` is gated on `mobx-persist-store` hydration of `UIStore`, and renders a **neutral background-only hold** (NOT a branded native-launch impersonation) while unhydrated. Rationale: AsyncStorage hydration is async; without the gate, the first paint uses in-memory defaults and a persisted non-Latin language user would see Fraunces for one frame before hydration completes. Alternatives considered and rejected: a branded JS splash impersonating the iOS launch storyboard (caused repeated native-matching churn — branding, safe-area, `initialWindowMetrics` — and introduces a novel branded screen on Android, which has no native launch screen, §9l); and holding the *native* launch screen until hydration via `react-native-bootsplash` / RN core splash API (the architecturally-correct end state, deferred to D12 as it is NATIVE_CHANGES=YES and adds a new native Android splash).
- **D12 (DEFERRED — human decision)**: The architecturally-correct long-term mechanism is to **hold the native launch screen until hydration** via `react-native-bootsplash` (or RN's built-in splash-hide API): JS calls `hide()` once `isHydrated(uiStore)` is true, the real native launch screen IS the splash on both platforms, and JS renders no hold at all. This closes the Android gap natively (Android gains a real native splash theme, where branding belongs — see §9l) and removes the JS hold entirely. **Not adopted in FOU-114** because it is NATIVE_CHANGES=YES (new dependency + iOS `pod install` + Android splash theme/drawable + native linking) AND it adds a *new branded launch surface on Android* that never existed — a product/design decision plus a native-build expansion that warrant their own task and visual sign-off, not a rider on an invisible token-foundation slice. Tracked as its own task.

### Phase 2 wrap-vs-rebuild decisions (FOU-115)

- **D13** (`Button`, rebuild): Visually defining (radius, padding, weight, state layer). Paper's `Button` ships MD3-specific ripple + label-uppercase quirks that fight the design.
- **D14** (`IconButton`, rebuild): Paper's `IconButton` enforces a circular hit area + MD3 state layer that doesn't match the canonical squarish IconButton in `746:26337`.
- **D15** (`Input`, rebuild): The Figma input has bottom-divider + helper-text + leading/trailing slot variants that don't map to Paper's `TextInput`. Build directly on RN `TextInput`.
- **D16** (`Chip`, rebuild): Chip variants (pill, badge, selectable) differ in radius + leading-icon slot + state in ways that fight Paper's `Chip`.
- **D17** (`Card`/`CardList`, rebuild): Pure visual primitive: surface + radius + padding + optional border. Paper's `Card.Title`/`Card.Content` slots don't match the DS shape.
- **D18** (`Tabs`, rebuild): Custom underline / state-layer behaviour. Paper's `SegmentedButtons` doesn't reach the Figma look.
- **D19** (`BottomNavBar`, rebuild): Custom icon-label stack + state-layer indicator. Presentational shell — navigation wiring happens in Phase 3.
- **D36** (`BottomNavBar` `floating` variant, additive — POC-30): The app shell (`context/architecture/app-shell.md`) needs the canonical floating bar with a yellow active pill. `BottomNavBar` gained a `variant: 'default' | 'floating'` axis. `default` is byte-identical to the pre-POC-30 rendering (bordered top-line bar, active = `theme.colors.primary` text) and its snapshot is frozen (I_UI5). `floating` = rounded floating container (drop shadow via `theme.colors.shadow`, `theme.radius.xxl`) with the active item on a yellow pill (`theme.colors.accent.yellowSubtle` fill `#f5dbbc` + `theme.colors.accent.yellowMute` border `#f8f1e2`); tokens-only, no store import. The floating variant ships its own additive snapshot cells (`floating-m-*`). The app shell picks `floating` as canonical (I_UI7); `default` remains for existing consumers. (Pixel-parity update: the earlier `accent.peach` pill was corrected to the canonical `Color/Yellow/Subtle` + `/Mute` pair.)
- **D20** (`RadioButton`+`RadioSection`, wrap Paper + composite): A11y-heavy form control. Paper's `RadioButton` handles `accessibilityRole="radio"`, group state, pressed/focused atomically. RadioSection is the composite layout rebuilt on top of the wrapped RadioButton.
- **D21** (`Checkbox`, wrap Paper): Same rationale as RadioButton.
- **D22** (`Switch`, wrap Paper): Paper's `Switch` handles `accessibilityRole="switch"`, value semantics, platform-specific iOS/Android thumb-track.
- **D23** (`Label` Informational/Status, rebuild): Pure visual primitive.
- **D24** (`CategoryBadge`, rebuild): Same as Label — visual primitive. Closed-union palette in Phase 2.
- **D25** (`Dropdown`, wrap Paper `Menu` + rebuild trigger): Trigger Pressable rebuilt against tokens; popup uses Paper's `Menu` directly (positioning + dismiss + item rendering). Reclassified from Rebuild to Wrap-Paper post-pipeline-review-round-1 — the initial Rebuild classification implicitly assumed the trigger-only delta sufficed, but the popup branch was Paper-coupled via the legacy `src/components/Menu` wrapper, breaching §4g #4 (one-way dependency). Dropdown's folder gets the same per-file ESLint allowance the other wrap-Paper families get when `Menu` enters the blocklist in Phase 3.
- **D26** (`MessageContent`, rebuild): Message bubbles are PocketPal-bespoke. The existing `src/components/Message/*` continues to render; this is the additive DS variant for Phase 3.
- **D27** (`Sheet`, compose gorhom): Sheet mechanics are non-trivial and well-handled by the existing `@gorhom/bottom-sheet` dependency. DS adds Header + Body + Actions composition.
- **D28** (`Modal`, compose Paper Portal): Paper Portal is the existing full-screen-overlay primitive (already in locked thin set). DS adds Header + Body + Actions composition.
- **D29** (`Dialog`, compose Paper Portal + centered DS Surface): Same rationale as Modal.
- **D30** (`Header`, rebuild): Net-new building block. Pure presentational shell.
- **D31** (Phase 2 blocklist seed `['Surface']`): Proof-of-life entry. Both Surface consumers (`UsageStats.tsx`, `PalDetailSheet.tsx`) swap to `Surface` in the same PR. Subsequent entries accrue in Phase 3 slice PRs.
- **D32** (`Surface`, rebuild — added as a 15th rebuild family): Needed as the replacement target for the blocklist seed (D31). Both consumers use `elevation={0}` with a `style` override (UsageStats omits elevation → Surface default elevation=1 keeps the Android shadow; PalDetailSheet passes elevation={0} explicitly). Minimal snapshot surface (1 variant × 1 size × 2 modes).
- **D33** (Theme fixtures byMode/byLocale factory): Extended `jest/fixtures/theme.ts` with `themeFixtures.byMode(mode).byLocale(language)`, memoized per `(mode, language)`. Rationale: the snapshot matrix needs `fa` in addition to `en`; the factory centralizes memoization and keeps every DS test reaching the theme through the same fixture surface.
- **D34** (`accessibilityLabel` enforcement = TS discriminated union, with __DEV__ runtime fallback): Primary mechanism rejects calls at compile time via `WithRequiredA11yLabel<P>` union forcing `label` OR `accessibilityLabel`. Runtime fallback `warnIfNoA11yLabel` catches dynamic-spread / `any`-typed bypasses.
- **D35** (`Header` default `accessibilityRole='header'` collides with RN nav headers — by design): Assistive tech (VoiceOver, TalkBack) treats both as document landmarks; sharing the role lets users navigate by landmark consistently across native nav headers and DS overlay headers.

### Phase 2 canonical-variant decisions (recorded under I_UI7)

- **D8 → Chip×3** (FOU-115): Canonical = `890:29153` (the standalone Chip definition). `768:29722` is the Chip-as-rendered-in-input-context variant; deferred Phase 4 designer ask.
- **D9 → Tabs×3** (FOU-115): Canonical = `764:27807`. `408:11226` is an older Tabs render preserved as legacy reference; deferred.
- **D10 → BottomNavBar×2** (FOU-115): Canonical = `143:4685`. `764:28530` mirrors with cosmetic icon swaps; structural shape identical. Cosmetic variant is a Phase 3 designer-spec call. POC-30 update (D36): the app shell's canonical render is the `floating` variant (yellow-pill floating bar, Figma `888:33854`); the bordered `default` variant is retained for any non-shell consumer.

### Phase 2 representative bespoke sheet (D7 / FOU-115)

- **D7-FOU-115**: `ChatPalModelPickerSheet` picked as the working pattern. It has a title row, a body that scrolls, and an action row — exercising the full Header + Body + Actions composition. Future shape-mismatch widens the DS `Sheet`'s slot contract, not the Header building block.

---

## 9. Edge cases

### 9a. Missing dark binding for a token

A token has a light value in the canonical Figma file but no dark binding. Builder behavior: the dark `Tokens` falls back to the corresponding current dark Theme value AND the tokens module flags the key in a `// TODO: dark binding missing` comment. The token is **not** invented from `withOpacity` math at the token level. Rationale: prefers visible "this looks wrong in dark mode" as a designer-fixable bug over a silent invention. (See FOU-112 designer asks.)

### 9b. Font asset present but PostScript name mismatch (iOS)

A font file is dropped into `src/assets/fonts/` but the iOS PostScript name differs from the filename. RN renders the system font instead. Mitigation: PostScript name verification with `otfinfo --postscript-name` at acquisition time + `scripts/verify-fonts.js` at CI.

### 9c. Font asset missing on Android only

The font is listed but native linking did not copy it into `android/app/src/main/assets/fonts/`. RN renders the system font. Mitigation: `npx react-native-asset` writes both `link-assets-manifest.json` files; CI `verify-fonts.js` checks Android dir.

### 9d. User switches language mid-session

`uiStore.setLanguage('fa')` fires while a screen is mounted → MobX reactivity propagates through `useTheme()` → `theme.typography.headlineH1` resolves to Inter on the next render frame.

### 9e. Cold start with persisted non-Latin language

App restarts with persisted `language = 'ja'`. `mobx-persist-store` hydrates `UIStore` from AsyncStorage asynchronously. `AppWithMigrationWrapper` gates `<PaperProvider>` mount on `isHydrated(uiStore)`, rendering a **neutral background-only hold** (a single `View` with `backgroundColor` from `Appearance.getColorScheme()`; no branding, no `Text`, no safe-area provider/insets, no `initialWindowMetrics`) while `false`. First theme-consuming paint reads the persisted `language` value. The neutral hold is the design that ends per-platform native-matching churn: a flat colored `View` has nothing to match against the iOS storyboard or the (absent) Android launch screen, so there is no divergence to review (§9l).

### 9f. RTL locale without RTL screen mirroring

User picks `he` or `fa`. App reading direction does NOT mirror in FOU-114 (RTL screen mirroring is later-slice work). Typography fallback still applies (headlines render in Inter). Visual mirroring is FOU-117+ work.

### 9g. A consumer still uses a not-aliased name

A consumer reads `theme.someThingNew` that exists in `Tokens` but the alias layer didn't preserve. Expected: TypeScript compile error (we own `Theme`'s type).

### 9h. PaperProvider passes a theme Paper doesn't recognise

Paper's `Provider` validates its theme shape minimally — it reads `dark`, `colors.primary`, `colors.background`, `fonts.bodyMedium`, etc. The builder preserves all the Paper-required fields. Verified by scenarios A + B.

### 9i. New font added but only on one platform

CI `verify-fonts.js` runs against both targets and fails if any of: src/assets, android/app/src/main/assets/fonts, ios/PocketPal/Info.plist is missing the family.

### 9j. JetBrains Mono not yet asked for by any current style

As of FOU-114, no consumer references JetBrains Mono explicitly. Code blocks in markdown render via `react-native-render-html` with default `<code>` styling. The new tokens module defines `codeM` / `codeS` but no current consumer uses it. Code blocks continue to render exactly as today (system monospace). The new token is available for the markdown / code-block restyle slice (FOU-117+).

### 9k. Hydration hold visible for too long

`mobx-persist-store` hydration normally completes within a few microtasks (one AsyncStorage key read). If it takes longer (slow device, cold disk cache), the hold `View` is visible for that duration. The hold is a flat colored `View` matching the system color scheme — **no spinner, no branding, no `Text` is required or permitted** — so a longer-than-microtask delay reads as plain "app launching" flat color on both platforms, which is acceptable. If hydration ever fails outright, `mobx-persist-store` proceeds with in-memory defaults; no error UI is invented in this slice.

### 9l. Android has no native launch screen (the per-platform divergence the rework addresses)

iOS ships a branded launch storyboard (`UILaunchStoryboardName = LaunchScreen` in `Info.plist`). Android has **none**: `styles.xml` defines `AppTheme` only, with no `windowBackground` splash drawable and no Android-12 splash-screen API, and `package.json` carries no splash dependency. Consequence for this slice: a branded JS hold (the rejected design) would be a **novel branded screen on Android** that did not exist before, and `initialWindowMetrics` can be `null` on Android, re-exposing a blank-frame risk. The neutral background-only hold (§4c #4 / I10) sidesteps both: it continues the OS's flat launch color on Android and the storyboard's flat background on iOS, matching neither's *content* because it has none. Closing the Android gap with a *real native* launch screen (so Android stops being the odd platform out) is the D12 deferred follow-up — explicitly NOT a FOU-114 deliverable because it adds a native dependency and a new branded surface.

---

## 10. What this doc is NOT

- Not an implementation plan — file layout, refactor order, and migration scripts live in the relevant `how.md` files.
- Not a designer hand-off — Figma is the design source; this doc reflects the slice of it that engineering owns.
- Not a record of what hard-codes exist today — those are migration entries in §1c / §1d.
- Not a long-term API design — the Paper-compat alias surface and the legacy `theme.fonts.*` MD3 typescale are explicitly migration layers (D10) with a removal line in FOU-123.
- Not a per-language a11y / l10n review — RTL screen mirroring, IME, dynamic text scaling are later-slice concerns.
- Not a Paper-surface-reduction plan — that is FOU-115/123.

**Cleanup reminders** (carry forward in this doc until each lands):

1. The deferred-cleanups list in §5 must be carried forward in this doc until each item lands.
2. If a future slice's dark-token extraction finds tokens with no dark binding in the canonical file, those are designer asks logged on FOU-112 — not invented at the engineering side.
3. The Phase 3 blocklist growth contract (I_UI4) must be re-stated when each Phase 3 slice ships, so every Phase 3 WHAT cites it as a check-off item.
4. The wrap-vs-rebuild matrix (D13–D32) and canonical-variant decisions (D8/D9/D10 under I_UI7) are the contract Phase 3 slices implement against. Widening a `variant` union or adding a non-canonical variant requires a delta WHAT that updates this doc.
3. The Paper-surface reduction to the thin set tracked under FOU-115/123.
