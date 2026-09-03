# Settings flow (launcher + sub-screens)

**Purpose**: cumulative architecture truth for the **Settings** bottom-tab root
(`SettingsScreen`) and its pushed sub-screens. This doc owns the Settings
information architecture, the per-control single-writer table, the testID freeze
contract, and the full Settings pushed-route enumeration. The bottom-tab shell
and root-Stack topology live in `app-shell.md`; DS components and token rules
live in `theming.md`; About-screen feedback wiring is unchanged.

Status: **Launcher root + Preferences / App Settings sub-screens shipped
(reskin only, no behaviour change).** **Account / auth is live**: the launcher
reads the real session, and three pushed account routes ship (Log in, Create
Account, Account Settings). Password management, Apple sign-in, and account
deletion remain unbuilt and are enumerated in §11.

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
5. **Log in** (`AccountLoginScreen`, `ROUTES.ACCOUNT_LOGIN = 'Log in'`): serif
   headline · Email + Password (reveal toggle) · `Forgot password?` · submit ·
   or-divider · Continue with Google · link to Create account · legal footer.
   Renders no Apple button, no email-existence router, no set-new-password, and
   no drawn ✕ (§11). (C)
6. **Create Account** (`AccountSignUpScreen`,
   `ROUTES.ACCOUNT_SIGN_UP = 'Create Account'`): serif headline · Your name +
   Email + Password · submit · or-divider · Continue with Google · link to Log
   in · legal footer, plus the in-place verification body that replaces the form
   when sign-up yields no session. No username field here — `updateProfile`
   needs a session sign-up may not produce. (C)
7. **Account Settings** (`AccountScreen`, `ROUTES.ACCOUNT = 'Account Settings'`,
   signed-in only): identity line · Your Username · Save Changes. No password
   controls, no Delete Account, no Log out (that stays on the launcher). (C)

Reset Password is **not** a route: a sheet over item 5 whose body swaps to a
"check your email" confirmation on success. (D)

**Launcher account surface.** The registered / not-registered row sets are
unchanged; only what the existing controls do changed, plus one addition:

- Registered header: `displayName` = `profile.full_name ?? profile.username ??
  user.user_metadata?.full_name ?? user.email?.split('@')[0]`, falling back to
  `settings.launcher.welcomeNoName` (no interpolation) when every source is
  absent. "Member since" reads `new Date(user.created_at).getFullYear()` and the
  row is omitted when `created_at` is absent or unparseable. (C)
- `settings-create-account` navigates to item 6; a new `settings-log-in` link
  below it navigates to item 5; the Account Settings row targets item 7 when
  signed in and item 5 when signed out; `settings-log-out` calls
  `authService.signOut()` with no confirmation dialog. (C)
- **The email is read from `user`, never `profile`** — `loadUserProfile` selects
  only `id, username, full_name, avatar_url`, so `profile.email` is structurally
  undefined at runtime (I_A8). (C)

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
- The three account routes (§1.5–7) are siblings of `PREFERENCES` /
  `APP_SETTINGS` on the root Stack, full-bleed, tab bar hidden. (C)
- **Items 5–6 pin `options={{title: ''}}`.** Omitting `title` is *not*
  equivalent: React Navigation falls back to the route name and paints hardcoded
  English (`'Log in'`) under every locale, because `RootStack.tsx` sets no
  default `headerTitle`. Item 7 uses `l10n.screenTitles.accountSettings`.
  `RootStack.test.tsx` pins all three, and the assertion fails with
  `Received: undefined` if the option is dropped. (D_A3)
- Cross-navigation between items 5 and 6 uses `navigation.replace`, so at most
  one account-auth route is ever on the stack. (D_A14)
- Success dismissal is one rule: `popToTop()` — lands on `MainTabs` with
  `SettingsTab` still focused. (C)
- **The session guard is symmetric and state-independent**
  (`useAccountSessionGuard`): items 5–6 pop on `isAuthenticated === true` from
  any state, item 7 pops on `isAuthenticated === false` from any state.
  `checkExistingSession` resolves asynchronously after mount, so without the
  forward direction a tap during restore lands a signed-in user on a sign-up
  form whose submit would run `signUpWithEmail` against a live session. The hook
  reads the flag during render, so **every caller must be an `observer`** or the
  guard is silently dead. No deep link targets these routes. (C)

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
- **I_S6 — Auth deferred cleanly.** ~~The launcher renders auth entry points as
  inert/styled-only.~~ **SUPERSEDED** by I_A1–I_A9 below: auth is wired, the
  entry points are live, and `IS_REGISTERED` is deleted.

**Account / auth (I_A\*)** — the launcher's account surface and §1.5–7:

- **I_A1 — `AuthService` is shared and not forked.** No method added, renamed,
  or re-signatured; no second auth service, store, or singleton. The seven real
  methods are `signInWithGoogle`, `signInWithEmail`, `signUpWithEmail`,
  `signOut`, `resetPassword`, `updateProfile`, `clearError`.
- **I_A2 — `AuthSheet` is untouched and stays the checkout path.**
  `ExploreScreen.tsx` remains its only mount; Settings never mounts it, and it
  never navigates.
- **I_A3 — frozen testIDs survive (inherits I_S3).** `email-input`,
  `password-input`, `auth-submit-button`, `full-name-input` stay on `AuthSheet`'s
  controls (`e2e/pages/PalPurchasePage.ts` resolves them). The account screens
  use a disjoint `account-*` namespace (§6).
- **I_A4 — no dead controls.** Every rendered control is pressable and reaches a
  real method; nothing is `disabled` to stand in for unbuilt capability. Unbuilt
  affordances are omitted and listed in §11.
- **I_A5 — tokens-only (inherits I_S5).** All visual values from `theme.*`.
  `screens/AccountScreens` is on the `theme.typography|radius|stroke` allow-list
  in `src/theme/tokens/__tests__/invariants.test.ts`; that list may not be
  relaxed without a matching note here, and this entry is that note.
- **I_A6 — every screen-owned string is localized**, route titles included:
  no literal English in the account TSX, keys under `settings.account.*`. Sole
  exception: service-owned `error` text (I_A9's note below).
- **I_A7 — no new persisted field or store.** `makePersistable(['profile'])`
  unchanged; Supabase still owns the session.
- **I_A8 — the email is read from `user`, never `profile`** (§1). Reading
  `profile.email` renders an empty string.
- **I_A9 — no test may assert through phantom mock capability.**
  `__mocks__/services/palshub/AuthService.js` is a `makeAutoObservable` object
  carrying the six real fields, the `authState` getter, and exactly the seven
  real methods with real return shapes (`boolean` ×3, `undefined` ×3, sync
  `clearError`); the methods are annotated `false` so they stay raw `jest.fn()`s.
  Making it observable is what lets a suite flip `isAuthenticated` **after mount**
  and see the launcher re-render, instead of unmounting and re-rendering.

**Error handling is a screen-local snapshot, never a live binding.**
`onAuthStateChange` nulls `authService.error` on *every* auth event,
`TOKEN_REFRESHED` and `INITIAL_SESSION` included, so a live binding can blank a
displayed error with no user action and an `error === null` read can be a false
success. Each screen snapshots `authService.error` into local state at the
transition, after the await. `signInWithGoogle` returns `void`, so its only
observable outcome is that snapshot — the post-await `isAuthenticated` is **not**
a success test, because `onAuthStateChange` fires independently of the awaited
call. `error` text is service-owned raw English; localizing it needs a taxonomy
`AuthService` does not expose (§11). (D_A15)

**`submitting` is screen-local, never `authService.isLoading`** — the flag is
singleton-wide, so a checkout sign-in would move it. (D_A10)

**Submit is enabled with empty fields; validation explains the refusal.** An
earlier reading disabled submit until every required field was non-empty, which
made `validation.{emailRequired, passwordRequired, nameRequired}` unreachable
from the UI — the strings ship to 13 locales but nothing could fire them — and
left an invisible control in dark mode. Pressing submit with an empty field now
runs local validation, makes no request, and renders the message in the error
slot. This is I_A4's first clause ("every rendered control is pressable") and the
same doctrine §11's 9a note states: the failure is explained, not hidden. The
only `disabled` state left on a submit is `submitting`. (D_A18)

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
| `authService.user` / `session` / `isAuthenticated` | `initAuthListener` + `checkExistingSession` (Supabase-driven) |
| `authService.profile` | `loadUserProfile` |
| `profiles.username` | `authService.updateProfile` — sole call site is Account Settings' Save Changes |
| `profiles.full_name` (at creation) | `signUpWithEmail` via `options.data.full_name` |
| `authService.error` | `AuthService` methods **and** `onAuthStateChange`, which nulls it on every auth event; screens never write it and never render it live (§3) |
| `authService.isLoading` | `AuthService` methods; no screen reads it as its busy state |
| account screen `submitting`, error snapshot, field values, reset-sheet open + email draft | the owning screen's local `useState` — not store state |

Component-local state, for completeness: `LanguageSelector` owns `sheetOpen`;
`SearchableSelectSheet` owns its search `query`. Neither is store state.

`updateProfile` had **zero call sites** before this slice, so Account Settings'
Save Changes is its first exercise. It returns `void` and its read-back fails
silently three ways — `loadUserProfile` returns early on a Supabase error, on a
throw, and nulls `profile` on `PGRST116` — so the save has **three** outcomes,
not two: snapshot non-null ⇒ error; snapshot null **and**
`profile?.username === submitted` ⇒ saved; snapshot null **and** mismatch ⇒
**saved-unconfirmed** ("the write landed, only the read-back failed"). Collapsing
saved-unconfirmed into error would report a landed write as a failure and leave
an empty error slot, breaching I_A4. (D_A16)

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

Additive account testIDs — a disjoint namespace from `AuthSheet`'s frozen four
(I_A3), so global testID uniqueness holds and the purchase e2e stays green:

```
launcher   settings-log-in
Log in     account-login-{screen,email,password,password-toggle,submit,forgot,google,error,signup-link}
Sign up    account-signup-{screen,name,email,password,password-toggle,submit,google,error,login-link,verify,verify-done,verify-login-link}
Reset      account-reset-{sheet,email,submit,error,sent,done}
Account    account-details-{screen,identity,username,save,error}
```

Account Settings' saved / saved-unconfirmed confirmation carries **no** testID —
it is asserted by its localized copy. If e2e later needs to reach it, add
`account-details-status` as a new additive leaf.

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
| D5 | ~~Auth entry points inert; registered variant dormant~~ **SUPERSEDED by D_A1–D_A17** | No-auth scope in that slice |
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

Account / auth (§1.5–7, §11):

| ID | Decision | Rationale |
| --- | --- | --- |
| D_A1 | Separate Log in and Create account entries, not the drawn email-first router | No email-existence check exists; Supabase declines to expose one |
| D_A2 | Full-screen pushed routes, not sheets | Design draws full-screen; keyboard-in-sheet is a known trap |
| D_A3 | Back chevron with `title: ''` on items 5–6 | An omitted title falls back to the English route name |
| D_A4 | Reset password stays a sheet over Log in | Drawn as a sheet; no route earns a single field |
| D_A5 | Verification is an in-screen terminal state, not a route | Its only unique affordance, resend, is unbuildable |
| D_A6 | Apple buttons omitted, not rendered disabled | Dead controls are the defect this slice removes (I_A4) |
| D_A7 | Sign-up collects a name; username lives on Account Settings | `updateProfile` needs a session sign-up may not yield |
| D_A8 | Account Settings row targets Log in when signed out | Row must be live; login is its only signed-out meaning |
| D_A9 | New secondary `settings-log-in` link on the CTA card | Splitting the router needs a second entry point |
| D_A10 | Screen-local `submitting`, not `authService.isLoading` | The flag is singleton-wide; checkout auth would move it |
| D_A11 | Log out signs out directly, no confirmation dialog | Design draws a plain button; sign-out is recoverable |
| D_A12 | Legal URLs extracted to `src/utils/legalUrls.ts` | They were inline literals in `AboutScreen`; reuse without extraction duplicates |
| D_A13 | Namespaced `account-*` testIDs, not `AuthSheet`'s | Global testID uniqueness; purchase e2e must stay green |
| D_A14 | Log in ⇄ Create account cross-link uses `replace` | Prevents an unbounded account-auth stack |
| D_A15 | Render `error` from a screen-local snapshot | The auth listener nulls the live field unprompted |
| D_A16 | Save read-back mismatch is `saved-unconfirmed`, not `error` | The write landed; only the confirming read failed |
| D_A18 | Submit stays pressable with empty fields; local validation refuses and explains | Disabling it made the required-field strings unreachable and the control invisible in dark mode |
| D_A17 | The reset sheet uses the legacy `src/components/Sheet`, **not** the DS `src/components/ui/Sheet` | Only the legacy one supplies `Sheet.TextInput`, a keyboard-aware `Sheet.ScrollView`, a backdrop, and `accessible={false}` for Appium child access on iOS; the DS sheet has none of those and zero call sites. `showCloseButton={false}` is passed explicitly (its default is `true`) — the sheet dismisses via its own Done or the backdrop. That component's hardcoded `accessibilityLabel="Close"` is pre-existing and out of scope |

Rejected (account): reusing `AuthSheet` from Settings — one sheet, no mode prop,
checkout-frozen (I_A2); the drawn email-first `Get Started` router — Supabase
declines account enumeration by design.

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

---

## 11. Account / auth — deviation register

The design draws a larger account surface than this slice ships. Two lists, so a
later slice does not re-derive them. **`10c`** = follow-up account slice;
**`designer`** = needs a design decision before it can be built.

### 11a. Drawn but not built

| # | Drawn element | Reason not built | Owner |
| --- | --- | --- | --- |
| 1 | Email-first entry modal / `Get Started` router | Needs an email-existence check Supabase declines as a user-enumeration vector. It also offered one-tap Google straight from the launcher, which the split into routes costs for an unrelated reason and could be restored independently | designer |
| 2 | Continue with Apple (entry, Log in, Create account) | No method, no native dependency; omitted rather than disabled (I_A4) | 10c |
| 3 | Account Settings — Apple variant | Follows row 2 | 10c |
| 4 | Set new password, in-app | `resetPassword` redirects to `${APP_URL}/auth/reset-password` on the **web**; `detectSessionInUrl:false` and `DeepLinkStore` has no auth handling, so the link cannot re-enter the app | 10c |
| 5 | Password-updated confirmation | Terminal state of row 4 | 10c |
| 6–7 | "Resend link" on Verify your account / Check your email | No resend method on `AuthService` | 10c |
| 8 | Check Your email as a full-screen route | Rendered instead as the reset sheet's success body (D_A4); without resend it has no unique affordance | designer |
| 9 | Delete Account | No method; the only `deleteAccount` in the tree was a mock, now removed (I_A9) | 10c |
| 10 | Create password / Change password on Account Settings | `supabase.auth.updateUser` is never called anywhere in the app | 10c |
| 11 | "Your username" on Create Account | Unwritable pre-confirmation (`updateProfile` requires a session); replaced by "Your name" → `full_name`, username edits move to Account Settings | designer |
| 12 | Mailbox illustration (verify / reset / Account Settings) | No such asset; the existing illustrations are hand-authored TSX. Needs an SVG export | designer |
| 13 | Google cancel shown as its own state | `signInWithGoogle` ignores the `userInfo.type` discriminant, and google-signin v16 **returns** `{type:'cancelled'}` rather than throwing, so cancel surfaces as `'No ID token received from Google'` and the `'Sign-in was cancelled'` branch is unreachable dead code. Distinguishing cancel needs an `AuthService` change I_A1 forbids | 10c |
| 14 | Localized auth error text | `error` is raw Supabase/Google English; localizing needs a taxonomy the service does not expose | 10c |
| 15 | ✕ top-right dismiss on Log in / Create account | Replaced by the Stack back chevron (D_A3); a bespoke ✕ needs `headerShown:false` and breaks the pushed-route pattern | designer |

### 11b. Built but not drawn — each needs a designer pass

| # | Addition | Why it exists |
| --- | --- | --- |
| 16 | Email field on Log in | The design draws password only; the router that collected the email is gone (11a.1) |
| 17 | Log in ⇄ Create account cross-links | Two entry points need to reach each other; the drawn flow had one |
| 18 | Legal footer on Log in | Drawn only on Create Account and the entry modal, but Log in can now create a session directly via Google |
| 19 | `settings-log-in` link on the CTA card | The launcher's only signed-out path was the router (D_A9) |
| 20 | Log in subtitle | The drawn subtitle ("Enter the password used for the account sam@gmail.com") has no source once the email is typed on that same screen. **No key ships and no subtitle renders** — `en.json` is the Weblate template, so a placeholder would enter the 13-language queue for copy that may never exist. Still open |
| 22 | Underlined inputs with an external label, not Figma's filled rounded rects with the label inside | The treatment belongs to the DS `Input` (`src/components/ui/Input`), which draws a bottom divider and an external label. Changing it is a DS visual change, which `theming.md` I_UI5 forbids from riding a Phase-3 screen slice. **Applies to every field on every account screen** (Log in, Create account, Account Settings, reset sheet). Needs a designer + DS decision: restyle the DS Input for everyone, or add a variant |
| 23 | The label is rendered by the call site (`LabeledInput`), not by the DS `Input`'s `label` prop | The DS label sets no `textAlign`, so it resolves to first-strong alignment and stays hard-left under RTL while the mirrored value sits right — a split label/value row, seen in the forced-RTL capture. Rendering the label at the call site with `textAlign: 'left'` (I_L6) is the call-site fix; folding it back into the DS is the DS-side fix |
| 24 | A disabled submit is repainted at the call site (`styles.submitDisabled` → `surfaceVariant`) | The DS Button's disabled fill is `surfaceContainerLow` = 8% of the surface, which over the `#000000` dark canvas is invisible: only the dim label showed. Repainted at the call site because I_UI5 forbids the DS change here. The DS Button's disabled fill is the real defect and should be raised alongside its dead `loading` prop |
| 21 | `account-signup-verify-login-link` on the verification state | An already-registered email lands in verification-pending (Supabase returns success with an obfuscated user — the same anti-enumeration behaviour as an unknown reset address), so that user must be able to leave |

### 11b-i. Copy differences from the drawn screens — l10n-owned, not defects

Registered so they are not rediscovered as bugs. Each is a wording choice, and
each is one `en.json` edit if a designer wants the drawn string instead:

| Drawn | Shipped | Note |
| --- | --- | --- |
| Create Account submit: "Verify Account" | `signUp.submit` = "Create Account" | The drawn label describes the *next* screen's outcome, and sign-up does not always land in verification (§9b). Deliberate |
| "Password" | `login.passwordLabel` / `signUp.passwordLabel` = "Your Password" | Matches the drawn "Your Email" / "Your username" possessive pattern |
| "By continuing you agree on our **Terms & Privacy**" | `legal.prefix` = "By continuing you agree to our" + `about.termsOfService` · `about.privacyPolicy` | §11's key plan budgets only `legal.prefix` and reuses the two existing `about.*` link labels; the `·` separator matches `AboutScreen`'s existing legal row |
| Create Account subtitle: "Finish setting up the account for sam@gmail.com" | `signUp.subtitle` = "Set up an account to get the most out of PocketPal." | The drawn subtitle interpolates an email collected by the deleted router (11a.1); there is no such value on this screen |
| Log in subtitle | **none** | 11b.20 — no key ships |

Also for 10c: `accountSettingsSubtitle` still reads "Email, Password" though this
slice ships no password management (left verbatim, I_S1); `AuthSheet`'s
hardcoded English and its five `Alert.alert` sites stay untouched (I_A2); the
`palsScreen.*` keys orphaned by the `CompactAuthBar` / `ProfileSheet` deletions
stay orphaned; and the DS `Button` declares `loading?: boolean` and never
renders it — a dead prop, raise against `theming.md` (a DS fix cannot ride a
Phase-3 screen commit).

### 11c. Cross-doc follow-ups

- **`app-shell.md §4a.4`** — the pushed-destination list needs
  `ROUTES.ACCOUNT_LOGIN`, `ROUTES.ACCOUNT_SIGN_UP`, `ROUTES.ACCOUNT` added. Not
  absorbed here: that list is app-shell's to own.
- **A `testID` on a nested `Text` does not reach the native tree.** The
  prompt/link phrases are one paragraph so bidi orders them (11b rows above);
  the link was first written as a nested pressable `<Text testID=...>`, and the
  XCUITest tree showed the identifier gone — nested `Text` nodes are
  attributed-string ranges in one native text view, and RN synthesizes their
  a11y children from those ranges with label/role/actions only, never `testID`.
  The paragraph now carries the `testID`, the press handler, and
  `accessibilityRole="button"` + `accessibilityLabel` (the link text); the child
  keeps only its colour. Both properties are needed and they trade off, so each
  has its own test: a phrase-composition assertion for the RTL ordering, and
  `isNestedInText(...) === false` (`jest/test-utils.tsx`) for the native
  precondition. **Jest cannot see the native identifier at all** — RNTL walks the
  React tree — so the second test asserts the structural rule, not the platform
  outcome; only a device/simulator capture confirms resolution.
- **Jest trap worth knowing** (found while writing these suites): after an
  awaited state update, RNTL can find the freshly rendered element while React
  has not yet flushed through `act()`, and a `fireEvent.press` on it is silently
  dropped. Wait on the *rendered* element (`waitFor(() => getByTestId(...))`)
  rather than on the mock call before pressing.
