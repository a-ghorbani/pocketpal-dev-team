# WHAT — Non-touch autostart trigger for the bench E2E matrix

**Task**: TASK-20260521-1735
**Delta on**: `context/architecture/benchmark-matrix.md`
**Scope**: automation-ergonomics only. Adds a non-touch way to start the matrix run that invokes the **exact same** start path the on-screen button uses. Does NOT change what is measured, the cell expansion, the report shape, or any data-model contract in §1–§9 of the flow doc.

This story touches a surface the current flow doc is **silent on**: the deep-link routing into `BenchmarkRunnerScreen` and the screen's start trigger. The delta therefore (a) folds the existing routing/trigger behaviour into the flow doc as `(C)`, then (b) proposes the autostart addition as `(P)`/`(D)`.

---

## Conventions

- **(C)** = current behaviour, verified by reading code in this worktree
- **(P)** = proposal, open for challenge
- **(?)** = open question (none remain in this doc)
- **(D)** = decision (resolved trade-off)

---

## 0. Drift note (read first)

The flow doc `benchmark-matrix.md` documents the runner / data model / CLI toolchain (§1–§10) but contains **no section** for how the matrix run is *triggered* or how `BenchmarkRunnerScreen` is *reached*. That routing/trigger infrastructure (`useDeepLinking.ts` E2E effect, `src/__automation__/deepLink.ts`, `isBenchmarkRunnerUrl`, the screen's `onRun`) was added by a later story and never folded into the flow doc. This is a **silence gap, not a contradiction** — the code I read is internally consistent. No code/doc contradiction was found, so this story proceeds. On merge, the implementer folds the new §11 (and the `(C)` facts in §A below) into `benchmark-matrix.md`.

---

## A. Current behaviour being amended (all (C), verified)

The path that gets a run started today, end to end:

```
adb am start -a VIEW -d "pocketpal://e2e/benchmark"   (e2e flavor only)
   │
   ▼
Android delivers the URL — two delivery paths, both __E2E__-gated:
   • cold launch: Linking.getInitialURL() in useDeepLinking.ts effect
   • warm launch: Linking 'url' addEventListener in the same effect
   │   (WDIO `mobile: deepLink` lands as a warm 'url' event)
   ▼
isBenchmarkRunnerUrl(url) startsWith 'pocketpal://e2e/benchmark'  → true
   │
   ▼
navigation.navigate(ROUTES.BENCHMARK_RUNNER)        (no params today)
   │
   ▼
BenchmarkRunnerScreen mounts; status='idle'; renders bench-run-button
   │
   ▼  HUMAN / WDIO TAP  ← the step that fails on HyperOS / MediaTek
   ▼
onRun(): single-flight gate (runningRef + status guard)
         → loadConfig()  (reads pushed bench-config.json)
         → runMatrix(cfg, setStatus, setLastCell)
```

Facts verified (C):

- **A1 (C)**: The `pocketpal://` scheme is registered ONLY in `android/app/src/e2e/AndroidManifest.xml` (e2e flavor). Prod has no intent-filter for it.
- **A2 (C)**: `dispatchAutomationDeepLink` (`src/__automation__/deepLink.ts`) is required only behind `if (__E2E__)` in `useDeepLinking.handleDeepLink`, and the whole bench-routing `useEffect` early-returns when `!__E2E__`. Hermes DCE-strips both in prod.
- **A3 (C)**: `isBenchmarkRunnerUrl` uses `startsWith(BENCHMARK_RUNNER_URL_PREFIX)`, so a URL with a query string (`pocketpal://e2e/benchmark?autostart=1`) already routes correctly — no match-helper change is needed for routing.
- **A4 (C)**: Two independent delivery sites navigate to `BENCHMARK_RUNNER`: the `dispatchAutomationDeepLink` router (DeepLinkParams; iOS/DeepLinkService origin) and the `useDeepLinking` cold/warm Linking effect (raw URL; Android origin). Today **neither passes navigation params** — `navigate(ROUTES.BENCHMARK_RUNNER)` with no second arg.
- **A5 (C)**: `BenchmarkRunnerScreen` is a function component that takes only test-seam props (`__runner`, `__loadConfig`); it does NOT currently read `route.params`. `onRun` is a `useCallback` whose single-flight gate is `runningRef` (a ref) plus a `status` guard (`idle | complete | error:*` may start; anything else is rejected).
- **A6 (C)**: The CI bundle-grep contract (`.github/workflows/ci.yml`, "DCE sanity check") asserts a fixed set of automation markers are **ABSENT** from the prod APK bundle: `AUTOMATION_BRIDGE`, `memory-snapshot-label`, `memory-snapshot-result`, `BENCH_RUN_MATRIX`, `bench-runner-screen-status`. There is **no** "must be present in e2e bundle" grep in this workflow.
- **A7 (C)**: `DeepLinkService.parseURL` populates `queryParams` from `url.searchParams` for the iOS/service path; the Android Linking effect handles only the raw `url` string (no parsing).
- **A8 (C)**: The WDIO spec (`e2e/specs/benchmark-matrix.spec.ts`) currently: `deepLinkLaunch()` (no query) → `bench-run-button.click()` → polls `bench-runner-screen-status` for `complete | error:*`. The `.click()` is the automation analogue of the injected tap that HyperOS/MediaTek drop.

---

## 1. Data model

No change to any persisted shape. `BenchConfig`, `BenchmarkRunRow`, `BenchmarkReport`, baselines: **unchanged**. The autostart param is a transient navigation/URL signal, never persisted, never echoed into a report.

One new **transient** field (navigation param, in-memory only):

```
BenchmarkRunner route params (E2E-only navigation param)
  autostart?: boolean      // true ⇒ screen kicks off onRun once after mount
```

Stored on disk: nothing. Computed/transient only: `autostart`, derived from the deep-link URL query string at navigation time.

**Glossary additions**:
- **Autostart** — a one-shot signal, carried on the deep-link URL as `?autostart=1`, instructing the runner screen to invoke its existing start path automatically once after mount, with no touch.

---

## 1b. External shape (wire format)

The deep-link URL is the wire format. (P) Extend the accepted bench URL with an optional query param:

```
pocketpal://e2e/benchmark            → route only (current behaviour, unchanged)
pocketpal://e2e/benchmark?autostart=1 → route AND auto-invoke onRun once
```

- **(D1)** Truthiness rule: `autostart` is true iff the query param `autostart` is present with value exactly `"1"` or `"true"` (case-insensitive). Any other value, or absence, is false. Rationale: adb/WDIO scripts pass string query values; a narrow allowlist avoids "autostart=0 still starts" foot-guns and keeps the contract trivially scriptable.
- **(D2)** The route prefix match (`isBenchmarkRunnerUrl`) is unchanged — it already tolerates the query string (A3). Only **parsing** of the query is added, at the navigation sites.

---

## 2. Event flow

```
deep link  pocketpal://e2e/benchmark?autostart=1   (e2e flavor)
   │
   ▼  parse autostart from URL query  (both delivery sites, __E2E__-gated)
   ▼
navigate(ROUTES.BENCHMARK_RUNNER, { autostart: <bool> })
   │
   ▼
BenchmarkRunnerScreen mounts; reads route.params.autostart
   │
   ├─ autostart falsey → idle, wait for button tap   (current behaviour)
   │
   └─ autostart truthy → fire onRun() ONCE after mount, via the SAME onRun
                          callback the button's onPress uses
                            └─ single-flight gate still applies (I-AS3)
```

No new events into `runMatrix`, no new report fields, no change to cell expansion (§2 of flow doc unchanged).

---

## 3. State machine

The screen status enum (`idle | running:<tag> | downloading:<f> | cell-failed:* | complete | error:*`) is **unchanged**. Autostart does not add a state; it injects exactly the transition the button tap injects: `idle → (onRun) → running:<tag>`.

User/automation-visible feedback is identical to a tap-initiated run; the `bench-runner-screen-status` testID still reports the same terminal values the spec polls (`complete | error:*`).

---

## 4. Contract

### 4a. URL parsing of `autostart` (new helper behaviour)

1. (P) A pure helper resolves `autostart` from a raw bench URL string, applying D1's truthiness rule. It returns a boolean. It does not navigate, does not touch the store, does not throw on a malformed URL (returns false).
2. (P) The helper is the **single** place D1's truthiness rule lives. Both delivery sites (Android Linking effect, `dispatchAutomationDeepLink`) call it; neither re-implements parsing. Rationale: one truthiness definition, no drift between the two routing paths (A4).
3. (C) `isBenchmarkRunnerUrl` remains the routing gate; the autostart helper is only consulted once a URL has already matched as a bench URL.

### 4b. Navigation sites pass the param (both delivery paths)

1. (P) The Android cold/warm Linking effect in `useDeepLinking.ts`: when `isBenchmarkRunnerUrl(url)` is true, navigate with `{ autostart: <resolved> }` instead of no params.
2. (P) `dispatchAutomationDeepLink` (`src/__automation__/deepLink.ts`): when `isBenchmarkRunnerUrl(params.url)` is true, navigate with `{ autostart: <resolved from params.url> }`.
3. (P) Both sites resolve from the **same raw URL string** via the 4a helper, so iOS-origin (DeepLinkService) and Android-origin (Linking) launches behave identically. The DeepLinkService-parsed `queryParams.autostart` (A7) MAY be used as the source, but to keep one truthiness rule both sites SHOULD resolve from the raw URL via the 4a helper (D-AS5).
4. (C) Routing for the bare `pocketpal://e2e/benchmark` URL is unchanged; it resolves `autostart=false` and the screen stays idle exactly as today.

### 4c. Screen autostart trigger

1. (P) `BenchmarkRunnerScreen` reads `autostart` from its navigation route params (E2E-only route; the screen is only registered under `__E2E__`).
2. (P) When `autostart` is truthy, the screen invokes the **existing** `onRun` callback exactly once after mount — the same callback bound to `bench-run-button`'s `onPress`. No second start path, no duplicated config-load or runMatrix logic. Rationale: AC requires "the exact same start handler the button does, same code path, same use of the already-pushed bench-config.json."
3. (P) The autostart invocation is fired at most once per screen mount even if the component re-renders. Rationale: avoid re-entrancy; `onRun`'s single-flight gate is a backstop, not the primary guard.
4. (C) `onRun` itself is unchanged: it keeps its `runningRef` + status guard, still calls `loadConfig()` then `runMatrix(cfg, setStatus, setLastCell)`. Autostart is purely an alternate *caller* of the unchanged `onRun`.

### 4d. E2E gating (must hold)

1. (C/P) All new logic lives behind `__E2E__` or inside `src/__automation__/` (which is reachable only behind `__E2E__`). The autostart helper, if placed in a prod-reachable module (e.g. alongside `isBenchmarkRunnerUrl` in `navigationConstants.ts`), MUST NOT introduce any string literal in the CI absent-marker set (A6) and MUST be free of side effects so it is harmless even though it ships in prod. Rationale: `navigationConstants.ts` is prod-reachable; a pure boolean helper there is acceptable, but it must not become a new automation marker.
2. (P) If a NEW marker string is introduced that must be DCE-verified absent from prod, it MUST be registered in the `.github/workflows/ci.yml` absent-marker list. (D-AS4: prefer introducing NO new marker — reuse the existing `onRun`/`BENCH_RUN_MATRIX` path so the marker set is unchanged.)
3. (C) The prod-absence DCE contract (A6) is the only bundle-grep gate; there is no present-marker grep to update.

### 4e. Hard invariants (new, autostart-specific)

- **I-AS1**: Autostart invokes the **same** `onRun` callback the button uses — there is exactly one start path into `runMatrix` from the screen. No alternate code path may load config or call `runMatrix` directly.
- **I-AS2**: Autostart changes nothing the runner measures: `BenchConfig` consumed, cell expansion, per-cell params (`composeCellParams`), fingerprints, and `BenchmarkReport`/row shapes are byte-for-byte what a tap-initiated run produces from the same `bench-config.json`. (Preserves flow-doc invariants I1–I8.)
- **I-AS3**: The single-flight gate (`runningRef` + status guard) remains authoritative. Autostart + a concurrent/subsequent tap cannot start two overlapping runs.
- **I-AS4**: Autostart fires at most once per screen mount. A re-render or param-stable re-evaluation does not re-trigger it.
- **I-AS5**: All autostart code is E2E-gated. The prod bundle's automation-marker set (A6) is unchanged; no new automation marker leaks into prod. If any new must-be-absent marker is added, ci.yml is updated in the same PR.
- **I-AS6**: A bare `pocketpal://e2e/benchmark` (no query) behaves exactly as today: route, stay idle, wait for tap. Autostart is strictly opt-in via the query param.

### 4f. What each component does (delta rows)

| Component | Produces / does | Does NOT do |
| --- | --- | --- |
| autostart URL helper (4a) | pure boolean from a raw URL per D1 | navigate, mutate store, throw, log |
| `useDeepLinking` Linking effect | navigate to BENCHMARK_RUNNER **with** `{autostart}` | parse beyond the helper; run anything |
| `dispatchAutomationDeepLink` | navigate to BENCHMARK_RUNNER **with** `{autostart}` | new start path |
| `BenchmarkRunnerScreen` | read `route.params.autostart`; call existing `onRun` once if true | a second config-load / runMatrix call |
| `onRun` (unchanged) | single-flight start: loadConfig → runMatrix | anything new |

---

## 5. Layer ownership (single-writer)

| Field | Single writer | Notes |
| --- | --- | --- |
| `autostart` route param | the two navigation sites (4b), resolved via 4a helper | Read-only on the screen. Transient; never persisted. |
| screen `status` | `setStatus` inside `onRun`/`runMatrix` (unchanged) | Autostart does not write status directly; it only calls `onRun`. |
| `runningRef` (single-flight) | `onRun`/`onReset` (unchanged) | Autostart respects it via I-AS3; it does not bypass or pre-set it. |

All flow-doc single-writer rows (§5: `contextInitParams`, `benchmarkActive`, `benchBase`, `cellParams`, fingerprint/overrides, report version, axes) are **unchanged** — autostart writes none of them.

---

## 6. Canonical scenarios

### A. Autostart on a HyperOS / MediaTek device (the motivating case)

```
adb am start -a VIEW -d "pocketpal://e2e/benchmark?autostart=1"   (e2e APK)
─────────────────────────────────────────
- screen routes to BENCHMARK_RUNNER with {autostart:true}
- onRun fires once, no touch injected
- status: idle → running:<tag> → ... → complete   (or error:*)
- report identical to a tap-initiated run from the same bench-config.json
```

### B. Bare URL (regression guard — current behaviour preserved)

```
pocketpal://e2e/benchmark
─────────────────────────────────────────
- routes to BENCHMARK_RUNNER with {autostart:false}
- status stays idle; bench-run-button shown; waits for tap
```

### C. Autostart + a redundant tap race

```
pocketpal://e2e/benchmark?autostart=1   then a human/WDIO tap arrives mid-run
─────────────────────────────────────────
- autostart starts the run (running:<tag>)
- the later tap hits onRun while runningRef is true → ignored (I-AS3)
- exactly one matrix run; one report
```

### D. autostart=0 / garbage value

```
pocketpal://e2e/benchmark?autostart=0
pocketpal://e2e/benchmark?autostart=banana
─────────────────────────────────────────
- helper returns false (D1); screen stays idle (same as scenario B)
```

### E. iOS-origin vs Android-origin parity

```
Same URL delivered via DeepLinkService (iOS) and via Linking (Android)
─────────────────────────────────────────
- both resolve autostart through the same 4a helper → identical {autostart}
- (Note: the bench runner screen is Android-only in practice per the spec,
   but the routing contract must not diverge between delivery paths)
```

---

## 7. State signals

No new long-lived signals. `autostart` is a transient navigation param, consumed once at mount. `modelStore.benchmarkActive` and all flow-doc §7 signals are unchanged.

---

## 8. Decisions

- **D-AS1**: `autostart` truthy iff query value is `"1"`/`"true"` (case-insensitive). Narrow allowlist; scriptable; no "autostart=0 still runs" foot-gun.
- **D-AS2**: Match helper (`isBenchmarkRunnerUrl`) unchanged; only query parsing is added at the navigation sites. The startsWith prefix already tolerates query strings (A3).
- **D-AS3**: Autostart calls the existing `onRun`; it does NOT add a parallel start path. Satisfies the AC ("exact same start handler / same code path / same config") and keeps single-flight authoritative.
- **D-AS4**: Reuse the existing trigger path so the prod DCE-absent marker set (A6) is unchanged; introduce no new automation marker. If a new must-be-absent marker is unavoidable, register it in `ci.yml` in the same PR.
- **D-AS5**: Both delivery sites resolve `autostart` from the **raw URL** via one shared pure helper, so iOS (DeepLinkService.queryParams) and Android (Linking raw url) cannot diverge in truthiness.
- **D-AS6**: Deep-link approach chosen over broadcast-intent / KEYCODE_ENTER. The `pocketpal://` scheme + intent-filter already exist in the e2e manifest (A1), so no `android/` change and `NATIVE_CHANGES` stays NO. The alternatives would add native surface for no extra capability.

---

## 9. Edge cases

- **9-AS-a. Param absent (bare URL)** — `autostart=false`; idle; identical to today (Scenario B, I-AS6).
- **9-AS-b. autostart=0 / unrecognized value** — false (D1); idle (Scenario D).
- **9-AS-c. Autostart + tap race** — single-flight wins; one run (Scenario C, I-AS3).
- **9-AS-d. Re-render after autostart fired** — does not re-trigger (I-AS4).
- **9-AS-e. Cold vs warm launch** — both delivery paths (A4) carry the param via the same helper (4b); parity holds. Cold: `getInitialURL()`. Warm: `addEventListener('url')` (WDIO `mobile: deepLink`).
- **9-AS-f. Run finishes, screen still mounted, second autostart link arrives** — a fresh deep link is a fresh navigation; if the framework re-mounts the screen with new params, autostart's once-per-mount guard (I-AS4) applies to the new mount. If the screen is merely re-focused without remount, no new autostart fires. Either way `onRun`'s status guard permits a restart only from `idle|complete|error:*` (A5), so no overlap is possible (I-AS3). Operators wanting a guaranteed fresh run should rely on the e2e `fullReset` already used by the spec (A8).
- **9-AS-g. Malformed URL** — helper returns false without throwing (4a.1); routing still governed by `isBenchmarkRunnerUrl`.

---

## 10. What this doc is NOT

- Not a change to what the matrix measures, expands, or reports (I-AS2). All of flow-doc §1–§9 stands.
- Not a broadcast-intent or KEYCODE_ENTER design (rejected, D-AS6).
- Not a native change — no `android/` / `ios/` / Podfile edits (NATIVE_CHANGES=NO).
- Not a list of files to edit or test code (planner's / implementer's job). Module placement of the 4a helper is a suggestion, not a contract.
- Not a change to the WDIO spec's measurement assertions — the spec may swap its `.click()` trigger for the autostart URL, but that is an implementer/planner decision; this doc only requires that the autostart path produce a byte-identical report.

---

## 11. Section to fold into `benchmark-matrix.md` on merge

A new top-level section "Trigger & routing" capturing:
- §A (C) facts: the deep-link → route → onRun → runMatrix path and its two __E2E__-gated delivery sites.
- The autostart contract: §1b external shape, §4c screen trigger, I-AS1–I-AS6, D-AS1–D-AS6.

The implementer absorbs this in the same PR that lands the code (per AGENTS.md "Drift is forbidden").
