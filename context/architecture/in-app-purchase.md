# In-App Purchase

## Purpose

Buying a paid PalsHub Pal through the platform store (StoreKit 2 on iOS, Play Billing on Android), turning the transaction into an installed Pal, and keeping ownership correct across crashes, refunds, withdrawals, creator updates and restore. Not covered: how a PalsHub Pal becomes a local Pal (`pals-and-talents.md`), the Pals grid (`pals-screen.md`), model selection (`model-loading.md`).

## Code map

| Path | Role |
| --- | --- |
| `src/store/PurchaseStore.ts` | Ledger, availability, transaction pipeline, recovery, refresh, restore, creator updates. Sole writer of purchase state |
| `src/services/iap/StorePort.ts` | Store interface (types only) |
| `src/services/iap/NativeStore.ts` | Adapter over `react-native-iap`; the only file importing it |
| `src/services/iap/storeOutcomes.ts` | Library error code → `PurchaseOutcome` |
| `src/services/iap/iapApi.ts`, `iapWire.ts` | Verify / refresh HTTP with chunking; `iapWire` is the single parse and build point for wire shapes |
| `src/services/iap/creatorContent.ts` | Pure creator-content projection and field diff |
| `src/services/iap/accountLink.ts` | `ACCOUNT_LINK_ENABLED` (off at launch) |
| `src/services/palshub/apiBase.ts`, `palEvents.ts` | API base and client headers; funnel events |
| `src/components/PalsHub/PalPurchaseFooter/` | Sheet footer: Buy (with the iOS US licence line), purchase phases, Open/Install, update prompt |
| `src/components/PalsHub/PalModelStep/` | Post-purchase model offer and Start chat |
| `src/screens/PalsScreen/myPals.ts`, `components/SquarePalCard/` | Owned sections and the Pending / Unlocking / Update badges |
| `src/screens/SettingsScreen/PurchasesCard.tsx` | Settings › Purchases |
| `src/__automation__/fakeStore.ts`, `adapters/IapAdapter.tsx` | e2e-only store and its Android command surface |

## How it works

`App.tsx` calls `purchaseStore.start()`: subscribe to store transactions and app foreground, wait for `palStore.ready`, then `recover()`. Recovery inits billing, drives every open record's transaction through `processTransaction`, drops stale pending records, then refreshes, but only if the entitlement query succeeded.

**Buy**: binding (when signed in) → `store.purchase` → outcome. `purchased` → `processTransaction`; `pending` → `pending_payment`; `already_owned` → `installOwned`; `cancelled` / `error` close the sheet.

**processTransaction** is serialized per product: write `unlocking`, verify with the server, write the outcome, then finish the transaction. `drainQueue` installs a grant via `palStore.installOwnedPal`, moving it to `active`.

**Refresh** sends what the device holds; the server answers `changed` (newer creator version), `revoked` (refund), `removed` (withdrawn) or `unchanged`.

**Creator updates are opt-in.** A `changed` Pal whose content differs from `applied` becomes `pendingUpdate` and shows a badge; Update → Confirm runs `applyUpdate`, which writes only the creator-changed fields.

```
(none) ─pending→ pending_payment ─purchased→ unlocking ─verify active→ granted ─install→ active
unlocking ─verify fail/unavailable→ unlocking (backoff)
          ─unfulfillable / removed→ unfulfillable (terminal)
          ─revoked→ removed (tombstone)     ─invalid→ deleted, or held_invalid with a support code
active ─refresh revoked→ removed           ─refresh removed→ unfulfillable
active ─changed→ active + pendingUpdate ─Update confirmed→ active
removed ─verify active→ granted (re-purchase)
```

## Contracts and invariants

- **One writer.** Only `PurchaseStore` writes the ledger (`purchase-ledger` in AsyncStorage), with awaited, serialized, full-document writes.
- **Status only moves forward.** Settled records (`granted`, `active`, `unfulfillable`, `removed`) never reopen; a failed verify never changes one.
- **Persist before finish.** The outcome is written before `finishTransaction` (non-consumable, never consumed).
- **Android acknowledges only delivered purchases.** `finishTransaction` is the Play acknowledgement, so it runs only after a verify `active`, and on recovery for a delivered purchase Play still reports unacknowledged. Never for pending, failed, `removed`, `unfulfillable`, `revoked` or `invalid`: Play refunds an unacknowledged purchase after 3 days. iOS finishes every settled outcome.
- **Only Buy starts a payment.** Recovery, restore and Owned never call `store.purchase`.
- **Only an explicit server verdict removes ownership.** `revoked` → tombstone, `removed` → `unfulfillable`. Moderation rejection, a failed refresh, sign-out or a Pal missing from a list removes nothing.
- **Nothing automatic overwrites an installed Pal.** Only `applyUpdate` after Confirm writes an existing row, and it is bound to the shown version.
- **`content_version` is opaque.** It is the server's Pal `updated_at` string, stored and sent back verbatim. The device never orders versions; equality only. Verify carries it on the result; a refresh `changed` pal carries it as its raw `updated_at`.
- **Refresh body** is `{platform, transactions, known: {pal_id: {content_version, purchase_ref}}}` under a strict server parser: no extra fields. `content_version` is the pending version if any, else the applied one; with none it is `UNKNOWN_CONTENT_VERSION` (`'0'`), because an empty or missing value 400s the whole request. `purchase_ref` is the support code from the latest verify `active`; records without one stay out of `known`.
- **Request caps.** Verify and refresh send at most 10 (Android) / 50 (iOS) transactions and 200 `known` entries per request; `iapApi` chunks so each item is sent once, and merges. A revocation wins only for the same support code, so a refunded old purchase never removes a re-purchase.
- **A failed store query never refreshes or clears records.**
- **Buy renders only when** billing is ready, the Pal is IAP-enabled for this platform, the store returned a product, and there is no ledger record. Otherwise nothing renders. The price comes only from the store.
- **iOS US licence line.** Apple's DPLA (Att. 2 §3.2) requires US-storefront one-time IAP to say, before Buy, that the user buys a licence, with links to the terms incl. the Apple Media Services Terms. `StorePort.storefront()` returns StoreKit's storefront country code (ISO alpha-3, so `USA`, not `US`; iOS only, undefined elsewhere or on failure). `purchaseStore.showsLicenseNotice` is true on iOS when the storefront is `USA` or unknown (it fails open); the footer renders the line above Buy with links to palshub.ai Terms of Sale and Apple's terms. Android and other storefronts show nothing.
- **Purchase errors never change availability.** Availability comes from billing init alone.
- **Headers.** `X-IAP-Capable: 1` and `X-Client-Platform` go on every PalsHub request. Verify, refresh and events carry no `Authorization`.
- **Secrets.** Purchase tokens, JWS and binding values are never persisted or logged.
- **Web purchases are untouchable.** A local owned Pal with no ledger record is never refreshed, changed or deleted by this flow.
- **FakeStore and the API-base override exist only under `__E2E__`**; CI greps the prod bundle for their markers.

## Traps and decisions

- **The e2e mock must follow the live server, not the app.** A mock built from the app's own assumptions passed every e2e run while every real refresh was a 400, and the same happened with the pal's version field. Change the mock only from the server's contract. Run a real-store licence-test purchase before trusting a wire change.
- **Play reports a declined card as `billing-unavailable`.** That is why purchase errors must not downgrade availability; doing so hid every Buy until relaunch.
- **Never exclude Gson on Android.** openiap-google uses it. Excluding it breaks billing at runtime, while builds and FakeStore e2e stay green. Only a real-store build proves a classpath exclude.
- **The library is event-based.** `requestPurchase` resolves before the outcome, so `NativeStore.purchase` waits for the matching event. The global listener sees the same purchase again; per-product serialization makes that a no-op.
- **iOS dedupes transaction events.** The purchase-scoped listener disables the dedupe so a re-buy can't hang `paying`. A 5 s fallback settles from the entitlement list.
- **iOS already-owned is inferred** from a transaction dated more than 60 s before the request. A misread is harmless, because it re-verifies.
- **Tombstones, not deletes.** The store keeps listing a refunded product; the `removed` record stops recovery re-driving it.
- **Stale pending differs by platform.** Android drops it once a successful query no longer lists it, and clears `held_invalid` the same way. iOS ages it out after 72 h or on Restore, because a declined Ask to Buy emits nothing.
- **Account linking is off at launch.** The server has no link or binding endpoints, so purchases go unbound and the link UI is hidden.
- **A failed storefront lookup emits an id-less purchase error.** OpenIAP's `getStorefront` does this when `Storefront.current` is nil (e.g. no Apple ID). With no JS error listener attached, react-native-iap's iOS side buffers the error and flushes it to the first listener, which is the next Buy, so that Buy fails. `NativeStore.storefront` holds a no-op `purchaseErrorListener` across the lookup to drain it. The storefront is read once per process, after the first successful billing init, and never awaited: the Apple pay sheet triggers a foreground `recover()` while a purchase listener is live, so a re-read there could still settle that purchase as an error. A storefront switch mid-session takes effect on the next launch.
- **iOS needs glog's textual module map** (`ios/Podfile` `post_install`). Without it, NitroModules fails to build.
- **Labels follow the store apps.** The price alone on Buy; a progress indicator with no text while paying or unlocking; `Pending`; `Open` / `Install`; `Purchased`.
- **iOS e2e can't see container testIDs.** XCUITest reports a plain container View as not visible, so specs wait on a visible leaf (`PalBuyPage.waitForReady`), not `purchase-ready`.

## Verification

- Jest: `src/store/__tests__/PurchaseStore.{pipeline,recover,link,update}.test.ts`, `src/services/iap/__tests__/` (including the exact refresh body), `PalStore.install.test.ts`, and the footer, model step and Purchases card tests.
- e2e: `e2e/specs/features/iap-{purchase,recovery,restore}.spec.ts`, run against the FakeStore and `e2e/helpers/iapMockServer.ts` (`adb reverse tcp:8787` on Android).
- By hand (Android): a prod build, sideloaded, signed in with a licence tester, against production. Buy with "always approves", the slow card (pending) and "always declines" (Buy must stay), reinstall + Restore, and a Play Console refund (the Pal locks on the next refresh). After a classpath change, check that Buy and the restore row appear on a real-store build.
