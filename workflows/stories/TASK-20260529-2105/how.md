# Implementation Plan: US iOS PalsHub authenticated in-app checkout

Executable worklist for `what.md` + `context/architecture/palshub-checkout.md`. Section
refs (§N, In, Dn, scenario X) point at those two docs — design is not re-derived here.

---

## Metadata

- **Task ID**: TASK-20260529-2105
- **Worktree**: `./worktrees/TASK-20260529-2105`
- **Branch**: `feature/TASK-20260529-2105`
- **Native Changes**: YES
- **Visual Confirmation**: YES
- **Intent Brief**: `./workflows/stories/TASK-20260529-2105/intent-brief.md`
- **WHAT**: `./workflows/stories/TASK-20260529-2105/what.md`
- **Architecture doc(s)**: `./context/architecture/palshub-checkout.md`
- **Status**: implemented

---

## Progress

| Step | Status | Commit | Notes |
| --- | --- | --- | --- |
| Step 1 (dep) | DONE | eb8e92c | react-native-inappbrowser-reborn@3.7.1 (SFSafariVC); New-Arch build + isAvailable() probe verified |
| Step 2 (API) | DONE | 0ed1d98 | createCheckoutSession; status via apiRequest details.status (400→already_owned) |
| Step 3 (store) | DONE | e9e92ad | CheckoutFlowStore (state, onReturn, reset) |
| Step 4 (browser open) | DONE | e9e92ad | start() + InAppBrowser.open; 400→owned |
| Step 5 (reconcile) | DONE | e9e92ad | bounded poll, epoch-abort, exhaustion→processing_deferred |
| Step 6 (sheet UI) | DONE | 011fbc4 | Platform branch + feedback + onSignInPress (6a/6b) |
| Step 7 (deep-link route) | DONE | ae8c536 | path-based /app-return/* |
| Step 8 (iOS native) | DONE | 93f5fe4 | applinks entitlement + continueUserActivity |
| Step 9 (l10n) | DONE | 011fbc4 | new copy keys in en.json |
| Step 10 (tests) | DONE | ed86feb, 011fbc4 | API + store + sheet + deep-link routing |
| Architecture doc updated | DONE | c23c4c5 (dev-team) | promote (P)→(C) in palshub-checkout.md |
| Native verification | DONE | - | pod install (New Arch) + iOS Release + Android Release all SUCCEEDED |

---

## Key location decision (round-2 SUGGESTION 2)

The buy-flow state owner is an **app-global MobX store** (`CheckoutFlowStore`), not
local `PalDetailSheet` state. Rationale grounded in code:
- `PalDetailSheet` is conditionally mounted (`{selectedPal && ...}`,
  `PalsScreen.tsx:452-461`) and is unmounted on dismiss; on **cold launch** via the
  return URL the sheet is not mounted at all (§9h).
- The deep-link return — warm AND cold (`DeepLinkModule.getInitialURL`,
  `DeepLinkService.ts:93-110`) — is delivered through `useDeepLinking`, mounted
  app-globally in `App.tsx:56-57,88` (`DeepLinkHandler`), **not** inside the sheet.
So the store (lifetime = app process) owns `CheckoutFlowState`; `useDeepLinking`
writes return events into it; `PalDetailSheet` reads it as a MobX observer. This
mirrors the existing `DeepLinkStore` pattern (`store/DeepLinkStore.ts`).

---

## Affected files

| Path | Change | Design ref |
| --- | --- | --- |
| `package.json`, `yarn.lock`, `ios/Podfile.lock` | add chosen SFSafariVC pod (Step 1 verifies under New Arch) | §4d / §5c |
| `src/services/palshub/PalsHubApiService.ts` | add `createCheckoutSession` + types | §1b, §3 status map |
| `src/services/palshub/PalsHubService.ts` | re-export `createCheckoutSession` | §5b |
| `src/store/CheckoutFlowStore.ts` | new — state owner + reconcile poll | §1 (CheckoutFlowState), §3, §4 |
| `src/store/index.ts` | export new store | - |
| `src/components/PalsHub/PalDetailSheet/PalDetailSheet.tsx` | `Platform` import + branch + state feedback + `onSignInPress` prop | §2, §4a, §4c |
| `src/screens/PalsScreen/PalsScreen.tsx` | pass `onSignInPress={() => setShowAuth(true)}` into `PalDetailSheet` | §6.E re-auth |
| `src/hooks/useDeepLinking.ts` | path-based `/app-return/*` route → store | §4c, D4, §9h |
| `ios/PocketPal/AppDelegate.swift` | wire `continueUserActivity` → RCTOpenURLNotification | §4c, §10.1 |
| `ios/PocketPal/PocketPal.entitlements` | add `applinks:<HOST>` | §10.2, I6 |
| `src/locales/en.json` | new checkout copy keys | §3 feedback column |
| tests (per §Testable-contract) | new + updated | §6 |
| `context/architecture/palshub-checkout.md` | promote (P)→(C) same PR | non-negotiable |

---

## Steps

Each step is atomic — one logical change, one commit.

### Step 1: Select + New-Arch-verify the system in-app browser dependency (GATE)

**Implements**: §4d / §5c. The §4d *constraint* (SFSafariViewController-backed, NOT
`react-native-webview`) is fixed; the *package* is not — §4d requires HOW to confirm exact
package, version, **and maintenance status**. This step is a gate: nothing downstream may
rest on an unverified legacy pod.

**Files**: `package.json`, `yarn.lock`, `ios/Podfile.lock`

**Maintenance status (recorded, §4d)**: candidate `react-native-inappbrowser-reborn@3.7.1`
is **stalled/legacy-arch** — `3.7.1` is a thin registry republish (2026-03-16) of real
release `3.7.0` (2022-07-30); `peerDependencies` is only `react-native: ">=0.56"` with **no
New-Arch declaration**, so build/run under this worktree's RN 0.82.1 New Architecture
(`newArchEnabled=true`, `RCT_NEW_ARCH_ENABLED=1`) is **unconfirmed** and must be proven.

**Approach** (≤5 lines):
1. `yarn add react-native-inappbrowser-reborn@3.7.1`; `cd ios && RCT_NEW_ARCH_ENABLED=1 pod install`
   (confirm `RNInAppBrowser` in `Podfile.lock`); add a **throwaway** call site logging
   `InAppBrowser.isAvailable()`; run a New-Arch `yarn ios --configuration Release`. Build +
   module-resolution under New Arch is the real check; revert the call site after.
2. **Decision**: builds AND `isAvailable()` resolves → keep, record "verified under RN 0.82
   New Arch". Fails to build / module unresolved → drop it, pick a maintained
   SFSafariVC-backed alternative satisfying §4d, re-run (1):
   (a) **thin custom SFSafariViewController TurboModule** (preferred) — ~1 Swift file over
   `RCTPresentedViewController()`, New-Arch-native spec, no 3rd-party runtime;
   (b) `expo-web-browser` (rejected unless (a) infeasible) — maintained + §4d-compliant, but
   repo has **zero Expo**, so it drags in `expo-modules-core`/Expo autolinking for one call.
   Record the rationale for whatever ships; that package feeds Step 4 + Step 11 §5c.

**Verification**: New-Arch `yarn ios --configuration Release` succeeds with the trivial call
site present (this IS the gate); `git diff ios/Podfile.lock` shows the chosen pod;
`npx tsc --noEmit`. Record chosen package + maintenance status in the commit message.

---

### Step 2: Add `createCheckoutSession` to PalsHubApiService

**Implements**: §1b (request/response), §3 status mapping table, I3 (Bearer reuse), D2/D7.

**Files**: `src/services/palshub/PalsHubApiService.ts`

**Approach** (≤5 lines): Add `CheckoutSessionRequest`/`CheckoutSession` types matching
§1b. Add `async createCheckoutSession(palId, {successUrl, cancelUrl, selectedCountryCode?})`:
POST `/api/mobile/purchases` reusing `getAuthHeaders` (`:142-154`, do **not** mint a
token — I3). Build body with `selected_country_code` only when `selectedCountryCode?.length === 2`
(D3 — caller passes it; omit otherwise). Do NOT route through `apiRequest` (it throws on
!ok and loses status); fetch directly so the **status code** can be mapped: 200→return
parsed `CheckoutSession`; 400→throw `PalsHubError('already_owned', {status:400})`; 401/404/500
→throw `PalsHubError` carrying `{status}`; fetch-throw→`PalsHubError` carrying
`{status:'network'}`. Caller (Step 4) interprets status, per §3.

**Verification**: `yarn test --findRelatedTests src/services/palshub/PalsHubApiService.ts`
(after Step 10a); `npx tsc --noEmit`.

---

### Step 3: Add `CheckoutFlowStore` (app-global state owner)

**Implements**: §1 CheckoutFlowState, §3 state machine, I7 (single in-flight), §1 single-writer.

**Files**: `src/store/CheckoutFlowStore.ts` (new), `src/store/index.ts`

**Approach** (≤5 lines): MobX store mirroring `DeepLinkStore`. Holds `status`, `palId`,
`purchaseId?`, `errorKind?` (§1 shape). Actions: `begin(palId)` (idle→creating; no-op if
already creating/finalizing — I7/9g), `setCreating/setBrowserOpen/setOwned/setError(kind)/
setCancelled/setProcessingDeferred`, and `reset()` (any→idle on dismiss). Add
`onReturn(palId, kind:'success'|'cancel')`: ignore if `palId !== this.palId` or no active
flow (I7/9f); success→start reconcile (Step 5); cancel→`setCancelled` (I5). This store is the
**sole writer** of CheckoutFlowState (§ single-writer); ownership is never written here (I8).

**Verification**: `yarn test --findRelatedTests src/store/CheckoutFlowStore.ts` (after Step 10b);
`npx tsc --noEmit`.

---

### Step 4: Wire create-session + open SFSafariViewController

**Implements**: §2 event flow, §3 (creating→browser_open / 400→owned / errors), §4a.2-4, scenarios A/D/E.

**Files**: `src/store/CheckoutFlowStore.ts`

**Approach** (≤5 lines): Add `async start(palId)` on the store: guard I7; `setCreating`;
compute `successUrl`/`cancelUrl` as `https://${RETURN_HOST}/app-return/{success,cancel}`
(RETURN_HOST = the one deferred placeholder, see Step 8/D6); read
`getStorefrontCountryCode()` and pass through (the API method applies the alpha-2 D3 gate).
Call `palsHubApiService.createCheckoutSession`. On success: `setBrowserOpen`, open
`checkout_url` via the system-browser open call chosen in Step 1 (SFSafariVC — I2/§4d). On `PalsHubError`: map
`details.status` → 400 `setOwned` (D2, no browser); 401 `setError('401')`; 404 `setError('404')`;
500 `setError('500')`; network `setError('network')` (§3, §9).

**Verification**: covered by store tests Step 10b; `npx tsc --noEmit`.

---

### Step 5: Reconcile poll (webhook-latency race)

**Implements**: §4 reconcile lifecycle, I4, D5/D9, I8, scenarios A/B.

**Files**: `src/store/CheckoutFlowStore.ts`

**Approach** (≤5 lines): Add cancellable `private async reconcile(palId)`: `setFinalizing`;
loop up to 6 attempts with backoff (~15–20s total, e.g. 1,2,3,4,4,4s). Each attempt
`await palsHubService.checkPalOwnership(palId)` — `owned===true`→`setOwned` and stop (I4
first-true wins); `owned===false`→continue; thrown `PalsHubError`→swallow→continue (both
non-terminal, I4). After loop exhausts for any reason→`setProcessingDeferred` (D5, never
error). Abort if `reset()`/cancel fired mid-flight (I7) via an instance epoch token checked
each attempt. Never write `is_owned` (I8 — read only via checkPalOwnership/getPal).

**Verification**: store tests Step 10b cover webhook-lag, already-settled, cancel-mid-poll.

---

### Step 6: PalDetailSheet — platform branch + state feedback + re-auth affordance

**Implements**: §2, §4a.1-2 (I1 platform gate), §4c render row, §3 feedback, scenarios C/E/F, 9a/9b/9g/9k.

**Files**: `src/components/PalsHub/PalDetailSheet/PalDetailSheet.tsx`

**Re-auth surface (corrected)**: `PalDetailSheet` today has **no** `onSignInPress`/AuthSheet
(only `pal`/`isVisible`/`onClose`, C `:31-35`); `AuthSheet` is owned by **`PalsScreen`**
(`showAuth`/`setShowAuth`, C `:61,447-449`), which already passes
`onSignInPress={() => setShowAuth(true)}` to other children (C `:368,442`). Chosen fix =
**option (a)**: add an optional `onSignInPress?: () => void` prop to `PalDetailSheet`, passed
from `PalsScreen`'s existing callback (Step 6b). On 401 the `error` state renders a "Sign in
again" control → `onSignInPress` (opens PalsScreen's AuthSheet); retry is the existing buy
button after sign-in (no auto-retry wiring).

**Approach (6a — sheet)** (≤5 lines): Add `Platform` to the `react-native` import (today only
`Linking` is imported, `:2`). Keep buy-button **visibility** gate unchanged
(`isUSRegion && premium && !is_owned`, `:325-327` — I1 leaves region gate alone). Replace the
`onPress` (`:331-332`): `Platform.OS !== 'ios'` → keep the existing
`Linking.openURL(getPalBuyUrl(displayPal.id)).catch(() => {})` **verbatim, including the
`.catch(() => {})`** (the unchanged Android path must not regress into an unhandled
rejection — F/9k); else `checkoutFlowStore.start(displayPal.id)`. Component is already
`observer`; derive button `loading` from `status==='creating'`, disabled while
`creating|finalizing` (9g). Render non-blocking "Finalizing…" (`finalizing`), "Processing —
will unlock shortly" (`processing_deferred`); for `error` render the errorKind message and,
when `errorKind==='401'`, a "Sign in again" button → `onSignInPress?.()` (9a/E); 404 →
"unavailable" (9b). `owned` needs no extra UI. Call `checkoutFlowStore.reset()` in `onClose`.

**Approach (6b — PalsScreen wiring)** (≤3 lines): On the `<PalDetailSheet>` element
(`PalsScreen.tsx:452-461`), add `onSignInPress={() => setShowAuth(true)}`, reusing the exact
callback already wired into `PalsScreen`'s other children. No new state.

**Verification**: `yarn test --findRelatedTests src/components/PalsHub/PalDetailSheet/PalDetailSheet.tsx`;
`npx tsc --noEmit`; lint.

---

### Step 7: useDeepLinking — path-based `/app-return/*` route

**Implements**: §4c routing, D4 (path not host), §9h cold launch, I7.

**Files**: `src/hooks/useDeepLinking.ts`

**Approach** (≤5 lines): In `handleDeepLink` (`:68-92`), **before/alongside** the
`host==='chat'` branch (do not repurpose it — D4), parse `new URL(params.url).pathname`.
If it starts with `/app-return/`, read the trailing segment: `success`→
`checkoutFlowStore.onReturn(checkoutFlowStore.palId, 'success')`; `cancel`→`'cancel'` (palId
comes from the active flow the store already holds — return URL carries no palId; I7 stale-guard
lives in the store). Keying on **path** is required because the return `host` is `<HOST>`, which
cannot discriminate (it would collide with any future host route). Cold launch reaches the same
handler via `DeepLinkService.checkInitialURL` (`:93-110`).

**Verification**: `yarn test --findRelatedTests src/hooks/useDeepLinking.ts`; `npx tsc --noEmit`.

---

### Step 8: iOS native — entitlement + continueUserActivity wiring

**Implements**: §10.1/§10.2, §4c iOS rows, I6 (host symmetry), D6 (placeholder host).

**Files**: `ios/PocketPal/PocketPal.entitlements`, `ios/PocketPal/AppDelegate.swift`

**Approach** (≤5 lines): Entitlements — add `com.apple.developer.associated-domains`
array with `applinks:<HOST>` (the **one deferred string**, D6 — keep a terse code comment
marking it a placeholder; same `<HOST>` used in Step 4 URLs, I6). AppDelegate
`continue userActivity` (`:64-71`, today `return false`): when
`userActivity.activityType == NSUserActivityTypeBrowsingWeb`, grab `userActivity.webpageURL`,
post `RCTOpenURLNotification` with `["url": url]` (mirror `application(_:open:)` at `:50-58`),
`return true`. This routes the https return URL through the existing
`DeepLinkModule`→`onDeepLink` path (§4c) with no DeepLinkModule change. Do not handle other
activity types (§4c "does NOT").

**Verification**: iOS build in native gate; `RETURN_HOST` JS constant (Step 4) and the
entitlement `applinks:` host are the **same** placeholder symbol (I6) — checked by review, not test.

---

### Step 9: l10n copy keys

**Implements**: §3 user-visible feedback column.

**Files**: `src/locales/en.json`

**Approach** (≤5 lines): Under `palsScreen.palDetailSheet`, add keys: `finalizingPurchase`
("Finalizing your purchase…"), `processingPurchase` ("Processing — will unlock shortly."),
`checkoutSessionExpired` (401 — message paired with the "Sign in again" button, Step 6a), `signInAgain` ("Sign in again" button label), `palNotAvailable` (404), `checkoutFailed`
(500/network generic retryable). Edit **only** `en.json` (other locales via Weblate). Keep
register consistent with existing keys; do not invent UX copy beyond §3's labels.

**Verification**: `node scripts/validate-l10n.js` (if present) or `yarn test --findRelatedTests src/locales`;
`npx tsc --noEmit` (typed via `typeof en`).

---

### Step 10: Tests

**Implements**: §6 scenarios A–F, §9 edges, §3/§4 state machine.

**Files**:
- (10a) `src/services/palshub/__tests__/PalsHubApiService.test.ts` — `createCheckoutSession`:
  200 happy (body shape incl. success/cancel URLs, Bearer header reuse), `selected_country_code`
  present (alpha-2) vs omitted (alpha-3 "USA"/null — D3/9i), and each error branch
  401/404/400/500/network mapped to `PalsHubError` with correct `details.status` (§3 table).
- (10b) `src/store/__tests__/CheckoutFlowStore.test.ts` (new) — state machine: 200→browser_open,
  400→owned (D2/D), reconcile owned-on-attempt-1 (A), webhook-lag false/thrown ×6→processing_deferred
  (B/9c, I4 — assert **never** error), cancel→cancelled silent (C/I5), double-start no-op while
  creating/finalizing (I7/9g), stale `onReturn` ignored (9f), reset→idle. Mock
  `palsHubApiService`, `palsHubService.checkPalOwnership`, `InAppBrowser`, `getStorefrontCountryCode`.
- (10c) `src/components/PalsHub/PalDetailSheet/__tests__/...` — Platform.OS branch: iOS press →
  `checkoutFlowStore.start` (not Linking); non-iOS press → `Linking.openURL(getPalBuyUrl)` with the
  `.catch` preserved (F/9k, I1). Also: `error` + `errorKind:'401'` renders a "Sign in again" control
  whose press calls the `onSignInPress` prop (9a/E re-auth surface).
- (10d) `src/hooks/__tests__/useDeepLinking.test.ts` — extend: `/app-return/success` →
  `onReturn(...,'success')`, `/app-return/cancel` → `'cancel'`, and existing `host:'chat'` route
  still works (D4 — no regression).
- (10e) `src/utils/__tests__/palshub-display.test.ts` — keep existing `getPalBuyUrl` tests
  (retained; assert unchanged behaviour).

**Approach**: Follow the existing `jest.doMock('@env')` + `require(...)` pattern in
PalsHubApiService.test.ts; mock the inappbrowser native module (no native mock dir exists today —
add a `jest.mock('react-native-inappbrowser-reborn', ...)` inline or under `__mocks__/external/`).

**Verification**: `yarn test --findRelatedTests <each file>`; full `yarn test` green.

---

### Step 11: Promote architecture doc (same PR)

**Implements**: non-negotiable — flow doc absorbs the WHAT delta in the landing PR.

**Files**: `context/architecture/palshub-checkout.md`

**Approach** (≤5 lines): Flip every `(P)` to `(C)` now that code exists (createCheckoutSession,
Platform branch, SFSafariVC open via inappbrowser-reborn, path route, AppDelegate
continueUserActivity, applinks entitlement). Replace the dep candidate wording in §5c with the
**chosen** package + version + "New-Arch verified" note recorded in Step 1 (the candidate
`react-native-inappbrowser-reborn` is replaced only if Step 1's gate fails — write whatever
actually shipped, not the candidate). Update §11 "source of truth in code" to add `src/store/CheckoutFlowStore.ts` (the new
state owner) and `src/services/DeepLinkService.ts` / `src/hooks/useDeepLinking.ts` — confirm
the list points at `src/services/DeepLinkService.ts` (NOT under `palshub/`); no prose may
imply a `palshub/` location for the deep-link service. Leave `<HOST>`/D6 as the single remaining placeholder. Confirm
**zero `(?)`**. Drop the "drafted from story" banner (`:22-25`). No internal refs (hygiene).

**Verification**: `grep -n '(?)' context/architecture/palshub-checkout.md` returns nothing;
`grep -nE 'FOU-|TASK-|round [0-9]|§[0-9]' context/architecture/palshub-checkout.md` returns nothing.

---

## Testable-contract coverage

| Contract item | Verified by |
| --- | --- |
| §6.A happy (settled) | 10b reconcile owned-on-attempt-1; visual scenario "buy-success" |
| §6.B happy (webhook lag) | 10b false/thrown ×6 → processing_deferred (asserts never error) |
| §6.C cancel | 10b cancel→cancelled silent (no error UI) |
| §6.D already owned (400) | 10a 400 branch + 10b 400→owned (no browser) |
| §6.E session expired (401) | 10a 401 mapping + 10c error('401') renders "Sign in again" → `onSignInPress` (PalsScreen AuthSheet) |
| §6.F US Android web path | 10c non-iOS → Linking.openURL(getPalBuyUrl); 10e getPalBuyUrl retained |
| §9b 404 not purchasable | 10a 404 + 10b setError('404') |
| §9d 500/network | 10a 500/network mapping |
| §9f stale return ignored | 10b stale onReturn ignored |
| §9g double-tap | 10b no-op while creating/finalizing |
| §9h cold launch | 10d path route reached via getInitialURL path; store survives (app-global) |
| §9i alpha-3 country | 10a country_code omitted for "USA"/null |
| I1 platform gate | 10c iOS vs non-iOS branch |
| I4 no false failure | 10b processing_deferred never error |

---

## Native verification (NATIVE_CHANGES=YES)

```bash
cd ./worktrees/TASK-20260529-2105
cd ios && pod install && cd ..
yarn ios --configuration Release        # iOS: new pod + entitlement + AppDelegate compile/run
yarn android --variant=release          # Android: confirm NO regression (adds no Android feature)
```

Android build is mandatory even though this slice adds no Android feature — it must
confirm the unchanged Android web path still builds (no accidental native coupling).
Skipping any of the three is a blocking review issue.

---

## Visual confirmation (Visual Confirmation=YES)

iOS simulator, US region, a premium unowned PalsHub pal in the detail sheet:

```json
[
  {"label": "buy-button-idle", "prompt": "open premium pal detail sheet", "look_for": "Buy on Palshub button enabled"},
  {"label": "creating-spinner", "prompt": "tap Buy", "look_for": "button shows loading spinner before browser opens"},
  {"label": "finalizing", "prompt": "return via /app-return/success", "look_for": "non-blocking 'Finalizing your purchase…' indicator"},
  {"label": "cancel-silent", "prompt": "return via /app-return/cancel", "look_for": "no error message, button back to normal"}
]
```

Note: a true end-to-end Stripe round trip is gated on the palshub prod deploy of the
`<HOST>` association file (§9j, cross-repo); simulate the return URL for the finalizing/cancel
captures.

---

## Deferred items

- `<HOST>` placeholder string — the only deferred value (D6); confirmed apex-vs-www before E2E.
- Android/EU native checkout + return leg — separate ticket (§5 deferred #1; no Android config here).
- Dedicated `GET /api/purchases/{purchase_id}` reconcile source — deferred (§5 deferred #2, D9).
- Local-currency / price presentment — out of scope (Stripe Adaptive Pricing).

---

## Review History

| Round | Finding | Severity | Resolution |
| --- | --- | --- | --- |
| 1 | C1: native dep compatibility unverified — Step 1 picked legacy `inappbrowser-reborn@^3.7.1` as "latest" without confirming build/run under RN 0.82 New Arch (§4d requires maintenance status) | CONCERN | FIXED — Step 1 is now a verification GATE: pick + New-Arch `pod install` + New-Arch iOS build of a trivial call site BEFORE the plan depends on it; recorded maintenance status (3.7.1 is a thin republish of 2022 `3.7.0`, peerDeps only `RN>=0.56`, no New-Arch declaration); if the gate fails, fallback to a thin custom SFSafariViewController TurboModule (preferred) or `expo-web-browser` (rejected unless infeasible — repo has zero Expo). Step 4/§5c made package-agnostic. |
| 1 | C2: 401 re-auth surface doesn't exist — `PalDetailSheet` has no `onSignInPress`/AuthSheet; AuthSheet is owned by `PalsScreen` (`:447-449`) | CONCERN | FIXED — chose option (a): added `onSignInPress?` prop to `PalDetailSheet` (Step 6a) wired from `PalsScreen`'s existing `() => setShowAuth(true)` (Step 6b, `:452-461`); 401 `error` renders a "Sign in again" control → `onSignInPress` (opens PalsScreen AuthSheet), retry via existing buy button. Corrected the false "existing onSignInPress/AuthSheet path" wording. |
| 1 | S3: preserve `.catch(() => {})` on non-iOS `Linking.openURL` (`:332`) | SUGGESTION | FIXED — Step 6a keeps the Android branch verbatim including `.catch(() => {})`; 10c asserts it. |
| 1 | S4: arch-doc promote must list `src/services/DeepLinkService.ts` (not under `palshub/`) | SUGGESTION | FIXED — Step 11 §11 update explicitly confirms `src/services/DeepLinkService.ts` and forbids any `palshub/` implication; adds `CheckoutFlowStore.ts` to source-of-truth. |
| 1 | Add implied `Platform` import to PalDetailSheet | SUGGESTION | FIXED — Step 6a adds `Platform` to the `react-native` import (today only `Linking`, `:2`). |
