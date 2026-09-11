# Theming, Design Tokens and the DS Component Layer

## Purpose

Covers the design tokens, the `Theme` builder and `useTheme()`, bundled fonts and the per-locale headline fallback, the first-paint hydration gate, the DS component layer (`src/components/ui/`), and the guards that keep changes on tokens. Per-screen restyles belong to each screen's flow doc. The only token source is Figma file `RZxDJea4t6jnBZrV4YBacF`.

This doc describes `main`. The unmerged `redesign/phase-3` branch adds colour tokens (e.g. `foreground*`, `mutedBackground*`, `accent.yellow*`), a `floating` `BottomNavBar` variant and a wider token-consumer allow-list, so check your branch before trusting a token name. The previous version of this doc described the branch (`git show 1ad6ce1:context/architecture/theming.md`); distill it back in when the branch lands.

## Code map

| Path | Role |
| --- | --- |
| `src/theme/tokens/` | Pure-data tokens. Exports `lightTokens` / `darkTokens`, `resolveTokens`, `NON_LATIN_LOCALES` and `typographyForLocale` |
| `src/utils/theme.ts` | `buildTheme({mode, language})`; also the legacy `fontStyles` and en-only `lightTheme` / `darkTheme` |
| `src/hooks/useTheme.ts` | `useTheme()`, the single consumer entry point. Memoised per Paper theme and `mode:language` |
| `src/utils/types.ts` | The `Theme` interface (still `extends MD3Theme`) |
| `App.tsx` | Hydration gate (`AppWithMigrationWrapper` / `HydrationHold`) and `<PaperProvider theme={useTheme()}>` |
| `src/components/ui/` | The DS layer. Public barrel `index.ts`; shared prop types in `types.ts` |
| `src/components/ui/primitives/Pressable/` | State-layer primitive under every interactive DS component |
| `.eslintrc.js` | Paper `importNames` blocklist and the raw-hex ban on DS `styles.ts` |
| `src/theme/tokens/__tests__/invariants.test.ts` | Grep guards: no x1 theme, and the token-consumer allow-list |
| `src/components/ui/__tests__/invariants.test.ts` | Grep guards: DS observation-free, one `<Header>` per overlay, no Paper `Surface` imports |
| `scripts/verify-fonts.js` | `yarn verify:fonts` (CI): font assets present; Fraunces covers each Fraunces locale's letters |
| `src/assets/fonts/` | Font source; `npx react-native-asset` generates iOS `UIAppFonts` / `link-assets-manifest.json` and `android/app/src/main/assets/fonts/` from it |

## How it works

`useTheme()` reads `uiStore.colorScheme` (`'light' | 'dark'`) and `uiStore.language` (both persisted) and calls `buildTheme()`, which spreads Paper's `MD3DarkTheme` / `DefaultTheme` for Paper-internal fields, overlays `resolveTokens(mode).colors`, sets `typography` from `resolveTypographyForLocale(language)`, adds `spacing` (token scale plus legacy `default: 16`), `radius` and `stroke`, and the frozen legacy `fonts` (`configureFonts` MD3 typescale plus message TextStyles), `borders` and `insets`.

`App` feeds the result to `<PaperProvider>`; a scheme or language change re-renders without a remount. On cold start, `AppWithMigrationWrapper` renders `HydrationHold` (`testID="hydration-splash"`), a black or white `View` chosen by `Appearance.getColorScheme()`, until `isHydrated(uiStore)`.

DS components map `(variant, size, state)` to tokens in `createStyles` (their own `styles.ts`) and render interactive surfaces through `primitives/Pressable`, which adds the `pressed` overlay.

## Contracts and invariants

- **Single writers.** `uiStore.setColorScheme()` writes `colorScheme`, `uiStore.setLanguage()` writes `_language`; builder and hook only read. `buildTheme` is the only code that builds a `Theme` and the only place that knows which keys are MD3 aliases. Tokens are `const`: a mode switch selects a binding, never mutates.
- **The tokens module is pure.** No React, Paper or MobX. Its only runtime import is `src/utils/colorUtils`; `react-native` and `locales` imports are types only.
- **Token names mirror Figma.**
  - `radius.l` is Figma `Radius/L` (20), and radius has no `sm` step.
  - `Gap/*` and `radius/radius-xs` are aliases resolved inside the token module, so each dimension has one scale.
  - Line heights are absolute px: Figma multipliers are converted, for example H1 is 36 × 1.4, giving 50.
- **Two type surfaces that never feed each other.** `theme.typography.*` is from Figma and locale-aware; `theme.fonts.*` is the frozen MD3 typescale. New and restyled code reads `typography`, `spacing`, `radius`, `stroke`; legacy code keeps `theme.fonts`, `theme.spacing.default`, `borders`, `insets` until it migrates.
- **Token-consumer allow-list.** A file reading `theme.typography.`, `theme.radius.` or `theme.stroke.` must be under `ALLOWED_RELATIVE` in the tokens invariants test, or it fails. A restyle slice adds its paths in the same PR.
- **Headline fallback.** For `NON_LATIN_LOCALES` (`fa he ja ko pl ru uk zh zh_Hant`), Fraunces swaps to Inter at the same weight, and Fraunces italic to `Inter-Medium` with `fontStyle: 'italic'`. Inter and JetBrains Mono never swap. The swap runs inside the builder, so components stay locale-agnostic.
- **Font names match the files.** Every family string in `typography.ts` and `utils/theme.ts` equals a TTF filename and its iOS PostScript name, and is present in `src/assets/fonts`, the Android `assets/fonts` directory and `UIAppFonts`. `verify-fonts.js` checks presence only; check the PostScript name (`otfinfo --postscript-name`) when adding a font, because iOS silently falls back on a mismatch.
- **Hydration gate.** Nothing that calls `useTheme()` mounts before `isHydrated(uiStore)`. The gate must wrap `App`, because `App` calls `useTheme()` above the provider. The hold has no branding, no `Text`, no safe-area or insets (`App.tsx`, `HydrationHold`).
- **DS layer rules.**
  - Tokens only: raw hex is lint-banned in `src/components/ui/**/styles.ts`; no `theme.fonts.*`; token-module imports are types only.
  - Observation-free: no `mobx` or store imports (grep test).
  - No imports from legacy `src/components/*`.
  - Named exports only.
  - `variant` and `size` are closed unions per component.
- **Every overlay uses `Header`.** `Sheet`, `Modal` and `Dialog` each render exactly one `<Header>` from `../Header` (grep test).
- **Accessibility label required.** `WithRequiredA11yLabel<P>` requires `label` or `accessibilityLabel` at compile time. `warnIfNoA11yLabel` catches bypasses in `__DEV__`.
- **testID freeze.** DS defaults are `ui-<kebab-name>` (plus `-<discriminator>` for repeated items). A screen swapping in a DS component passes the legacy testID at the call site so Appium selectors still resolve. New testIDs are additive.
- **Paper-import blocklist.** `no-restricted-imports` bans Paper `importNames` (today `['Surface']`). An entry is added once its DS replacement ships and every call site has migrated, and is never removed. The end state leaves only `Text`, `Button`, `IconButton`, `Portal`, `Provider` importable.
- **Paper stays in the wrap folders.** `Switch`, `Checkbox`, `RadioButton` and `Dropdown` (whose popup is a Paper `Menu`) are the DS folders that wrap Paper widgets. `Modal` and `Dialog` import only `Portal`. `Sheet` composes `@gorhom/bottom-sheet`.
- **Snapshot discipline.** A screen-swap PR never changes a DS snapshot.

## Traps and decisions

- **`usePaperTheme()` inside `useTheme()` is load-bearing.** Through Paper's context, non-`observer` and memoised consumers re-render on a theme change. The cache is keyed on the Paper theme identity, so it cannot return a stale merge.
- **Use fixtures for locale tests.** `lightTheme` / `darkTheme` are en-only, so tests that need the Inter swap use `themeFixtures.byMode().byLocale()` (`jest/fixtures/theme.ts`).
- **`NON_LATIN_LOCALES` tracks glyph coverage, not script.** The bundled Fraunces is a Latin-1 subset (no Cyrillic, no Latin Extended-A), so `pl` is listed (ą ć ę ł ń ś ź ż are missing) and `pt` is not. `verify-fonts.js` fails the build, naming the letters, when a Fraunces-rendered locale uses one the subset lacks. Check a new locale against the TTF `cmap`, not its script.
- **A wrong family name silently renders the system font** (RN has no fallback lists). `verify-fonts.js` scans only `typography.ts` and `utils/theme.ts`; family literals elsewhere are unchecked.
- **The Fraunces TTFs are pinned static instances** (SOFT=0, WONK=1, opsz=36) that keep the original PostScript names. Regenerate with the same pins.
- **H1 uses `Fraunces-Medium` (500)** because Figma sets its "Fraunces-Regular" family at weight 500.
- **Synthesised italic** on `Inter-Medium` for the non-Latin italic fallback is deliberate: an `Inter-Italic` cut would cost about 200 KB for one accent style.
- **Colour sources.** Dark colours come from the Figma dark band, except where it disagreed with a visible shipped dark value; there the shipped value won.
- **The hydration hold is neutral on purpose.** A branded JS splash would chase the iOS storyboard pixel for pixel and add a branded screen to Android, which has no native launch screen. Holding the native splash (e.g. `react-native-bootsplash`) is the better end state, deferred as `NATIVE_CHANGES=YES`.
- **Wrap or rebuild.** Visual families are rebuilt on RN primitives because Paper's MD3 ripple, shapes and slots fight the design; form controls wrap Paper to keep its accessibility role and state semantics.
- **Enforcement gaps.**
  - Only Paper `Surface` also has a grep test over `src/`; a new blocklist entry gets only the lint rule unless you add a test.
  - The override that turns `no-restricted-imports` off for `App.tsx` and `src/hooks/useDeepLinking.ts` (automation bridge) also lifts the Paper blocklist there.
  - No per-folder Paper carve-out exists yet (see `.eslintrc.js`): add the wrap folder's allowance in the same change as an overlapping entry (`Menu` will hit `Dropdown`).
  - The raw-hex ban covers only DS `styles.ts`. Screen styles aren't linted, and some already hardcode non-mode-aware hex (onboarding `ModelRadioGroup/styles.ts`, `PipMascot`).
- **Canonical Figma variants.** Where Figma draws a family more than once, implement against Chip `890:29153`, Tabs `764:27807`, BottomNavBar `143:4685`; the other drawings are dead designs.
- **Pressed and focused states are not snapshotted:** Jest can't drive them, so those cells would duplicate default. `Pressable` resolves only `pressed`; focus belongs to the consumer (e.g. `Input`).
- **Remaining legacy.** MD3 types are still imported in `utils/types.ts`, `utils/index.ts`, `SidebarContent/` and `RenameModal/`, and `ChatInput/` imports `fontStyles`. Remove them only with the legacy surface.

## Verification

- Tests: `src/theme/tokens/__tests__/`, `src/hooks/__tests__/useTheme.test.tsx`, `src/utils/__tests__/theme.test.ts`, `__tests__/App.test.tsx` (hydration hold), each `src/components/ui/<Family>/__tests__/` (snapshots via `__tests__/helpers/snapshotMatrix.tsx`), and `src/components/ui/__tests__/invariants.test.ts`.
- Gates: `yarn lint`, `yarn typecheck`, `yarn verify:fonts`.
- Visual work: the `figma-implement` skill; `pocketpal-design-parity-reviewer` checks parity; captures per `docs/workflows/visual-capture.md`.
- By hand: toggle dark mode; switch to `fa` or `ja` (headlines in Inter), then cold-start with it persisted and confirm no Fraunces frame appears first.
