# Settings flow (launcher + sub-screens)

**Purpose**: cumulative architecture truth for the **Settings** bottom-tab root
(`SettingsScreen`) and its pushed sub-screens. This doc owns the Settings
information architecture, the per-control single-writer table, the testID freeze
contract, and the full Settings pushed-route enumeration. The bottom-tab shell
and root-Stack topology live in `app-shell.md`; DS components and token rules
live in `theming.md`; About-screen feedback wiring is unchanged.

Status: **Launcher root + Preferences / App Settings sub-screens shipped
(reskin only, no behaviour change).** Auth entry points render inert; the
registered launcher header variant is implemented but dormant until account
reads are wired in a later slice.

Convention: **(C)** = current behaviour from code · **(D)** = decision.

(settings.md owns the Settings IA; app-shell.md owns only the nav topology.)

---

## 1. Information architecture

The former single Settings screen decomposes into a launcher root plus two
pushed sub-screens. Every control moves verbatim — same store field, same
writer, same testID, same conditional (`Platform.OS`, `__DEV__`,
`deviceOptions.length`, `gpuSupported`). No control is added or removed except
the Background Download row (§4). (C)

1. **Launcher root** (`SettingsScreen`, `SettingsTab`): an account header/CTA
   plus a list of navigation rows (icon + title + subtitle + chevron), then a
   Log out footer (registered only). Renders no settings control inline and no
   Stack header (it is a tab root). Rows in order: My pals (registered) ·
   Account Settings · Preferences · Benchmark · Models · App Settings ·
   About App, plus a `__DEV__`-gated Dev Tools row.
2. **Preferences sub-screen** (`PreferencesScreen`, pushed route): the
   model-engine surface — device selection, GPU layers, context size, the
   dissolved Advanced rows (batch / physical-batch / threads / image-max-tokens
   / flash-attention / K-cache / V-cache), Memory (mlock / mmap / Android
   weight-repacking), Model Loading (auto-offload / auto-navigate), API
   (HF token + use-HF-token), iOS Cache & Storage, and legacy Export. The
   Advanced accordion is dissolved into flat stacked containers. (D)
   - Speculative decoding (master toggle + draft-model picker + draft
     GPU-layers + draft K/V cache-type menus gated on flash-attn compatibility)
     is a control group in the same model-engine surface, below the target's own
     K/V cache rows. The fold out of the monolithic `SettingsScreen.tsx`
     Advanced accordion happened in the second `main` → `redesign/phase-3`
     reconcile; the accordion is gone, so the group renders flat like the rest.
     Contract in `model-loading.md`. (C)
   - All four cache-type rows (target K/V + draft K/V) render through the shared
     `CacheTypeMenuRow` + `useMenuAnchor` pair, which moved from
     `SettingsScreen/` to `PreferencesScreen/` with that fold. Each carries
     `accessibilityLabel = "<label>, <value>"` and the disabled explanation as
     its hint. (C)
3. **App Settings sub-screen** (`AppSettingsScreen`, pushed route): Dark Mode,
   Background Download, Language, TTS availability, (iOS-only) Display Memory
   Usage, and the Internet Search section (§9). (D)
   - The screen scrolls (`ScrollView`): with Internet Search folded in, the
     content exceeds a phone viewport. (C)
   - **Language** is the self-contained `LanguageSelector`
     (`src/components/LanguageSelector/`): a content-sized trigger plus the
     shared `SearchableSelectSheet` (title, search field, full-bleed rows,
     check mark on the active row). It replaced the Paper `Menu` anchored to an
     outlined `Button`, which was width-capped at 170px and unbounded in height.
     Because it is a component, the later `AppSettingsScreen` relocation is
     verbatim (I_S1). §10 owns its contract. (C)
4. **About App** maps to the existing `AboutScreen` (`ROUTES.APP_INFO`),
   reskinned in place — not a new screen. Its Send-feedback sheet and
   Feedback-sent toast are AboutScreen's existing `submitFeedback` flow. (D)

Seed (shown in the Figma Preferences frame) is intentionally omitted: there is
no `seed` field in `modelStore.contextInitParams` and no existing control, so
rendering it would be net-new behaviour plus a new persisted field. (D)

---

## 2. Navigation contract

- Two pushed routes are siblings of the existing pushed routes on the root
  Stack, full-bleed with a Stack back header, tab bar hidden:
  `ROUTES.PREFERENCES` (`'Preferences'`) and `ROUTES.APP_SETTINGS`
  (`'App Settings'`). Titles come from `screenTitles.preferences` /
  `screenTitles.appSettings`. (C)
- The launcher reaches sub-screens via `navigation.navigate(<route>)`; Benchmark
  / About App / Dev Tools via `ROUTES.BENCHMARK` / `ROUTES.APP_INFO` /
  `ROUTES.DEV_TOOLS`; My pals / Models via `ROUTES.PALS` / `ROUTES.MODELS`
  (launcher reskins the row only; the destination screens are owned elsewhere).
- The launcher root stays the `SettingsTab` screen and has no Stack header.

---

## 3. Hard invariants

- **I_S1 — No behaviour/semantics change.** Every toggle/slider/menu/button
  keeps its exact store field, writer, value mapping, disabled/visibility
  condition, and side effects. The restructure is pure relocation + reskin.
- **I_S2 — No orphaned screens (inherits app-shell I2).** Benchmark, App Info
  (About), and Dev Tools (`__DEV__`) remain reachable as launcher rows.
- **I_S3 — testID + a11y-label freeze (inherits theming testID freeze).** Every
  existing settings testID survives the move, on the same control, with a stable
  accessibility label. New testIDs are additive at new leaves only.
- **I_S4 — Single-writer preserved (§5).** No control gains a second writer; the
  **reskin relocation slice** itself adds no store and no persisted field.
  Net-new *feature* stores (e.g. `SearchProviderStore` for the Internet Search
  section, §8) are permitted and follow the standard single-writer rule (§5);
  the relocation slice still relocates existing controls verbatim without
  introducing a store or field of its own.
- **I_S5 — Tokens-only, mode-aware.** All colour/spacing/radius/type flow
  through `theme.*` tokens; no raw hex in screens or DS `styles.ts`.
- **I_S6 — Auth deferred cleanly.** The launcher renders auth entry points
  (Create Account CTA, Account Settings row, Log out) as inert/styled-only; no
  auth store, route, or handler is added in this slice. The root defaults to the
  not-registered variant and never reads account state here; the registered
  variant is implemented but dormant.

**Language picker (I_L\*)** — the `LanguageSelector` + `SearchableSelectSheet`
control (§1.3, §10):

- **I_L1 — No option truncates.** Full-bleed row width is the guarantee: no
  fixed pixel width on a row or a label, at any locale, in any script. The rows'
  `numberOfLines={1}` is a defensive cap that must not engage at any supported
  locale; if a future label overflows it, the cap is raised, never the row
  narrowed.
- **I_L2 — Trigger content-sized, never fixed-width.** The trigger sizes to its
  label. A single-line overflow guard is permitted but must not engage at any
  supported locale; the full value is in the sheet and the a11y label.
- **I_L3 — Bounded height, locale-count-independent.** The open picker occupies
  the same screen fraction at 14, 20 or 40 locales; overflow scrolls inside the
  sheet. No dimension is a function of `supportedLanguages.length`.
- **I_L4 — Query is per-open.** The search query resets on every close path,
  dismiss *and* selection, so reopening always shows the full list.
- **I_L5 — Every label carries a Latin handle.** Every `languageDisplayNames`
  entry contains its parenthesised uppercase locale code, so every locale is
  reachable by ASCII typing. Guarded structurally in
  `src/locales/__tests__/locales.test.ts`. This is a property of the language
  surface, not of `SearchableSelectSheet` (the TTS call site's labels carry no
  code suffix).
- **I_L6 — RTL by auto-flip only.** Direction comes from `flexDirection: 'row'`
  plus symmetric padding. Text alignment follows the *layout* direction, not the
  script — but **`Text` and `TextInput` need different expressions**, verified by
  forced-RTL device capture:
  RN's `textAlign` has **no `start`/`end`** — the legal values are
  `'auto' | 'left' | 'right' | 'center' | 'justify'` (`StyleSheetTypes.js`), so
  `textAlign: 'start'` is a type error. This differs from CSS *and* from RN's own
  layout props, which do offer `paddingStart` / `marginStart` / `start`. `'left'`
  is therefore how "start" is spelled for text.

  - `Text` (row label, empty state): plain `textAlign: 'left'`. RN mirrors
    `left`/`right` for `Text` under RTL (`RCTTextAttributes.mm`), so `'left'`
    resolves to the layout start in both directions. An
    `I18nManager.isRTL ? 'right' : 'left'` ternary **double-flips** and pushes
    rows to the layout *end* — the exact ragged edge this invariant forbids.
  - `TextInput` (search field): `textAlign: I18nManager.isRTL ? 'right' : 'left'`.
    `TextInput` does *not* get that mirroring, so the ternary is required here.

  `textAlign: 'auto'` is forbidden throughout — it resolves to natural
  (first-strong) alignment, so an RTL UI flips the field mid-keystroke as soon as
  a Latin code is typed, and Hebrew / Persian rows detach to the opposite edge
  from every other row in an LTR UI. No `translateX`, no absolute
  `left`/`right`, no anchor maths.
- **I_L7 — testID freeze (inherits I_S3).** `language-selector-button` and
  `language-option-<lang>` survive on the same controls; new testIDs are
  additive leaves only.
- **I_L8 — Single writer.** `uiStore.setLanguage()` remains the only writer of
  `_language` (`theming.md I6`).

---

## 4. Background Download row

`uiStore.iOSBackgroundDownloading` is force-set `true` in the UIStore ctor and is
**not** in `makePersistable.properties` — non-persisted by design. The row
renders read-reflecting the current value, bound to the existing
`uiStore.setiOSBackgroundDownloading` writer; no persisted field is added and the
ctor default is unchanged. (C)

---

## 5. Single-writer rule

| Field | Single writer (unchanged) |
| --- | --- |
| `contextInitParams.*` | `modelStore.set*` (existing) |
| `useAutoRelease` | `modelStore.updateUseAutoRelease` |
| `autoNavigatetoChat` / `colorScheme` / `displayMemUsage` / `_language` | `uiStore.set*` |
| `iOSBackgroundDownloading` | `uiStore.setiOSBackgroundDownloading` (existing) |
| `useHfToken` / token | `hfStore.setUseHfToken` / `HFTokenSheet` |
| `userTTSOverride` | `ttsStore.setUserTTSOverride` |
| search BYOK key per provider (Keychain) | `searchProviderStore.setKey/clearKey` |
| `activeProviderId` | `searchProviderStore.setActiveProvider` |
| search `resultCount` | `searchProviderStore.setResultCount` |
| `hasConsentedToSearch` | `searchProviderStore.setConsent` |

Component-local state, for completeness: `LanguageSelector` owns `sheetOpen`;
`SearchableSelectSheet` owns its search `query`. Neither is store state.

Cross-store reads: launcher and sub-screens read these fields as observers only;
no new write coupling, no multi-writer.

**Deferred cleanups** (known, out of scope of the language-picker slice):

1. The three remaining `styles.menu` Paper menus on `SettingsScreen` (key-cache,
   value-cache, search-provider) — same 170px truncation class on out-of-scope
   controls. `styles.menu` is shared by all four menus, so it stayed untouched
   when the language menu was removed.
2. English-name / ISO alias search terms so "chinese" matches `中文 (ZH)`.
3. Renaming `Português (PT_BR)` → `Português (BR)`.
4. Splitting the TTS call site's snap point if the two pickers later diverge.

---

## 6. Frozen testID set (I_S3)

These testIDs survive the restructure, on the same control:

```
Preferences sub-screen:
  context-size-input, gpu-layers-slider, device-option-*, batch-size-slider,
  ubatch-size-slider, thread-count-slider, image-max-tokens-slider,
  use-mlock-switch, use-mmap-switch, weight-repacking-switch,
  auto-offload-load-switch, auto-navigate-to-chat-switch, use-hf-token-switch
App Settings sub-screen:
  language-selector-button, language-option-*, dark-mode-switch,
  tts-availability-switch, display-memory-usage-switch, background-download-switch
Launcher rows (nav, kept reachable — I_S2):
  settings-nav-benchmark, settings-nav-app-info, settings-nav-dev-tools
```

Additive language-picker testIDs: `language-sheet` (the sheet container, waited
on by the e2e page object because the sheet animates in and out) and
`language-search` (its search field). Both are new leaves; the frozen
`language-selector-button` / `language-option-*` are unchanged (I_L7).

Additive launcher-row testIDs (`settings-nav-<row>`) name the remaining rows:
`settings-nav-preferences`, `settings-nav-app-settings`, `settings-nav-models`,
`settings-nav-my-pals`, `settings-nav-account-settings`, plus
`settings-create-account` / `settings-log-out` for the auth CTAs.

---

## 7. DS Switch off-track polish

The settings switches route through the DS `Switch`
(`src/components/ui/Switch`), which binds a mode-aware `ios_backgroundColor`
(`theme.colors.surfaceVariant`) so the off-state iOS track is visible in light
mode. See `theming.md §4k.3`. Out-of-scope screens still using Paper's `Switch`
directly are migrated in later slices.

---

## 8. Decisions

| ID | Decision | Rationale |
| --- | --- | --- |
| D1 | Preferences absorbs all model-engine + memory + loading + API + cache + export controls | Engine-adjacent; the Figma Preferences frame is the model-settings surface |
| D2 | App Settings holds Dark Mode + Background Download + Language + TTS + (iOS) Display Memory | App-level prefs; Language/TTS have no other Figma home (recorded deviation) |
| D3 | About / Send-feedback / Feedback-sent reskin the existing AboutScreen | AboutScreen already implements this exact flow |
| D5 | Auth entry points inert; registered variant dormant | No-auth scope in this slice |
| D6 | New `settings.md` flow doc; app-shell stays nav-only | Settings is now a multi-screen flow |
| D7 | Dissolve Advanced accordion into flat Preferences rows | Figma shows flat stacked containers |
| D8 | Seed omitted | No store field/control exists; net-new behaviour + persistence |

Language picker (§1.3, §10):

| ID | Decision | Rationale |
| --- | --- | --- |
| DL1 | Reuse `SearchableSelectSheet` unchanged in shape | Same problem already solved for TTS locales |
| DL2 | Keep search on at 14 items | Recovery from an unreadable locale; also deterministic e2e |
| DL3 | Fixed snap point, not item-count sizing | Height must not track locale count (I_L3) |
| DL4 | Registry order; no recents, no selected-first | Stable order for muscle memory and tests |
| DL5 | Extract a `LanguageSelector` component | Later `AppSettingsScreen` move stays verbatim |
| DL6 | Filter on label only; no English-name aliases | The `(CODE)` suffix already gives every locale a Latin handle |
| DL7 | Not a Figma parity slice | Canonical file specifies no picker component |
| DL8 | Fix query-reset + empty state in the shared component | Both are load-bearing invariants here |

Rejected: capping the Paper `Menu` (anchored popup width stays layout-fragile,
and `Menu` is on the `theming.md §4g` final-state blocklist); a sheet without
search (leaves a user stranded in an unreadable locale scrolling, and leaves
virtualized rows untappable in e2e); the DS `Dropdown` (wraps Paper `Menu`
directly per `theming.md D25`, so it inherits the exact defect).

---

## 9. Internet Search section

A net-new feature surface (not part of the reskin relocation slice). On the
current branch the launcher / sub-screen split does **not** exist — only the
monolithic `src/screens/SettingsScreen/SettingsScreen.tsx`. The section is a new
`Card` rendered **after** the App Settings card (`l10n.settings.appSettings`)
and **before** the API Settings card (`l10n.settings.apiSettingsTitle`). It
carries:

- **Provider picker** — Brave (default), Tavily, Exa; Parallel is listed but
  gated (not selectable as the active provider until its free-tier/PAYG terms
  are confirmed). Active provider written by
  `searchProviderStore.setActiveProvider`.
- **Per-provider BYOK key entry** — `SearchProviderKeySheet` writes/clears the
  active provider's key to Keychain via `searchProviderStore.setKey/clearKey`,
  one entry per provider under service `'search_provider_service_<id>'`. Keys
  never reach plain storage or the bundle.
- **Result-count control** — slider (1–8, default 5) →
  `searchProviderStore.setResultCount`; maps to the search budget `maxResults`.
- **First-enable consent** — a disclosure that the query leaves the device to
  the chosen provider, and that a `read_url` page read may instead be sent to a
  default reader service (`r.jina.ai`) when the selected provider has no native
  reader. Gates key entry until accepted (`searchProviderStore.setConsent` →
  `hasConsentedToSearch`). Consent is **reversible**: once given, the card shows
  a consent-given row with a **Revoke** affordance (`setConsent(false)`), which
  re-shows the disclosure on next enable.
- **Consent is load-bearing at execution** — the engines short-circuit with an
  error result unless `hasConsentedToSearch === true` AND the active provider has
  a key (`searchProviderStore.canSearch`), not just in the Settings UI.

Non-secret prefs (`activeProviderId`, `resultCount`, `hasConsentedToSearch`)
persist via `makePersistable`/AsyncStorage; BYOK keys persist only in Keychain.
New testIDs are additive (`internet-search-card`, `internet-search-consent*`,
`internet-search-consent-given`, `internet-search-consent-revoke`,
`search-provider-selector-button`, `search-provider-option-*`,
`search-provider-key-button`, `search-result-count-slider`,
`search-provider-key-*`) — no frozen testID is touched (I_S3 intact). The talent
side of this feature (the `web_search` / `read_url` engines, the provider
adapters, and the `searchBudget` util) lives in `pals-and-talents.md`.

**Location**: the section lives in the App Settings sub-screen, below Display
Memory Usage, as an app-level pref. It was relocated there verbatim from the
monolithic `SettingsScreen` card in the second `main` → `redesign/phase-3`
reconcile — same store, same writers, same testIDs, no behaviour change (I_S1).
The Paper `Card` wrapper became a `styles.group` block to match the sub-screen's
grouping, and the section's own rows became `styles.row`; nothing else changed.

---

## 10. Language picker

`LanguageSelector` (`src/components/LanguageSelector/`) renders a trigger
(`language-selector-button`, showing `languageDisplayNames[uiStore.language]`
plus a chevron, content-sized) and the shared `SearchableSelectSheet`
(`language-sheet`, `language-search`, rows `language-option-<lang>`). It owns
only `sheetOpen`; options are derived, not stored:
`uiStore.supportedLanguages.map(l => ({value: l, label: languageDisplayNames[l]}))`
in registry order. Selection calls `uiStore.setLanguage` and closes the sheet.
(C)

Behaviour: the sheet opens at a fixed snap point with the search field **not**
autofocused; typing filters rows case-insensitively on the label, so the
parenthesised locale code is a Latin handle for every locale; a query that
matches nothing renders an empty-state row and the sheet stays open; the query
resets on every close path. Display-name strings are unchanged — the layout does
not depend on shortening them. (C)

Shared-component scope: `SearchableSelectSheet` also backs the TTS Supertonic
language picker (`tts-hero-language-picker`), so the query-reset and empty-state
behaviour above applies there too. It renders nothing language-specific — its
empty-state copy comes from `common`, never from `settings`. (C)

RTL is not e2e-reachable (the app never calls `I18nManager.forceRTL`), so I_L6
is verified by an RTL capture with a Latin query typed into the search field,
via simulator launch args. (C)

e2e contract: `language-selector-button` / `language-option-<lang>` are frozen,
so `e2e/specs/features/language.spec.ts` is unchanged. The page object changes
internals only — `openLanguageMenu()` waits for `language-sheet` to be displayed
(the sheet animates in, where the popup was synchronous), and `selectLanguage()`
types the language code into `language-search` before tapping the row
(`BottomSheetFlatList` virtualizes; an unrendered row is not tappable) and then
waits for `language-sheet` to disappear before returning. (C)
