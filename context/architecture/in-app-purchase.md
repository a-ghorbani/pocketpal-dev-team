# In-App Purchase

## Purpose

Buying a paid PalsHub Pal through the platform store (StoreKit 2 on iOS, Play Billing on Android), turning the transaction into an installed Pal, and keeping ownership correct across crashes, refunds, withdrawals, creator updates and restore; and the PocketPal Plus entitlement, which is store-only and never touches PalsHub. Not covered: the Plus host, sidebar entry and back handling (`app-shell.md`), how a PalsHub Pal becomes a local Pal (`pals-and-talents.md`), the Pals grid (`pals-screen.md`), model selection (`model-loading.md`).

Voice mode's paywall is Plus: hands-free voice is the `handsFreeVoice` feature, read through `voiceEntitlement`'s default source, and a free user reaches this flow only from the locked-voice teaser's Get Plus (`voice-mode.md`).

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
| `src/services/iap/bindingSource.ts` | The Buy binding, fetched only for a signed-in Pal purchase |
| `src/services/plus/catalog.ts` | `PLUS_PRODUCT_IDS`, the only Plus product list, and `PLUS_FEATURES`, the bundled feature table |
| `src/services/plus/features.ts`, `deviceRam.ts`, `shipOverride.ts`, `shipped.ts` | Feature status rows, the one RAM read per process, the `__E2E__`-only "shipped" override; `shipped.ts` (`shippedPlusFeatures`, `plusFeatureRows`) is the one derived source the gate, sidebar item and screen read. Feature ids are typed as the `plus.features` keys of `en.json` |
| `src/services/plus/gate.ts` | `isPlusUnlocked`, `isPlusAvailable`, `openPlus`, `dismissPlus`, `plusGate.request` |
| `src/screens/PlusScreen/` | The Plus screen; `plusScreenState.ts` is its state table |
| `src/components/PlusHost/`, `src/components/SidebarContent/PlusDrawerItem/` | Global host and sidebar entry (`app-shell.md`) |
| `src/services/palshub/apiBase.ts`, `palEvents.ts` | API base and client headers; funnel events |
| `src/components/PalsHub/PalPurchaseFooter/` | Sheet footer: Buy (with the iOS US licence line), purchase phases, Open/Install, update prompt |
| `src/components/LicenseNotice/`, `src/config/urls.ts` | The two-link licence line shared by the Pal footer and the Plus screen (each caller passes its own Text component, styles, copy, first link and testIDs); `APPLE_MEDIA_TERMS_URL`, `APPLE_EULA_URL`, `REPO_URL` |
| `src/components/PalsHub/PalModelStep/` | Post-purchase model offer and Start chat |
| `src/screens/PalsScreen/myPals.ts`, `components/SquarePalCard/` | Owned sections and the Pending / Unlocking / Update badges |
| `src/screens/SettingsScreen/PurchasesCard.tsx` | Settings › Purchases |
| `src/__automation__/fakeStore.ts`, `adapters/IapAdapter.tsx` | e2e-only store and its Android command surface |
| `src/__automation__/plusShipOverride.ts`, `screens/PlusTestFeatureScreen.tsx` | e2e-only `plus_ship` verb and a locked test feature behind Plus |

## How it works

`App.tsx` calls `purchaseStore.start()`: kick `loadPlus()`, subscribe to app foreground, wait for `palStore.ready`, then `recover()`. Prod subscribes to store transactions lazily, at the first `storePort` use inside that first recovery; e2e subscribes at `start` through `setStore(fakeStore)`. Recovery inits billing, drives every open record's transaction through `processTransaction`, drops stale pending records, then refreshes, but only if the entitlement query succeeded.

**Buy**: binding (when signed in) → `store.purchase` → outcome. `purchased` → `processTransaction`; `pending` → `pending_payment`; `already_owned` → `installOwned`; `cancelled` / `error` close the sheet.

**processTransaction** is serialized per product: write `unlocking`, verify with the server, write the outcome, then finish the transaction. `drainQueue` installs a grant via `palStore.installOwnedPal`, moving it to `active`.

**Refresh** sends what the device holds; the server answers `changed` (newer creator version), `revoked` (refund), `removed` (withdrawn) or `unchanged`.

**Plus**. `processTransaction` sends a `PLUS_PRODUCT_IDS` transaction to `runPlus` on its own serialize key `'plus'` before any Pal code. Purchased: write the `plus-entitlement` doc unless a valid one is already on disk, then `finish` if `unfinished`. Pending: `plusPending`. After each recovery or restore query, Plus transactions and `reconcilePlus` run before the Pal loop. `buyPlus` → `store.purchase(id, null)`; `already_owned` delivers from a fresh `currentEntitlements()`. Features call `isPlusUnlocked()`, else `openPlus({onUnlocked})`; `PlusHost` shows the screen and runs `onUnlocked` after dismissal when unlocked.

```
locked ─deliver (purchased Plus tx, any tier)→ unlocked
unlocked ─clean query, no purchased Plus tx, revision unchanged→ locked
unlocked ─failed query | offline | sign-out | account deletion | already_owned→ unlocked
screen: purchased > paying > pending > billing unavailable > loading > no product > idle (+ error, licence, unsupported)
```

**Creator updates are opt-in.** A `changed` Pal whose content differs from `applied` becomes `pendingUpdate` and shows a badge; Update → Confirm runs `applyUpdate`, which writes only the creator-changed fields.

```
(none) ─pending→ pending_payment ─purchased→ unlocking ─verify active→ granted ─install→ active
unlocking ─verify fail/unavailable→ unlocking (backoff)
          ─unfulfillable / removed→ unfulfillable (terminal)
          ─revoked→ removed (tombstone)     ─invalid→ deleted, or held_invalid with a support code
active ─refresh revoked→ removed           ─refresh removed→ unfulfillable
active ─changed→ active + pendingUpdate ─Update confirmed→ active
removed ─new purchase→ unlocking (verify decides)   ─new pending purchase→ pending_payment
removed ─held purchase, settled verify active→ granted
unlocking ─Android, successful query no longer lists it→ deleted
```

## Contracts and invariants

- **One writer.** Only `PurchaseStore` writes the ledger (`purchase-ledger` in AsyncStorage), with awaited, serialized, full-document writes.
- **Status only moves forward.** Settled records (`granted`, `active`, `unfulfillable`, `held_invalid`, `removed`) never reopen; a failed verify never changes one. The one exception is a `removed` tombstone meeting a transaction it does not hold (its id is absent from `transactionIds`, or it has no id): that is a new purchase and runs the normal pipeline (`unlocking` or `pending_payment` → verify → retry → outcome → finish). A held transaction on a tombstone stays inert: no `unlocking`, no retry, and Android acknowledges it only after a settled verify `active`.
- **Every revoke ends buyable.** Refresh `revoked` and verify `revoked` (open pipeline, settled verify, held re-verify) all write the tombstone; Buy then renders, and a new purchase is verified like any other.
- **Persist before finish.** The outcome is written before `finishTransaction` (non-consumable, never consumed).
- **Android acknowledges only delivered purchases.** `finishTransaction` is the Play acknowledgement, so it runs only after a verify `active`, and on recovery for a delivered purchase Play still reports unacknowledged. Never for pending, failed, `removed`, `unfulfillable`, `revoked` or `invalid`: Play refunds an unacknowledged purchase after 3 days. iOS finishes every settled outcome.
- **Only Buy starts a payment.** Recovery, restore and Owned never call `store.purchase`.
- **Only an explicit server verdict removes ownership.** `revoked` → tombstone, `removed` → `unfulfillable`. Moderation rejection, a failed refresh, sign-out or account deletion, or a Pal missing from a list removes nothing.
- **Nothing automatic overwrites an installed Pal.** Only `applyUpdate` after Confirm writes an existing row, and it is bound to the shown version.
- **`content_version` is opaque.** It is the server's Pal `updated_at` string, stored and sent back verbatim. The device never orders versions; equality only. Verify carries it on the result; a refresh `changed` pal carries it as its raw `updated_at`.
- **Refresh body** is `{platform, transactions, known: {pal_id: {content_version, purchase_ref}}}` under a strict server parser: no extra fields. `content_version` is the pending version if any, else the applied one; with none it is `UNKNOWN_CONTENT_VERSION` (`'0'`), because an empty or missing value 400s the whole request. `purchase_ref` is the support code from the latest verify `active`; records without one stay out of `known`.
- **Request caps.** Verify and refresh send at most 10 (Android) / 50 (iOS) transactions and 200 `known` entries per request; `iapApi` chunks so each item is sent once, and merges. A revocation wins only for the same support code, so a refunded old purchase never removes a re-purchase.
- **A failed store query never refreshes or clears records.**
- **Buy renders only when** billing is ready, the Pal is IAP-enabled for this platform, the store returned a product, and the Pal has no ledger record other than a `removed` tombstone. Otherwise nothing renders. The price comes only from the store.
- **iOS US licence line.** Apple's DPLA (Att. 2 §3.2) requires US-storefront one-time IAP to say, before Buy, that the user buys a licence, with links to the terms incl. the Apple Media Services Terms. `StorePort.storefront()` returns StoreKit's storefront country code (ISO alpha-3, so `USA`, not `US`; iOS only, undefined elsewhere or on failure). `purchaseStore.showsLicenseNotice` is true on iOS when the storefront is `USA` or unknown (it fails open); the footer renders the line above Buy with links to palshub.ai Terms of Sale and Apple's terms. Android and other storefronts show nothing.
- **Purchase errors never change availability.** Availability comes from billing init alone.
- **Headers.** `X-IAP-Capable: 1` and `X-Client-Platform` go on every PalsHub request. Verify, refresh and events carry no `Authorization`.
- **Secrets.** Purchase tokens, JWS and binding values are never persisted or logged.
- **Web purchases are untouchable.** A local owned Pal with no ledger record is never refreshed, changed or deleted by this flow.
- **Account deletion ends library-only ownership**. It clears `palStore.userLibrary` (`clearAccountPals`), so a library Pal that is not installed stops counting in `isOwned` and `keptByLibrary`, and the next account never inherits it. Ledger ownership stays, and so does an installed paid Pal's `isLegacyInstall` ownership (the rule above). Deletion never touches the ledger or `local_pals` (`palshub-auth.md`).
- **FakeStore and the API-base override exist only under `__E2E__`**; CI greps the prod bundle for their markers. So do the Plus shipped override (`PLUS_SHIP_OVERRIDE`) and the Plus test feature (`PLUS_GATE_PROBE`).

Plus:

- **Store-only.** No Plus transaction reaches verify, refresh, link, `palEvents` or the ledger; Buy sends a null binding. PalsHub sees zero Plus traffic.
- **Persist before finish, never consume.** The doc write resolves before `finish` (only for `unfinished`); a failed write skips it, so recovery re-delivers. Pending is never finished. Delivery skips the write when a valid doc is already on disk (never judged from memory; a read that throws counts as absent), keeping the first `productId`/`unlockedAt`. It still bumps `plusRevision` and finishes an unfinished transaction.
- **Only a clean query relocks:** `ok`, no purchased Plus transaction listed, and `plusRevision` equal to the snapshot taken before the query. Memory clears before the doc delete.
- **Pending is memory-only.** Android re-derives it from each clean query; iOS clears it only on Restore.
- **Plus before Pal.** `recoverOnce` and `restore` settle Plus before the Pal loop; `dropStalePending` still gets every transaction.
- **Buy waits for `plusChecked`,** set by the first Plus step (any `ok`) or a recovery throw, never by a billing-init failure; also refused while unlocked, pending or paying.
- **`loadPlus` seeds once** and every Plus writer awaits it. `isPlusUnlocked()` is false until then; a boot-time reader awaits `purchaseStore.loadPlus()`.
- **One of each:** product list, check (`isPlusUnlocked`), availability (`isPlusAvailable`), entry (`openPlus`), host (`PlusHost`).
- **Availability gates UI, never the store.** With no shipped `PLUS_FEATURES` row: no sidebar entry, `openPlus` no-op; the store side still runs, so an owner is unlocked when a feature ships.
- **Feature status is bundled:** `PLUS_FEATURES` and device RAM (`minRamGb × 0.85 × 10⁹`) only; RAM-gated rows wait for the RAM read.
- **Hands-free voice ships** (pending PR; `voice-mode.md`), so `shippedPlusFeatures()` is never empty: the sidebar entry shows and `openPlus` opens. It has no `minRamGb`, so a failed RAM read never hides it. Whenever voice mode is off (`voiceModeStore.supported` false), its row is `optIn`: a short "Off" status with a second line under the name (a long status squeezed the name to zero width). The row's `reason` picks that line: `belowGate` (under the device gate, no Settings override) → "Off on this phone. Turn it on in Settings if you're brave."; `offInSettings` (supported phone, user turned it off, pending PR #1007) → "Turned off in Settings." `shipped.ts` derives the reason; `featureRows` takes it as a map, not a parallel flag. `optIn` still counts as runnable, so the screen keeps "Get Plus" and its normal subline. Voice opens Plus only from its locked-voice teaser (`voice-mode.md`). Above the prices (`plus-free-line`) the screen says "Plus is optional. Chatting stays free."
- **Restore** awaits the in-flight recovery (or runs one) when billing isn't ready, keeping `recoverOnce` the only availability writer, and resolves `{queryOk}`. The Plus screen disables Restore while restoring or paying.
- **The Plus product fetch** is single-flight, separate from the Pal fetch and outside `requestedProducts`. It starts only when billing becomes ready and when the Plus host opens (`openPlus` → `retryPlusProducts`), never from the PalsHub-driven `syncProducts`, and it asks only for missing IDs. The open-time retry sets `plusProductsLoading` before the first frame, and nothing retries while the screen is open. The fetch counts as loading only while no Plus price has loaded, so a missing ID never hides the loaded prices; the loading phase shows a spinner in the button slot.

## Traps and decisions

- **The e2e mock must follow the live server, not the app.** A mock built from the app's own assumptions passed every e2e run while every real refresh was a 400, and the same happened with the pal's version field. Change the mock only from the server's contract. Run a real-store licence-test purchase before trusting a wire change.
- **Play reports a declined card as `billing-unavailable`.** That is why purchase errors must not downgrade availability; doing so hid every Buy until relaunch.
- **Never exclude Gson on Android.** openiap-google uses it. Excluding it breaks billing at runtime, while builds and FakeStore e2e stay green. Only a real-store build proves a classpath exclude.
- **The library is event-based.** `requestPurchase` resolves before the outcome, so `NativeStore.purchase` waits for the matching event. The global listener sees the same purchase again; per-product serialization makes that a no-op.
- **iOS dedupes transaction events.** The purchase-scoped listener disables the dedupe so a re-buy can't hang `paying`. A 5 s fallback settles from the entitlement list.
- **iOS already-owned is inferred** from a transaction dated more than 60 s before the request. A misread is harmless, because it re-verifies.
- **Tombstones, not deletes.** The store keeps listing a refunded product; the `removed` record stops recovery re-driving its held transaction while leaving Buy available.
- **A tombstone tells purchases apart by transaction id.** Android's id is openiap's optional order id, absent on some purchases, so an id-less transaction counts as new and verify decides; `revoked` re-tombstones it. Cost: an id-less refunded purchase still listed and unacknowledged is re-verified on each recovery.
- **Already-owned on a refunded tombstone.** A Play refund without "Remove entitlement" keeps the purchase listed, so Buy answers `already_owned`. When the listed purchase leaves the record `removed`, Buy closes the sheet with `purchase_error`. When nothing is listed, `restore_needed` stays and the sheet stays open, because closing would end the session and wipe it.
- **Stale pending differs by platform.** Android drops it once a successful query no longer lists it, and clears `held_invalid` and `unlocking` the same way (snapshotted before the query, deleted only if the status is unchanged). An unverified `unlocking` purchase is one Play refunds after 3 days unacknowledged; its retry is cleared with it so a timer can't rewrite it from a dead token. A failed query drops nothing, and the drop never touches owned records. iOS ages it out after 72 h or on Restore, because a declined Ask to Buy emits nothing.
- **Account linking is off at launch.** The server has no link or binding endpoints, so purchases go unbound and the link UI is hidden.
- **A failed storefront lookup emits an id-less purchase error.** OpenIAP's `getStorefront` does this when `Storefront.current` is nil (e.g. no Apple ID). With no JS error listener attached, react-native-iap's iOS side buffers the error and flushes it to the first listener, which is the next Buy, so that Buy fails. `NativeStore.storefront` holds a no-op `purchaseErrorListener` across the lookup to drain it. The storefront is read once per process, after the first successful billing init, and never awaited: the Apple pay sheet triggers a foreground `recover()` while a purchase listener is live, so a re-read there could still settle that purchase as an error. A storefront switch mid-session takes effect on the next launch.
- **iOS needs glog's textual module map** (`ios/Podfile` `post_install`). Without it, NitroModules fails to build.
- **Labels follow the store apps.** The price alone on Buy; a progress indicator with no text while paying or unlocking; `Pending`; `Open` / `Install`; `Purchased`.
- **Plus traps**:
  - RAM factor 0.85, decimal: a phone sold with X GB reports under X GiB, and the next size down is at most 0.75 of it.
  - The revision snapshot exists because a delivery or pending purchase can land mid-query; that query must not relock or clear what it never saw.
  - `plusChecked` stops a reinstalling owner being offered Buy before recovery lists the purchase; a failed query releases it so offline users can buy.
  - A Play refund without "Remove entitlement" keeps Plus unlocked; a declined iOS Ask to Buy stays pending until Restore or relaunch.
  - A failed relock delete: locked this process, unlocked from the stale doc next launch until a clean recovery relocks.
  - `drainQueue` runs before the recovery query, so a granted Pal's install delays the Plus step.
  - Four products grant one entitlement; dropping to one is a one-line edit of `PLUS_PRODUCT_IDS`.
  - Android announces by live region and iOS by `announceForAccessibility`. The live region goes on the message Text: TalkBack never speaks a container View's live region when it mounts already filled (the buy error line was silent this way). Static lines carry none: a live region on the always-mounted speed line spoke it on every open. The in-development line is its own Text, mounted only while shown. The pending and unavailable notices carry one on their title. So Android speaks them on any open in that state, in no guaranteed order against the headline focus; this is accepted as status. iOS announces a pending buy result and the in-development line toggled on.
  - On Android, a `Pressable` with `accessibilityState.busy` and no `accessibilityLabel` reads "busy" and keeps it after busy ends: RN's `updateViewContentDescription` never resets an empty description. Busy controls carry a label, and the main button's variants are keyed so they never share a native view.
  - Only `HeaderLeft` fills the return-focus slot, and `PlusRequest` has no target. An opener inside a screen would therefore return focus to the hamburger on a locked dismiss. When the first such caller ships, add a return target to `PlusRequest` (e.g. `returnFocusTo`) that `PlusHost` uses before the slot.
  - Store prices must rise with the Plus ID suffix (`plus.1` < … < `plus.4`); tiles keep catalog order and preselect the first, which is the cheapest only because of this store-configuration rule.
- **iOS e2e can't see container testIDs.** XCUITest reports a plain container View as not visible, so specs wait on a visible leaf (`PalBuyPage.waitForReady`), not `purchase-ready`.

## Verification

- Jest: `src/store/__tests__/PurchaseStore.{pipeline,recover,link,update,accountDeletion,storefront}.test.ts`, `PurchaseStore.plus.test.ts` and `src/services/plus/__tests__/`, `src/services/iap/__tests__/` (including the exact refresh body), `PalStore.install.test.ts`, and the footer, model step and Purchases card tests.
- e2e: `e2e/specs/features/iap-{purchase,recovery,restore}.spec.ts`, run against the FakeStore and `e2e/helpers/iapMockServer.ts` (`adb reverse tcp:8787` on Android). `iap-plus.spec.ts` sets `plus_ship::<feature>` after every `reset` (which clears it and the saved Plus unlock) and asserts no Plus verify, refresh or event traffic.
- Plus by hand: an iOS sandbox and an Android licence-tester run of purchase from the host, slow card (pending), declined card, reinstall + Restore, and a Play Console refund with Remove entitlement (relock on the next foreground).
- By hand (Android): a prod build, sideloaded, signed in with a licence tester, against production. Buy with "always approves", the slow card (pending) and "always declines" (Buy must stay), reinstall + Restore, and a Play Console refund (the Pal locks on the next refresh, Buy returns, and buying again ends on Open). After a classpath change, check that Buy and the restore row appear on a real-store build.
