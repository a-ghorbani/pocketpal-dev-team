# Implementation Plan: US iOS PalsHub checkout — switch return to ASWebAuthenticationSession

Executable worklist for `what.md` + `context/architecture/palshub-checkout.md`. Section
refs (§N, In, Dn, scenario X) point at those two docs — design is not re-derived here.

This is a **revision against already-landed code**. The committed branch implemented the
**Universal-Link** return (entitlement, AppDelegate UL forwarding, `/app-return/*` deep-link
route, `RETURN_HOST` coupling, `react-native-inappbrowser-reborn`). The WHAT now mandates an
**`ASWebAuthenticationSession`** callback (scheme `"pocketpal"`, ephemeral). Each step below
is tagged **ADD/CHANGE** or **REMOVE**; REMOVE steps delete now-dead code rather than orphan it.

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
- **Status**: revised — re-planning against landed Universal-Link code

---

## Progress

| Step | Status | Commit | Notes |
| --- | --- | --- | --- |
| Step 1 (native module + spec, GATE) | DONE | 4a7c585 | ADD ASWebAuthenticationSession TurboModule + spec + pbxproj wiring |
| Step 2 (store: open via module) | DONE | 2e14182 | openAuth + parse callback; dropped InAppBrowser + exported RETURN_HOST |
| Step 3 (revert AppDelegate UL) | DONE | 7162c3c | continueUserActivity reverted to `return false` |
| Step 4 (drop applinks entitlement) | DONE | 7162c3c | associated-domains block removed |
| Step 5 (drop /app-return deep-link route) | DONE | 7162c3c | useDeepLinking checkout branch + checkoutFlowStore import removed |
| Step 6 (drop inappbrowser dep) | DONE | 7162c3c | dep + pod + jest mapper + mock removed |
| Step 7 (tests) | DONE | 04830d0 | module mock + openAuth resolve/reject paths; dead UL `it` blocks removed |
| Step 8 (arch-doc promote) | DONE | (control-plane) | already (C); neutralized lone Linear mention; zero (?) |
| Native verification (GATE) | DONE | - | pod install (RNInAppBrowser gone) + iOS Release New-Arch build + Android Release |

---

## What changed vs the prior HOW (add / remove summary)

**ADD / CHANGE**
- New thin native module `AuthSessionModule` (Swift + `.m`) wrapping
  `ASWebAuthenticationSession`, plus its codegen spec `src/specs/NativeAuthSession.ts`
  (mirrors `StorefrontModule` + `NativeStorefront`). Step 1, now the load-bearing GATE.
- `CheckoutFlowStore.start()` opens `checkout_url` via the module's `openAuth(url, "pocketpal")`
  and parses path + `purchase_id` from the **resolved callback URL string**, then drives the
  existing reconcile poll. The store's `onReturn`/reconcile machine is reused, now called
  inline from the promise instead of from `useDeepLinking`.

**REMOVE (now dead under the session-callback mechanism)**
- `react-native-inappbrowser-reborn` (package.json, yarn.lock, ios/Podfile.lock) + jest mapper +
  `__mocks__/external/react-native-inappbrowser-reborn.ts`.
- `applinks:` associated-domains block in `ios/PocketPal/PocketPal.entitlements`.
- `AppDelegate.continueUserActivity` web-URL forwarding → revert to original `return false`.
- `useDeepLinking` `/app-return/*` path route + its two dead UL `it` blocks
  (`useDeepLinking.test.ts:299-323`). The `checkoutFlowStore` import (`:22`) and the
  chat-host regression test (`:325-336`) are KEPT. DeepLinkService/DeepLinkModule are no
  longer part of the checkout return.
- `RETURN_HOST` constant in `CheckoutFlowStore.ts` + its assertions (`CheckoutFlowStore.test.ts:64-69`).

**KEEP unchanged** (no step touches these): `createCheckoutSession` / `POST /api/mobile/purchases`
(Bearer, status map, 400→`already_owned`); the `Platform.OS` iOS-only gate (Android keeps
`Linking.openURL(getPalBuyUrl).catch`); the reconcile state machine + I4 error semantics;
alpha-2 `selected_country_code` gate; the 401 re-auth surface via `PalsScreen onSignInPress`;
server-derived ownership. `PalDetailSheet` already consumes store state — no UI change needed.

---

## Affected files

| Path | Change | Design ref |
| --- | --- | --- |
| `ios/PocketPal/AuthSessionModule.swift` | **add** — ASWebAuthenticationSession wrapper | §10, §4d, D12 |
| `ios/PocketPal/AuthSessionModule.m` | **add** — `RCT_EXTERN_MODULE` bridge | §10, D12 |
| `src/specs/NativeAuthSession.ts` | **add** — TurboModule spec (New-Arch JS surface) | §4d |
| `src/store/CheckoutFlowStore.ts` | **change** — open via module, parse callback; drop InAppBrowser + RETURN_HOST | §1b return, §2, §4a.4-6, I6 |
| `ios/PocketPal/AppDelegate.swift` | **remove** — revert `continueUserActivity` to `return false` | §10 removed |
| `ios/PocketPal/PocketPal.entitlements` | **remove** — `applinks:` associated-domains block | §10 removed, D6 |
| `src/hooks/useDeepLinking.ts` | **remove** — `/app-return/*` branch + `checkoutFlowStore` import | §4c, I6, §10 removed |
| `package.json`, `yarn.lock`, `ios/Podfile.lock` | **remove** — `react-native-inappbrowser-reborn` | §5c (dropped) |
| `jest.config.js` | **remove** — inappbrowser moduleNameMapper entry | - |
| `__mocks__/external/react-native-inappbrowser-reborn.ts` | **remove** | - |
| *(inline `jest.doMock('../../specs/NativeAuthSession', …)` in the store test)* | **add** — spec mock, mirrors `region.test.ts:7` | §6 |
| `src/store/__tests__/CheckoutFlowStore.test.ts` | **change** — module mock + openAuth paths; drop RETURN_HOST/InAppBrowser | §6 A/B/C, I5/I6 |
| `src/hooks/__tests__/useDeepLinking.test.ts` | **remove** — the two UL `it` blocks (`:299-323`) + the `palId` line in the block `beforeEach` (`:296`); KEEP `checkoutFlowStore` import + chat-host regression (`:325-336`) | §4c removed |
| `context/architecture/palshub-checkout.md` | **change** — promote (P)→(C); already re-targeted to ASWebAuth | non-negotiable |

`src/services/palshub/PalsHubApiService.ts`, `PalDetailSheet.tsx`, `PalsScreen.tsx`, `en.json`,
and `region.ts` are **untouched** by this revision (landed correctly; KEEP list).

---

## Steps

Each step is atomic — one logical change, one commit. Steps 3–6 are REMOVE steps and may be
sequenced in any order after Step 2 compiles, but all land in this PR.

### Step 1 (ADD, GATE): ASWebAuthenticationSession native module + spec

**Implements**: §4d, §10 "Added by this flow", D12, I2. Same build-gate discipline as the
prior Step 1 — nothing downstream rests on an unbuilt native module.

**Files**: `ios/PocketPal/AuthSessionModule.swift` (new), `ios/PocketPal/AuthSessionModule.m`
(new), `src/specs/NativeAuthSession.ts` (new)

**Approach** (≤5 lines):
1. Swift: `@objc(AuthSessionModule) class … : NSObject, RCTBridgeModule` mirroring
   `StorefrontModule.swift` (moduleName `"AuthSessionModule"`, `requiresMainQueueSetup → true`
   since it presents UI). Expose `openAuth(_ urlString:, callbackScheme:, resolve:, reject:)`:
   on the main queue build `ASWebAuthenticationSession(url:, callbackURLScheme: callbackScheme,
   completionHandler:)`, set `prefersEphemeralWebBrowserSession = true`, set
   `presentationContextProvider` (an `ASWebAuthenticationPresentationContextProviding` returning
   the key window), `start()`. Completion: callback URL → `resolve(url.absoluteString)`; error
   (incl. `.canceledLogin` user-dismiss) → `reject(...)` (store maps reject → silent cancel, I5).
2. `.m`: `RCT_EXTERN_MODULE(AuthSessionModule, NSObject)` +
   `RCT_EXTERN_METHOD(openAuth:(NSString *)url callbackScheme:(NSString *)scheme
   resolver:(RCTPromiseResolveBlock)resolve rejecter:(RCTPromiseRejectBlock)reject)` — copy the
   `StorefrontModule.m` shape exactly.
3. Spec: `src/specs/NativeAuthSession.ts` — `interface Spec extends TurboModule {
   openAuth(url: string, callbackScheme: string): Promise<string>; }` then
   `export default TurboModuleRegistry.get<Spec>('AuthSessionModule')` (mirrors
   `NativeStorefront.ts`). Hold a strong reference to the session inside the module so ARC does
   not deallocate it mid-flow (instance property; cleared in the completion handler).

**Decision pinned** (from §4d/D12 — no choice for implementer): custom module, NOT
`inappbrowser-reborn`; scheme literal `"pocketpal"`; ephemeral `true`. These are fixed by WHAT.

**Verification (THE GATE)**: `cd ios && RCT_NEW_ARCH_ENABLED=1 pod install` succeeds and the
module appears in the generated project; New-Arch `yarn ios --configuration Release` **builds
green** (this compiles the TurboModule under New Arch — capture the build log per Native
verification). `npx tsc --noEmit` resolves the spec. The native gate is artifact-backed
(see Native verification) — do NOT assert it.

---

### Step 2 (CHANGE): CheckoutFlowStore opens via the module and parses the callback

**Implements**: §1b return path, §2 event flow, §4a.4-6, §4c (`CheckoutFlowStore` row), I5/I6/I7.

**Files**: `src/store/CheckoutFlowStore.ts`

**Approach** (≤5 lines):
1. Replace `import InAppBrowser …` with `import NativeAuthSession from '../specs/NativeAuthSession'`.
   Delete the `RETURN_HOST` constant + its `TODO(checkout-host)` comment; inline the host as a
   plain string (D6 — `<HOST>` carries no entitlement coupling now): keep
   `successUrl`/`cancelUrl` = `https://<HOST>/app-return/{success,cancel}`.
   `NativeAuthSession` is `TurboModuleRegistry.get<Spec>(...)` → typed `Spec | null`; guard it
   before calling `.openAuth(...)` exactly like `region.ts:18` (`if (!NativeStorefront) {…}`).
   On null, map to **silent cancel** (`onReturn(this.palId, 'cancel')`, I5) — the iOS-only branch
   should never reach a null spec, but no non-null assertion (`!`) is permitted (`tsc --noEmit` gate).
2. In `start()`, after `setBrowserOpen`, replace `await InAppBrowser.open(checkout_url)` with:
   `await NativeAuthSession.openAuth(checkout_url, 'pocketpal')` → on resolve, parse the returned
   URL string: `new URL(callback).pathname` trailing segment (`success`|`cancel`) and
   `searchParams.get('purchase_id')`; drive the **existing** machine — `success` →
   `onReturn(this.palId, 'success')` (reconcile); `cancel` → `onReturn(this.palId, 'cancel')`
   (silent). Wrap in try/catch: a **reject** (user-dismiss / session error) → `onReturn(this.palId,
   'cancel')` (silent cancel, I5). Guard the whole branch with the I7 epoch/`palId` check the
   store already enforces inside `onReturn`.
3. Keep `onReturn`/`reconcile`/`reset`/the epoch token **unchanged** (the WHAT keeps the reconcile
   machine and I4 semantics verbatim). Update the store doc-comment: it is no longer driven by a
   Universal-Link return — it now consumes the session callback inline (terse, no internal refs).

**Verification**: `npx tsc --noEmit`; covered by Step 7 store tests (openAuth resolve-success /
resolve-cancel / reject paths).

---

### Step 3 (REMOVE): revert AppDelegate Universal-Link forwarding

**Implements**: §10 "Removed by this revision", §4c (AppDelegate reverts to `return false`).

**Files**: `ios/PocketPal/AppDelegate.swift`

**Approach** (≤5 lines): In `application(_:continue:restorationHandler:)` (`:64-83`) delete the
`NSUserActivityTypeBrowsingWeb` web-URL forwarding block and its comment; the method body becomes
just `return false` (its original state). Leave `application(_:open:options:)` (the `pocketpal`
custom-scheme Shortcuts path, `:45-62`) **untouched** — it is unrelated to checkout.

**Verification**: compiles in the Step 1 New-Arch build / Native verification iOS build; review
confirms only the UL block was removed.

---

### Step 4 (REMOVE): drop the applinks associated-domains entitlement

**Implements**: §10 "Removed by this revision", D6, I6.

**Files**: `ios/PocketPal/PocketPal.entitlements`

**Approach** (≤3 lines): Delete the `com.apple.developer.associated-domains` key + its
`<array><string>applinks:…</string></array>` value **and** the explanatory comment above it.
Leave keychain / Siri / memory-limit / virtual-addressing entitlements intact.

**Verification**: iOS Release build still signs/builds (Native verification); `grep -c applinks
ios/PocketPal/PocketPal.entitlements` → 0.

---

### Step 5 (REMOVE): drop the `/app-return/*` deep-link route

**Implements**: §4c (deep-link path NOT part of return), I6, §10 removed.

**Files**: `src/hooks/useDeepLinking.ts`

**Approach** (≤5 lines): In `handleDeepLink` delete the entire `/app-return/` block (`:87-102`:
the `returnPath` parse, the `startsWith('/app-return/')` branch, and its early `return`). Remove
`checkoutFlowStore` from the `'../store'` import (`:16`) — it is no longer referenced here. Leave
the `host === 'chat'` branch and the E2E benchmark routing untouched. The checkout return now
arrives only through the session promise (Step 2), never this hook (I6).

**Verification**: `npx tsc --noEmit` (no unused-import error); `grep -c app-return
src/hooks/useDeepLinking.ts` → 0; Step 7 removes the now-dead tests.

---

### Step 6 (REMOVE): drop the `react-native-inappbrowser-reborn` dependency

**Implements**: §5c (package dropped), D12. The custom module (Step 1) is the only browser surface.

**Files**: `package.json`, `yarn.lock`, `ios/Podfile.lock`, `jest.config.js`,
`__mocks__/external/react-native-inappbrowser-reborn.ts`

**Approach** (≤5 lines): `yarn remove react-native-inappbrowser-reborn` (updates `package.json`
+ `yarn.lock`); `cd ios && RCT_NEW_ARCH_ENABLED=1 pod install` to drop the `RNInAppBrowser` pod
from `Podfile.lock`. Delete the `'react-native-inappbrowser-reborn'` moduleNameMapper entry in
`jest.config.js` (`:40-41`) and delete `__mocks__/external/react-native-inappbrowser-reborn.ts`.
Confirm no `src/` import of it remains (only `CheckoutFlowStore.ts` referenced it; removed in Step 2).

**Verification**: `grep -rn inappbrowser src package.json jest.config.js ios/Podfile.lock` → 0;
`yarn jest --listTests >/dev/null` loads config without the missing-mapper error.

---

### Step 7 (TESTS): module mock + openAuth paths; remove the two dead UL `it` blocks + RETURN_HOST tests

**Implements**: §6 A/B/C, §9f/9g/9h, I4/I5/I6.

**Files**:
- **add** an inline spec mock in the store test, mirroring `region.test.ts:7`:
  `jest.doMock('../../specs/NativeAuthSession', () => ({ __esModule: true, default: { openAuth }}))`
  with a per-test `openAuth = jest.fn()`. No standalone `__mocks__/external/specs/...` file.
- **change** `src/store/__tests__/CheckoutFlowStore.test.ts`:
  - Remove the `react-native-inappbrowser-reborn` mock + import + `openBrowser` handle (`:14-27`)
    and the `openBrowser` assertions (`:69,77`).
  - Mock `NativeAuthSession.openAuth` instead. New cases: (a) `openAuth` resolves
    `https://h/app-return/success?purchase_id=pur_1` → status reaches `finalizing`→`owned`
    (drives reconcile, A); (b) resolves `…/app-return/cancel` → `cancelled` silent (C/I5);
    (c) `openAuth` **rejects** (user-dismiss) → `cancelled` silent (I5, 9h). Keep the existing
    create-error matrix, in-flight no-op, reconcile webhook-lag/reset, and "no active flow"
    tests (they don't depend on the browser surface).
  - Drop the `successUrl`/`cancelUrl` `stringContaining('/app-return/...')` assertions only if
    they referenced `RETURN_HOST`; the URL-shape assertion itself may stay (host is now an inline
    literal). No `RETURN_HOST` symbol remains to import.
- **edit** `src/hooks/__tests__/useDeepLinking.test.ts` — delete **only** the two dead UL `it`
  blocks: `routes /app-return/success …` (`:299-310`) and `routes /app-return/cancel …`
  (`:312-323`). Drop the `(checkoutFlowStore as any).palId = 'pal-active';` line from the routing
  block's `beforeEach` (`:296`) — it only fed those two tests. **KEEP** the `checkoutFlowStore`
  import (`:22`): the surviving `does not route checkout for the chat host link (no regression)`
  test (`:325-336`) asserts `checkoutFlowStore.onReturn` was **not** called (`:334`), so the
  import stays USED. Keep the `host:'chat'` and benchmark routing tests.

**Verification**: `yarn test --findRelatedTests src/store/CheckoutFlowStore.ts
src/hooks/useDeepLinking.ts`; then full `yarn test` green; `npx tsc --noEmit`.

---

### Step 8 (arch-doc): confirm flow doc reflects the revised mechanism (same PR)

**Implements**: non-negotiable — flow doc absorbs the WHAT delta in the landing PR.

**Files**: `context/architecture/palshub-checkout.md`

**Approach** (≤5 lines): The flow doc is **already** re-targeted to `ASWebAuthenticationSession`
(it was rewritten alongside the WHAT). This step only verifies code-truth: every checkout flow
element now reads `(C)` (module, store openAuth+parse, reconcile) — promoted from `(P)`; §10
"Removed by this revision" matches the actual removals in Steps 3–6 (entitlement, AppDelegate UL,
`/app-return/*` route, RETURN_HOST, cold-launch) and is **expected** to name applinks / RETURN_HOST /
inappbrowser-reborn as the things it removed; §5c names the custom module and "dropped
inappbrowser-reborn"; §11 source-of-truth lists `CheckoutFlowStore.ts` + the custom module and does
**not** imply any `DeepLinkService` involvement in the return. Fold architect-critic SUGGESTION 1 —
already captured in D11/§10 prose. Optional, low-priority: neutralize the lone `FOU-139` mention
(`:442`) to generic wording (e.g. "the palshub server change") so the control-plane doc stays clean —
not required (arch doc is dev-team-repo internal, not a public/GitHub artifact). Confirm **zero
`(?)`**; `<HOST>` is the one remaining placeholder (D6).

**Verification**:
- Arch doc invariants (control-plane doc — do NOT scrub applinks/RETURN_HOST/inappbrowser here; §10/§5c
  removal prose legitimately names them): `grep -n '(?)' context/architecture/palshub-checkout.md` →
  nothing; and every checkout flow element reads `(C)` (none of the checkout return/module/store/reconcile
  elements still carries `(P)`) — verify by reading the flow table, not by grepping the removal sections.
- Non-negotiable hygiene scrub applies to the **changed source/test/config files in the worktree**, not the
  arch doc: `git diff --name-only origin/main...HEAD -- ':!context/**' ':!workflows/**' | xargs grep -nE
  'FOU-|TASK-|round [0-9]|linear\.app' 2>/dev/null` → nothing (no internal refs leak into shipped code/tests/config).

---

## Testable-contract coverage

| Contract item | Verified by |
| --- | --- |
| §6.A happy (settled) | Step 7 store: openAuth resolves success URL → finalizing→owned attempt 1 |
| §6.B happy (webhook lag) | Step 7 store: reconcile false/thrown ×6 → processing_deferred (never error, I4) |
| §6.C cancel | Step 7 store: openAuth resolves `…/cancel` → cancelled silent |
| §6.D already owned (400) | KEPT — existing create-error matrix `already_owned → owned` (no openAuth) |
| §6.E session expired (401) | KEPT — existing `401 → error('401')`; PalDetailSheet re-auth unchanged |
| §6.F US Android web path | KEPT — PalDetailSheet platform-branch test unchanged (`Linking.openURL(getPalBuyUrl)`) |
| §6.G app-kill | accepted behaviour — no callback, SyncService backstop; not unit-tested (no path) |
| 9f stale/idle callback | KEPT — store `return with no active flow is ignored` (`CheckoutFlowStore.test.ts:157`) + stale-pal (`:153`) via `onReturn` epoch guard |
| 9g double-tap | KEPT — in-flight no-op test |
| 9h user-dismiss | Step 7 store: openAuth **reject** → cancelled silent (I5) |
| I5 cancel silent | Step 7 store: cancel-URL resolve AND reject both → cancelled, no error |
| I6 session-scoped callback | Step 5 removes the `/app-return/*` route; Step 7 deletes the two UL `it` blocks; the `:325-336` chat-host regression test stays |

---

## Native verification (NATIVE_CHANGES=YES) — ARTIFACT-BACKED, must be run

The prior reviewer flagged the iOS Release build claim as not artifact-backed. This revision adds
a new TurboModule under New Arch; the build MUST actually run and be evidenced (tee logs; record
the exact "BUILD SUCCEEDED" lines + Podfile.lock diff in the commit/PR, not asserted).

```bash
cd ./worktrees/TASK-20260529-2105
cd ios && RCT_NEW_ARCH_ENABLED=1 pod install 2>&1 | tee /tmp/pod-install.log && cd ..
# iOS Release — compiles AuthSessionModule (Swift+.m) under New Arch; this is the Step 1 gate:
yarn ios --configuration Release 2>&1 | tee /tmp/ios-release-build.log
# Android Release — return path is UNCHANGED (Linking.openURL only); confirm no regression:
yarn android --variant=release 2>&1 | tee /tmp/android-release-build.log
```

Evidence required before "ready": `pod-install.log` shows `RNInAppBrowser` **gone** and the
new module present; `ios-release-build.log` shows `** BUILD SUCCEEDED **` with the new Swift file
compiled; `android-release-build.log` shows `BUILD SUCCESSFUL`. Missing or asserted-only native
verification is a blocking review issue.

---

## Visual confirmation (Visual Confirmation=YES)

iOS simulator, US region, a premium unowned PalsHub pal in the detail sheet. The
`ASWebAuthenticationSession` sheet and a true Stripe round-trip are gated on the palshub prod
deploy of the `/app-return/*` → `pocketpal://` 302 redirect (§9j, cross-repo); for captures,
stub `NativeAuthSession.openAuth` to resolve the success/cancel callback URL.

```json
[
  {"label": "buy-button-idle", "prompt": "open premium pal detail sheet", "look_for": "Buy on Palshub button enabled"},
  {"label": "creating-spinner", "prompt": "tap Buy", "look_for": "button shows loading spinner before the auth session opens"},
  {"label": "finalizing", "prompt": "resolve openAuth with /app-return/success", "look_for": "non-blocking 'Finalizing your purchase…' indicator"},
  {"label": "cancel-silent", "prompt": "reject openAuth (user dismiss)", "look_for": "no error message, button back to idle"}
]
```

---

## Deferred items

- `<HOST>` placeholder string — the only deferred value (D6); confirm apex-vs-www before E2E.
- Android/EU native checkout + return leg — separate ticket (§5 deferred #1; Android keeps the
  unchanged web path here).
- Dedicated `GET /api/purchases/{purchase_id}` reconcile source — deferred (§5 deferred #2, D9).
- Local-currency / price presentment — out of scope (Stripe Adaptive Pricing).

---

## Review History

| Round | Finding | Severity | Resolution |
| --- | --- | --- | --- |
| 1 | C1: native dep compatibility unverified — Step 1 picked legacy `inappbrowser-reborn` without confirming build under RN 0.82 New Arch | CONCERN | SUPERSEDED — WHAT D11/D12 dropped the Universal-Link return and the dep entirely; this revision builds a custom ASWebAuthenticationSession TurboModule (Step 1 GATE) and removes inappbrowser-reborn (Step 6). |
| 1 | C2: 401 re-auth surface (`onSignInPress` on PalDetailSheet wired from PalsScreen) | CONCERN | UNCHANGED — landed correctly; KEEP list. No HOW action this revision. |
| 1 | S3 / Platform import / S4 (`DeepLinkService.ts` location) | SUGGESTION | UNCHANGED — landed; the deep-link route is now removed (Step 5), so the S4 path-location concern is moot. |
| 1 | iOS Release build claim not artifact-backed | CONCERN | FIXED — Native verification is now an explicit tee-logged GATE (pod-install / ios-release / android-release logs); Step 1 cannot complete on assertion. |
| 2 | B1: useDeepLinking test-removal plan had wrong line refs — `:296` is a shared `beforeEach`, `:325-336` is a KEEP chat-host regression test, and the `checkoutFlowStore` import (`:22`) is load-bearing for `:334` | BLOCKER | FIXED — re-scoped Steps 5/7 + affected-files/summary to delete ONLY the two UL `it` blocks (`:299-323`), drop just the `palId` line from the block `beforeEach` (`:296`), KEEP the import + the chat-host test; dropped the nonexistent "no active flow ignored" UL reference. |
| 2 | C1: Step 2 omitted the nullable-spec guard its own `tsc --noEmit` gate requires (`NativeAuthSession` is `Spec | null`) | CONCERN | FIXED — Step 2 now pins a `if (!NativeAuthSession)` guard mirroring `region.ts:18`, mapping null → silent cancel (I5); no non-null assertion permitted. |
| 2 | S1: speculative `__mocks__/external/specs/NativeAuthSession.ts` option | SUGGESTION | FIXED — standardized on the inline `jest.doMock('../../specs/NativeAuthSession', …)` pattern (`region.test.ts:7`); dropped the standalone-file option from the affected-files table and Step 7. |
| — | Design change: Universal-Link return doesn't fire (iOS suppresses ULs into own SFSafariVC) | DESIGN-CHANGE | RE-EMITTED — return switched to ASWebAuthenticationSession callback; HOW now ADDs the native module + store openAuth/parse and REMOVEs the applinks entitlement, AppDelegate UL forwarding, `/app-return/*` deep-link route, RETURN_HOST, and the inappbrowser dep. Architect-critic SUGGESTION 1 already folded into WHAT/flow-doc D11 — no HOW action. |

## Implementation Notes (deviations)

- **Spec mock pattern**: Step 7 prescribed an inline `jest.doMock(...)` mirroring
  `region.test.ts:7`. That file pairs `doMock` with `jest.resetModules()` + an
  in-function `require()` because it re-imports `region` per case. The store test
  imports the `checkoutFlowStore` **singleton** at top level, where a non-hoisted
  `doMock` lands after the hoisted ES `import`, so the store binds the real
  (null-in-jest) spec and the guard short-circuits. Used hoisted
  `jest.mock('../../specs/NativeAuthSession', …)` instead — the same equivalent the
  prior test used for the inappbrowser mock, and the dominant codebase pattern for a
  top-level singleton import. Same effect (spec.openAuth is a jest.fn); no behaviour
  change. All §6 A/C/I5 paths covered.
- **No non-null assertion**: the nullable-spec guard captures `NativeAuthSession`
  into a local and passes the narrowed `NonNullable<…>` into `openAuthAndHandle`,
  so neither `start()` nor the helper uses `!` (tsc --noEmit gate honoured).
