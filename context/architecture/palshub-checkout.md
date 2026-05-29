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
configured here (Android has no deep-link delivery: `DeepLinkService` is gated on
`Platform.OS === 'ios'`).

Convention:
- **(C)** = current behaviour, documented from code
- **(D)** = decision (was open, now resolved)

The canonical Universal-Link host is a **PLACEHOLDER** (`<HOST>`, currently
`palshub.ai`) pending confirmation of apex-vs-www; it is the single remaining
deferred value and is identical across the iOS entitlement and the JS return
URLs (I6, D6).

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
                 open checkout_url in SYSTEM in-app browser (SFSafariViewController) (C)
                   │  NOT an embedded WebView (Apple 3.1.1) — I2
                   ▼
                 Stripe-hosted checkout → user pays / cancels
                   ▼
                 PalsHub 302 → https://<HOST>/app-return/{success|cancel}        (C)
                   │  iOS Universal Link
                   ▼
                 OS hands control back to PocketPal
                   │  iOS: AppDelegate.continueUserActivity → RCTOpenURLNotification (C)
                   ▼
                 DeepLinkModule → onDeepLink → useDeepLinking PATH route /app-return/* (C)
                   ├─ success → reconcile poll (§4) → owned | processing_deferred
                   └─ cancel  → silent return (I5)
```

---

## 2. Data model

No persisted schema change. Checkout is transient; ownership persists only via
the existing library cache and is read live from the server.

```
CheckoutSession (request/response, in-memory)                     (C)
  checkout_url       : string   // Stripe page opened in system browser
  session_url        : string   // alias; ignored client-side (D7)
  session_id         : string   // Stripe id; unused by app today
  purchase_id        : string   // PalsHub purchase row; telemetry (reconcile keys on palId — D9)
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
  success_url:            "https://<HOST>/app-return/success",
  cancel_url:             "https://<HOST>/app-return/cancel",
  selected_country_code?: string          // 2-letter only (§5 rule 3)
}
```

**Response 200** — `{ checkout_url, session_url, session_id, purchase_id, platform_fee_cents }`

**Status mapping**

| Status | Meaning | Behaviour |
| --- | --- | --- |
| 200 | created | open `checkout_url` → `browser_open` |
| 400 | already owned | → `owned` (no browser) — D2 |
| 401 | session invalid | re-auth, no browser — `error('401')` |
| 404 | not purchasable | non-fatal "unavailable" |
| 500 / network | server/transport | generic retryable error |

**Return path (iOS)** — `https://<HOST>/app-return/{success|cancel}`, delivered as
`DeepLinkParams { scheme:'https', host:'<HOST>', url, queryParams }`
(C shape — `DeepLinkService.ts:11-21`). Routed by **path**, not host (D4),
because `host` already keys the `chat` route (C, `useDeepLinking.ts:83`). On
Android this channel does not exist (C, `DeepLinkService.ts:31`) — the Android
buy path stays on the web URL (I1).

### 2c. Glossary

- **Return URL** — `https://<HOST>/app-return/{success|cancel}`, registered as an
  iOS Universal Link.
- **`<HOST>`** — canonical PalsHub host (apex vs www **unconfirmed**, D6).
  Identical across iOS entitlement, success/cancel URLs (I6).
- **Webhook-latency race** — gap between user return and PalsHub's Stripe webhook
  marking the purchase owned.
- **Reconcile poll** — bounded ownership re-check after a success return (§4).

---

## 3. State machine

```
idle ─Buy press(iOS)→ creating
creating ─200→ browser_open      creating ─400→ owned
creating ─401/404/500/network→ error
browser_open ─return cancel→ cancelled
browser_open ─return success→ finalizing
finalizing ─is_owned→ owned      finalizing ─exhausted→ processing_deferred
{owned, cancelled, error, processing_deferred} ─dismiss→ idle
```

| State | User-visible feedback |
| --- | --- |
| `idle` | normal buy button |
| `creating` | buy button spinner |
| `browser_open` | system browser foreground; app shows nothing extra |
| `finalizing` | non-blocking "Finalizing your purchase…" |
| `owned` | pal flips owned; button → download (existing logic) |
| `processing_deferred` | non-error "Processing — will unlock shortly" |
| `cancelled` | quiet return, no message |
| `error` | actionable message per `errorKind` |

US Android does not enter this machine — its press goes straight to
`Linking.openURL(getPalBuyUrl)` (I1).

---

## 4. Reconcile lifecycle (webhook-latency race)

Entered on `/app-return/success`. Up to ~6 attempts over ~15–20s with backoff,
each calling `palsHubService.checkPalOwnership(palId)` (C, `PalsHubService.ts:64`,
which delegates to `getPal().is_owned`).

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
`error`. The poll is cancellable: leaving the sheet or backgrounding the app
aborts in-flight attempts (I7). The app never writes ownership locally — it only
*triggers* a server re-read (I8). This slice reconciles via `checkPalOwnership`
only (D9); a dedicated `GET /api/purchases/{purchase_id}` source is deferred.

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
4. `checkout_url` opens in a system browser (SFSafariViewController), never an
   embedded WebView (I2, §5c).
5. `/app-return/success` → reconcile poll (§4). `/app-return/cancel` → silent
   idle (I5).

### 5a. Hard invariants

- **I1 (iOS-only boundary via platform gate)**: the new checkout flow is entered
  **only** under `Platform.OS === 'ios'`. The buy button stays visible on US
  Android (region-only gate unchanged), and US Android presses keep calling
  `Linking.openURL(getPalBuyUrl)`. No Android caller of `createCheckoutSession`
  and no Android return leg is added (Android deep-link delivery does not exist,
  C `DeepLinkService.ts:31`).
- **I2 (no IAP WebView)**: Stripe checkout opens only in the OS system browser;
  no purchase is ever completed in an embedded `react-native-webview` (Apple 3.1.1).
- **I3 (Bearer reuse)**: checkout authenticates via the existing native Supabase
  session (`getAuthHeaders`); no new token/JWT/identity artifact is minted.
- **I4 (no false failure on webhook lag)**: any per-attempt reconcile failure
  (thrown OR `owned:false`) is non-terminal; first `owned===true` → `owned`;
  exhaustion (any reason) → `processing_deferred` (success track), never `error`.
- **I5 (cancel is silent)**: a cancel return shows no error UI and mutates no
  ownership.
- **I6 (host symmetry, iOS)**: `<HOST>` is identical across the iOS `applinks:`
  entitlement, `success_url`, and `cancel_url`.
- **I7 (single in-flight checkout)**: at most one CheckoutFlowState per sheet;
  stale-flow return events are ignored; a press while `creating`/`finalizing`
  is a no-op.
- **I8 (ownership is server-derived)**: ownership is read from
  `getPal().is_owned` / library sync, never written locally on return.

### 5b. What each component does

| Component | Owns | Does NOT |
| --- | --- | --- |
| `PalDetailSheet` buy button | branch on Platform.OS; on iOS drive CheckoutFlowState + show creating/finalizing/result; on non-iOS keep `Linking.openURL(getPalBuyUrl)` | open the anonymous browser on iOS; write ownership; add Android return path |
| buy-flow owner (hook/handler, iOS) | call createCheckoutSession; open system browser; run reconcile | persist ownership; touch region gate |
| `PalsHubApiService.createCheckoutSession` (C) | POST /api/mobile/purchases with Bearer; map statuses | render; hold flow state |
| `useDeepLinking` | path route `/app-return/*` alongside `host:'chat'` (C :83) | repurpose host route for app-return |
| iOS `AppDelegate.continueUserActivity` (C) | forward Universal-Link URL via RCTOpenURLNotification | parse purchase semantics |
| iOS `DeepLinkModule` | emit `onDeepLink` for the https URL (C path works once posted) | interpret app-return semantics |
| `SyncService.syncUserLibrary` | (C) library cache backstop for deferred ownership | drive checkout |

### 5c. System-browser dependency

The iOS checkout URL opens in OS browser chrome — an `SFSafariViewController`-
backed in-app browser, never `react-native-webview` (an embedded WebView
forbidden by I2). The dependency is `react-native-inappbrowser-reborn@3.7.1`
(C), opened via `InAppBrowser.open(checkout_url)`. It is a legacy bridge module
(no codegen), verified to build and resolve the native module under this app's
New Architecture (RN 0.82.1, `RCT_NEW_ARCH_ENABLED=1`) through the bridgeless
interop layer.

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
US iOS premium !owned → Buy → 200 → SFSafariVC → pay
return /app-return/success → finalizing → owned on attempt 1 → download button
```

### B. Happy path (iOS) — webhook lag

```
return success → finalizing → false/thrown ×6 (~18s) → processing_deferred
SyncService later reflects ownership; no error
```

### C. Cancel (iOS)

```
dismiss Stripe → return /app-return/cancel → cancelled (silent) → idle
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

---

## 8. Decisions

- **D1** — Net-new flow doc, not a section of `pals-and-talents.md`. Purchase is
  a distinct concern from PACT/config; mixing them would couple two lifecycles.
- **D2** — `400 "already own"` is treated as success (`owned`), not error. The
  user already owns the pal; opening Stripe would be wrong.
- **D3** — `selected_country_code` sent only when alpha-2. Alpha-3 ("USA", iOS 15)
  and `null` are omitted; server IP fallback handles them. It is a tax hint only.
- **D4** — `/app-return/*` is routed by path, not host. `host` already keys the
  `chat` deep-link route, and all Universal Links share `<HOST>`.
- **D5** — Reconcile exhaustion maps to `processing_deferred`, never `error`.
  Webhook propagation lag is expected behaviour, not a failure (I4).
- **D6** — `<HOST>` ships as a clearly-marked placeholder. Apex-vs-www is
  unconfirmed; everything except the final host string can be built now.
- **D7** — `session_url` / `session_id` are ignored client-side; `checkout_url`
  is the only URL the app opens.
- **D8** — Ownership is confirmed via the server, never written locally on return
  (I8). PalsHub is the single source of truth.
- **D9** — Reconcile uses `checkPalOwnership` only this slice; a dedicated
  purchase-status endpoint is deferred (§10 cleanups).
- **D10** — iOS-only via `Platform.OS` gate; US Android keeps the web path.
  Android deep-link delivery is iOS-only, so there is no Android return leg.

---

## 9. Edge cases

| ID | Edge case | Behaviour |
| --- | --- | --- |
| 9a | 401 on create (iOS) | no browser; re-auth; `error('401')` |
| 9b | 404 not purchasable (iOS) | non-fatal "unavailable"; back to idle |
| 9c | Webhook never lands in poll window | `processing_deferred`; SyncService backstop (I4) |
| 9d | 500 / network on create (iOS) | generic retryable error; no browser |
| 9e | Force-quit during Stripe page | no return event; next sheet open reflects live `is_owned` (I8) |
| 9f | Return for closed/stale sheet | ignored (I7) |
| 9g | Double-tap Buy (iOS) | no-op while creating/finalizing (I7) |
| 9h | Cold-launch via return URL (iOS) | `DeepLinkModule.getInitialURL` delivers it (C :94-101); same path route |
| 9i | iOS 15 alpha-3 country | field omitted (D3) |
| 9j | `<HOST>` association file not yet deployed | OS opens URL in Safari, not app; reconcile won't auto-trigger — gated on palshub prod deploy |
| 9k | US Android taps Buy | unchanged web path via `getPalBuyUrl` (I1) |

---

## 10. Native gaps closed by this flow (iOS only)

These were previously unwired and are now closed (C):

1. iOS `AppDelegate.application(_:continue:restorationHandler:)` forwards the
   `NSUserActivity` web URL (when `activityType == NSUserActivityTypeBrowsingWeb`)
   into the existing `RCTOpenURLNotification` path so `DeepLinkModule` emits
   `onDeepLink` (C, `AppDelegate.swift`). It previously returned `false`.
2. `applinks:<HOST>` is present in `ios/PocketPal/PocketPal.entitlements` (C);
   `<HOST>` matches `RETURN_HOST` in `CheckoutFlowStore.ts` (I6).

This makes iOS natives `NATIVE_CHANGES=YES`: pod install + iOS build (and an
Android build to confirm no regression on the unchanged Android path) are
required before the work is ready.

**Out of scope (future Android slice):** Android App-Link config — an
`autoVerify` VIEW intent-filter in `AndroidManifest.xml`, `MainActivity`
`onNewIntent`/VIEW handling, and the JS-side Android deep-link delivery — is
**not** added here. Android `MainActivity` has only a LAUNCHER intent-filter
today (C, `AndroidManifest.xml`) and `DeepLinkService` is iOS-gated (C
`DeepLinkService.ts:31`), so any Android return config would be dead with no
caller. The palshub-side `assetlinks.json` is authored separately (cross-repo)
and stays referenced as future-Android; this PocketPal slice adds no Android
native config.

---

## 11. Cross-references

- **`pals-and-talents.md`** — Pal config surface (PACT/greeting); ownership-gated
  content rendering is `shouldShowPalContent` (C, `palshub-display.ts:120`).
- **`DeepLinkService.ts` / `useDeepLinking.ts`** — deep-link delivery (iOS-only)
  and routing.
- **`SyncService.ts`** — library cache; the deferred-ownership backstop (§4).

Source of truth in code: `src/services/palshub/PalsHubApiService.ts`
(`createCheckoutSession`), `src/store/CheckoutFlowStore.ts` (the checkout state
owner + reconcile poll), `src/components/PalsHub/PalDetailSheet/PalDetailSheet.tsx`,
`src/services/DeepLinkService.ts` (deep-link delivery, iOS-only) and
`src/hooks/useDeepLinking.ts` (routing), `ios/PocketPal/AppDelegate.swift`,
`ios/PocketPal/PocketPal.entitlements`.

When this doc and the code disagree, the code wins; the same PR that lands the
change updates this file.
