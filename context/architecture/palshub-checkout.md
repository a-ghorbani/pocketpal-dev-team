# PalsHub Checkout

**Purpose**: cumulative architecture truth for **how a user buys a premium
PalsHub Pal from inside the app** and how the app confirms ownership afterwards.
The Pal *configuration* surface (PACT/talents/greeting) lives in
`pals-and-talents.md`; the PalsHub *download* and library-sync side lives with
`SyncService` / `PalStore`. This doc owns the **purchase** flow only.

Status: **Slice 1 — iOS only.** The authenticated in-app checkout is added on the
iOS branch only. **US Android keeps the existing web buy path** (the buy button
is region-gated with no platform check, and `isUSStorefront()` resolves on
Android — so a US Android user uses the button today via `Linking.openURL`).
Android/EU **native** checkout + return is a separate future slice and is **not**
configured here.

**Return mechanism: `ASWebAuthenticationSession`.** The checkout web flow is
opened, and its success/cancel callback captured, by `ASWebAuthenticationSession`
(callback scheme `"pocketpal"`, ephemeral session). The callback arrives through
the session's completion promise — **not** through the OS deep-link pipeline and
**not** via a Universal Link. (The earlier Universal-Link return was removed: iOS
suppresses Universal Links that point back into the app from inside the app's own
`SFSafariViewController`, so the auto-return never fired. See §10.)

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
   │  (C gate: palStore.isUSRegion only — no platform check; PalDetailSheet.tsx:325-327)
   ▼
branch on Platform.OS                                                          (C)
   ├─ NOT ios  → Linking.openURL(getPalBuyUrl)   (C, unchanged — US Android web path)
   └─ ios      → createCheckoutSession(palId, {successUrl, cancelUrl, selectedCountryCode?}) (C)
                   │  POST {PALSHUB_API_BASE_URL}/api/mobile/purchases, Bearer reuse
                   │  (C auth path: PalsHubApiService.getAuthHeaders)
                   ▼
                 200 { checkout_url, session_url, session_id, purchase_id, platform_fee_cents }
                   ▼
                 ASWebAuthenticationSession.start(checkout_url,
                     callbackURLScheme:"pocketpal", prefersEphemeralWebBrowserSession:true) (C)
                   │  NOT an embedded WebView (Apple 3.1.1) — I2
                   ▼
                 Stripe-hosted checkout → user pays / cancels
                   ▼
                 PalsHub /app-return/checkout/{success|cancel} page 302 →        (C)
                     pocketpal://checkout/{success|cancel}?purchase_id=...&session_id=...
                   │  ASWebAuthenticationSession captures the custom-scheme callback,
                   │  dismisses its sheet, and resolves the promise with the callback URL
                   ▼
                 CheckoutFlowStore parses path + purchase_id from the callback URL  (C)
                   ├─ success → reconcile poll (§4) → owned | processing_deferred
                   └─ cancel / user-dismiss / session error → silent return (I5)
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
  status   : idle | creating | browser_open | finalizing
           | owned | processing_deferred | cancelled | error
  palId    : string
  purchaseId? : string
  errorKind?  : '401' | '404' | '500' | 'network'
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
  cancel_url:             "https://<HOST>/app-return/checkout/cancel",
  selected_country_code?: string          // 2-letter only (§5 rule 3)
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
idle ─Buy press(iOS)→ creating
creating ─200→ browser_open      creating ─400→ owned
creating ─401/404/500/network→ error
browser_open ─callback success→ finalizing
browser_open ─callback cancel / user-dismiss / session error→ cancelled
finalizing ─is_owned→ owned      finalizing ─exhausted→ processing_deferred
{owned, cancelled, error, processing_deferred} ─dismiss→ idle
```

| State | User-visible feedback |
| --- | --- |
| `idle` | normal buy button |
| `creating` | buy button spinner |
| `browser_open` | ASWebAuthenticationSession sheet foreground; app shows nothing extra |
| `finalizing` | non-blocking "Finalizing your purchase…" |
| `owned` | pal flips owned; button → download (existing logic) |
| `processing_deferred` | non-error "Processing — will unlock shortly" |
| `cancelled` | quiet return, no message |
| `error` | actionable message per `errorKind` |

US Android does not enter this machine — its press goes straight to
`Linking.openURL(getPalBuyUrl)` (I1).

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
   (C, `PalDetailSheet.tsx:325-327`).
2. On press, branch on `Platform.OS` (I1): non-iOS → existing
   `Linking.openURL(getPalBuyUrl)` web path (`getPalBuyUrl` retained); iOS →
   `createCheckoutSession` + CheckoutFlowState.
3. `selected_country_code` sent only when `getStorefrontCountryCode()` returns an
   alpha-2 (`length === 2`); alpha-3 / null omitted (D3). Tax hint only.
4. `checkout_url` opens via `ASWebAuthenticationSession`
   (`callbackURLScheme:"pocketpal"`, `prefersEphemeralWebBrowserSession:true`),
   never an embedded WebView (I2, §5c).
5. A `checkout/success` callback → reconcile poll (§4). A `checkout/cancel`
   callback, a user-dismiss, or a session error → silent idle (I5).

### 5a. Hard invariants

- **I1 (iOS-only boundary via platform gate)**: the new checkout flow is entered
  **only** under `Platform.OS === 'ios'`. The buy button stays visible on US
  Android (region-only gate unchanged), and US Android presses keep calling
  `Linking.openURL(getPalBuyUrl)`. No Android caller of `createCheckoutSession`
  and no Android return leg is added.
- **I2 (no IAP WebView)**: Stripe checkout opens only via
  `ASWebAuthenticationSession`; no purchase is ever completed in an embedded
  `react-native-webview` (Apple 3.1.1).
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
| `PalDetailSheet` buy button | branch on Platform.OS; on iOS drive CheckoutFlowState + show creating/finalizing/result; on non-iOS keep `Linking.openURL(getPalBuyUrl)` | open the anonymous browser on iOS; write ownership; add Android return path |
| `CheckoutFlowStore` (C) | call createCheckoutSession; start ASWebAuthenticationSession; parse path + purchase_id from the resolved callback; run reconcile | route via DeepLinkService; use a Universal Link; persist ownership |
| `PalsHubApiService.createCheckoutSession` (C) | POST /api/mobile/purchases with Bearer; map statuses | render; hold flow state |
| ASWebAuthenticationSession native module | present `checkout_url`, capture the `pocketpal` callback, resolve/reject a promise | parse purchase semantics; touch reconcile state |
| `SyncService.syncUserLibrary` | (C) library cache backstop for deferred ownership / app-kill recovery | drive checkout |

The OS deep-link path (`useDeepLinking` / `DeepLinkService`) is **not** part of
the checkout return (I6) and is not wired for `pocketpal://checkout/*`.

### 5c. Browser dependency

The iOS checkout URL opens in an `ASWebAuthenticationSession` — the purpose-built
primitive for opening a web flow in-app and capturing a custom-scheme callback —
with `callbackURLScheme:"pocketpal"` and `prefersEphemeralWebBrowserSession:true`
(ephemeral avoids the system "wants to use X to sign in" prompt; shared Safari
cookies are not needed because identity is in the Stripe `checkout_url`). It is
**not** `react-native-webview` (embedded WebView forbidden by I2), **not** a plain
`SFSafariViewController` open (cannot capture the callback — the Universal-Link
trap §10 fixes), and **not** a Universal Link.

The implementation is a thin custom `ASWebAuthenticationSession` TurboModule
authored in this repo, following the existing Swift-module + `.m` bridge pattern
(C `StorefrontModule.swift`/`StorefrontModule.m`, `DeepLinkModule.swift`/`.m`).
`react-native-inappbrowser-reborn` is **dropped** (stale 2022 republish, no
New-Arch declaration); its `openAuth()` is the documented fallback only if the
custom module proves disproportionate.

---

## 6. Single-writer rule

| Field | Single writer |
| --- | --- |
| `CheckoutFlowState` | (C) `CheckoutFlowStore` (`store/CheckoutFlowStore.ts`) |
| ownership (`is_owned`) | **server** — read via `getPal()`; never written client-side (I8) |
| library cache rows | (C) `SyncService.syncUserLibrary` (`SyncService.ts:102`) |
| `palStore.isUSRegion` | (C) `PalStore.checkRegion` (`PalStore.ts:112-121`) |

The only relevant race is webhook latency, handled by §4 reconcile — not a
multi-writer race. No local ownership write exists, so none can drift.

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

### F. US Android — unchanged web path

```
Buy → Platform.OS !== 'ios' → Linking.openURL(getPalBuyUrl) → web product page
(no checkout session, no return leg — identical to today)
```

### G. App killed mid-checkout (iOS) — accepted behaviour

```
force-quit while session sheet open → session torn down with the process
no callback, NO cold-launch return (ASWebAuthenticationSession is contained)
next app open → SyncService.syncUserLibrary reconciles → live is_owned correct (I8)
no error shown
```

---

## 8. Decisions

- **D1** — Net-new flow doc, not a section of `pals-and-talents.md`. Purchase is
  a distinct concern from PACT/config; mixing them would couple two lifecycles.
- **D2** — `400 "already own"` is treated as success (`owned`), not error. The
  user already owns the pal; opening Stripe would be wrong.
- **D3** — `selected_country_code` sent only when alpha-2. Alpha-3 ("USA", iOS 15)
  and `null` are omitted; server IP fallback handles them. It is a tax hint only.
- **D6** — `<HOST>` is the canonical PalsHub apex `palshub.ai`, a plain string
  inside `success_url`/`cancel_url`; no entitlement or host-symmetry coupling (the
  callback scheme is `"pocketpal"`, the callback host is the feature `checkout`).
- **D7** — `session_url` / `session_id` are not used to open the browser;
  `checkout_url` is the only URL the session opens.
- **D8** — Ownership is confirmed via the server, never written locally on return
  (I8). PalsHub is the single source of truth.
- **D9** — Reconcile uses `checkPalOwnership` only this slice (keys on `palId`);
  `purchase_id` is parsed from the callback for telemetry. A dedicated
  purchase-status endpoint is deferred (§10 cleanups).
- **D10** — iOS-only via `Platform.OS` gate; US Android keeps the web path.
  Android has no callback mechanism for this slice, so there is no Android return.
- **D11** — Return via `ASWebAuthenticationSession` callback (scheme `"pocketpal"`,
  ephemeral), **not** a Universal Link. iOS suppresses Universal Links that point
  back into the app from inside the app's own `SFSafariViewController`, so the
  Universal-Link auto-return never fired.
- **D12** — Implement with a thin custom `ASWebAuthenticationSession` TurboModule;
  drop `react-native-inappbrowser-reborn`. The dropped package was a stale 2022
  republish with no New-Arch declaration; the codebase already has the native
  module pattern. `openAuth()` is the fallback only if the custom module is
  disproportionate.

---

## 9. Edge cases

| ID | Edge case | Behaviour |
| --- | --- | --- |
| 9a | 401 on create (iOS) | no browser; re-auth; `error('401')` |
| 9b | 404 not purchasable (iOS) | non-fatal "unavailable"; back to idle |
| 9c | Webhook never lands in poll window | `processing_deferred`; SyncService backstop (I4) |
| 9d | 500 / network on create (iOS) | generic retryable error; no browser |
| 9e | Force-quit during checkout | session dies with process; no cold-launch return; SyncService reconciles on next open (scenario G, I8) |
| 9f | Callback for a reset()/idle flow | ignored (I6, I7) |
| 9g | Double-tap Buy (iOS) | no-op while creating/finalizing (I7) |
| 9h | User dismisses the session sheet | session rejects → silent `cancelled` (I5); indistinguishable from checkout/cancel |
| 9i | iOS 15 alpha-3 country | field omitted (D3) |
| 9j | palshub `/app-return/checkout/*` not deployed / not redirecting to scheme | session never resolves; user dismiss → silent cancel; gated on palshub prod deploy |
| 9k | US Android taps Buy | unchanged web path via `getPalBuyUrl` (I1) |

---

## 10. Native surface (iOS only)

**Added by this flow:**
- A thin custom `ASWebAuthenticationSession` TurboModule (Swift module + `.m`
  bridge, matching `StorefrontModule`/`DeepLinkModule`) that opens `checkout_url`,
  captures the `pocketpal`-scheme callback, and resolves/rejects a JS promise.
- No new URL scheme: `pocketpal` is already registered (C `Info.plist:38-41`).

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
  (scenario G).

This makes the iOS native surface `NATIVE_CHANGES=YES`: pod install + iOS build
(and an Android build to confirm no regression on the unchanged Android path) are
required before the work is ready.

**Out of scope (future Android slice):** Android native checkout + return. Android
would need its own callback mechanism (Custom Tabs + intent, or an
ASWebAuthenticationSession analogue) that does not exist today; `DeepLinkService`
is iOS-gated (C `DeepLinkService.ts:31`). This PocketPal slice adds no Android
native config.

---

## 11. Cross-references

- **`pals-and-talents.md`** — Pal config surface (PACT/greeting); ownership-gated
  content rendering is `shouldShowPalContent` (C, `palshub-display.ts:120`).
- **`SyncService.ts`** — library cache; the deferred-ownership / app-kill backstop
  (§4, scenario G).

**Cross-repo (palshub):** the `/app-return/checkout/*` pages **302-redirect to the
custom scheme** `pocketpal://checkout/{success|cancel}?purchase_id=...&session_id=...`
(gated on the palshub prod deploy). The `.well-known` association files
(`apple-app-site-association` / `assetlinks.json`) are **dropped** — the return no
longer relies on Universal/App Links.

Source of truth in code: `src/services/palshub/PalsHubApiService.ts`
(`createCheckoutSession`), `src/store/CheckoutFlowStore.ts` (the checkout state
owner + ASWebAuthenticationSession driver + reconcile poll),
`src/components/PalsHub/PalDetailSheet/PalDetailSheet.tsx`, and the custom
`ASWebAuthenticationSession` iOS native module.

When this doc and the code disagree, the code wins; the same PR that lands the
change updates this file.
