# Implementation Plan: Non-touch autostart trigger for the bench E2E matrix

**Purpose**: executable worklist that lands the design in `what.md`. Section references (`§4a`, `§4c`, ...) point at `what.md`. Design lives there; this file does not re-derive it.

---

## Metadata

- **Task ID**: TASK-20260521-1735
- **Worktree**: `./worktrees/TASK-20260521-1735`
- **Branch**: `feature/TASK-20260521-1735`
- **Native Changes**: NO
- **Visual Confirmation**: NO
- **Intent Brief**: `./workflows/stories/TASK-20260521-1735/intent-brief.md`
- **WHAT**: `./workflows/stories/TASK-20260521-1735/what.md`
- **Architecture doc(s) being updated**: `./context/architecture/benchmark-matrix.md`
- **Status**: draft

> **User hold (intent-brief NOTE)**: produce code + commits in the worktree, but the pipeline must STOP short of opening the PR. The user validates the trigger on locally connected HyperOS / MediaTek devices first. `pipeline-reviewer` runs through tests/verification but does NOT open the draft PR.

---

## Progress Tracking

| Step | Status | Commit | Notes |
| --- | --- | --- | --- |
| Step 1 | DONE | 064a44c | `parseBenchmarkAutostart` pure helper (§4a) |
| Step 2 | DONE | 2f67810 | `useDeepLinking` Linking effect passes `{autostart}` (§4b.1) |
| Step 3 | DONE | 39b7354 | `dispatchAutomationDeepLink` passes `{autostart}` (§4b.2) |
| Step 4 | DONE | bf5119d | Screen reads `autostart` + once-per-mount fire of `onRun` (§4c) |
| Step 5 | DONE | 2811e42 | WDIO spec drops `.click()` + dead `bench-run-button` wait; helper sends `?autostart=1` (§10) |
| Architecture doc updated | DONE | (folded with story artifacts) | absorbed WHAT §11 delta into `context/architecture/benchmark-matrix.md` as new §0 "Trigger & routing" |

---

## Affected Files

| Path | Change kind | WHAT reference |
| --- | --- | --- |
| `src/utils/navigationConstants.ts` | edit (add pure helper) | §4a, §4d.1 |
| `src/utils/__tests__/navigationConstants.test.ts` | add (new test file) | §4a, §6.D, §6.E |
| `src/hooks/useDeepLinking.ts` | edit (pass `{autostart}`) | §4b.1, §4b.3 |
| `src/hooks/__tests__/useDeepLinking.test.ts` | edit (assert param) | §6.A, §6.B, §6.D |
| `src/__automation__/deepLink.ts` | edit (pass `{autostart}`) | §4b.2, §4b.3 |
| `src/__automation__/__tests__/deepLink.test.ts` | edit (assert param) | §6.A, §6.B, §6.E |
| `src/__automation__/screens/BenchmarkRunnerScreen.tsx` | edit (read param + autostart effect) | §4c |
| `src/__automation__/screens/__tests__/BenchmarkRunnerScreen.test.tsx` | edit (autostart + race + once-per-mount) | §6.A, §6.B, §6.C |
| `e2e/specs/benchmark-matrix.spec.ts` | edit (drop `.click()`) | §10 |
| `e2e/helpers/bench-runner.ts` | edit (`deepLinkLaunch` adds `?autostart=1`) | §10 |
| `context/architecture/benchmark-matrix.md` | edit (new "Trigger & routing" section) | §11 |

No `package.json` / `ios/` / `android/` / Podfile edits → `NATIVE_CHANGES` stays NO (§8 D-AS6; the `pocketpal://` intent-filter already exists in the e2e manifest per §A1). No `.github/workflows/ci.yml` edit — no new automation marker is introduced (§4d.2, §8 D-AS4).

---

## Implementation Steps

### Step 1: Add the `parseBenchmarkAutostart` pure helper

**Implements**: WHAT §4a, §1b D1, §4d.1.

**Files**:

- `src/utils/navigationConstants.ts` — add an exported pure function next to `isBenchmarkRunnerUrl`.
- `src/utils/__tests__/navigationConstants.test.ts` — new unit test file.

**Approach**: Add `parseBenchmarkAutostart(url: string | null | undefined): boolean`. Extract ONLY the `autostart` query value from the raw URL string and apply D1's allowlist: true iff the value is exactly `"1"` or `"true"` (case-insensitive); anything else, or absence, is false. Wrap the parse in try/catch and return `false` on any throw (§4a.1, §9-AS-g). It does NOT call `isBenchmarkRunnerUrl`, does NOT re-implement host/path matching, does NOT navigate, mutate, log, or throw — `isBenchmarkRunnerUrl` stays the sole routing gate (§4a.3, critic suggestion 1). Do not lean on `URL.hostname` semantics for `scheme://e2e/benchmark`; parse the query substring directly (e.g. split on `?`, read the `autostart` key) or use `URLSearchParams` on the post-`?` slice — never depend on host parsing of the custom scheme. The helper is pure and side-effect-free, so it is harmless even though `navigationConstants.ts` ships in prod; it introduces no string in the CI absent-marker set (§4d.1, §A6).

**Verification**:

- `yarn lint` passes
- `yarn typecheck` passes
- `yarn test --findRelatedTests src/utils/navigationConstants.ts` passes, covering: `?autostart=1`→true; `?autostart=true` / `?autostart=TRUE`→true; `?autostart=0`→false; `?autostart=banana`→false; bare URL (no query)→false; malformed/garbage string→false (no throw); `null`/`undefined`→false (§6.D, §6.E).

### Step 2: `useDeepLinking` Linking effect passes `{autostart}`

**Implements**: WHAT §4b.1, §4b.3, §4b.4.

**Files**:

- `src/hooks/useDeepLinking.ts` — in the `__E2E__`-gated `routeIfBench(url)` closure, when `isBenchmarkRunnerUrl(url)` is true, navigate with `{autostart: parseBenchmarkAutostart(url)}` instead of no params.
- `src/hooks/__tests__/useDeepLinking.test.ts` — update existing assertions and add cases.

**Approach**: Import `parseBenchmarkAutostart` from `navigationConstants`. Keep `isBenchmarkRunnerUrl(url)` as the gate (unchanged routing); only the second `navigate` arg changes from absent to `{autostart: <resolved>}` for both the cold-launch (`getInitialURL`) and warm-launch (`addEventListener('url')`) deliveries — both flow through the same `routeIfBench` so parity holds by construction (§9-AS-e). Resolve from the same raw `url` string the gate matched (§4b.3, D-AS5).

**Verification**:

- `yarn lint`, `yarn typecheck` pass
- `yarn test --findRelatedTests src/hooks/useDeepLinking.ts` passes. Update the existing cold-launch and warm-launch tests to expect `navigate(ROUTES.BENCHMARK_RUNNER, {autostart: true})` for `pocketpal://e2e/benchmark?autostart=1` and `{autostart: false}` for the bare `pocketpal://e2e/benchmark` (§6.A, §6.B). Add a `?autostart=0` warm-event case asserting `{autostart: false}` (§6.D). The `__E2E__=false` and unrelated-URL no-navigate guards must still hold unchanged.

### Step 3: `dispatchAutomationDeepLink` passes `{autostart}`

**Implements**: WHAT §4b.2, §4b.3.

**Files**:

- `src/__automation__/deepLink.ts` — when `isBenchmarkRunnerUrl(params.url)` is true, navigate with `{autostart: parseBenchmarkAutostart(params.url)}`.
- `src/__automation__/__tests__/deepLink.test.ts` — update bench-host assertions.

**Approach**: Import `parseBenchmarkAutostart` from `navigationConstants`. Resolve from the same raw `params.url` string via the shared helper so the iOS/DeepLinkService origin and the Android/Linking origin cannot diverge (§4b.3, D-AS5) — do not use `params.queryParams.autostart` as the source. Widen the local `NavigationLike.navigate` signature to accept an optional second params arg. Routing gate (`isBenchmarkRunnerUrl`) and the memory-host branch are unchanged.

**Verification**:

- `yarn lint`, `yarn typecheck` pass
- `yarn test --findRelatedTests src/__automation__/deepLink.ts` passes. Update the "navigates to BenchmarkRunner" test to expect `navigate('BenchmarkRunner', {autostart: false})` for `pocketpal://e2e/benchmark`, and add a case for `pocketpal://e2e/benchmark?autostart=1` expecting `{autostart: true}` (§6.A, §6.B). Add a `?autostart=0` case expecting `{autostart: false}` (§6.D). The memory-host and fall-through (`returns false`) cases stay unchanged.

### Step 4: Screen reads `autostart` and fires `onRun` once per mount

**Implements**: WHAT §4c, §4e (I-AS1, I-AS3, I-AS4, I-AS6), §6.A, §6.B, §6.C.

**Files**:

- `src/__automation__/screens/BenchmarkRunnerScreen.tsx` — read the `autostart` route param and add a once-per-mount autostart effect that invokes the existing `onRun`.
- `src/__automation__/screens/__tests__/BenchmarkRunnerScreen.test.tsx` — add autostart tests.

**Approach**: Resolve `autostart` from navigation route params via `useRoute()` (`(useRoute().params as {autostart?: boolean})?.autostart`). Add an optional `__autostart?: boolean` test-seam prop (mirrors the existing `__runner`/`__loadConfig` seam) and prefer it when provided, so unit tests can drive autostart without registering a navigator route — the production path always reads `route.params`. Fire the existing `onRun` callback exactly once per mount when resolved truthy, using a `useRef` latch set inside an effect (the effect depends on the latch + `onRun`, and the latch guarantees a single invocation even though `BenchmarkRunnerScreen` is a MobX `observer` that re-renders on store changes — single-flight is the backstop, not the primary guard) (§4c.3, I-AS4, critic suggestion 3). Do NOT add any second start path: autostart only calls the unchanged `onRun` (§4c.2, I-AS1, D-AS3); `onRun`'s `runningRef` + status guard remain authoritative (§4c.4, I-AS3). When `autostart` is falsey the screen stays idle exactly as today (§4c, I-AS6, §6.B).

**Verification**:

- `yarn lint`, `yarn typecheck` pass
- `yarn test --findRelatedTests src/__automation__/screens/BenchmarkRunnerScreen.tsx` passes. Add tests using the `__autostart` seam + the existing `__runner`/`__loadConfig` mocks:
  - autostart truthy → `runner` called exactly once after mount, no button press (§6.A)
  - autostart falsey/absent → `runner` NOT called; status stays `idle` (§6.B)
  - autostart truthy then a button press arrives mid-run → `runner` still called exactly once (single-flight; §6.C, I-AS3)
  - re-render (e.g. trigger an observed store change or a parent re-render) after autostart fired → `runner` not called again (once-per-mount; I-AS4)
  - all existing screen tests (tap-initiated run, single-flight, reset, missing/malformed config) still pass unchanged (I-AS1 — `onRun` untouched).

### Step 5: Swap the WDIO spec trigger for the autostart deep link

**Implements**: WHAT §10 (spec may swap `.click()` for the autostart URL — measurement assertions unchanged), §6.A.

**Files**:

- `e2e/helpers/bench-runner.ts` — `deepLinkLaunch()` sends `pocketpal://e2e/benchmark?autostart=1`.
- `e2e/specs/benchmark-matrix.spec.ts` — remove the `runBtn.click()` step (and the `bench-run-button` wait if it becomes unused); keep polling `bench-runner-screen-status` for `complete | error:*` and all report/measurement assertions byte-identical.

**Approach**: Change the helper URL to carry `?autostart=1` so the matrix starts without an injected tap — the motivating fix for HyperOS / MediaTek (intent-brief CONTEXT, §6.A). Delete the `.click()` in the spec since the screen now self-starts; leave the status-poll loop, the per-row pass gate, and the top-level device/soc/commit fill untouched (§10 — no change to what is measured). This is automation-ergonomics only.

**Verification**:

- `yarn lint`, `yarn typecheck` pass (these are `.ts` E2E sources).
- E2E is not run in this pipeline (device-dependent, and the user holds for local-device validation). Static-only check: confirm the spec no longer references `bench-run-button` for tapping and the helper URL contains `?autostart=1`. Live confirmation is the user's local-device step before PR (see User hold).

---

## Testable-Contract Coverage

Testable contract = canonical scenarios in WHAT §6.

| Contract item | Verified by |
| --- | --- |
| §6.A Autostart starts the run (no touch) | `useDeepLinking.test.ts` (`{autostart:true}` nav) + `deepLink.test.ts` (`{autostart:true}` nav) + `BenchmarkRunnerScreen.test.tsx` (autostart fires `onRun` once); E2E live-verified by user on HyperOS/MediaTek |
| §6.B Bare URL → idle (regression guard) | `useDeepLinking.test.ts` + `deepLink.test.ts` (`{autostart:false}` nav) + `BenchmarkRunnerScreen.test.tsx` (falsey → stays idle) |
| §6.C Autostart + redundant tap race → one run | `BenchmarkRunnerScreen.test.tsx` (autostart then press; `runner` called once) |
| §6.D autostart=0 / garbage → false | `navigationConstants.test.ts` (helper unit) + `useDeepLinking.test.ts` + `deepLink.test.ts` (`?autostart=0` → `{autostart:false}`) |
| §6.E iOS/Android parity (helper-level) | `navigationConstants.test.ts` asserts both sites resolve identically from the same raw URL via the one helper — a unit-level "both resolve identically" assertion, NOT a device E2E (matrix is Android-only in v1; critic suggestion 2). Reinforced by `deepLink.test.ts` (DeepLinkService/iOS-origin path) and `useDeepLinking.test.ts` (Linking/Android-origin path) both consuming `parseBenchmarkAutostart`. |

### Architecture-doc update step

**Implements**: WHAT §11 (Drift is forbidden — same PR).

**Files**:

- `context/architecture/benchmark-matrix.md` — add a new top-level "Trigger & routing" section.

**Approach**: Fold in the WHAT delta per §11: (a) the §A `(C)` facts — the deep-link → route → `onRun` → `runMatrix` path and its two `__E2E__`-gated delivery sites; (b) the autostart contract — §1b external shape (`?autostart=1`), §4c screen trigger, invariants I-AS1–I-AS6, decisions D-AS1–D-AS6. Convert the proposal markers that landed to `(C)` (the autostart behaviour is now implemented), keep any `(D)` decisions as `(D)`, and confirm zero `(?)` markers remain. Use the doc's existing `(C)`/`(D)` convention (the flow doc does not use `(P)`). Leave `workflows/stories/TASK-20260521-1735/what.md` intact for archival.

**Verification**:

- The new section exists and references the implemented files.
- `grep -n '(?)' context/architecture/benchmark-matrix.md` returns nothing.
- The §1–§10 contracts (data model, fingerprint, merge/compare) are unchanged — autostart adds only the trigger/routing section (I-AS2).

---

## Native Verification

Not applicable — `NATIVE_CHANGES=NO`. No `package.json` / native module / `ios/` / `android/` / Podfile / build.gradle edits. The `pocketpal://` scheme + intent-filter already exist in `android/app/src/e2e/AndroidManifest.xml` (§A1, D-AS6).

---

## Visual Confirmation

Not applicable — `Visual Confirmation=NO`. This is an automation-ergonomics change with no user-facing UI delta.

---

## Deferred Items

None. WHAT defers nothing for this story. WHAT §10 explicitly rejects broadcast-intent / KEYCODE_ENTER alternatives (D-AS6) — those are out of scope and not implemented here.

---

## What this plan is NOT

- not a design doc — design lives in `what.md`
- not a justification — `intent-brief.md` holds the request
- not a change to what the matrix measures, expands, or reports (I-AS2); §1–§9 of the flow doc stand
