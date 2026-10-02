# Settings

## Purpose

The Settings screen (`SettingsScreen`, drawer route `ROUTES.SETTINGS`): one scrolling screen of Paper cards. Covers which store each control writes, the testIDs e2e depends on, the language picker, and the Internet Search card. Not covered: what the engine does with `contextInitParams` (`model-loading.md`), search engines (`pals-and-talents.md`), tokens and DS (`theming.md`), drawer navigation (`app-shell.md`).

The launcher root, Preferences / App Settings sub-screens and account routes exist only on unmerged `redesign/phase-3`; the previous version of this doc described them (`git show 1ad6ce1:context/architecture/settings.md`). Distill it back in when the branch lands.

## Code map

| Path | Role |
| --- | --- |
| `src/screens/SettingsScreen/SettingsScreen.tsx` | The whole screen: card order, control → setter wiring, local UI state |
| `src/screens/SettingsScreen/CacheTypeMenuRow.tsx` | `CacheTypeMenuRow` + `useMenuAnchor`: shared row for the target and draft K/V cache-type menus |
| `src/utils/deviceSelection.ts` | `getDeviceOptions()`: the device segmented-control options and each option's valid / default flash-attn types |
| `src/utils/flashAttnCompatibility.ts` | `inferBackendType`, `getAllowedCacheType{K,V}Options`: which cache types a flash mode + backend allows |
| `src/components/LanguageSelector/` | Language trigger plus the searchable sheet |
| `src/components/SearchableSelectSheet/` | Shared searchable picker; also used by the TTS `HeroRow` |
| `src/store/SearchProviderStore.ts` | Search provider, result count, consent, BYOK keys in Keychain |
| `src/store/CustomToolStore.ts`, `src/screens/CustomToolsScreen/` | Custom HTTP tools: the count the card shows, and the manager the card opens (`custom-tools.md`) |
| `src/components/SearchProviderKeySheet/`, `src/components/HFTokenSheet/` | Key entry sheets for search providers and Hugging Face |
| `src/store/UIStore.ts`, `ModelStore.ts`, `HFStore.ts`, `TTSStore.ts` | The stores every control writes to |
| `src/screens/SettingsScreen/PurchasesCard.tsx` | Settings › Purchases: store-owned Pals with status and support code, Restore, link; drives the screen's `AuthSheet` |
| `App.tsx` | Mounts `SettingsScreen` as the `ROUTES.SETTINGS` drawer screen |
| `e2e/pages/SettingsPage.ts`, `e2e/helpers/selectors.ts` (`settings`) | The e2e page object and its selectors |

## How it works

`SettingsScreen` is a MobX `observer` that reads every value from its store and writes through that store's setter. Card order is in the JSX; engine controls sit under Model Initialization, mostly inside the collapsible Advanced accordion.

On mount the screen calls `checkGpuSupport()` and `getDeviceOptions()`. `inferBackendType()` re-runs when `contextInitParams.devices` changes and decides which cache types the K/V menus offer. With one device option or fewer, the device control collapses to a CPU-only notice.

`LanguageSelector` owns only `sheetOpen`: it builds its options from `uiStore.supportedLanguages` in registry order and calls `uiStore.setLanguage`. `SearchableSelectSheet` owns its search `query`.

## Contracts and invariants

- **One writer per field.** Settings holds no store state; every control goes through its store's setter:
  - `contextInitParams.*` → `modelStore.set*`; `useAutoRelease` → `modelStore.updateUseAutoRelease`
  - `colorScheme`, `_language`, `autoNavigatetoChat`, `displayMemUsage` → the `uiStore` setters
  - `userTTSOverride` → `ttsStore.setUserTTSOverride`
  - HF token → `hfStore.setToken / clearToken` (from `HFTokenSheet`); `useHfToken` → `hfStore.setUseHfToken`
  - search prefs → `searchProviderStore.setActiveProvider / setResultCount / setConsent`; keys → `setKey / clearKey`
  - purchases → only `purchaseStore.restore` / `requestLink` / `link` (`in-app-purchase.md`). The card lists `active | granted | unfulfillable` records, never account-only Pals, and hides when billing is unavailable and nothing was bought.
  - custom tools → **nothing**. The card only reads the count and navigates to `ROUTES.CUSTOM_TOOLS`; every write belongs to the manager and editor (`custom-tools.md`). The route is hidden from the drawer sidebar (`drawerItemStyle: {display:'none'}`), so the card is the only way in.
- **`uiStore.setLanguage` is the only writer of `_language`**, and `LanguageSelector` is its only caller.
- **testIDs are frozen.** e2e resolves:
  - `context-size-input` (the `SettingsPage.waitForReady` probe)
  - `advanced-settings-accordion`, with `batch-size-slider` as its "expanded" probe (`speculative*.spec.ts`)
  - `speculative-*`, `device-option-{cpu,gpu,hexagon}`, `gpu-layers-slider`, `dark-mode-switch`, `display-memory-usage-switch`
  - `language-selector-button`, `language-sheet`, `language-search`, `language-option-<lang>`
  - `custom-tools-card`, `custom-tools-open-button` (additive)
  - `purchases-card`, `settings-restore-purchases`, `settings-link-purchases` (additive; the link row hides when signed in and everything is linked)

  A rename or move lands with `e2e/helpers/selectors.ts` and the affected specs in the same change. New testIDs are additive.
- **The device option reads back from persisted names.** On Android `getCurrentDeviceId()` maps any name starting with `HTP` to `hexagon`, so a saved wildcard still shows as Hexagon.
- **Selecting a device writes only the option's device list.** `handleDeviceSelect` calls `setDevices(option.devices)`, never writes `n_gpu_layers`, and changes the flash type only when the current one is invalid for the new option.
- **The Hexagon option lists one exact name:** the first discovered `HTP*` device with no wildcard (`selectHexagonDevice`). If discovery finds none or fails, Hexagon isn't offered. Settings never rewrites persisted intent on fallback; `resolveDeviceSelection` does that at load time (`model-loading.md`, Contracts and invariants, "Hexagon resolution").
- **Flash-attn gates the K/V caches.** `setFlashAttnType('off')` resets both to F16; `setCacheTypeK/V` no-op while flash is off, and the rows are disabled. The draft K/V menus use `'on'` compatibility whatever the target's flash mode, and are disabled while `modelStore.effectiveDraftMode === 'off'`.
- **Search consent is enforced at execution, not only in the UI.** `WebSearchEngine` and `ReadUrlEngine` refuse unless `SearchAccess.canSearch()` — consent *and* a key for the active provider (`services/talents/index.ts`). In Settings the key button stays disabled until consent; Revoke calls `setConsent(false)`.
- **BYOK keys live only in Keychain,** under service `search_provider_service_<id>`. Only `activeProviderId`, `resultCount` and `hasConsentedToSearch` persist.
- **`normalizeHydratedPrefs` re-validates after hydration**, which bypasses the setters: a gated or unknown provider falls back to `brave`, the count is clamped to 1–8, consent counts only as a literal `true`.
- **Gated providers are shown but can't be selected.** `parallel` is disabled in the menu and `setActiveProvider` refuses it. Changing provider, consent or a key calls `resetSearchCache()`.
- **The language picker's layout doesn't depend on the locale.**
  - Trigger content-sized, rows full-bleed, no fixed pixel widths. `numberOfLines={1}` is a defensive cap that must never engage.
  - Fixed `75%` snap point; no dimension depends on `supportedLanguages.length`.
  - The query resets on every close path (`handleClose`), so reopening shows the full list.
  - Every `languageDisplayNames` entry contains its `(CODE)`, a Latin search handle for every locale (guarded by `src/locales/__tests__/locales.test.ts`).
- **`languageRegistry` (`src/locales/index.ts`) is the only writable locale list.** Every other wired-locale set is derived from it — the Weblate download list and the l10n validator fixture via `scripts/lib/registry-languages.js`, the `locales.test.ts` ranges off the `ALL_LANGUAGES` pin — or is a hand-maintained value fixture (the pin itself, display names, e2e strings). `en` never appears in a translation-side set, and directory enumeration never defines wired behaviour (the validator's fallback is the one sanctioned use).

## Traps and decisions

- **RTL text alignment differs between `Text` and `TextInput`.** RN's `textAlign` has no `start`/`end`, so `'left'` spells "start". RN mirrors `left`/`right` for `Text` under RTL, so row labels use plain `'left'`; an `isRTL` ternary would flip twice. `TextInput` is not mirrored, so the search field *needs* the ternary. `'auto'` is forbidden: it aligns by the first strong character, so the field flips mid-keystroke once a Latin code is typed. RTL follows the device locale (the app never calls `forceRTL`), so e2e can't reach it: use a forced-RTL capture.
- **The language list is virtualized** (`BottomSheetFlatList`), so unrendered rows can't be tapped. `SettingsPage.selectLanguage` types the code into `language-search` before tapping; the page waits for `language-sheet` to appear and to disappear, because a lingering backdrop swallows the next gesture.
- **`language.spec.ts` hardcodes translated text per locale:** `screenTitles.settings` and `settings.modelInitializationSettings` (the first card's title). Changing either string, or the first card, breaks it. Its locale list and assertion keys stay literal but are cross-checked against the registry by `scripts/__tests__/language-sync.test.js` on every `yarn test`; the translated strings themselves are still only proven by running the spec. e2e reaches Settings through the drawer by the English text `Settings`.
- **`SearchableSelectSheet` is shared with the TTS language picker**, so a behaviour change reaches both, and its empty-state copy comes from `common.noResults`, never `settings`.
- **The context-size input keeps a local draft.** A valid value is debounced 500 ms into `setNContext`; the store re-sync is skipped while the input is focused. e2e waits ~700 ms after typing.
- **`uiStore.iOSBackgroundDownloading` has a setter but no control.** Not persisted; the `UIStore` constructor forces it `true`; `DownloadManager` reads it.
- **Why the language picker is a searchable sheet.** An anchored Paper `Menu` is width-fragile and grows with locale count; the DS `Dropdown` wraps `Menu`, so it has the same defect, and `Menu` is slated for the Paper blocklist (`theming.md`, Contracts and invariants). Search stays on whatever the locale count, so a user stuck in an unreadable script can recover, and e2e stays deterministic. Filtering is on the label only, in registry order.

## Verification

- Jest: `src/screens/SettingsScreen/__tests__/SettingsScreen.test.tsx`; `src/components/{SearchableSelectSheet,SearchProviderKeySheet}/__tests__/`; `src/store/__tests__/{SearchProviderStore,UIStore}.test.ts`; `src/locales/__tests__/locales.test.ts`; `scripts/__tests__/language-sync.test.js` (cross-checks the e2e locale lists against the registry). `yarn l10n:validate` gates the locale JSONs.
- e2e: `e2e/specs/features/language.spec.ts` (cycles every locale); `speculative.spec.ts`, `speculative-paired.spec.ts`, `speculative-visual.spec.ts` (Advanced accordion and draft rows).
- By hand: toggle flash-attn off (K/V rows disable and reset to F16); switch device on an Android with Hexagon or OpenCL; type a code in the language sheet, select, reopen (full list); before consent, the search key button is disabled.
