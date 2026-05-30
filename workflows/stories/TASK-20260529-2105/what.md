# PalsHub Checkout — WHAT

New-flow delta. There is no existing flow doc for PalsHub purchase; this WHAT
introduces `context/architecture/palshub-checkout.md` (drafted alongside). On
promotion, the new flow doc lands in the same PR as the code.

Scope: **iOS only**. The new authenticated in-app checkout is added on the iOS
branch only. **US Android keeps the existing web path** (`Linking.openURL(
getPalBuyUrl)`) untouched — the buy button is gated on region (`isUSRegion`)
with **no** platform check today (C, `PalDetailSheet.tsx:325-327`), and
`isUSStorefront()` resolves true on Android (C, `region.ts:36-42`), so a US
Android user sees and uses the buy button right now. Android native checkout +
return is a **separate future slice** (its own ticket); this slice adds no
Android native config and no Android caller of the new flow.

**Return mechanism (revised, D11):** the checkout web flow is opened and its
callback captured by **`ASWebAuthenticationSession`** (callback URL scheme
`"pocketpal"`, ephemeral session). The earlier Universal-Link return is **dropped**
— iOS suppresses Universal Links that point back into the app from inside the
app's own `SFSafariViewController`, so the auto-return never fires. The callback
arrives through the session's completion promise, **not** the OS deep-link
pipeline. See §4d and the Review History.

**Conventions**: `(C)` current (verified from code), `(P)` proposal, `(D)`
decision ≤ 12-word rationale. Zero `(?)`.

---

## Drift check

`minor drift, repaired here` — the landed code implemented the Universal-Link
return (entitlement `applinks:palshub.ai` C `PocketPal.entitlements`; web-URL
forwarding in `AppDelegate.continueUserActivity` C `:64-82`; path route in
`useDeepLinking.ts:87-104`; `RETURN_HOST` coupling C `CheckoutFlowStore.ts:31`).
That return is **superseded** here; this WHAT removes it and re-targets the flow
doc to `ASWebAuthenticationSession`. The `pocketpal` URL scheme already exists in
`Info.plist:38-41` (C) — no new scheme registration is needed. `react-native-
webview@^13.16.1` (C `package.json:89`) is unrelated to checkout and is **not**
the browser dep (I2 still forbids it for payment).

---

## 1. Data model

No persisted schema change. Checkout is a transient in-memory flow; ownership
persists only through the existing library cache (`SyncService.syncUserLibrary`)
and is read live via `getPal().is_owned`.

```
CheckoutSession (in-memory, request/response only)        // (C)
  checkout_url       : string        // Stripe-hosted page — opened via ASWebAuthenticationSession
  session_url        : string        // alias of checkout_url; ignored client-side (D7)
  session_id         : string        // Stripe session id; carried in callback, telemetry only
  purchase_id        : string        // PalsHub purchase row id; parsed from callback (D9)
  platform_fee_cents : number        // display/telemetry only; not gating

CheckoutFlowState (in-memory, CheckoutFlowStore)          // (C)
  status   : 'idle' | 'creating' | 'browser_open'
           | 'finalizing' | 'owned' | 'processing_deferred' | 'cancelled' | 'error'
  palId    : string                  // pal whose checkout is in flight
  purchaseId? : string               // captured from CheckoutSession / callback (telemetry; reconcile uses palId)
  errorKind?  : '401' | '404' | '500' | 'network'
```

Persisted: nothing new. Derived: ownership is `getPal(palId).is_owned` (C,
`PalsHubService.ts:73`), surfaced into `PalDetailSheet` local `detailedPal`
state (C, `PalDetailSheet.tsx:44-48`).

**Glossary**:
- **Checkout callback** — the `pocketpal://checkout/{success|cancel}` custom-
  scheme URL that PalsHub's `/app-return/checkout/*` page **302-redirects** to. It
  is captured by `ASWebAuthenticationSession`, never by the OS deep-link pipeline.
  Host `checkout` namespaces the return under the shared `pocketpal://` scheme.
- **`success_url` / `cancel_url`** — `https://<HOST>/app-return/checkout/{success|cancel}`.
  These stay **https** because Stripe rejects custom schemes; `<HOST>` is now just
  a string inside the URL (no entitlement/host symmetry, D6).
- **Webhook-latency race** — the window between the user returning to the app and
  PalsHub's Stripe webhook flipping the purchase to owned (§3, §9c).
- **Reconcile poll** — bounded retry of the ownership check after success return.

### 1b. External shape

#### Request — `POST {PALSHUB_API_BASE_URL}/api/mobile/purchases`

```
headers:  Authorization: Bearer <access_token>     // (C) reuse PalsHubApiService getAuthHeaders, :161-162
          Content-Type: application/json
body:     {
            pal_id:               string,           // required
            success_url:          string,           // https://<HOST>/app-return/checkout/success
            cancel_url:           string,           // https://<HOST>/app-return/checkout/cancel
            selected_country_code?: string          // 2-letter only; omitted otherwise (§4a.3)
          }
```

#### Response 200

```
{ checkout_url, session_url, session_id, purchase_id, platform_fee_cents }
```

#### Error mapping (status → behaviour, §3 / §9)

| Status | Meaning | Client behaviour |
| --- | --- | --- |
| 200 | session created | open `checkout_url` via ASWebAuthenticationSession, enter `browser_open` |
| 400 | already owned | treat as success → `owned` (D2) |
| 401 | session invalid/expired | re-auth prompt, no browser (9a) |
| 404 | pal not purchasable | non-fatal "unavailable" message (9b) |
| 500 | server error | generic error, retry allowed (9d) |
| network | fetch threw | generic error, retry allowed (9d) |

#### Return path — captured callback `pocketpal://checkout/{success|cancel}`

Stripe redirects to `https://<HOST>/app-return/checkout/{success|cancel}` (its
`success_url`/`cancel_url`); that page **302-redirects** to
`pocketpal://checkout/{success|cancel}?purchase_id=...&session_id=...`.
`ASWebAuthenticationSession` matches the `"pocketpal"` callback scheme, dismisses
its sheet, and resolves with the callback URL string. The app matches host
`checkout` and the trailing `success` vs `cancel` segment, and reads the
`purchase_id` query param directly from that string (P) — no `DeepLinkService`, no `useDeepLinking`,
no OS URL-open notification. The session never resolving (user dismiss / session
error) is treated as cancel (I5, §3).

---

## 2. Event flow

```
buy-button press
  ├─ Platform.OS !== 'ios'  → Linking.openURL(getPalBuyUrl(palId))   // (C) unchanged web path (US Android)
  └─ Platform.OS === 'ios'  → authenticated checkout flow:            // (P, revised)
       createCheckoutSession(palId, {successUrl, cancelUrl, selectedCountryCode?})
         └─ 200 → ASWebAuthenticationSession.start(checkout_url, scheme:"pocketpal", ephemeral:true)
       user pays / cancels on Stripe-hosted page
       PalsHub /app-return/checkout/* page 302 → pocketpal://checkout/{success|cancel}?purchase_id=...
         └─ ASWebAuthenticationSession captures callback → dismisses sheet → resolves promise
            └─ store parses host + segment + purchase_id from callback URL → buy-flow:
               ├─ checkout/success → reconcile poll (§3)
               └─ checkout/cancel  → status:'cancelled' (silent)
       session rejected (user dismiss / error) → status:'cancelled' (silent, I5)
```

---

## 3. State machine (CheckoutFlowState.status)

```
idle ─press(iOS)→ creating ─200→ browser_open ─callback success→ finalizing
  creating ─400→ owned                                  finalizing ─is_owned→ owned
  creating ─401/404/500/network→ error                  finalizing ─exhausted→ processing_deferred
  browser_open ─callback cancel / dismiss / session err→ cancelled
  cancelled / owned / error / processing_deferred ─dismiss→ idle
```

| State | User-visible feedback |
| --- | --- |
| `idle` | normal buy button |
| `creating` | buy button shows loading spinner |
| `browser_open` | ASWebAuthenticationSession sheet is foreground; app shows nothing extra |
| `finalizing` | non-blocking "Finalizing your purchase…" indicator |
| `owned` | pal flips to owned; buy button → download button (existing logic) |
| `processing_deferred` | non-error "Processing — will unlock shortly" (relies on SyncService) |
| `cancelled` | quiet return, no message, button back to idle |
| `error` | actionable message per `errorKind` (§9) |

**Reconcile poll** (entered on a `checkout/success` callback): up to ~6
attempts over ~15–20s with backoff, calling
`palsHubService.checkPalOwnership(palId)` (C, `PalsHubService.ts:64`). **Error
semantics (I4)**: each attempt's outcome is one of (a) `owned===true`, (b)
`owned===false` (returned when no signed-in user, C `:68-70`), or (c) a thrown
`PalsHubError` (API/network failure, C `:80-86`). Outcomes (b) and (c) are both
**non-terminal** — the poll swallows them and proceeds to the next attempt. The
**first** `owned===true` ends the poll as `owned`. Exhausting all attempts for
**any** reason (all-false, all-thrown, or a mix) → `processing_deferred`,
**never** `error`. Poll is cancellable: a `reset()` (sheet close / new flow)
bumps the epoch and aborts in-flight attempts (I7).

---

## 4. Contract

### 4a. Buy flow rules (order matters)

1. Buy button visibility is unchanged: `palStore.isUSRegion && premium &&
   !is_owned` (C, `PalDetailSheet.tsx:325-327`). No region/visibility change.
2. On press, **branch on platform** (I1):
   - `Platform.OS !== 'ios'` → keep the existing
     `Linking.openURL(getPalBuyUrl(palId))` web path (C,
     `PalDetailSheet.tsx:331-332`). `getPalBuyUrl` (C, `palshub-display.ts:133`)
     is **retained** — it is the Android leg's only caller.
   - `Platform.OS === 'ios'` → call `createCheckoutSession` and drive
     CheckoutFlowState. This branch never reaches `Linking.openURL`.
3. `selected_country_code` is sent **only** when `getStorefrontCountryCode()`
   returns a value with `length === 2` (alpha-2). Alpha-3 ("USA", iOS 15) and
   `null` → field omitted; server IP fallback handles it (C region helper,
   `region.ts:12`; D3). This is a tax hint only — currency presentment is out of
   scope (Stripe Adaptive Pricing).
4. `checkout_url` is opened via **`ASWebAuthenticationSession`** with
   `callbackURLScheme:"pocketpal"` and `prefersEphemeralWebBrowserSession:true`,
   never an embedded WebView (I2, §4d). The session captures the custom-scheme
   callback and resolves with its URL.
5. On a `checkout/success` callback, run the reconcile poll (§3); never show a
   "failed" state purely because ownership has not yet propagated (I4).
6. On a `checkout/cancel` callback, OR on session dismissal/error, return to
   `idle` silently — no error (I5). The store cannot distinguish explicit cancel
   from user-dismiss; both are silent and identical.

### 4b. Hard invariants

- **I1 (iOS-only boundary, enforced by a platform gate)**: the new checkout flow
  is entered **only** under `Platform.OS === 'ios'`. The buy button itself stays
  visible on US Android (its region-only gate is unchanged), and on US Android
  the press continues to call `Linking.openURL(getPalBuyUrl)`. No Android caller
  of `createCheckoutSession` is added; no Android return leg is required.
- **I2 (no in-app-purchase WebView)**: the Stripe checkout is opened only via
  `ASWebAuthenticationSession` (system browser surface). No payment is ever
  completed inside an embedded `react-native-webview` (Apple 3.1.1).
- **I3 (Bearer reuse)**: the checkout request authenticates with the existing
  native Supabase session via the same `getAuthHeaders` path as all other
  PalsHub calls — no new token, JWT, or identity artifact is minted.
- **I4 (no false failure on webhook lag)**: any per-attempt reconcile failure
  (thrown OR `owned:false`) is non-terminal; only the first `owned===true` ends
  the poll as `owned`; exhausting attempts for any reason → `processing_deferred`
  (a success-track state), never `error`.
- **I5 (cancel is silent)**: a cancel callback, a user-dismiss, or a session
  error all produce no error UI and no ownership mutation; all map to `cancelled`.
- **I6 (callback is session-scoped)**: the success/cancel callback is delivered
  **only** through the `ASWebAuthenticationSession` completion promise of the
  in-flight checkout — never through the OS deep-link pipeline
  (`DeepLinkService`/`useDeepLinking`) and never via a Universal Link. A callback
  for a `reset()`/idle flow is ignored.
- **I7 (single in-flight checkout)**: at most one CheckoutFlowState / one live
  session is active; a return for a stale/closed flow is ignored (epoch guard),
  and a new press while `creating`/`finalizing` is a no-op (no double charge).
- **I8 (ownership is server-derived)**: the app never writes "owned" locally on
  return; it confirms via `getPal().is_owned` / library sync. Return only
  *triggers* reconciliation.

### 4c. Component renders / routing

| Component | Renders / does | Does NOT |
| --- | --- | --- |
| `PalDetailSheet` buy button | branch on `Platform.OS`; on iOS drive CheckoutFlowState and show `creating`/`finalizing`/result feedback; on non-iOS keep `Linking.openURL(getPalBuyUrl)` | open an anonymous browser on iOS; write ownership; add an Android native return path |
| `CheckoutFlowStore` | call createCheckoutSession; start ASWebAuthenticationSession; parse path + purchase_id from the resolved callback; drive reconcile | route via DeepLinkService; use a Universal Link; write ownership |
| ASWebAuthenticationSession native module | present the checkout URL, capture the `pocketpal` scheme callback, resolve/reject a promise | parse purchase semantics; touch reconcile state |

The OS deep-link path (`useDeepLinking` / `DeepLinkService`) is **not** part of
the checkout return and must not be wired for `pocketpal://checkout/*` (I6). No Android
manifest / `MainActivity` change is in scope. iOS `AppDelegate.continueUserActivity`
reverts to its original `return false` (§4d, §10).

### 4d. Browser dependency (constraint; exact pick deferred to HOW)

The iOS checkout URL must open in an **`ASWebAuthenticationSession`** — the
purpose-built primitive for "open a web flow in-app and capture a custom-scheme
callback." Required behaviour:

- Open via `ASWebAuthenticationSession`, `callbackURLScheme:"pocketpal"`,
  `prefersEphemeralWebBrowserSession:true` (ephemeral avoids the "wants to use X
  to sign in" consent prompt; shared Safari cookies are not needed because
  identity is already baked into the Stripe `checkout_url`).
- MUST resolve with the captured callback URL on the `pocketpal` scheme, and
  reject on user-dismiss / session error (mapped to silent cancel, I5).
- MUST NOT be `react-native-webview` (embedded WebView, I2), a plain
  `SFSafariViewController` open (cannot capture the callback — the Universal-Link
  trap this revision fixes), or a Universal Link.

**Native dep decision (D12, exact pick to HOW):** prefer a **thin custom
`ASWebAuthenticationSession` TurboModule** authored in this repo (the codebase
already has the Swift-module + `.m` bridge pattern, C `StorefrontModule.swift`/
`StorefrontModule.m`, `DeepLinkModule.swift`/`.m`), and **drop
`react-native-inappbrowser-reborn` entirely** (C `package.json:73` —
flagged a stale 2022 republish with no New-Arch declaration). Fall back to
`react-native-inappbrowser-reborn`'s `openAuth()` (which is
`ASWebAuthenticationSession`-backed) **only** if the custom module proves
disproportionate. Either way the surface is `ASWebAuthenticationSession`-backed
and callback-capturing.

---

## 5. Single-writer rule

| Field | Single writer |
| --- | --- |
| `CheckoutFlowState` | (C) `CheckoutFlowStore` (`store/CheckoutFlowStore.ts`) |
| ownership (`is_owned`) | **server** — read via `getPal()`; never written client-side (I8) |
| library cache rows | (C) `SyncService.syncUserLibrary` (`SyncService.ts:102`) |
| `palStore.isUSRegion` | (C) `PalStore.checkRegion` (`PalStore.ts:112-121`) — untouched |

Cross-store reads: buy-flow reads `palStore.isUSRegion` (gate) and calls
`palsHubService.checkPalOwnership` / `getPal` (reconcile). One direction only.

Past pain related to multi-writer races: none here (no local ownership write).
The relevant race is webhook latency, handled by §3 reconcile, not a writer race.

**Deferred cleanups** (out of scope):
1. Android (and EU) native checkout + return path — its own ticket. Android
   would need its own callback mechanism (Custom Tabs + intent, or its own
   ASWebAuthenticationSession analogue) that does not exist today.
2. Dedicated `GET /api/purchases/{purchase_id}` reconcile source. This slice
   reconciles via `checkPalOwnership` only (D9); a purchase-status endpoint, if
   added server-side later, can replace the poll source in a follow-up.
3. Currency/local-price presentment.

---

## 6. Canonical scenarios

### A. Happy path (iOS) — webhook already settled

```
US iOS, premium pal, not owned → tap Buy
─────
POST /purchases 200 → ASWebAuthenticationSession opens checkout_url → pay
/app-return/checkout/success page 302 → pocketpal://checkout/success → session resolves
→ finalizing → checkPalOwnership owned on attempt 1
→ status owned → buy button becomes download button
```

### B. Happy path (iOS) — webhook lag

```
session resolves on pocketpal://checkout/success → finalizing
→ checkPalOwnership false/thrown × 6 over ~18s
─────
status processing_deferred → "Processing — will unlock shortly"
SyncService.syncUserLibrary later reflects ownership; no error shown
```

### C. Cancel (iOS)

```
user dismisses the session sheet (or checkout/cancel callback)
─────
status cancelled (silent) → button back to idle, no error
```

### D. Already owned (400, iOS)

```
tap Buy → POST /purchases 400 "already own"
─────
treated as success → status owned (no session opened)
```

### E. Session expired (401, iOS)

```
tap Buy → POST /purchases 401
─────
no browser; prompt re-auth; flow → error(errorKind:'401'); retry after sign-in
```

### F. US Android — unchanged web path

```
US Android, premium pal, not owned → tap Buy
─────
Platform.OS !== 'ios' → Linking.openURL(getPalBuyUrl(palId)) → web product page
(no checkout session, no return leg — identical to today)
```

### G. App killed mid-checkout (iOS) — accepted behaviour

```
user force-quits while the ASWebAuthenticationSession sheet is open
─────
the session is torn down with the process; no callback, no cold-launch return
(ASWebAuthenticationSession is a contained session — there is NO cold-launch
Universal-Link return). On next app open, SyncService.syncUserLibrary reconciles
ownership; live getPal().is_owned reflects truth (I8). No error shown.
```

---

## 7. State signals

| Signal | Set by | Read by | True when |
| --- | --- | --- | --- |
| `isUSRegion` | `PalStore.checkRegion` | buy button gate | US storefront (C) |
| `Platform.OS` | RN | buy-press branch (I1) | `'ios'` selects checkout flow |
| `is_owned` | server (via `getPal`) | sheet button selection | user owns pal (C) |
| `CheckoutFlowState.status` | `CheckoutFlowStore` | buy button UI | per §3 |

---

## 8. Decisions

| ID | Decision | Rationale |
| --- | --- | --- |
| D1 | New flow doc `palshub-checkout.md`, not a delta on `pals-and-talents.md` | Purchase is a distinct flow from PACT/config |
| D2 | 400 "already own" → success, not error | User already owns it; opening Stripe is wrong |
| D3 | Send `selected_country_code` only when alpha-2 | Alpha-3/null → server IP fallback; avoids bad hint |
| D6 | `<HOST>` is a plain string in success/cancel URLs; no entitlement coupling | ASWebAuthenticationSession needs no host symmetry |
| D7 | Ignore `session_url`/`session_id` for opening | `checkout_url` is the only URL the session opens |
| D8 | Confirm ownership via server, no local write | Single source of truth is PalsHub (I8) |
| D9 | Reconcile via `checkPalOwnership` only; parse purchase_id from callback | Endpoint exists today; status route deferred |
| D10 | iOS-only via `Platform.OS` gate; US Android keeps web path | No Android callback mechanism; web path stays |
| D11 | Return via ASWebAuthenticationSession callback, not Universal Link | iOS suppresses ULs back into own SFSafariVC |
| D12 | Thin custom ASWebAuthenticationSession TurboModule; drop inappbrowser-reborn | Drop unneeded stale dep; codebase has module pattern |

---

## 9. Edge cases

| ID | Edge case | Behaviour |
| --- | --- | --- |
| 9a | 401 on create | no browser; re-auth prompt; `error('401')` (E) |
| 9b | 404 pal not purchasable | non-fatal "unavailable" message; back to idle |
| 9c | Webhook never lands within poll window | `processing_deferred`; SyncService backstops (I4, scenario B) |
| 9d | 500 / network on create | generic retryable error; no browser opened |
| 9e | User force-quits during checkout | session dies with process; no cold-launch return; SyncService reconciles on next open (scenario G, I8) |
| 9f | Callback arrives for a `reset()`/idle flow | ignored (I6, I7) |
| 9g | Double-tap Buy | second press is no-op while `creating`/`finalizing` (I7) |
| 9h | User dismisses the ASWebAuthenticationSession sheet | session rejects → silent `cancelled` (I5); indistinguishable from checkout/cancel |
| 9i | iOS 15 alpha-3 country code | field omitted; server IP fallback (D3) |
| 9j | palshub `/app-return/checkout/*` page not yet deployed / not redirecting to scheme | session never resolves; user dismiss → silent cancel; gated on palshub prod (cross-repo) |
| 9k | US Android taps Buy | unchanged web path via `getPalBuyUrl` (I1, scenario F) |

---

## Review History

| Round | Finding | Severity | Resolution |
| --- | --- | --- | --- |
| 1 | B1: WHAT replaced buy handler unconditionally on a false "Android never shows buy button" premise; US Android would enter a flow with no return leg | BLOCKER | FIXED — added `Platform.OS === 'ios'` gate (§2, §4a.2, I1, D10); US Android keeps `Linking.openURL(getPalBuyUrl)`; `getPalBuyUrl` retained; I1 rewritten as a platform-gate boundary, not a region-gate claim |
| 1 | B2: Android App-Link/return machinery is dead config — `onDeepLink` is iOS-only and cannot fire | BLOCKER | FIXED — removed all Android native config (intent-filter, MainActivity VIEW, assetlinks delivery) from §2/§4c/§10; Android checkout/return noted as a future slice (§5 deferred #1) |
| 1 | C3: system-browser library fully punted to HOW | CONCERN | FIXED — §4d constrains the dep; exact pick left to HOW |
| 1 | C4: reconcile error semantics unspecified | CONCERN | FIXED — §3 + I4 state that thrown OR owned:false are non-terminal; first owned===true ends as owned; exhaustion → processing_deferred, never error |
| 1 | S5: commit to checkPalOwnership; drop "if endpoint exists" branch | SUGGESTION | FIXED — D9 commits to `checkPalOwnership` |
| — | Post-impl design change: Universal-Link return doesn't fire — iOS suppresses ULs back into the app from inside its own SFSafariViewController; user would be stranded on the bounce page | DESIGN-CHANGE | RE-EMITTED — switched return to ASWebAuthenticationSession (callback scheme `pocketpal`, ephemeral); dropped applinks entitlement, AppDelegate UL wiring, `/app-return/*` deep-link route, RETURN_HOST coupling + old I6 host-symmetry, and the cold-launch return (9h); added D11, D12, new I6 (session-scoped callback), scenario G (kill → SyncService reconcile); native dep → custom ASWebAuthenticationSession TurboModule, drop inappbrowser-reborn (D12) |
