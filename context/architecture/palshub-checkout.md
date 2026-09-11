# PalsHub Checkout

## Purpose

Buying a premium PalsHub Pal in-app and confirming ownership, on iOS and US Android. Not covered: Pal configuration (`pals-and-talents.md`), discovery (`explore-tab.md`), library download and sync (`SyncService`, `PalStore`), and EU checkout (not built).

## Code map

| Path | Role |
| --- | --- |
| `src/store/CheckoutFlowStore.ts` | Sole owner of checkout state, the `isAllowedCheckoutUrl` trust gate, reconcile, and the Android report |
| `src/services/palshub/PalsHubApiService.ts` | `createCheckoutSession()`: `POST /api/mobile/purchases`; maps the error statuses |
| `src/services/palshub/PalsHubService.ts` | `checkPalOwnership()` / `getPal()`: server-side ownership (`is_owned`) |
| `src/store/PalStore.ts` | `checkCheckoutEligibility()`: sole writer of `isCheckoutEligible` |
| `src/utils/region.ts` | `isUSStorefront()`: the iOS eligibility signal (StoreKit storefront) |
| `src/components/PalsHub/PalDetailSheet/PalDetailSheet.tsx` | Buy button, `handleBuyPress`, checkout feedback; calls `reset()` on close |
| `src/specs/NativeAuthSession.ts` | `openAuth(url, scheme) → Promise<callbackUrl>`; optional TurboModule |
| `src/specs/NativeExternalContentLink.ts` | Android-only Play External Content Links spec; `null` on iOS |
| `ios/PocketPal/AuthSessionModule.swift` (+ `.m`) | `ASWebAuthenticationSession`, ephemeral |
| `android/app/src/main/java/com/pocketpalai/AuthSessionModule.kt` | Chrome Custom Tab; resolves the promise from the callback intent |
| `android/app/src/main/java/com/pocketpalai/ExternalContentLinkModule.kt` | Availability probe, link-out prep, report (Billing 8.2.1) |
| `android/app/src/main/java/com/pocketpalai/MainActivity.kt` | `onNewIntent` → `forwardCheckoutCallback` |
| `android/app/src/main/java/com/pocketpalai/MainApplication.kt` | Registers `AuthSessionPackage` and `ExternalContentLinkPackage` by hand |
| `android/app/src/main/AndroidManifest.xml` | BROWSABLE `pocketpal://checkout` filter, separate from `host=hub` |

## How it works

At init, `PalStore.checkCheckoutEligibility()` sets `isCheckoutEligible`: iOS uses `isUSStorefront()`, Android uses `isExternalContentLinkAvailable()`. `PalDetailSheet` shows Buy only when the flag is true and the Pal is premium and not owned. Otherwise it shows `getPremiumInfoText()`.

`handleBuyPress` sends a signed-out user to `onSignInPress`; otherwise it calls `checkoutFlowStore.start(palId)` on both platforms.

`start()` calls `createCheckoutSession` with `success_url`/`cancel_url` = `${PALSHUB_API_BASE_URL}/app-return/checkout/{success|cancel}` and checks `checkout_url` against `isAllowedCheckoutUrl`. Then:

- **Android:** `start()` calls `prepareExternalLink(checkout_url)`. That runs eligibility, then mints a fresh token, then calls `launchExternalLink`, during which Play shows its own disclosure. Only the outcome `launched` continues.
- **Both platforms:** `openAuth(checkout_url, 'pocketpal')` opens the page. The PalsHub `/app-return` page 302-redirects to `pocketpal://checkout/{success|cancel}?purchase_id=…`. The session captures that URL and resolves the promise with it.

`openAuthAndHandle` parses the host and last path segment. `success` runs `reconcile()`: 6 `checkPalOwnership` attempts after waits of 1, 2, 3, 4, 4, 4 s (18 s). On `owned`, the sheet re-reads `getPal` so Buy flips to Download.

```
idle → creating ─200→ [Android: linking] → browser_open ─success→ finalizing → owned | processing_deferred
creating ─400 already-owned→ owned        creating ─401/404/500/other→ error(kind)
linking ─user_canceled|ineligible→ cancelled        linking ─error→ error('network')
browser_open ─cancel / dismiss / reject→ cancelled
any ─reset() (sheet close)→ idle
```

## Contracts and invariants

- **Only `CheckoutFlowStore` writes checkout state.** Ownership is never written on the client: it is always re-read from the server (`getPal().is_owned`).
- **The epoch guards every async step.** `reset()` bumps `epoch`. `start()`, `openAuthAndHandle()` and each `reconcile()` attempt re-check the epoch after every `await`, so a late create, prep, callback or poll result is dropped (`CheckoutFlowStore.ts`).
- **One checkout at a time.** `start()` does nothing while `isInFlight` (`creating | linking | browser_open | finalizing`), and the Buy button is disabled then. Android's `openAuth` also rejects a second call while one is pending.
- **Cancel is silent.** A cancel callback, the user dismissing the page, a session error, and a prep outcome of `user_canceled` or `ineligible` all end in `cancelled`, with no error UI.
- **A failed poll attempt is never an error.** `owned:false` and thrown errors are both non-terminal. The first `owned === true` wins, and running out of attempts gives `processing_deferred`, never `error`.
- **Only an explicit already-owned 400 counts as success.** `createCheckoutSession` maps a 400 with `code: already_owned` or a message matching `/already own/i` to `already_owned` (→ `owned`, no browser); any other 400 is `network`. `errorKind` `401` shows `checkout-signin-button`, and `404` shows "not available".
- **The trust gate.** Only `https` URLs on `stripe.com` / `*.stripe.com` or the PalsHub API host reach the in-app browser; a rejected `checkout_url` ends in `error('network')`. The one `__E2E__` exception skips the https check on the PalsHub host, for the LAN test harness. `PalStore` also forces `isCheckoutEligible = true` under `__E2E__`.
- **Eligibility is the store's purchase signal, never device locale,** and fail-closed (null module or exception → `false`). `isExternalContentLinkAvailable` is side-effect-free: no token, no launch, no `currentActivity`; those happen only in `prepareExternalLink`.
- **Android External Content Links token.** Minted fresh per link-out (Google forbids reuse), never cached, returned only on `launched`. The report fires only after reconcile reaches `owned`, never on the already-owned path; it is fire-and-forget, never changes state, and is a logged no-op today.
- **The callback is scoped to the session.** It is consumed only through the `openAuth` promise, never through `DeepLinkService` or a Universal Link. On Android, `MainActivity.onNewIntent` calls `super.onNewIntent` before forwarding, so the URL also reaches RN Linking's `url` event; that is harmless only because `useDeepLinking` acts on `hub`/`chat` hosts alone. Keep `checkout` out of it.
- **The request reuses the Supabase session** (`getAuthHeaders()`) and sends no country hint; Stripe takes the tax location from the billing address.

## Traps and decisions

- **Never use an embedded WebView for payment** (Apple guideline 3.1.1). Use `ASWebAuthenticationSession` on iOS and a Chrome Custom Tab on Android.
- **Never use a Universal Link for the return.** iOS suppresses a Universal Link that points back into the app from the app's own `SFSafariViewController`, so the return never fired. The fix is the custom-scheme callback captured by the session. That is why `AppDelegate.continue userActivity` returns `false` and `PocketPal.entitlements` has no `applinks`. Don't re-add either.
- **`success_url`/`cancel_url` must be https** (Stripe rejects custom schemes); the palshub repo's `/app-return/checkout/*` page does the 302 to `pocketpal://`. If it isn't deployed, the session never resolves and the user's dismiss reads as a silent cancel.
- **iOS uses an ephemeral session.** That avoids the system "wants to use … to sign in" prompt, and no Safari cookies are needed. If `session.start()` returns `false`, the module rejects: otherwise the promise would hang forever.
- **Android back-out detection.** `onHostResume` with a promise still pending means the user left the Custom Tab, so the module rejects one main-loop tick later (`mainHandler.post`), letting a racing `onNewIntent` resolve win. `handleIntent` consumes only `pocketpal://checkout` while a promise is pending; anything else falls through to `setIntent`.
- **Play shows the disclosure.** The app must render none: a sheet of its own would prompt twice and break the program's rules. The user declining it shows up as `USER_CANCELED`. There is also no `Linking.openURL` web-buy path on either platform; don't re-add one for ineligible users.
- **Prep outcomes are not symmetric.** In `prepareExternalLink`, a billing setup failure, a failed token mint or a missing activity is `error`; a program-availability result other than `OK`, or `launchExternalLink` returning `BILLING_UNAVAILABLE`, is `ineligible`. In the probe, any setup failure is `false`.
- **Null modules fail quietly.** A null auth-session module is a silent cancel; a null External Content Links module skips prep and opens the tab directly. Fail-closed eligibility normally hides Buy first, but `__E2E__` forces eligibility, so a missing `getPackages()` registration goes unnoticed there.
- **Reconcile keys on `palId`** (`checkPalOwnership`), not on `purchase_id`. `purchaseId` comes from the create response, not the callback URL, and only the report uses it.
- **A force-quit gets no cold-launch return.** The sheet's `getPal` on next open shows the right ownership, and the library cache catches up via `syncService.syncAll()` on `PalsScreen` mount (throttled to 5 min).
- **Thin custom native modules, not libraries.** `react-native-inappbrowser-reborn` is stale with no New-Architecture support; `expo-web-browser` pulls in `expo-modules-core`.
- **Still to verify live:** Play Console confirmation of the program and its reports, and a Google Pay round-trip on a real US device.

## Verification

- Jest: `src/store/__tests__/CheckoutFlowStore.test.ts`, `PalStore.test.ts`; `src/services/palshub/__tests__/PalsHubApiService.test.ts`, `PalsHubService.test.ts`; `src/components/PalsHub/PalDetailSheet/__tests__/PalDetailSheet.test.tsx`; `src/hooks/__tests__/useDeepLinking.test.ts` (checkout is not a deep link).
- e2e: `e2e/specs/features/purchase-flow.spec.ts` + `e2e/pages/PalPurchasePage.ts` against the palshub test harness. Needs an `E2E_BUILD` build and `E2E_PALSHUB_*`, `E2E_API_KEY`, `E2E_BUYER_*`. Frozen testIDs: `palshub-pal-card-<id>`, `buy-button`, `download-button`, and `AuthSheet`'s `email-input`, `password-input`, `auth-submit-button`. On an emulator Play may return `ineligible`/`error` before the tab opens.
- By hand, on a US device: Buy → pay → Download appears; dismiss the page → silent return; close the sheet mid-checkout → no stray tab.
