# Implementation Plan: US Android in-app PalsHub checkout (Custom Tabs) + Play External Offers reporting

Executable worklist for `what.md`. Section refs (`§4b`, `I-A3`, `D-A4`, `9j-A`, scenario `§6.X`) point into the WHAT; do not re-derive design here.

---

## Metadata

- **Task ID**: TASK-20260607-2338
- **Worktree**: `./worktrees/TASK-20260607-2338`
- **Branch**: `feature/TASK-20260607-2338`
- **Native Changes**: YES
- **Visual Evidence Required**: YES
- **Intent Brief**: `./workflows/stories/TASK-20260607-2338/intent-brief.md`
- **WHAT**: `./workflows/stories/TASK-20260607-2338/what.md`
- **Architecture doc(s)**: `./context/architecture/palshub-checkout.md`
- **Status**: revised (round 1)

---

## Progress

| Step | Status | Commit | Notes |
| --- | --- | --- | --- |
| Step 1 (native AuthSession + wiring) | DONE | 7166aaf | Custom Tabs module + host=checkout intent forwarding; registered first. Fixed a Kotlin nested-comment build break in the MainActivity KDoc; uses `ReactHost.currentReactContext` (new-arch), not legacy `reactInstanceManager` |
| Step 2 (External Offers reporting module) | DONE | e5ed398 | billing 7.1.1 verified to expose enableExternalOffer/createExternalOfferReportingDetailsAsync; no-op-with-log when inactive |
| Step 3 (store reporting hook + tests) | DONE | 77256d6 | bound to reconcile-success owned only; 32/32 store tests pass |
| Step 4 (un-branch + disclosure gate + tests) | DONE | ffc4e2a | the behavioural flip; 52/52 PalDetailSheet tests pass |
| Step 5 (Android E2E + visual captures) | DONE | 1e1c86d | spec+POM committed; gitignored visual spec authored; full E2E run + captures left for tester |
| Architecture doc updated | DONE | (dev-team) | absorbs WHAT delta; stale `:43`/`:209` citations fixed; future-Android-slice line removed; Status flipped |
| Native verification (iOS + Android build) | DONE | n/a | Android assembleProdRelease SUCCESS (APK 221 MB); iOS Release build SUCCEEDED; Podfile.lock restored (no iOS dep change) |
| Review fix — dismiss settles auth promise + host-scoped callback | DONE | 743deb8 | single-phase onHostResume (dropped two-phase awaitingReturn flag); handleIntent now requires host=checkout so a pocketpal://hub intent falls through to setIntent/DeepLinkService |
| Review fix — platform-neutral store comments | DONE | c9e76fe | CheckoutFlowStore header/openAuthAndHandle/null-spec comments describe both platforms; null spec stated as an Android build/registration defect |
| Review fix — dismiss recovery test | DONE | 1ca1414 | store test: dismiss → cancelled, isInFlight false, reset → fresh start reaches browser_open (not blocked) |
| Review-fix verification | DONE | n/a | CheckoutFlowStore 33/33 + PalDetailSheet 52/52 green; Android assembleProdRelease SUCCESS (APK 211 MB), compileProdReleaseKotlin clean; no iOS file changed (no iOS rebuild). Live emulator dismiss-E2E left for tester |

---

## Affected files

| Path | Change | Design ref |
| --- | --- | --- |
| `android/app/src/main/java/com/pocketpalai/AuthSessionModule.kt` | add (Kotlin, Custom Tabs) | §4c, D-A3 |
| `android/app/src/main/java/com/pocketpalai/AuthSessionPackage.kt` | add | I-A2, D-A3 |
| `android/app/src/main/java/com/pocketpalai/MainApplication.kt` | edit (register packages) | I-A2, 9j-A |
| `android/app/src/main/java/com/pocketpalai/MainActivity.kt` | edit (forward warm-launch intent) | §4c, D-A3 |
| `android/app/src/main/AndroidManifest.xml` | edit (`host=checkout` BROWSABLE filter) | §4c, 9i-A |
| `android/app/build.gradle` | edit (androidx.browser + Play billing deps) | §1b, NATIVE_CHANGES |
| `android/app/src/main/java/com/pocketpalai/ExternalOfferModule.kt` | add (Kotlin, reporting) | §4c, I-A3, D-A4 |
| `android/app/src/main/java/com/pocketpalai/ExternalOfferPackage.kt` | add | §4c |
| `src/specs/NativeExternalOffer.ts` | add (optional TurboModule spec) | §1 data model |
| `src/store/CheckoutFlowStore.ts` | edit (post-`owned` best-effort report) | §2, I-A3, D-A5 |
| `src/store/__tests__/CheckoutFlowStore.test.ts` | edit (reporting active/no-op tests) | §6.A, §6.G |
| `src/components/PalsHub/PalDetailSheet/PalDetailSheet.tsx` | edit (un-branch press; disclosure gate) | §4a, D-A1, D-A7 |
| `src/components/PalsHub/PalDetailSheet/__tests__/*` | add/edit (disclosure gate tests) | §6.B |
| `src/locales/en.json` | edit (disclosure copy) | §4a |
| `e2e/specs/features/purchase-flow.spec.ts` | edit (Android branch / disclosure step) | §6.A, §6.B, 9j-A |
| `e2e/pages/PalPurchasePage.ts` | edit (disclosure consent helper) | §6.B |
| `e2e/specs/visual-capture/TASK-20260607-2338.spec.ts` | add (gitignored) | visual evidence |
| `context/architecture/palshub-checkout.md` | edit (absorb delta; fix citations) | drift check |

---

## Plan exploration

Candidates: `plan-candidate-A.md` (JS-first, native-last), `plan-candidate-B.md` (native seam first, then flip), `plan-candidate-C.md` (browser cluster then reporting cluster). Selected **B**: registering the native AuthSession module before the JS un-branch structurally precludes edge `9j-A` (an unregistered module silently maps to `cancel` — `CheckoutFlowStore.ts:124-128` — passing a JS-mocked happy path while shipping a dead-end Buy). Every commit leaves Android wholly old-path or wholly new-path.

### Sequencing note

Native seam registered first, JS un-branch (Step 4) is the single behavioural flip — never a buildable-but-dead-end intermediate.

---

## Steps

### Step 1: Android AuthSession Custom Tabs module + intent capture, registered

**Implements**: §4c (AuthSessionModule row), I-A2, D-A3, edge 9i-A/9d-A.

**Files**: `AuthSessionModule.kt`, `AuthSessionPackage.kt` (new, dir `com/pocketpalai/`, `package com.pocketpal`); `MainApplication.kt`, `MainActivity.kt`, `AndroidManifest.xml`, `android/app/build.gradle` (edit).

**Approach** (≤ 5 lines): Module extends the codegen `NativeAuthSessionSpec` (generated from existing `src/specs/NativeAuthSession.ts`, java pkg `com.pocketpal.specs`), name `"AuthSessionModule"`, mirroring `StorefrontModule`/`StorefrontPackage`. `openAuth(url, scheme)` launches a Chrome Custom Tab (add `androidx.browser:browser`) and parks one in-flight promise; resolve on the captured `pocketpal://checkout/*` intent, reject on tab dismiss (silent cancel, I5). Register a `host=checkout` BROWSABLE filter (distinct from `host=hub`, §4c/9i-A) and route it to the module: `MainActivity.onNewIntent` forwards the warm-launch intent to the module (today it only `setIntent`s, `MainActivity.kt:53-56`) — NOT `DeepLinkService`. Register `AuthSessionPackage()` in `MainApplication.getPackages()` (manual pattern, like `StorefrontPackage`). Resolve at most one promise; epoch dedup stays in the JS store (9d-A).

**Verification**: `yarn android --variant=release` builds; `cd e2e` not needed yet; manual: confirm `TurboModuleRegistry.get('AuthSessionModule')` resolves on a debug run (logged once).

---

### Step 2: External Offers reporting Kotlin module (build-ahead)

**Implements**: §4c (External Offers client row), I-A3, D-A4, scenario §6.G, edges 9e-A/9f-A.

**Files**: `ExternalOfferModule.kt`, `ExternalOfferPackage.kt` (new); `src/specs/NativeExternalOffer.ts` (new optional spec: `reportTransaction(purchaseId: string): Promise<void>`, exported via `TurboModuleRegistry.get<Spec>('ExternalOfferModule')` — nullable, mirroring `NativeAuthSession.ts:8`, NOT `getEnforcing`, so iOS skips it via `?.`); `android/app/build.gradle` (add Play Billing dependency that exposes the External Offers reporting API); `MainApplication.kt` (register package).

**Approach** (≤ 5 lines): Wrap the Play Billing External Offers `reportTransaction` handshake to Google's documented contract (https://developer.android.com/google/play/billing/external/integration). Active path = real report; inactive/uncredentialed = **logged no-op**, never throw, never queue (D-A4). The Kotlin method always resolves the JS promise (success or swallowed), so JS treats it as best-effort. Field set defers to the chosen Play library version (§1b); only `purchaseId` correlation is passed in. iOS has no counterpart — Android-only spec, never imported on the iOS path.

**Verification**: `yarn android --variant=release`; `npx tsc --noEmit` for the new spec.

---

### Step 3: Store post-`owned` best-effort reporting hook + unit tests

**Implements**: §2 (ExternalOfferReport), I-A3, D-A5, scenarios §6.A/§6.C/§6.D/§6.G, edges 9e-A/9f-A.

**Files**: `src/store/CheckoutFlowStore.ts`, `src/store/__tests__/CheckoutFlowStore.test.ts` (edit).

**Approach** (≤ 5 lines): Bind reporting to the reconcile-success `owned` transition ONLY (`CheckoutFlowStore.ts:222`, §4a r5 "On reaching owned after checkout/success"); the `already_owned` (400) branch in `start()` (`:133`) also reaches `owned` but does NOT report — no external transaction occurred via this flow. In `reconcile`, after that `setStatus('owned')`, call `NativeExternalOffer?.reportTransaction(this.purchaseId)` (optional spec; absent on iOS → skipped) wrapped so any rejection is swallowed (I-A3): reporting NEVER writes `CheckoutFlowState`, never re-reports, never gates the outcome. Fire-and-forget after the `owned` transition is committed. No report on `cancelled`/`processing_deferred`/`error` (D-A5). Mock the spec in tests: assert called once on the reconcile-success `owned`, NOT called on the `already_owned` (400) path, not called on cancel/deferred, and that a throwing report leaves status `owned` (9f-A).

**Verification**: `yarn test --findRelatedTests src/store/CheckoutFlowStore.ts`.

---

### Step 4: Un-branch `handleBuyPress` + Android disclosure gate (the flip)

**Implements**: §4a rules 1-2, I1′, D-A1, D-A7, scenarios §6.A/§6.B/§6.E/§6.F, edge 9b-A/9h-A.

**Files**: `src/components/PalsHub/PalDetailSheet/PalDetailSheet.tsx`, its `__tests__`, `src/locales/en.json` (edit).

**Approach** (≤ 5 lines): Remove the `Platform.OS !== 'ios'` → `Linking.openURL(getPalBuyUrl)` branch at `PalDetailSheet.tsx:135-146`. New flow: auth guard (`authService.isAuthenticated` → `onSignInPress`) for both platforms; then on Android only, show a disclosure/consent gate (new local state `idle → declined → idle`, scenario §6.B) before `checkoutFlowStore.start(displayPal.id)`; iOS reaches `start` directly with NO gate (D-A7). iOS press path byte-for-byte unchanged (D-A2). Decline = no `start`, no Custom Tab, no report (9b-A). Disclosure UI uses the existing `Sheet` primitive; copy in `en.json` (no Linear/task IDs). Buy-button gate at `:405-408` untouched (I1′).

**Verification**: `yarn test --findRelatedTests src/components/PalsHub/PalDetailSheet/PalDetailSheet.tsx`; `npx tsc --noEmit`.

---

### Step 5: Android E2E coverage + visual evidence

**Implements**: §6.A/§6.B happy + disclosure on Android; edge 9j-A (Buy must reach the Custom Tab, proving the module is registered).

**Files**: `e2e/specs/features/purchase-flow.spec.ts`, `e2e/pages/PalPurchasePage.ts` (edit); `e2e/specs/visual-capture/TASK-20260607-2338.spec.ts` (new, gitignored).

**Approach** (≤ 5 lines): Generalise the iOS-only spec: add an Android describe (or platform-branch) that opens the pal, consents the disclosure gate (new POM helper `acceptDisclosureIfPresent`), and asserts Buy reaches the Custom Tab then flips to Download via the palshub e2e harness (test-complete checkout, no Google Pay UI). 9j-A is covered structurally: Buy reaching the in-app Custom Tab proves the native module resolved (a registration defect short-circuits to silent cancel, no tab). No new `__E2E__` concession (D-A6). Visual capture (Flavour B, `docs/workflows/visual-capture.md`): disclosure sheet + in-app Custom Tab. Output is gitignored at `e2e/debug-output/screenshots/visual-captures/TASK-20260607-2338/<label>/` (NOT committed — Flavour B dies with the worktree); reviewers reference that dir, or attach side-by-side as a PR comment.

**Verification**: Android E2E run against the palshub harness; visual captures saved.

---

### Step 6: Absorb WHAT delta into the architecture doc

**Implements**: drift check + WHAT delta absorption (mandatory same-PR).

**Files**: `context/architecture/palshub-checkout.md` (edit).

**Approach** (≤ 5 lines): Replace I1 (iOS-only) with I1′ (region-gated, both platforms in-app) and un-branch the §1 flow / §5 buy-press rules; add the three Android invariants (I-A1/I-A2/I-A3), Android scenarios, edges 9a-A..9j-A, decisions D-A1..D-A8; add the Android native surface (AuthSession Custom Tabs module, External Offers reporting, manifest `host=checkout`, package registration); **remove** the §10 "Out of scope (future Android slice)" line. Fix the stale buy-button gate citation `PalDetailSheet.tsx:325-327` at `:43` and `:209` → `PalDetailSheet.tsx:405-408`. Flip the doc Status off "Slice 1 — iOS only". No Linear IDs / story anchors in the doc's prose that lands; keep it current-state.

**Verification**: `grep -n "325-327" context/architecture/palshub-checkout.md` returns nothing; `grep -n "future Android slice" ...` returns nothing.

---

## Testable-contract coverage

| Contract item | Verified by |
| --- | --- |
| §6.A US Android happy path | `purchase-flow.spec.ts` (Android) + `CheckoutFlowStore.test.ts` (report on owned) |
| §6.B disclosure declined | `PalDetailSheet` test (decline → no `start`) + E2E disclosure step |
| §6.C cancel / tab dismiss | `CheckoutFlowStore.test.ts` (reject → cancelled, no report) |
| §6.D webhook lag | `CheckoutFlowStore.test.ts` (exhaust → processing_deferred, no report) |
| §6.E iOS unchanged | `PalDetailSheet` test (iOS reaches `start`, no gate) + iOS build |
| §6.F non-US | existing region-gate test (button hidden) unchanged |
| §6.G reporting inactive | `CheckoutFlowStore.test.ts` (report no-op leaves status `owned`) |
| edge 9j-A unregistered module | native registration (Step 1) + E2E Buy reaching Custom Tab (Step 5) |

---

## Review / debug strategy

- **Riskiest files**: `AuthSessionModule.kt` — Custom Tab intent capture under `singleTask`/`onNewIntent`, the only non-JS-testable seam; `CheckoutFlowStore.ts` — reporting must stay strictly post-`owned` and non-gating; `PalDetailSheet.tsx` — iOS path must stay byte-for-byte.
- **Expected failure modes**: warm-launch intent not forwarded to module → promise hangs; report fired off the wrong transition; iOS regression from the un-branch.
- **Tests that should fail if wrong**: `CheckoutFlowStore.test.ts` (report-on-owned-only); `PalDetailSheet` disclosure/iOS-unchanged tests; Android E2E Buy-reaches-Custom-Tab (9j-A).
- **Manual verification required**: Android E2E checkout + disclosure against palshub harness; visual captures of disclosure sheet + Custom Tab. Live Play-Console reporting + real-US-device Google Pay round-trip are DEFERRED (D-A8), NOT gating this PR.
- **Independent reviewer focus**: (1) edge 9j-A is precluded by native registration, not just mocked; (2) reporting never mutates `CheckoutFlowState` and never fires on cancel/deferred (I-A3).

---

## Native verification (NATIVE_CHANGES=YES)

```bash
cd "/Users/aghorbani/codes/pocketpal-dev-team/worktrees/TASK-20260607-2338"
# No iOS Podfile change expected (Android-only native) -> pod install only if ios/ changes.
yarn ios --configuration Release      # proves no iOS regression (D-A2)
yarn android --variant=release        # AuthSession + ExternalOffer modules + manifest
```

Skipping is a blocking review issue. iOS build is mandatory to prove the un-branch did not regress the iOS path.

---

## Visual evidence (Visual Evidence Required=YES)

Flavour B (per-task one-shot, gitignored) per `docs/workflows/visual-capture.md`. Author `e2e/specs/visual-capture/TASK-20260607-2338.spec.ts`; captures land gitignored at `e2e/debug-output/screenshots/visual-captures/TASK-20260607-2338/<label>/` (referenced as review evidence / attached to the PR, NOT committed).

```json
[
  {"label": "android-disclosure-gate", "look_for": "pre-purchase consent sheet shown before the Custom Tab, with consent + cancel actions"},
  {"label": "android-checkout-custom-tab", "look_for": "in-app Chrome Custom Tab foregrounding the checkout_url (not the system browser, not the old web product page)"}
]
```

---

## Deferred items

- Live Play Console reporting verification — blocked on enrollment Active (WHAT §5 #1, D-A8).
- Live Google Pay round-trip on a real US Android device — emulator has no wallet (WHAT §5 #2, D-A8).
- Active-program behaviour switch — no app-code change beyond credentials when enrollment goes Active (WHAT §5 #3).
- Live region eligibility (locale-derived `isUSRegion` vs Play-account region) (WHAT §5 #4).

---

## Review History

| Round | Finding | Severity | Resolution |
| --- | --- | --- | --- |
| 1 | Visual-capture flavour vs commit-location mismatch (committed `visual-diff/` is Flavour C) | CONCERN | FIXED — Step 5 + Visual evidence now point at gitignored `e2e/debug-output/screenshots/visual-captures/<TASK-ID>/<label>/`; evidence referenced/attached, not committed |
| 1 | `already_owned` (400) → `owned` reporting path unaddressed | CONCERN | FIXED — Step 3 binds report to reconcile-success `owned` (`:222`) ONLY; `already_owned` (400, `:133`) does NOT report; test asserts not-called on that path |
| 1 | Step 2 spec registry pattern unstated | SUGGESTION | FIXED — Step 2 names `TurboModuleRegistry.get<Spec>(...)` (nullable, mirrors `NativeAuthSession.ts:8`), iOS skips via `?.` |
