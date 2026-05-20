# Implementation Plan: Token foundation + fonts + theme decoupling + non-Latin fallback (FOU-114)

**Purpose**: land the design in `what.md` (LGTM round 2). Invisible foundation slice — the build must look pixel-identical to today. New token surface (`theme.typography.*`, `theme.spacing.s/m/...`) coexists with the verbatim legacy MD3 surface (`theme.fonts.*`, `theme.spacing.default`) per D10. No new Paper imports (I7); no Paper surface reduction.

**Round 1 revisions**: C1 reshaped Step 14 from inference-driven `VISUAL_CAPTURES` JSON to a manual cold-start visual-diff acceptance description (the `visual-capture.spec.ts` runs an inference flow that empty prompts cannot drive); C2 fixed Step 12 + Native-Verification section to use the repo's actual scripts (`yarn build:android:release` / `yarn ios:build:release`) — `--variant=release` and `--mode=release` are not what this repo wires; S1 added a positive-case assertion (`hydration-splash` is null when `_hydrated=true`) to Step 11 Test 2 wording (existing Test 1); S2 reordered Step 12/13 — e2e build runs first as the artifact that proves font registration, Release builds run last as the ship gate.

**Post-implementation revision (2026-05-20)**: Steps 4 + 5 are partially retired. `scripts/verify-paper-surface.js` + its Jest test + its `verify:paper` package.json entry + its CI step were stripped from the branch before PR open. Rationale: enforcing a Paper-import baseline (snapshot-style) is premature without the FOU-115 wrap-vs-rebuild architectural decision. If FOU-115 wraps Paper components (e.g. `Switch`/`Checkbox`), the snapshot guard fires on every wrapper PR for no useful reason; if FOU-115 rebuilds from RN primitives, an ESLint `no-restricted-imports` rule is the cleaner enforcement vector (real-time editor feedback, component-specific messages). I7 remains a slice-scoped invariant for FOU-114 — preserved as designed and code-reviewed; post-merge enforcement of Paper discipline is deferred to FOU-115 once the wrap-vs-rebuild call is made. Step 3 (`verify-fonts`) and its wiring remain — different value proposition (catches genuine "token references a family but TTF isn't bundled" bugs that the editor can't catch).

---

## Metadata

- **Task ID**: TASK-20260519-2110
- **Worktree**: `./worktrees/TASK-20260519-2110`
- **Branch**: `feature/TASK-20260519-2110`
- **Native Changes**: YES (Fraunces + Fraunces-Italic + JetBrains Mono TTFs; iOS `UIAppFonts`; Android assets)
- **Visual Confirmation**: YES (proves I1)
- **Intent Brief**: `./workflows/stories/TASK-20260519-2110/intent-brief.md`
- **WHAT**: `./workflows/stories/TASK-20260519-2110/what.md`
- **Architecture doc being created in this PR**: `./context/architecture/theming.md` (in the dev-team control-plane repo, NOT the worktree — per D7)
- **Status**: draft (revised — round 1 critic)

---

## Progress Tracking

| Step | Status | Commit | Notes |
| --- | --- | --- | --- |
| 0  Extract dark tokens from canonical Figma | DONE | (pre-staged) | `dark-tokens.json` already in story dir from parent session |
| 1  Acquire font assets (Fraunces, FrauncesItalic, JetBrainsMono — Regular + Medium) | DONE | 17b7125 | Filenames differ from how.md: italic cuts ship as Fraunces-Italic.ttf / Fraunces-MediumItalic.ttf (forced by upstream PostScript names — §9b rule satisfied) |
| 2  Drop fonts in `src/assets/fonts/`; mirror to Android; add iOS `UIAppFonts` | DONE | 17b7125 | iOS plist hand-edited; Android dir hand-copied; later linking via `npx react-native-asset` in df6c235 |
| 3  Add `scripts/verify-fonts.js` + Jest test | DONE | fbde600 | 5 tests pass; I8 enforced |
| 4  Add `scripts/verify-paper-surface.js` + Jest test | DONE | fbde600 | 6 tests pass; baseline is 35 IDs (WHAT §11's 23 was incomplete; full enumeration in commit) |
| 5  Wire verifiers into CI + `package.json` | DONE | fbde600 | `verify:fonts`, `verify:paper` scripts; CI steps next to `validate-l10n` |
| 6  Create token module at `src/theme/tokens/` (light + dark + alias resolution + locale selector) | DONE | d88a6da | 38 unit tests pass; tokens pure-data + colorUtils only |
| 7  Refactor `src/utils/theme.ts` into the `Theme` builder; preserve legacy `theme.fonts.*` verbatim | DONE | 6b550d9 | `buildTheme({mode, language})`; legacy fonts pinned verbatim; spacing.default=16 kept |
| 8  Remove `x1Theme` + `AppTheme.X1` | DONE | 6b550d9 | Combined into Step 7 commit (same file); grep `x1Theme\|AppTheme.X1` returns 0 |
| 9  Refactor `src/hooks/useTheme.ts` to read `colorScheme` + `language` | DONE | 92f50d7 | Thin wrapper; usePaperTheme spread retained |
| 10 Hydration gate in `AppWithMigrationWrapper` (above `App`'s `useTheme()` call) | DONE | b16ba31 | observer() wraps the wrapper; splash uses Appearance.getColorScheme() background |
| 11 Jest unit test for Scenario H (gate renders splash when `isHydrated(uiStore)` is false) | DONE | dfb8928 | 2 tests; mock has __setHydrated() escape hatch |
| 12 Native verify — fonts ship in bundle (e2e build first, then Release builds) | DONE | df6c235 + (build commands) | npx react-native-asset wired pbxproj; e2e + iOS Release + Android Release builds OK; 6 TTFs ship in each |
| 13 Lint / typecheck / full Jest / E2E quick-smoke | DONE | (verification commands) | typecheck 0 errors; lint 0 errors (4 pre-existing warnings); 2293/2293 Jest tests pass; iOS quick-smoke PASS in 74.7s |
| 14 Manual visual diff vs `origin/main` reference build (cold-start chat + settings, light + dark, iOS sim + Android emu) | PARTIAL | (screenshots in story dir) | Feature-branch screenshots captured (`screenshots/`). Reference-build comparison deferred to reviewer per `visual-diff-procedure.md` (disk space ran out trying to host both builds concurrently) |
| 15 Promote WHAT to `context/architecture/theming.md` (dev-team repo) in the same PR cycle | DONE | (dev-team repo) | Promoted to `context/architecture/theming.md` in the control-plane repo — all (P) → (C), zero (?) markers remain |

---

## Affected Files

| Path | Change kind | WHAT reference |
| --- | --- | --- |
| `workflows/stories/TASK-20260519-2110/dark-tokens.json` (dev-team repo) | add | §4a.3 / D6 |
| `src/assets/fonts/{Fraunces,FrauncesItalic,JetBrainsMono}-{Regular,Medium}.ttf` | add (6) | §1e / D9 |
| `android/app/src/main/assets/fonts/<same 6>` | add (6, mirrored) | §1e / §5 |
| `ios/PocketPal/Info.plist` | edit (`UIAppFonts` array) | §1e / §5 |
| `scripts/verify-fonts.js` + `scripts/__tests__/verify-fonts.test.js` | add | I8 |
| `scripts/verify-paper-surface.js` + `scripts/__tests__/verify-paper-surface.test.js` | add | I7 |
| `.github/workflows/ci.yml` | edit (2 `run:` steps next to `validate-l10n.js`) | §5 |
| `package.json` | edit (`verify:fonts`, `verify:paper` scripts) | §5 |
| `src/theme/tokens/{index,types,colors,typography,spacing,radius,stroke}.ts` | add | §4a, §1a, §1c, §1d, §4d |
| `src/theme/tokens/__tests__/typography.test.ts` | add | §6.C / §6.D / §6.G |
| `src/utils/theme.ts` | edit (becomes `Theme` builder; legacy surface verbatim) | §4b / D10 |
| `src/utils/types.ts` | edit (extend `Theme` with `typography`, `radius`, `stroke`; `ThemeSpacing` gains token keys, keeps `default`) | §1b |
| `src/hooks/useTheme.ts` | edit | §4b / D2 |
| `App.tsx` (`AppWithMigrationWrapper`) | edit (hydration gate) | §4c.4 / I10 |
| `__mocks__/external/mobx-persist-store.js` | edit (add `isHydrated` mock) | §6.H |
| `__tests__/App.test.tsx` | edit (gate behaviour test) | §6.H |
| `context/architecture/theming.md` (dev-team repo, NOT worktree) | add | D7 |

---

## Implementation Steps

### Step 0: Extract dark-mode token values from the canonical Figma file

**Implements**: WHAT §4a.3, §1c, D6.

**Files**: `workflows/stories/TASK-20260519-2110/dark-tokens.json` (dev-team repo story dir).

**Approach**:

1. Use Figma MCP `get_variable_defs` against file `RZxDJea4t6jnBZrV4YBacF`, node `989:*` (dark render of `789:19792`). Capture the dark binding of every variable from the mode-aware collection as JSON keyed by token name.
2. For every dark-binding value, compare with the current `src/utils/theme.ts` dark output (`createBaseColors(AppTheme.Dark)` + `createSemanticColors(...,true)`). Per D6: if the canonical disagrees at a key with a visible consumer, **the current dark value wins for I1** and the disagreement gets appended under `"designer_asks": [...]` (token, canonical, current, reason).
3. Tokens with no dark binding in the canonical file (§9a): record under `"missing_dark_binding": [...]`. Step 6 will fall back to the light value and emit a TODO comment.

**Verification**:

- `dark-tokens.json` exists with full snapshot + `designer_asks` + `missing_dark_binding` arrays.
- Spot-check `background`, `surface`, `onSurface`, `primary` resolve.
- No design decisions made here — disagreements are recorded, not re-litigated.

---

### Step 1: Acquire font binaries (Regular + Medium for each family)

**Implements**: WHAT §1e, D9, §9b.

**Files**: none (acquisition only; assets land in Step 2).

**Approach**:

1. Download static TTFs from Google Fonts (OFL):
   - Fraunces upright — 400 (Regular) and 500 (Medium).
   - Fraunces italic — 400 and 500 (separate RN family per §1d / glossary; see filenames below).
   - JetBrains Mono — 400 and 500.
2. Filenames (must equal the iOS PostScript name; §9b):
   - `Fraunces-Regular.ttf`, `Fraunces-Medium.ttf`
   - `FrauncesItalic-Regular.ttf`, `FrauncesItalic-Medium.ttf`
   - `JetBrainsMono-Regular.ttf`, `JetBrainsMono-Medium.ttf`
3. Verify with `otfinfo --postscript-name <file>` (macOS: `brew install lcdf-typetools`). PostScript name MUST equal filename sans `.ttf`. On any mismatch, fetch a different cut — do NOT proceed.
4. Record source URLs and SHA-256 of each TTF in the Step 2 commit body.

**Verification**: all 6 TTFs validated; PostScript names match filenames sans extension.

---

### Step 2: Drop fonts; mirror to Android; add iOS UIAppFonts entries

**Implements**: WHAT §1e, §5.

**Files**:

- `src/assets/fonts/` — add 6 TTFs alongside the existing 7 Inter files.
- `android/app/src/main/assets/fonts/` — same 6 files mirrored.
- `ios/PocketPal/Info.plist` — append 6 `<string>...ttf</string>` entries inside the existing `UIAppFonts` array (currently lines 67–78).

**Approach**:

1. Copy verified TTFs into `src/assets/fonts/`.
2. Run `npx react-native-asset` from the worktree to mirror to Android. Verify the 6 files land in `android/app/src/main/assets/fonts/`. If `react-native-asset` is unavailable, copy manually (the existing Inter set was mirrored the same way).
3. Manually append 6 entries to `ios/PocketPal/Info.plist`'s `UIAppFonts` array — auto-link does NOT update the plist:
   ```
   <string>Fraunces-Regular.ttf</string>
   <string>Fraunces-Medium.ttf</string>
   <string>FrauncesItalic-Regular.ttf</string>
   <string>FrauncesItalic-Medium.ttf</string>
   <string>JetBrainsMono-Regular.ttf</string>
   <string>JetBrainsMono-Medium.ttf</string>
   ```
4. Do NOT edit `react-native.config.js` (the existing `assets: ['./src/assets/fonts']` already covers the directory).

**Verification**:

- `ls src/assets/fonts/ | wc -l` → 13. `ls android/app/src/main/assets/fonts/ | wc -l` → 13.
- `grep -c '<string>.*\.ttf</string>' ios/PocketPal/Info.plist` → 15 (2 Material + 7 Inter + 6 new).
- Fonts pickable by build (verified in Step 12).

---

### Step 3: `scripts/verify-fonts.js` + Jest test

**Implements**: WHAT I8 (critic SUGGESTION 2).

**Files**: `scripts/verify-fonts.js`; `scripts/__tests__/verify-fonts.test.js`.

**Approach** (pattern mirrors `scripts/validate-l10n.js` + `validate-l10n.test.js`):

1. Script reads the union of `fontFamily` string literals from `src/theme/tokens/typography.ts` (Step 6) AND `src/utils/theme.ts` (legacy `fontStyles`).
2. For every distinct family name, assert: `<Name>.ttf` exists in `src/assets/fonts/`, in `android/app/src/main/assets/fonts/`, and as a `<string>` in `ios/PocketPal/Info.plist`. Exit non-zero with a list of mismatches.
3. Test invokes the script and asserts exit 0.

**Verification**: `node scripts/verify-fonts.js` exits 0; `yarn test scripts/__tests__/verify-fonts.test.js` passes.

---

### Step 4: `scripts/verify-paper-surface.js` + Jest test (I7 guard)

**Implements**: WHAT I7 (critic SUGGESTION 2).

**Files**: `scripts/verify-paper-surface.js`; `scripts/__tests__/verify-paper-surface.test.js`.

**Approach**:

1. Script greps `src/**/*.{ts,tsx}` (excluding `__tests__`, `__mocks__`) for `from 'react-native-paper'`. Parses each import line, extracts the identifier set (handling aliases like `Dialog as PaperDialog` and type-only imports).
2. Compares against a baseline JSON literal embedded in the script — exactly the snapshot from WHAT §11 (the ~23 identifiers + types: `ActivityIndicator, Button, Card, Checkbox, Chip, Dialog, Divider, DividerProps, Drawer, FAB, Icon, IconButton, List, MD3Theme, Menu, Paragraph, Portal, ProgressBar, SegmentedButtons, Snackbar, Surface, Switch, Text, TextInput, Tooltip, useTheme`).
3. Exits non-zero on any add OR remove. Future Paper-reduction PRs (FOU-115/123) update the baseline as part of that PR.

**Verification**: `node scripts/verify-paper-surface.js` exits 0 against the unchanged surface; Jest passes.

---

### Step 5: Wire verifiers into CI + `package.json`

**Implements**: WHAT §5, I7, I8.

**Files**:

- `package.json` — add `"verify:fonts": "node scripts/verify-fonts.js"` and `"verify:paper": "node scripts/verify-paper-surface.js"` next to existing `"l10n:validate"` (line 22).
- `.github/workflows/ci.yml` — add two `run:` steps next to the existing `node scripts/validate-l10n.js` step (line 84). Same job, same `if:` conditions.

**Approach**: minimal mirror of existing l10n validator wiring; no new job introduced.

**Verification**: `yarn verify:fonts` and `yarn verify:paper` pass locally.

---

### Step 6: Token module at `src/theme/tokens/`

**Implements**: WHAT §4a (entire), §1a, §1c, §1d row 4 (new typography surface), §4d (fallback selector).

**Files**:

- `src/theme/tokens/types.ts` — `Tokens`, `TokenColors`, `TokenTypography`, `TokenSpacing`, `TokenRadius`, `TokenStroke`, `Mode = 'light' | 'dark'`. Shapes verbatim from §1a.
- `src/theme/tokens/spacing.ts` — `export const spacing: TokenSpacing = { none: 0, xxs: 2, xs: 4, s: 8, sm: 12, m: 16, ml: 20, l: 24 }` (§1a verbatim).
- `src/theme/tokens/radius.ts` — `{ none: 0, xxs: 2, xs: 4, s: 8, sm: 12, m: 16, ml: 20, l: 32, xl: 40 }`.
- `src/theme/tokens/stroke.ts` — `{ hairline: 0.5, s: 1, m: 1.5, l: 3 }`.
- `src/theme/tokens/colors.ts` — `lightColors` and `darkColors`. Sources:
  - Light: verified canonical (intent brief) + every name in the §1c migration table.
  - Dark: `dark-tokens.json` (Step 0); apply D6 — current dark value wins on I1 conflict, baked in as literal with comment referencing the `designer_asks` entry.
  - `surfaceContainer*`, `surfaceDim`, `surfaceBright`: ship today's `withOpacity` math output baked in as literals, `// TODO: explicit binding pending (FOU-115)` (§5 deferred #4).
  - Every name in §1c — including `menu*`, `thinkingBubble*`, `btn*`, `iconModelType*`, `bgStatus*`, `searchBarBackground`, `authorBubbleBackground`, `userAvatarNameColors`, `stateLayerOpacity` and friends — both light and dark entries.
- `src/theme/tokens/typography.ts` —
  - Family-name constants: `'Inter-Regular' / -Medium`, `'Fraunces-Regular' / -Medium`, `'FrauncesItalic-Regular' / -Medium`, `'JetBrainsMono-Regular' / -Medium`.
  - Latin (base) typography: every named style in WHAT §1a — `bodyM`, `bodyS`, `uiM`, `uiS`, `titleL/M/S`, `captionM/S`, `headlineH1`, `styledXs`, `codeM`, `codeS`. Values sourced from the canonical Figma typography variables (intent brief verified light side).
  - Two normalised offenders (§4a.4): `headlineH1 = { fontFamily: 'Fraunces-Regular', fontSize: 36, lineHeight: 50, fontWeight: '400' }` (36 × 1.4 → 50; I4). `styledXs.lineHeight = fontSize` (100% multiplier resolved).
  - Weight `500` → `*-Medium` family (§4a.5). If the canonical uses any weight other than 400/500 on these tokens, STOP and re-route to architect — D9 boundary.
  - Constant `NON_LATIN_LOCALES: ReadonlyArray<AvailableLanguage> = ['fa','he','ja','ko','zh','zh_Hant']` (WHAT glossary).
  - `typographyForLocale(style, locale): TextStyle` implementing §4d.2:
    - Fraunces-family + non-Latin → swap to `Inter-Regular` / `Inter-Medium` (same weight).
    - `FrauncesItalic-*` + non-Latin → `Inter-Medium` + `fontStyle: 'italic'` (D5).
    - Inter / JetBrains Mono → no swap (Inter covers Latin+Cyrillic; code is locale-agnostic).
- `src/theme/tokens/index.ts` — re-exports + `lightTokens`, `darkTokens`, `resolveTokens(mode): Tokens`. `Tokens.typography` is the Latin base; locale swap runs in the builder (§4d.3).
- `src/theme/tokens/__tests__/typography.test.ts` — unit tests covering Scenarios §6.C, §6.D, §6.G (see Testable-Contract Coverage).

**Approach**:

1. Pure data + types. NO `from 'react'` / `from 'react-native-paper'` / `from '../store'` imports anywhere under `src/theme/tokens/`.
2. `Gap/*` and lowercase `radius/radius-xs` aliases (§4a.7) are NOT exposed — only `spacing` and `radius` surfaces exist. Consumers map `Gap/S` → `spacing.s` etc.

**Verification**:

- `yarn typecheck` passes (`TokenColors` field parity across `lightColors`/`darkColors`).
- `yarn lint` passes.
- `grep -rn "from 'react'\|from 'react-native-paper'\|from '\.\./store'" src/theme/tokens/` returns no hits (purity).
- Token unit tests pass.

---

### Step 7: Refactor `src/utils/theme.ts` into the `Theme` builder

**Implements**: WHAT §4b, §1b, §1d rows 1–3 (legacy preservation), D10, I1.

**Files**: `src/utils/theme.ts`; `src/utils/types.ts` (extend `Theme`).

**Approach**:

1. `src/utils/types.ts`: extend `Theme` with `typography: TokenTypography`, `radius: TokenRadius`, `stroke: TokenStroke`. Extend `ThemeSpacing` with all token keys (`none/xxs/xs/s/sm/m/ml/l`) AND keep `default: number` for legacy consumers (§1b, D10). Keep `extends MD3Theme` — §5 deferred #5 (not in scope).
2. `src/utils/theme.ts` becomes a builder. New surface:
   - `buildTheme({ mode, language }): Theme` — pure function; explicit args for unit-testability.
   - `lightTheme = buildTheme({ mode: 'light', language: 'en' })`; `darkTheme = buildTheme({ mode: 'dark', language: 'en' })` (en-locale snapshots per §4b.6).
3. `buildTheme` constructs `Theme` per §1b:
   - `colors`: spread `resolveTokens(mode).colors` plus every MD3-compat alias name that current `createBaseColors` + `createSemanticColors` produce — values preserved verbatim (I1; the alias layer is the builder's job per §4b.3).
   - `typography`: every key in `Tokens.typography` mapped via `typographyForLocale(key, language)`.
   - `fonts`: **constructed exactly as today** — same `configureFonts({config: fontStyles.regular})` baseline, same `customVariants` (bold/medium/thin/light/semibold), same per-variant overrides (`displayMedium`/`titleSmall`), same custom TextStyles (`titleMediumLight`, `dateDividerTextStyle`, `emptyChatPlaceholderTextStyle`, `inputTextStyle`, all `receivedMessage*`/`sentMessage*`, `userAvatarTextStyle`, `userNameTextStyle`). **Values copied verbatim from current `createTheme` body — pinned per §1d row 2 + D10.** The two surfaces do not cross-feed.
   - `spacing`: `{ ...tokens.spacing, default: tokens.spacing.m }` — `m === 16`, current `default === 16` (D10).
   - `radius`, `stroke`: new fields from tokens.
   - `borders: { inputBorderRadius: 16, messageBorderRadius: 15, default: 12 }` (verbatim).
   - `insets: { messageInsetsHorizontal: 20, messageInsetsVertical: 10 }` (verbatim).
   - `icons: {}` (verbatim).
   - Non-color/non-font Paper internals: spread `MD3DarkTheme` / `PaperLightTheme` for `isV3`, `dark`, `roundness`, `animation` (D3) — same as today.
4. Preserve `fontStyles` export (the Inter map) verbatim — `src/components/ChatInput/styles.ts:4` imports it; removal lives in FOU-123.

**Verification**:

- `yarn typecheck` and `yarn lint` pass.
- `yarn test --findRelatedTests src/utils/theme.ts src/hooks/useTheme.ts` passes (existing tests against `lightTheme`/`darkTheme` continue to resolve).
- Consumer-count parity: `grep -rn "theme\.fonts\.\(bodyMedium\|titleSmall\|bodyLarge\|displaySmall\|headlineLarge\|headlineMedium\|labelLarge\)" src/ | wc -l` → 18 (unchanged). `grep -rln "theme\.spacing\.default" src/ | wc -l` → 4 (unchanged).

---

### Step 8: Remove `x1Theme` + `AppTheme.X1`

**Implements**: WHAT D4, I9.

**Files**: `src/utils/theme.ts` — delete `AppTheme.X1` enum member and `x1Theme` export.

**Approach**: pure deletion. Pre-research found zero consumers in `src/`. Before commit: `grep -rn "x1Theme\|AppTheme.X1" src/` must return zero hits.

**Verification**: grep is empty; `yarn typecheck` passes.

---

### Step 9: Refactor `src/hooks/useTheme.ts`

**Implements**: WHAT §4b (hook), §4d (locale subscription), D2, D8.

**Files**: `src/hooks/useTheme.ts`.

**Approach**:

1. Body becomes a thin wrapper: reads `uiStore.colorScheme` AND `uiStore.language` (both MobX-observable — consumers are already `observer`-wrapped where reactivity matters), calls `buildTheme({ mode, language })`, returns the result. Keep the `usePaperTheme<MD3Theme>()` spread for Paper-internal fields PocketPal does not override (preserves I7 compatibility — same merge pattern as today's line 14).
2. No companion `useTokens()` (D2). Return type stays `Theme` (now extended in Step 7).

**Verification**: `yarn typecheck` passes; existing tests that call `useTheme()` pass.

---

### Step 10: Hydration gate in `AppWithMigrationWrapper`

**Implements**: WHAT §4c.4, D11, I10, Scenario H, §9e. Critic SUGGESTION 1 placement.

**Files**: `App.tsx`.

**Approach**:

1. The current `useTheme()` call at `App.tsx:60` runs BEFORE `<PaperProvider>` mounts at `:82`. The gate MUST therefore wrap `App` itself (or short-circuit before `useTheme()` is called). `AppWithMigrationWrapper` (currently lines 213–219) is the chosen host — it sits above `App` and has no theme dependency.
2. Convert `AppWithMigrationWrapper` to `observer(...)`. Read `isHydrated(uiStore)` from `mobx-persist-store`. When `false`: render a hydration splash — a `View` with `testID="hydration-splash"`, `flex: 1`, and `backgroundColor` resolved from `Appearance.getColorScheme()` (hard-code `#000000` for `'dark'`, `#ffffff` for `'light'` — matches the eventual `tokens.colors.background` for the common case). No spinner (§9k).
3. When `true`: render `<AppWithMigration><App /></AppWithMigration>` as today. The `useTheme()` call at `:60` is unreachable until hydration completes — persisted `language` / `colorScheme` are observed on first theme-consuming frame (Scenario H).
4. Do NOT touch `AppWithMigration` itself (DB migration UI is a separate concern).

**Verification**:

- Code-read: `useTheme()` is unreachable while `isHydrated(uiStore)` is false.
- Unit test in Step 11 covers the gate.

---

### Step 11: Jest unit test for Scenario H (gate behaviour)

**Implements**: WHAT §6 Scenario H "automated (preferred)". Critic SUGGESTION 1.

**Files**: `__mocks__/external/mobx-persist-store.js` (extend); `__tests__/App.test.tsx` (extend).

**Approach**:

1. Extend the existing mock to add a controllable `isHydrated`:
   ```js
   // __mocks__/external/mobx-persist-store.js
   let _hydrated = true;
   export const makePersistable = jest.fn().mockImplementation(() => Promise.resolve());
   export const isHydrated = jest.fn(() => _hydrated);
   export const __setHydrated = (v) => { _hydrated = v; };
   ```
2. In `__tests__/App.test.tsx`:
   - **Test 1** (existing "renders correctly"): default `_hydrated = true` — render returns the migration wrapper subtree (`<PaperProvider>` mounts). Add a positive-case assertion: `queryByTestId('hydration-splash')` is `null` while `_hydrated = true` (closes the regression where the gate could be silently disabled and the splash never renders even though `<PaperProvider>` mounts). One-line assertion per critic S1.
   - **Test 2** (new): import `__setHydrated`, set to `false`, render. Assert `queryByTestId('hydration-splash')` is truthy and `<PaperProvider>` is NOT in the tree. Reset in `afterEach`.

**Verification**: `yarn test __tests__/App.test.tsx` passes both tests; removing the Step 10 gate breaks Test 2; toggling the gate's condition to always-true breaks Test 1's new null-splash assertion.

---

### Step 12: Native verification — bundles ship the fonts (NATIVE_CHANGES=YES)

**Implements**: repo non-negotiable, §1e. Critic C2 + S2.

**Approach** — run from the worktree (`${WORKTREE_PATH}`), NEVER the submodule. Order is deliberate (critic S2): the e2e build is the artifact that exercises runtime font registration on the simulator — run it first so a missing-glyph or postscript-mismatch failure surfaces against the same artifact the next step (Step 13 quick-smoke) consumes. Release builds run last, as the ship gate.

```bash
cd "${WORKTREE_PATH}"
cd ios && pod install && cd ..

# 1. e2e build — registers fonts at runtime; consumed by Step 13 quick-smoke
yarn ios:build:e2e

# 2. Release builds — final ship-gate. Use the repo's own scripts (RN 0.79; the
#    repo wires Android via gradle directly and iOS via xcodebuild — neither
#    uses --variant=release or --mode=release on the CLI, see package.json).
yarn ios:build:release           # xcodebuild Release / iphoneos arm64+x86_64
yarn build:android:release       # ./gradlew bundleRelease
```

Verify the 6 new TTFs ship inside both bundles:

- iOS (e2e build): `find ios/build -name 'Fraunces*.ttf' -o -name 'JetBrainsMono*.ttf' | wc -l` → 6.
- iOS (Release): same find against the Release output dir (or open the resulting `.xcarchive` / app bundle and inspect Resources).
- Android (Release): the gradle `bundleRelease` task emits an `.aab` under `android/app/build/outputs/bundle/<flavor>Release/`; verify with `unzip -l <aab> | grep -c -E 'Fraunces|JetBrainsMono'` → 6. If only an APK output is needed, fall back to `cd android && ./gradlew assembleRelease` and `unzip -l android/app/build/outputs/apk/<flavor>/release/*.apk | grep -c -E 'Fraunces|JetBrainsMono'` → 6.

**Verification**: all 3 build commands exit 0; both Release bundles + the e2e build contain the 6 new files. Skipping is a blocking review issue.

---

### Step 13: Lint / typecheck / Jest / E2E quick-smoke

**Implements**: intent-brief acceptance + repo non-negotiable on hooks.

**Approach** (depends on Step 12's `yarn ios:build:e2e` artifact already existing):

```bash
cd "${WORKTREE_PATH}"
yarn lint
yarn typecheck
yarn test
yarn verify:fonts
yarn verify:paper
node scripts/validate-l10n.js

# Step 12 already produced the e2e artifact; reuse via --skip-build.
cd e2e && yarn install && cd ..
yarn e2e:ios --spec quick-smoke --skip-build
```

Hooks: husky `.husky/` exists in repo. Do NOT bypass (`--no-verify`, `LEFTHOOK=0`, `core.hooksPath` overrides).

**Verification**: all commands exit 0; `quick-smoke` PASS; commits go through hooks.

---

### Step 14: Manual visual diff against `origin/main` reference build (Visual Confirmation=YES)

**Implements**: I1 evidence; intent-brief acceptance. Critic C1.

**Why not driven by `e2e/specs/visual-capture.spec.ts`**: that spec is inference-driven (`sendMessage(prompt)` then `waitForExist(aiMessage)` then `waitForInferenceComplete()` — see `e2e/specs/visual-capture.spec.ts` lines 108–125 in this worktree). Passing `prompt: ""` either fails at `sendMessage` or hangs awaiting an AI message that never arrives. This slice's evidence is **cold-start screen state with NO inference** — chat empty state + settings, both light and dark, both iOS sim and Android emu. The spec has no screen-navigation-only mode today; growing one is a useful dev-team-side cleanup but is **out of scope here** (see Deferred Items).

**What to capture** (8 screenshots total = 4 screens × 2 platforms; collected manually using `xcrun simctl io <udid> screenshot` for iOS sim and `adb exec-out screencap -p` for Android emu):

| # | Screen | Mode | Platform |
| --- | --- | --- | --- |
| 1 | Chat (cold start, empty state) | light | iOS simulator (iPhone 16 Pro) |
| 2 | Chat (cold start, empty state) | dark  | iOS simulator (iPhone 16 Pro) |
| 3 | Settings                       | light | iOS simulator (iPhone 16 Pro) |
| 4 | Settings                       | dark  | iOS simulator (iPhone 16 Pro) |
| 5 | Chat (cold start, empty state) | light | Android emulator (Pixel 7-class) |
| 6 | Chat (cold start, empty state) | dark  | Android emulator (Pixel 7-class) |
| 7 | Settings                       | light | Android emulator (Pixel 7-class) |
| 8 | Settings                       | dark  | Android emulator (Pixel 7-class) |

**Reference build (the "current production" to diff against)** — built from `origin/main` of the source repo, NOT the worktree branch, captured on the SAME simulator / emulator instance and the SAME screen state for an apples-to-apples diff:

```bash
# Reference build lives in a separate worktree off origin/main — not the submodule.
./tools/create-worktree.sh TASK-20260519-2110-ref --ref origin/main --branch main-ref-tmp
cd worktrees/TASK-20260519-2110-ref
cd ios && pod install && cd ..
yarn ios:build:e2e                       # same simulator-targeted Release build
# Boot the same simulator UDID used for the worktree captures, install this build,
# capture screenshots 1–4 for the reference. Repeat the Android variant:
yarn android:build:e2e                   # same e2e Release path for Android
# Install on the same emulator AVD; capture screenshots 5–8 for the reference.
```

**Acceptance ("visually indistinguishable to a designer's eye"; I1)** — for each of the 8 capture indices, place the worktree screenshot beside the `origin/main` reference screenshot. The pair MUST be visually indistinguishable: background colours, surface colours, text colours, font (Inter on all rendered text in Phase 1 — Fraunces files ship but no consumer renders them yet, §1d row 4), borders, radii, spacing. Any visible delta is a regression caused by an incorrect entry in the §1c migration table or a copy bug in Step 7's `fonts:` block — fix the token / restore the literal; do NOT reclassify the delta as an intentional design change (this slice is invisible by definition).

**Deliverables on the PR**:

1. 8 pairs (worktree vs `origin/main` reference) attached, one per row in the table above.
2. A short narrative noting "no visible diff observed" (or, if any diff IS observed, that the migration table was corrected and a re-capture confirms parity).
3. The dark-mode pair MUST also confirm there is no light-mode flicker on mount (the hydration gate of §9e / D11 eliminates the `colorScheme` race; the very first painted pixel must be the persisted mode's background colour).

**Verification**: PR reviewer signs off on no visible diff vs reference; the 8 pairs are attached.

---

### Step 15: Promote WHAT to `context/architecture/theming.md`

**Implements**: D7, §10 cleanup #1, repo non-negotiable.

**Files**: `context/architecture/theming.md` in the **dev-team control-plane repo** (`/Users/aghorbani/codes/pocketpal-dev-team/context/architecture/theming.md`), NOT in the worktree.

**Approach**:

1. Copy `workflows/stories/TASK-20260519-2110/what.md` into the new architecture file.
2. Convert markers (per `context/architecture/README.md`): every **(P)** → **(C)**; every **(D)** stays **(D)**; **zero (?)** must remain — re-grep before commit.
3. Strip story-scoped headers (`Revision history`, `Status: ...`, `Story: ...`) — those belong to the audit trail in the story dir, not the cumulative doc.
4. Leave `workflows/stories/TASK-20260519-2110/what.md` intact for archival.
5. Commit on the same dev-team branch covering this story so the architecture promotion lands as part of the same PR cycle that ships the code (D7). The app-side PR description references the dev-team commit hash.

**Verification**:

- `grep -c '(?)' context/architecture/theming.md` → 0.
- `grep -c '(P)' context/architecture/theming.md` → 0.
- Sections 0–9 from the WHAT are all present.

---

## Testable-Contract Coverage

Every canonical scenario in WHAT §6 has a verification path.

| Contract item | Verified by |
| --- | --- |
| §6.A — Light, en, unchanged pixels | Step 14 chat-cold-start (light) + settings (light) pairs vs `origin/main` reference; Step 13 Jest suite (existing tests still resolve against unchanged `theme.fonts.*` + `theme.colors.*`) |
| §6.B — Dark, en, unchanged pixels | Step 14 chat-cold-start (dark) + settings (dark) pairs vs `origin/main` reference; Step 13 Jest suite |
| §6.C — Headline = Fraunces for Latin locale | Step 6 unit test `src/theme/tokens/__tests__/typography.test.ts`: `typographyForLocale('headlineH1', 'en')` → `fontFamily: 'Fraunces-Regular'`, `fontSize: 36`, `lineHeight: 50` |
| §6.D — Headline falls back to Inter for non-Latin | Same test file: `typographyForLocale('headlineH1', l)` for `l ∈ {fa, he, ja, ko, zh, zh_Hant}` → `fontFamily: 'Inter-Regular'`, same metrics |
| §6.E — Mode swap is reactive | Add `src/hooks/__tests__/useTheme.test.ts` (or extend `__tests__/App.test.tsx`): render a tiny consumer, `runInAction(() => uiStore.setColorScheme('dark'))`, assert re-render with dark `theme.colors.background` |
| §6.F — Language swap is reactive | Same test file: `runInAction(() => uiStore.setLanguage('fa'))`, assert `theme.typography.headlineH1.fontFamily === 'Inter-Regular'` |
| §6.G — JetBrains Mono for code (locale-agnostic) | Token unit: `typographyForLocale('codeM', 'ja')` → `'JetBrainsMono-Regular'` (no swap). No rendered-pixel check — no consumer is updated in this slice (§9j) |
| §6.H — Cold start with persisted non-Latin language — no Fraunces flash | Step 11 Jest test on `__tests__/App.test.tsx` (both Test 1 positive-case `hydration-splash` null assertion AND Test 2 splash-rendered-while-not-hydrated assertion) |

---

## Native Verification (NATIVE_CHANGES=YES)

```bash
cd "${WORKTREE_PATH}"
cd ios && pod install && cd ..

# e2e build first — proves runtime font registration on the simulator (consumed by Step 13).
yarn ios:build:e2e

# Release builds as the ship gate. CLI flags taken from this repo's package.json
# (RN 0.79 — neither --variant=release nor --mode=release is wired here; the
# project drives release via xcodebuild and gradle directly).
yarn ios:build:release           # xcodebuild Release iphoneos
yarn build:android:release       # ./gradlew bundleRelease
```

Plus per Step 12: confirm all 6 new TTFs ship inside the e2e bundle, the iOS Release bundle, and the Android Release bundle. Skipping is a blocking review issue (repo non-negotiable).

---

## Visual Confirmation

See Step 14 for the 8-screenshot manual-diff procedure against an `origin/main` reference build. The `e2e/specs/visual-capture.spec.ts` spec is NOT used for this slice (inference-driven; no screen-navigation-only mode today — see Deferred Items).

---

## Deferred Items

Items WHAT explicitly defers — do NOT land here. They stay in `context/architecture/theming.md` for the next story.

- §5 cleanup #1 — migrate consumer `styles.ts` from `theme.spacing.default` → `theme.spacing.m` and `theme.fonts.bodyMedium` → `theme.typography.bodyM`. **FOU-117–122.**
- §5 cleanup #2 — remove MD3-compat aliases once consumers migrate. **FOU-123.**
- §5 cleanup #3 — move `stateLayerOpacity` family into a dedicated `interaction` namespace. **FOU-115+.**
- §5 cleanup #4 — `withOpacity` semantic-surface keys to explicit Figma bindings, per-key. Today's literal values shipped with TODO comment.
- §5 cleanup #5 — eliminate `MD3Theme` / `MD3Colors` / `MD3Typescale` imports from `src/utils/types.ts`, `src/utils/index.ts`, `src/components/{SidebarContent,RenameModal}/styles.ts`. **FOU-123.**
- Paper-surface reduction to the thin set. **FOU-115/123.**
- RTL screen mirroring beyond the typography layer (§9f). **FOU-117+.**
- Dev-team-side: grow `e2e/specs/visual-capture.spec.ts` (or a sibling) to support a screen-navigation-only / no-inference capture mode so invisible-foundation slices like this one can be driven by `VISUAL_CAPTURES` JSON rather than manual screenshots. Out of scope here.

---

## What this plan is NOT

- Not a design doc — design lives in `what.md`. Disagreements push back to the architect, not resolved here.
- Not a justification — `intent-brief.md` is where the request lives.
- Not exhaustive — only steps the implementer needs.
