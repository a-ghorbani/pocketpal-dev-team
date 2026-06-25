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
   - Speculative decoding (global engine knobs: master toggle + draft K/V
     cache-type menus gated on flash-attn compatibility) is a control group in
     the same model-engine surface. It currently lives in the live monolithic
     `SettingsScreen.tsx` Advanced accordion (the `PreferencesScreen` split is
     redesign-track, not yet on main); folds into this surface on that cutover.
     Contract in `model-loading.md`. (C)
3. **App Settings sub-screen** (`AppSettingsScreen`, pushed route): Dark Mode,
   Background Download, Language, TTS availability, and (iOS-only) Display
   Memory Usage. (D)
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

Cross-store reads: launcher and sub-screens read these fields as observers only;
no new write coupling, no multi-writer.

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

---

## 9. Internet Search section

A net-new feature surface (not part of the reskin relocation slice). On the
current branch the launcher / sub-screen split does **not** exist — only the
monolithic `src/screens/SettingsScreen/SettingsScreen.tsx`. The section is a new
`Card` rendered **after** the App Settings card (`l10n.settings.appSettings`)
and **before** the API Settings card (`l10n.settings.apiSettingsTitle`). It
carries:

- **Provider picker** — Tavily (default), Brave, Exa; Parallel is listed but
  gated (not selectable as the active provider until its free-tier/PAYG terms
  are confirmed). Active provider written by
  `searchProviderStore.setActiveProvider`.
- **Per-provider BYOK key entry** — `SearchProviderKeySheet` writes/clears the
  active provider's key to Keychain via `searchProviderStore.setKey/clearKey`,
  one entry per provider under service `'search_provider_service_<id>'`. Keys
  never reach plain storage or the bundle.
- **Result-count control** — slider (1–8, default 3) →
  `searchProviderStore.setResultCount`; maps to the search budget `maxResults`.
- **First-enable consent** — a disclosure that queries (and `read_url` targets)
  leave the device to the chosen provider; gates key entry until accepted
  (`searchProviderStore.setConsent` → `hasConsentedToSearch`).

Non-secret prefs (`activeProviderId`, `resultCount`, `hasConsentedToSearch`)
persist via `makePersistable`/AsyncStorage; BYOK keys persist only in Keychain.
New testIDs are additive (`internet-search-card`, `internet-search-consent*`,
`search-provider-selector-button`, `search-provider-option-*`,
`search-provider-key-button`, `search-result-count-slider`,
`search-provider-key-*`) — no frozen testID is touched (I_S3 intact). The talent
side of this feature (the `web_search` / `read_url` engines, the provider
adapters, and the `searchBudget` util) lives in `pals-and-talents.md`.

**Relocation note**: when the reskin cutover lands (launcher +
`AppSettingsScreen`), this section moves verbatim into the App Settings
sub-screen as an app-level pref — same store, same writers, same testIDs, no
behaviour change (I_S1).
