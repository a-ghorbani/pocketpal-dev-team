# PalsHub Checkout

**Purpose**: cumulative architecture truth for **how a user buys a premium
PalsHub Pal from inside the app** and how the app confirms ownership afterwards.
The Pal *configuration* surface (PACT/talents/greeting) lives in
`pals-and-talents.md`; the PalsHub *download* and library-sync side lives with
`SyncService` / `PalStore`. This doc owns the **purchase** flow only.

Status: **US iOS + US Android in-app checkout.** The authenticated in-app
checkout runs on **both** platforms, region-gated on `palStore.isUSRegion` (no
platform check). There is no `Linking.openURL` web buy path on either platform.
The two platforms differ only in the in-app browser primitive and an Android-only
native link-out prep: on Android the store calls Google Play **External Content
Links** (`launchExternalLink`) before opening the Custom Tab, and **Google Play
renders its own disclosure** during that call — there is no app-rendered
disclosure sheet on either platform. They share the same `CheckoutFlowStore`,
`createCheckoutSession`, reconcile poll, and `NativeAuthSession` spec. Android
additionally fires a best-effort External Content Links transaction report after
ownership is confirmed (a logged no-op today — US reporting enforcement is off;
live Play-Console verification is deferred — see §10). EU checkout remains a
separate future slice.

**Return mechanism:** the checkout web flow is opened, and its success/cancel
callback captured, by `ASWebAuthenticationSession` on iOS and a **Chrome Custom
Tab** on Android. On iOS the callback arrives through the session's completion
promise; on Android it arrives as a `host=checkout` BROWSABLE intent routed to
the native auth-session module — **not**, on either platform, through the
`DeepLinkService` OS deep-link pipeline and **not** via a Universal Link. (The
earlier iOS Universal-Link return was removed: iOS suppresses Universal Links that
point back into the app from inside the app's own `SFSafariViewController`, so the
auto-return never fired. See §10.)

The custom-scheme callback is namespaced by feature — host segment `checkout`
(`pocketpal://checkout/{success|cancel}`) — matching the `pocketpal://<feature>/...`
convention so the shared scheme stays collision-free as return types grow.

Convention:
- **(C)** = current behaviour, documented from code
- **(D)** = decision (was open, now resolved)

The `<HOST>` in `success_url`/`cancel_url` is the canonical PalsHub apex
`palshub.ai`. It is just a string inside those URLs — there is no entitlement or
host-symmetry coupling (D6). The callback scheme is `"pocketpal"` (already
registered, C `Info.plist:38-41`).

---

## 1. Flow at a glance

```
PalDetailSheet "Buy" (US, premium, !owned)
   │  (C gate: palStore.isUSRegion only — no platform check; PalDetailSheet.tsx:405-408)
   ▼
auth guard (both platforms): !isAuthenticated → onSignInPress                  (C)
   ▼
createCheckoutSession(palId, {successUrl, cancelUrl})                          (C)
   │  POST {PALSHUB_API_BASE_URL}/api/mobile/purchases, Bearer reuse
   │  (C auth path: PalsHubApiService.getAuthHeaders)
   ▼
 200 { checkout_url, session_url, session_id, purchase_id, platform_fee_cents }
   ▼
Android only: link-out prep (eligibility → token → launchExternalLink;          (C)
   │  Play renders its disclosure). 'launched' → continue; 'user_canceled'/
   │  'ineligible' → silent cancel; 'error' → error. iOS skips prep.
   ▼
 open checkout_url in the in-app browser (NativeAuthSession spec)              (C)
   │  iOS: ASWebAuthenticationSession (ephemeral, scheme "pocketpal")
   │  Android: Chrome Custom Tab (callback via host=checkout BROWSABLE intent)
   │  NOT an embedded WebView (Apple 3.1.1 / I2)
   ▼
 Stripe-hosted checkout → user pays / cancels (Google Pay surfaces on Android)
   ▼
 PalsHub /app-return/checkout/{success|cancel} page 302 →                      (C)
     pocketpal://checkout/{success|cancel}?purchase_id=...&session_id=...
   │  the in-app browser captures the custom-scheme callback and resolves the promise
   ▼
 CheckoutFlowStore parses path + purchase_id from the callback URL            (C)
   ├─ success → reconcile poll (§4) → owned | processing_deferred
   │             on owned, Android fires a best-effort External Content Links
   │             report with the prep token (a logged no-op today)
   └─ cancel / dismiss / session error → silent return (I5)
```

---

## 2. Data model

No persisted schema change. Checkout is transient; ownership persists only via
the existing library cache and is read live from the server.

```
CheckoutSession (request/response, in-memory)                     (C)
  checkout_url       : string   // Stripe page opened by ASWebAuthenticationSession
  session_url        : string   // alias; ignored client-side (D7)
  session_id         : string   // Stripe id; carried in callback, telemetry only
  purchase_id        : string   // PalsHub purchase row; parsed from callback (reconcile keys on palId — D9)
  platform_fee_cents : number   // display/telemetry only

CheckoutFlowState (in-memory, CheckoutFlowStore)                  (C)
  status   : idle | creating | linking | browser_open | finalizing
           | owned | processing_deferred | cancelled | error
           // `linking` (Android only) sits between creating and browser_open
  palId    : string
  purchaseId? : string
  errorKind?  : '401' | '404' | '500' | 'network'
  reportToken? : string  // Android: fresh per-link-out token, held for the report
```

```
ExternalLinkPrep (native→JS result of the Android link-out prep)  (C, Android only)
  outcome  : 'launched' | 'user_canceled' | 'ineligible' | 'error'
  token?   : string   // fresh external-transaction token; opaque to JS; held for report
```

Persisted: nothing new. Derived: ownership = `getPal(palId).is_owned`
(C, `PalsHubService.ts:73`), surfaced into `PalDetailSheet`'s `detailedPal`
local state (C, `PalDetailSheet.tsx:44-48`).

### 2b. External wire shape

**Request** — `POST {PALSHUB_API_BASE_URL}/api/mobile/purchases`

```
Authorization: Bearer <access_token>      (C reuse — getAuthHeaders)
Content-Type:  application/json
{
  pal_id:                 string,
  success_url:            "https://<HOST>/app-return/checkout/success",
  cancel_url:             "https://<HOST>/app-return/checkout/cancel"
}
```

`success_url`/`cancel_url` stay **https** (Stripe rejects custom schemes). The
PalsHub `/app-return/checkout/*` page then **302-redirects** to
`pocketpal://checkout/{success|cancel}?purchase_id=...&session_id=...`.

**Response 200** — `{ checkout_url, session_url, session_id, purchase_id, platform_fee_cents }`

**Status mapping**

| Status | Meaning | Behaviour |
| --- | --- | --- |
| 200 | created | open `checkout_url` via ASWebAuthenticationSession → `browser_open` |
| 400 | already owned | → `owned` (no browser) — D2 |
| 401 | session invalid | re-auth, no browser — `error('401')` |
| 404 | not purchasable | non-fatal "unavailable" |
| 500 / network | server/transport | generic retryable error |

**Return callback (iOS)** — `pocketpal://checkout/{success|cancel}`, delivered
through the **`ASWebAuthenticationSession` completion promise** (NOT
`DeepLinkService` / `useDeepLinking` / a Universal Link). `CheckoutFlowStore`
matches host `checkout` and the trailing `success` vs `cancel` segment, and reads
`purchase_id` from the resolved URL string. A rejected session (user-dismiss /
error) is a silent cancel (I5).

### 2c. Glossary

- **Checkout callback** — `pocketpal://checkout/{success|cancel}`, the custom-
  scheme URL the `/app-return/checkout/*` page redirects to; captured by the session.
- **`<HOST>`** — canonical PalsHub apex `palshub.ai` (D6); a plain string inside
  `success_url`/`cancel_url`, with no entitlement coupling.
- **Webhook-latency race** — gap between user return and PalsHub's Stripe webhook
  marking the purchase owned.
- **Reconcile poll** — bounded ownership re-check after a success return (§4).

---

## 3. State machine

```
idle ─Buy press (iOS or US Android, authenticated)→ creating
creating ─200, iOS→ browser_open          creating ─400→ owned
creating ─200, US Android→ linking         creating ─401/404/500/network→ error
linking ─prep 'launched'→ browser_open
linking ─prep 'user_canceled' | 'ineligible'→ cancelled   (silent)
linking ─prep 'error'→ error('network')
browser_open ─callback success→ finalizing
browser_open ─callback cancel / user-dismiss / session error→ cancelled
finalizing ─is_owned→ owned (Android: best-effort report w/ token)  finalizing ─exhausted→ processing_deferred
{owned, cancelled, error, processing_deferred} ─dismiss→ idle
```

| State | User-visible feedback |
| --- | --- |
| `idle` | normal buy button |
| `creating` | buy button spinner |
| `linking` (Android) | buy-button spinner continues; **Play** renders its disclosure (not app UI) |
| `browser_open` | ASWebAuthenticationSession (iOS) / Custom Tab (Android) foreground; app shows nothing extra |
| `finalizing` | non-blocking "Finalizing your purchase…" |
| `owned` | pal flips owned; button → download (existing logic) |
| `processing_deferred` | non-error "Processing — will unlock shortly" |
| `cancelled` | quiet return, no message |
| `error` | actionable message per `errorKind` |

US Android inserts one new transient state, `linking`, between `creating` and
`browser_open`; it is owned by `start()` under the same epoch pin. There is **no**
app disclosure state — Play owns the disclosure inside `launchExternalLink`. The
decline path is `linking → cancelled` via `USER_CANCELED`, not a sheet cancel.
Reporting is invisible to the user in every state.

---

## 4. Reconcile lifecycle (webhook-latency race)

Entered on a `checkout/success` callback. Up to ~6 attempts over ~15–20s with
backoff, each calling `palsHubService.checkPalOwnership(palId)` (C,
`PalsHubService.ts:64`, which delegates to `getPal().is_owned`).

**Error semantics (I4)** — each attempt resolves to one of:
- `owned===true` — the **first** such result ends the poll as `owned`.
- `owned===false` — returned when there is no signed-in user (C `:68-70`).
  Non-terminal; proceed to next attempt.
- thrown `PalsHubError` — API/network failure (C `:80-86`). Non-terminal;
  swallowed; proceed to next attempt.

```
finalizing
  attempt n (backoff): checkPalOwnership(palId)
    owned===true      → owned (stop)
    owned===false     → next attempt
    PalsHubError       → swallow → next attempt
  attempts exhausted (any reason) → processing_deferred  (SyncService.syncUserLibrary backstops)
```

Exhausting attempts for **any** reason → `processing_deferred`, **never**
`error`. The poll is cancellable via the store's epoch token: a `reset()` (sheet
close / new flow) bumps the epoch and aborts in-flight attempts (I7). The app
never writes ownership locally — it only *triggers* a server re-read (I8). This
slice reconciles via `checkPalOwnership` only (D9); a dedicated
`GET /api/purchases/{purchase_id}` source is deferred.

---

## 5. Contract

Buy-press rules (order matters):

1. Buy button visibility unchanged: `palStore.isUSRegion && premium && !is_owned`
   (C, `PalDetailSheet.tsx:405-408`). `handleBuyPress` is at
   `PalDetailSheet.tsx:135-146`.
2. On press, the auth guard runs first on **both** platforms
   (`authService.isAuthenticated` → `onSignInPress`). Then **both** platforms
   call `checkoutFlowStore.start(palId)` directly — there is **no** app
   disclosure gate. There is no `Linking.openURL` checkout path on either
   platform (I1′, D-A1, D-A7′).
3. The app sends no country hint (D3); Stripe `automatic_tax` derives the tax
   location from the billing address collected at checkout (authoritative for VAT).
4. `checkout_url` opens via the `NativeAuthSession` spec — `ASWebAuthenticationSession`
   on iOS (`callbackURLScheme:"pocketpal"`, `prefersEphemeralWebBrowserSession:true`),
   a Chrome Custom Tab on Android — never an embedded WebView (I2, §5c). The
   `isAllowedCheckoutUrl` trust gate and its two `__E2E__` carve-outs are reused
   unchanged on both platforms; no new concession (D-A6).
5. After a 200, **US Android only** runs link-out prep
   (`prepareExternalLink(checkout_url)`: eligibility → fresh token →
   `launchExternalLink`, where Play renders its disclosure) **before** opening
   the Custom Tab; the tab opens only on prep outcome `'launched'`. iOS skips
   prep. (I-A3′, D-A3′)
6. A `checkout/success` callback → reconcile poll (§4); on reaching `owned`,
   Android additionally fires a best-effort External Content Links report **with
   the prep token** (I-A3′). A `checkout/cancel` callback, a user-dismiss, or a
   session error → silent idle (I5).

### 5a. Hard invariants

- **I1′ (region-gated, both platforms in-app)**: the authenticated checkout flow
  is entered on `palStore.isUSRegion` for **both** iOS and US Android. No
  `Linking.openURL` checkout path remains on either platform. (Was I1: iOS-only
  via `Platform.OS`.)
- **I-A1 (no parallel store)**: Android reuses `CheckoutFlowStore` (sole
  epoch-pinned writer) and `start()`/`reconcile()`/`reset()` as-is. No Android
  checkout store, no duplicate state. The new `linking` status and the prep call
  live **inside** `start()` under the same epoch pin — a `reset()` during prep
  bumps the epoch and the resolved prep result is dropped.
- **I-A2 (single JS seam, one new prep method)**: Android satisfies the **same**
  `NativeAuthSession` spec iOS implements (`openAuth → Promise<callbackUrl>`;
  reject → silent cancel); the store is not platform-branched for the browser
  call. Link-out prep is **one** new native promise method `prepareExternalLink`
  on the Android External Content Links module; the store calls it only when that
  spec is present (it is `null` on iOS). Both specs are *optional*
  `TurboModuleRegistry.get(...)`; a missing/unresolvable module is a
  build/registration defect, not a user state (edge cases 9j-A / 9l-A).
- **I-A3′ (link-out prep precedes the browser; report is best-effort,
  post-ownership, token-bound)**: on US Android `prepareExternalLink` runs
  eligibility → token → `launchExternalLink` **before** the Custom Tab; the tab
  opens **only** on `'launched'`. The external-transaction token is minted
  **inside** that same prep (fresh, never cached) and threaded to the report. The
  report is fired by the store **after** reconcile reaches `owned`, and **never**
  gates, blocks, delays, or fails the checkout outcome; it is a **logged no-op
  today** (US enforcement off). A report failure never changes
  `CheckoutFlowState`, never shows error UI, never re-reports. It is **not** fired
  on the already-owned (400) path (no external transaction occurred). iOS never
  preps and never reports.
- **I-A4 (Play owns the disclosure)**: the pre-purchase disclosure is rendered by
  Google Play inside `launchExternalLink` — the app renders **no** disclosure UI
  on either platform. The decline path is `USER_CANCELED`, not an app sheet
  cancel.
- **I2 (no IAP WebView)**: Stripe checkout opens only via the in-app browser
  primitive (`ASWebAuthenticationSession` on iOS, a Chrome Custom Tab on Android);
  no purchase is ever completed in an embedded `react-native-webview` (Apple 3.1.1).
- **I3 (Bearer reuse)**: checkout authenticates via the existing native Supabase
  session (`getAuthHeaders`); no new token/JWT/identity artifact is minted.
- **I4 (no false failure on webhook lag)**: any per-attempt reconcile failure
  (thrown OR `owned:false`) is non-terminal; first `owned===true` → `owned`;
  exhaustion (any reason) → `processing_deferred` (success track), never `error`.
- **I5 (cancel is silent)**: a cancel callback, a user-dismiss, or a session
  error all show no error UI and mutate no ownership; all map to `cancelled`.
- **I6 (callback is session-scoped)**: the success/cancel callback is delivered
  **only** through the in-flight `ASWebAuthenticationSession` completion promise —
  never through the OS deep-link pipeline (`DeepLinkService`/`useDeepLinking`) and
  never via a Universal Link. A callback for a `reset()`/idle flow is ignored.
- **I7 (single in-flight checkout)**: at most one CheckoutFlowState / one live
  session per app; stale-flow callbacks are ignored (epoch guard); a press while
  `creating`/`finalizing` is a no-op.
- **I8 (ownership is server-derived)**: ownership is read from
  `getPal().is_owned` / library sync, never written locally on return.

### 5b. What each component does

| Component | Owns | Does NOT |
| --- | --- | --- |
| `PalDetailSheet` buy button | un-branched press: auth guard → `start` on both platforms; show creating/finalizing/result | render any disclosure sheet; open an anonymous browser; write ownership; keep the Android web path |
| `CheckoutFlowStore` (C) | call createCheckoutSession; on Android call `prepareExternalLink` before the tab; call `openAuth`; parse path + purchase_id from the resolved callback; run reconcile; on `owned` (Android) fire best-effort report with the prep token | fork per platform; route via DeepLinkService; use a Universal Link; persist ownership; render a disclosure; let prep/report gate the outcome beyond the `'launched'` gate |
| `PalsHubApiService.createCheckoutSession` (C) | POST /api/mobile/purchases with Bearer; map statuses | render; hold flow state |
| `AuthSessionModule` (iOS Swift / Android Kotlin) | present `checkout_url`, capture the `pocketpal` callback, resolve/reject a promise | run eligibility/token/launch; parse purchase semantics; touch reconcile state; report to Play |
| External Content Links module (Android, Kotlin) | `prepareExternalLink`: eligibility gate → mint fresh token → `launchExternalLink(LINK_TO_DIGITAL_CONTENT_OFFER, CALLER_WILL_LAUNCH_LINK)` (Play renders its disclosure); return verdict+token. `reportExternalContentLink(purchaseId, token)`: best-effort no-op-with-log today | open the Custom Tab; block/fail checkout; render a disclosure; exist on iOS |
| `SyncService.syncUserLibrary` | (C) library cache backstop for deferred ownership / app-kill recovery | drive checkout |

The OS deep-link path (`useDeepLinking` / `DeepLinkService`) is **not** part of
the checkout return on either platform (I6). On Android the return is captured by
the auth module via a `host=checkout` BROWSABLE intent, distinct from the
existing `host=hub` HF deep link, and is not routed to `DeepLinkService`.

### 5c. Browser dependency

The iOS checkout URL opens in an `ASWebAuthenticationSession` — the purpose-built
primitive for opening a web flow in-app and capturing a custom-scheme callback —
with `callbackURLScheme:"pocketpal"` and `prefersEphemeralWebBrowserSession:true`
(ephemeral avoids the system "wants to use X to sign in" prompt; shared Safari
cookies are not needed because identity is in the Stripe `checkout_url`). It is
**not** `react-native-webview` (embedded WebView forbidden by I2), **not** a plain
`SFSafariViewController` open (cannot capture the callback — the Universal-Link
trap §10 fixes), and **not** a Universal Link.

The iOS implementation is a thin custom `ASWebAuthenticationSession` TurboModule
authored in this repo, following the existing Swift-module + `.m` bridge pattern
(C `StorefrontModule.swift`/`StorefrontModule.m`, `DeepLinkModule.swift`/`.m`).
`react-native-inappbrowser-reborn` is **dropped** (stale 2022 republish, no
New-Arch declaration); its `openAuth()` is the documented fallback only if the
custom module proves disproportionate.

The Android counterpart is a thin Kotlin module satisfying the **same**
`NativeAuthSession` spec, mirroring `StorefrontModule`/`StorefrontPackage`
(`com.pocketpal`, dir `com/pocketpalai/`, manual registration in
`MainApplication.getPackages()`). `openAuth(url, scheme)` launches a Chrome
Custom Tab (`androidx.browser`) and parks one in-flight promise; the
`pocketpal://checkout/*` callback returns as a `host=checkout` BROWSABLE intent
to the singleTask `MainActivity`, which forwards it to the module
(`onNewIntent`), resolving the promise. A tab dismiss with no callback rejects to
a silent cancel (I5). No Expo tree; `expo-web-browser` was rejected (pulls
`expo-modules-core`/autolinking + iOS pods into a bare RN app).

---

## 6. Single-writer rule

| Field | Single writer |
| --- | --- |
| `CheckoutFlowState` (incl. `linking`) | (C) `CheckoutFlowStore` (`store/CheckoutFlowStore.ts`) |
| ownership (`is_owned`) | **server** — read via `getPal()`; never written client-side (I8) |
| external-transaction token | native module (minted per link-out); held transiently by the store for the report only; never persisted |
| library cache rows | (C) `SyncService.syncUserLibrary` (`SyncService.ts:102`) |
| `palStore.isUSRegion` | (C) `PalStore.checkRegion` (`PalStore.ts:112-121`) |

The only relevant race is webhook latency, handled by §4 reconcile — not a
multi-writer race. No local ownership write exists, so none can drift. The
Android External Content Links report is a fire-and-forget side effect of the
store's `owned` transition; it reads only the `purchaseId` + the prep token the
store already holds and writes nothing.

---

## 7. Canonical scenarios

### A. Happy path (iOS) — settled

```
US iOS premium !owned → Buy → 200 → ASWebAuthenticationSession → pay
/app-return/checkout/success 302 → pocketpal://checkout/success → session resolves
→ finalizing → owned on attempt 1 → download button
```

### B. Happy path (iOS) — webhook lag

```
session resolves on success → finalizing → false/thrown ×6 (~18s) → processing_deferred
SyncService later reflects ownership; no error
```

### C. Cancel (iOS)

```
user dismisses session (or checkout/cancel) → cancelled (silent) → idle
```

### D. Already owned (iOS)

```
Buy → 400 → owned (no browser)
```

### E. Session expired (iOS)

```
Buy → 401 → no browser → error('401') → re-auth → retry
```

### F. App killed mid-checkout (iOS) — accepted behaviour

```
force-quit while session sheet open → session torn down with the process
no callback, NO cold-launch return (ASWebAuthenticationSession is contained)
next app open → SyncService.syncUserLibrary reconciles → live is_owned correct (I8)
no error shown
```

### G. US Android — happy path

```
US Android premium !owned (auth'd) → Buy → start → 200 → linking
→ prepareExternalLink: eligible → token → launchExternalLink (Play disclosure) → 'launched'
→ Custom Tab(checkout_url) → Google Pay → checkout/success redirect
→ finalizing → owned on attempt 1 → best-effort report(token) (no-op today)
→ Download button
```

### H. US Android — disclosure declined (Play screen)

```
Buy → start → 200 → linking → launchExternalLink → USER_CANCELED
→ cancelled (silent; no Custom Tab, no report) → idle
```

### I. US Android — cancel / tab dismiss

```
Custom Tab dismissed (or checkout/cancel) → openAuth rejects → cancelled (silent) → idle
no report fired (reporting is post-owned only)
```

### J. US Android — webhook lag

```
checkout/success → finalizing → false/thrown ×6 → processing_deferred
no report (report fires only on owned); SyncService backstops ownership; no error
```

### K. Reporting program inactive (US Android, owned)

```
owned → reportExternalContentLink(purchaseId, token) attempted → US enforcement off
→ logged no-op → state stays owned, no UI, checkout already succeeded (I-A3′, D-A8′)
```

### M. US Android — ineligible / link-out error

```
Buy → start → 200 → linking → isBillingProgramAvailableAsync != OK (or BILLING_UNAVAILABLE)
→ 'ineligible' → cancelled (silent; no Custom Tab, no report)
launchExternalLink ERROR / transient → 'error' → error('network')
```

### L. Non-US (either platform) — unchanged

```
premium !owned, !isUSRegion → info text, no Buy button (region gate unchanged)
```

---

## 8. Decisions

- **D1** — Net-new flow doc, not a section of `pals-and-talents.md`. Purchase is
  a distinct concern from PACT/config; mixing them would couple two lifecycles.
- **D2** — `400 "already own"` is treated as success (`owned`), not error. The
  user already owns the pal; opening Stripe would be wrong.
- **D3** — the app sends **no** country hint. Tax location is derived server-side
  from the billing address Stripe collects at checkout (authoritative for VAT). The
  storefront country is the Apple-ID region (not the buyer's tax location), iOS
  returns it as alpha-3 needing conversion, and the billing address overrides any
  hint anyway — not worth the bug surface.
- **D6** — `<HOST>` is `PALSHUB_API_BASE_URL` (e.g. `palshub.ai`): `success_url`/
  `cancel_url` derive from the same env value as the API, so pointing the app at any
  host just works. No entitlement or host-symmetry coupling (the
  callback scheme is `"pocketpal"`, the callback host is the feature `checkout`).
- **D7** — `session_url` / `session_id` are not used to open the browser;
  `checkout_url` is the only URL the session opens.
- **D8** — Ownership is confirmed via the server, never written locally on return
  (I8). PalsHub is the single source of truth.
- **D9** — Reconcile uses `checkPalOwnership` only this slice (keys on `palId`);
  `purchase_id` is parsed from the callback for telemetry. A dedicated
  purchase-status endpoint is deferred (§10 cleanups).
- **D10** — *(superseded by D-A1 / I1′)* The flow is no longer iOS-only; US
  Android now runs the same authenticated in-app checkout via a Custom Tab.
- **D11** — Return via `ASWebAuthenticationSession` callback (scheme `"pocketpal"`,
  ephemeral), **not** a Universal Link. iOS suppresses Universal Links that point
  back into the app from inside the app's own `SFSafariViewController`, so the
  Universal-Link auto-return never fired.
- **D12** — Implement with a thin custom `ASWebAuthenticationSession` TurboModule;
  drop `react-native-inappbrowser-reborn`. The dropped package was a stale 2022
  republish with no New-Arch declaration; the codebase already has the native
  module pattern. `openAuth()` is the fallback only if the custom module is
  disproportionate.
- **D-A1** — Un-branch `handleBuyPress`; remove the Android `Linking.openURL`
  checkout path. Android now runs the authenticated in-app flow.
- **D-A2** — iOS code path byte-for-byte unchanged; no iOS pod/native edit. The
  "no iOS regression" guarantee is honoured by reusing the existing spec.
- **D-A3** — Native Kotlin Custom Tabs module resolving the existing
  `NativeAuthSession` spec; the module's callback is captured via a `host=checkout`
  BROWSABLE intent forwarded by `MainActivity.onNewIntent`, not `DeepLinkService`.
  (No Expo tree; mirrors the iOS seam.)
- **D-A3′** — Native-orchestrated link-out: one `prepareExternalLink` returns a
  verdict; the store opens the existing Custom Tab on `'launched'`.
  Eligibility/token/launch are atomic Play-side; one mock point; single JS seam.
- **D-A4′** — Billing 7.1.1 → 8.2.1+; `enableBillingProgram(EXTERNAL_CONTENT_LINK)`;
  do **not** enable `PurchasesUpdatedListener` (guide: not needed). External
  Offers is deprecated; External Content Links is the correct US program.
- **D-A5′** — The external-transaction token is minted inside `prepareExternalLink`
  (fresh per link-out, never cached) and threaded to the post-ownership report.
  Google contract: a new token each external visit; reuse is forbidden.
- **D-A6** — Reuse `isAllowedCheckoutUrl` + its two existing `__E2E__` carve-outs
  on both platforms; add none.
- **D-A7′** — **No app disclosure sheet.** Google Play renders the disclosure
  inside `launchExternalLink`; an app sheet would double-prompt and is
  non-compliant. Decline = `USER_CANCELED` (silent cancel). Supersedes D-A7
  (the External-Offers app-rendered gate).
- **D-A8′** — Report is a no-op-with-log today (US enforcement off); token+launch
  built now; live Play-Console verification + the Google Pay round-trip on a real
  US Android device are DEFERRED (enrollment not Active), mirroring the iOS
  slice's deferred live Stripe/Apple Pay.

---

## 9. Edge cases

| ID | Edge case | Behaviour |
| --- | --- | --- |
| 9a | 401 on create (iOS) | no browser; re-auth; `error('401')` |
| 9b | 404 not purchasable (iOS) | non-fatal "unavailable"; back to idle |
| 9c | Webhook never lands in poll window | `processing_deferred`; SyncService backstop (I4) |
| 9d | 500 / network on create (iOS) | generic retryable error; no browser |
| 9e | Force-quit during checkout | session dies with process; no cold-launch return; SyncService reconciles on next open (scenario F, I8) |
| 9f | Callback for a reset()/idle flow | ignored (I6, I7) |
| 9g | Double-tap Buy (iOS) | no-op while creating/finalizing (I7) |
| 9h | User dismisses the session sheet | session rejects → silent `cancelled` (I5); indistinguishable from checkout/cancel |
| 9j | palshub `/app-return/checkout/*` not deployed / not redirecting to scheme | session never resolves; user dismiss → silent cancel; gated on palshub prod deploy |
| 9a-A | US Android double-tap Buy | no-op while in-flight (I7 / `isInFlight`, which now includes `linking`) |
| 9b-A | Play disclosure declined (`USER_CANCELED`) | `linking → cancelled` (silent); no Custom Tab, no report (D-A7′, scenario H) |
| 9c-A | Custom Tab dismissed without return | `openAuth` rejects → silent cancel (I5, I-A2); no report (scenario I) |
| 9d-A | `reset()` during `linking` (sheet close) | epoch bumped; resolved prep result dropped; no stray tab opened (I-A1) |
| 9e-A | Not eligible (`isBillingProgramAvailableAsync != OK` / `BILLING_UNAVAILABLE`) | `'ineligible'` → silent cancel; no Custom Tab, no report (scenario M) |
| 9f-A | `launchExternalLink` ERROR / FEATURE_NOT_SUPPORTED / DEVELOPER_ERROR / transient | `'error'` → `error('network')`; no Custom Tab; user may retry (scenario M) |
| 9g-A | Report throws / token absent | swallowed; never re-reported, never error UI, state stays `owned` (I-A3′) |
| 9h-A | Reporting program inactive (today) | logged no-op; state stays `owned` (I-A3′, D-A8′, scenario K) |
| 9i-A | 401/404/500 on create (Android) | same as iOS (9a/9b/9d); no prep, no browser, no report |
| 9j-A | Non-US Android | info text only; region gate unchanged (I1′, scenario L) |
| 9k-A | `host=checkout` collides with `host=hub` HF deep link | distinct hosts; checkout return routes only to the auth module, not `DeepLinkService` |
| 9l-A | External Content Links module unregistered (`TurboModuleRegistry.get` → null) | **build/registration DEFECT**: on US Android `prepareExternalLink` is unavailable; the store must not silently open the tab without prep. Caught by native-build wiring (`MainApplication.getPackages()`) + E2E Buy-press reaching the Play disclosure / Custom Tab — never a silent Buy dead-end |

---

## 10. Native surface

**Added on iOS:**
- A thin custom `ASWebAuthenticationSession` TurboModule (Swift module + `.m`
  bridge, matching `StorefrontModule`/`DeepLinkModule`) that opens `checkout_url`,
  captures the `pocketpal`-scheme callback, and resolves/rejects a JS promise.
- No new URL scheme: `pocketpal` is already registered (C `Info.plist:38-41`).

**Added on Android:**
- An `AuthSessionModule` (Kotlin, `com.pocketpal`, dir `com/pocketpalai/`)
  satisfying the same `NativeAuthSession` spec via a Chrome Custom Tab
  (`androidx.browser`), with `AuthSessionPackage` registered in
  `MainApplication.getPackages()`.
- A `host=checkout` BROWSABLE intent filter in `AndroidManifest.xml` (distinct
  from the existing `host=hub` HF deep link), forwarded from
  `MainActivity.onNewIntent` to the module — not `DeepLinkService`.
- An `ExternalContentLinkModule` (Kotlin) driving the Play Billing **External
  Content Links** program (`com.android.billingclient:billing:8.2.1`,
  `enableBillingProgram(EXTERNAL_CONTENT_LINK)` — no `PurchasesUpdatedListener`):
  `prepareExternalLink` runs `isBillingProgramAvailableAsync` →
  `createBillingProgramReportingDetailsAsync` (fresh token) →
  `launchExternalLink(LINK_TO_DIGITAL_CONTENT_OFFER, CALLER_WILL_LAUNCH_LINK)`
  (Play renders its disclosure) and returns a verdict+token;
  `reportExternalContentLink` is best-effort, no-op-with-log today. Exposed as the
  optional `NativeExternalContentLink` spec (null on iOS).
- No new URL scheme: `pocketpal` is already a registered host-scoped deep link.

**Removed by this revision (previously landed for the Universal-Link approach):**
- The `applinks:<HOST>` associated-domains entitlement in
  `ios/PocketPal/PocketPal.entitlements` — **dropped**. The return no longer uses
  a Universal Link.
- The `application(_:continue:restorationHandler:)` web-URL forwarding in
  `ios/PocketPal/AppDelegate.swift` — **reverted to the original `return false`**.
  Universal-Link `NSUserActivity` is no longer part of the checkout return.
- The `/app-return/*` **path route** in `src/hooks/useDeepLinking.ts` and any
  `DeepLinkService`/`DeepLinkModule` involvement in the checkout return —
  **dropped**. The callback comes back through the session promise, not the OS
  deep-link pipeline (I6).
- The `RETURN_HOST` host coupling and the old host-symmetry invariant —
  **dropped**. `<HOST>` is now just a string inside `success_url`/`cancel_url`.
- The cold-launch-via-return scenario — **dropped**. `ASWebAuthenticationSession`
  is a contained session; if the app is killed mid-checkout there is no
  cold-launch return. Ownership reconciles on next open via `SyncService`
  (scenario F).

Both surfaces are `NATIVE_CHANGES=YES`: the Android slice adds native modules +
manifest + Play/androidx dependencies, so an Android release build and an iOS
build (to confirm no regression on the unchanged iOS path; no iOS pod change) are
required before the work is ready.

**Deferred (operational, not gating):** live Play-Console verification that the
External Content Links (US) program is Active and reported events appear, and the
Google Pay round-trip on a real US Android device (emulator has no wallet; the
harness auto-completes). When enrollment goes Active the no-op-with-log report
(D-A8′) becomes a real call with no app-code change beyond the server-side
submission. EU checkout + return is a separate future slice.

---

## 11. Cross-references

- **`explore-tab.md`** — the PalsHub discovery surface (Explore tab) is a second
  entry point into this checkout. It opens the **same** `PalDetailSheet`
  (reskinned in place; still a `Sheet`, not promoted to a page) and the same
  buy/download/owned actions — checkout behaviour is preserved verbatim. The
  pre-existing `handleBuyPress` Android web-buy branch (`Platform.OS !== 'ios'` →
  `Linking.openURL(getPalBuyUrl)`) remains the **drift vs this doc's §5/I1′**
  un-branched description; it is preserved, not reconciled (checkout-flow owner).
- **`pals-and-talents.md`** — Pal config surface (PACT/greeting); ownership-gated
  content rendering is `shouldShowPalContent` (C, `palshub-display.ts:120`).
- **`SyncService.ts`** — library cache; the deferred-ownership / app-kill backstop
  (§4, scenario F).

**Cross-repo (palshub):** the `/app-return/checkout/*` pages **302-redirect to the
custom scheme** `pocketpal://checkout/{success|cancel}?purchase_id=...&session_id=...`
(gated on the palshub prod deploy). The `.well-known` association files
(`apple-app-site-association` / `assetlinks.json`) are **dropped** — the return no
longer relies on Universal/App Links.

Source of truth in code: `src/services/palshub/PalsHubApiService.ts`
(`createCheckoutSession`), `src/store/CheckoutFlowStore.ts` (the checkout state
owner + Android link-out prep + in-app browser driver + reconcile poll +
token-bound post-`owned` report), `src/components/PalsHub/PalDetailSheet/PalDetailSheet.tsx`
(un-branched press, no app disclosure), the specs `src/specs/NativeAuthSession.ts`
/ `src/specs/NativeExternalContentLink.ts`, the iOS
`ios/PocketPal/AuthSessionModule.swift`, and the Android `AuthSessionModule.kt` /
`ExternalContentLinkModule.kt` (+ their packages,
`MainActivity.kt`/`MainApplication.kt` wiring, and the `host=checkout` manifest
filter).

When this doc and the code disagree, the code wins; the same PR that lands the
change updates this file.
