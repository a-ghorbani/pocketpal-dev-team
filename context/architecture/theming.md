# Theming & Design Tokens — Architecture & Flow Board

Promoted from `workflows/stories/TASK-20260519-2110/what.md` on merge of
FOU-114 (Phase 1 of the FOU-112 redesign rollout).

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

Explicitly NOT in scope:

- Any visible restyle of any screen / component (FOU-114 was invisible).
- Per-component restyle work (FOU-117–122).
- Sheet/Modal/ConfirmationDialog rework (FOU-115).
- Per-language locale UI direction switching beyond what the token layer needs.
- Reducing the current `react-native-paper` import surface (FOU-115/123).
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

  typography: TokenTypography
    bodyM, bodyS                       // Inter
    uiM, uiS                           // Inter Medium
    titleL, titleM, titleS             // Inter Medium
    captionM, captionS                 // Inter
    headlineH1                         // Fraunces — Latin/Cyrillic only
    styledXs                           // Fraunces-Italic
    codeM, codeS                       // JetBrains Mono

  spacing: TokenSpacing
    none: 0, xxs: 2, xs: 4, s: 8, sm: 12, m: 16, ml: 20, l: 24

  radius: TokenRadius
    none: 0, xxs: 2, xs: 4, s: 8, sm: 12, m: 16, ml: 20, l: 32, xl: 40

  stroke: TokenStroke
    hairline: 0.5, s: 1, m: 1.5, l: 3
```

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
- **Latin script-set** — `latin extended + cyrillic`. The serif accent (Fraunces) is restricted to this set; non-Latin/CJK falls back to Inter (and Inter falls back to system).
- **Non-Latin locale** — any language whose primary script falls outside the Latin script-set. For PocketPal's supported languages (`en/fa/he/id/ja/ko/ms/ru/uk/zh/zh_Hant`), the non-Latin set is `{fa, he, ja, ko, zh, zh_Hant}`.
- **RTL locale** — `{he, fa}`. RTL mirroring is handled by RN's `I18nManager`; tokens are RTL-safe (no directional values baked in).

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

The one new addition is the **hydration gate** at `App.tsx`: before the first render of `<PaperProvider>`, the app awaits `mobx-persist-store`'s `isHydrated(uiStore)` so the persisted `language` / `colorScheme` values are observed by the theme builder on first frame. This is a one-time gate at app startup, not a runtime event. Implemented in `AppWithMigrationWrapper` (App.tsx).

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
4. **Hydration gate:** the app defers rendering `<PaperProvider>` until `mobx-persist-store`'s hydration of `UIStore` completes. While hydrating, renders a minimal splash (a `View` with `backgroundColor` resolved from the **system color scheme** via `Appearance.getColorScheme()`). Implemented in `AppWithMigrationWrapper` (App.tsx).

### 4d. RTL & non-Latin fallback at the typography layer

1. For each `TokenTypography` style, the resolved `fontFamily` is a single string (RN limitation: no CSS-style font-family fallback lists).
2. The non-Latin fallback is a **per-style selection function**:
   - If the style is Fraunces-family AND the active locale is in the non-Latin set → swap the family for the Inter equivalent at the same weight (e.g. `Fraunces-Regular` → `Inter-Regular`).
   - If the style is Fraunces-Italic AND active locale is non-Latin → swap to `Inter-Medium` with `fontStyle: 'italic'` (D5).
   - If the style is Inter or JetBrains Mono → no swap (Inter covers Latin + Cyrillic; JetBrains Mono is for code blocks regardless of locale).
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
- **I10 (hydration gate on first render)**: `<PaperProvider>` and any subtree that reads `useTheme()` are not mounted until `mobx-persist-store` has hydrated `UIStore`. Persisted `language` and `colorScheme` are observed on first frame.

### 4f. What each component / module renders

| Component / module | Renders / produces | Does NOT render / produce |
| --- | --- | --- |
| `src/theme/tokens` | Pure-data `lightTokens`, `darkTokens`, `Tokens` type. Family-name strings only — no font loading. | No React, no MobX, no Paper, no derived styles, no MD3 aliases. |
| `src/utils/theme.ts` (`buildTheme`) | The `Theme` superset for a given (mode, locale). MD3-compat aliases + pinned legacy `theme.fonts.*`. | Token data (sourced from the tokens module). Components do not call this directly. |
| `useTheme()` (`src/hooks/useTheme.ts`) | The reactive `Theme` for the current (`colorScheme`, `language`) pair. | No state of its own. Pure reader. |
| `lightTheme`, `darkTheme` exports | Pre-built `Theme` snapshots for the default locale (`en`). Used by jest fixtures and non-React code. | No locale-aware swaps — these are the en-locale snapshots. |
| `App.tsx` | (a) Hydration gate (I10) in `AppWithMigrationWrapper`: renders splash while `mobx-persist-store` hydrates `UIStore`. (b) `<PaperProvider theme={theme}>` — wraps app with `useTheme()` output once hydrated. | No theme construction logic. |
| Existing component `styles.ts` files | Continue to read `theme.colors.*`, `theme.fonts.*` (MD3 typescale + custom), `theme.spacing.default`, `theme.borders.*`, `theme.insets.*`. | Direct font-file imports, raw hex values, or MD3 internals. |
| `src/utils/types.ts`, `src/utils/index.ts`, `src/components/SidebarContent/styles.ts`, `src/components/RenameModal/styles.ts` | Continue to import `MD3Theme` / `MD3Colors` / `MD3Typescale`. | Migration to a Paper-free type is deferred — see §5 #5. |

---

## 5. Layer ownership (single-writer rule)

| Field | Single writer | Notes |
| --- | --- | --- |
| `uiStore.colorScheme` | `uiStore.setColorScheme()` (`src/store/UIStore.ts:104`) | Settings toggle is the only caller. |
| `uiStore._language` | `uiStore.setLanguage()` | Read via `uiStore.language` getter. |
| `Tokens.{colors,typography,spacing,radius,stroke}` | The tokens module exports — values are `const`, never mutated at runtime. | No runtime mutation; mode swap is binding selection, not mutation. |
| `Theme.colors.*` / `Theme.fonts.*` / `Theme.typography.*` / etc. | The theme builder (`buildTheme`) is the **only** code path that constructs a `Theme`. | Components must never mutate the returned object. |
| Bundled font file set | `react-native.config.js` + `ios/PocketPal/Info.plist` `UIAppFonts` + `ios/link-assets-manifest.json` + `android/link-assets-manifest.json` + `android/app/src/main/assets/fonts/` | Single source = `src/assets/fonts/`. iOS plist + pbxproj and Android assets are linked outputs from `npx react-native-asset`. CI verifies drift (I8). |

**Deferred cleanups** (recorded, not done in FOU-114):

1. Migrate component `styles.ts` files from `theme.spacing.default` → `theme.spacing.m` and from `theme.fonts.bodyMedium` → `theme.typography.bodyM` etc. Belongs to per-screen restyle slices (FOU-117–122).
2. Remove MD3-compat aliases (`theme.spacing.default`, MD3 typescale on `theme.fonts`) once all consumers are migrated. Belongs to FOU-123.
3. Move `stateLayerOpacity` family out of `colors` and into a dedicated `interaction` namespace. Belongs to FOU-115 or later.
4. Migrate `withOpacity`-computed semantic surface colors (`surfaceContainer*`, `surfaceDim`, `surfaceBright`) from their current opacity-math derivations to explicit Figma tokens. FOU-115.
5. **Eliminate `MD3Theme` / `MD3Colors` / `MD3Typescale` imports from `src/`.** Today these are imported by:
   - `src/utils/types.ts:4,9` — `Theme extends MD3Theme`; `MD3BaseColors extends MD3Colors`; `ThemeFonts extends MD3Typescale`.
   - `src/utils/index.ts:6` — `getThemeColorsAsArray(theme: MD3Theme)`.
   - `src/components/SidebarContent/styles.ts:3` — `createStyles(theme: MD3Theme)`.
   - `src/components/RenameModal/styles.ts:2` — `createStyles(theme: MD3Theme)`.
   Belongs to FOU-123.

---

## 6. Canonical scenarios

Each scenario is manually verifiable. Visual diffing is the primary acceptance check.

### A. Light mode, en locale, unchanged pixels

App renders against light tokens; pixel-identical to pre-FOU-114 baseline. Verified by manual visual diff against `origin/main` reference (Step 14 of how.md).

### B. Dark mode, en locale, unchanged pixels

App renders against dark tokens; pixel-identical to pre-FOU-114 baseline. No light flash on mount (hydration gate).

### C. Headline rendered in Fraunces for a Latin locale

`uiStore.language ∈ {en, id, ru, ms, uk}` → `theme.typography.headlineH1.fontFamily === 'Fraunces-Regular'`, 36 / 50 / 400. Verified by `src/theme/tokens/__tests__/typography.test.ts`.

### D. Headline falls back to Inter for a non-Latin locale

`uiStore.language ∈ {fa, he, ja, ko, zh, zh_Hant}` → `theme.typography.headlineH1.fontFamily === 'Inter-Regular'`, same metrics. Same test file.

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
| `uiStore.language` ∈ non-Latin set | `uiStore.setLanguage(lang)` | Theme builder (typography fallback selector, §4d) | User's selected language is in `{fa, he, ja, ko, zh, zh_Hant}`. |
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
- **D11**: The first render of `<PaperProvider>` is gated on `mobx-persist-store` hydration of `UIStore`. Rationale: AsyncStorage hydration is async; without the gate, the first paint uses in-memory defaults and a persisted non-Latin language user would see Fraunces for one frame before hydration completes.

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

App restarts with persisted `language = 'ja'`. `mobx-persist-store` hydrates `UIStore` from AsyncStorage asynchronously. `AppWithMigrationWrapper` gates `<PaperProvider>` mount on `isHydrated(uiStore)`. First theme-consuming paint reads the persisted `language` value.

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

### 9k. Hydration splash visible for too long

`mobx-persist-store` hydration normally completes within a few microtasks. If it takes longer (slow device), the splash View is visible for that duration. The splash is visually neutral (a colored View matching the system color scheme). If hydration ever fails outright, `mobx-persist-store` proceeds with in-memory defaults.

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
3. The Paper-surface reduction to the thin set tracked under FOU-115/123.
