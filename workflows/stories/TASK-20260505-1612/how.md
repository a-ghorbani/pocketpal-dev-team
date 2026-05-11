# Implementation Plan: Settings sweep + Hexagon backend for BenchmarkRunnerScreen

**Purpose**: land WHAT §1–§9 — extend `bench-config.json`, the runner, log parser, merge / compare scripts, and baselines from the v1.0 schema (3-tuple key, `cpu|gpu` only) to the v1.1 schema (4-tuple key with `settings_fingerprint`, `cpu|gpu|hexagon`). Reference WHAT sections by number; do not re-derive design content.

---

## Metadata

- **Task ID**: TASK-20260505-1612
- **Worktree**: `./worktrees/TASK-20260505-1612`
- **Branch**: `feature/TASK-20260505-1612`
- **Native Changes**: YES (added during implementation — Android JNI shim for `mallopt(M_PURGE_ALL)` + iOS no-op for `purgeNativeAllocator`)
- **Visual Confirmation**: NO
- **Intent Brief**: `./workflows/stories/TASK-20260505-1612/intent-brief.md`
- **WHAT**: `./workflows/stories/TASK-20260505-1612/what.md`
- **Architecture doc(s) being updated**: `./context/architecture/benchmark-matrix.md` (seeded here; resynced to the isolated lifecycle + purge mechanism in dev-team commit c8bd7af)
- **Status**: Merged in #713 (f34c6bf) on 2026-05-11

---

## Progress Tracking

| Step | Status | Commit | Notes |
| --- | --- | --- | --- |
| Step 1 — Type widening (Backend, EffectiveBackend, BenchConfig, BenchmarkRunRow) | DONE | f6217e2 | WHAT §1a, §1b, §1c |
| Step 2 — `logSignals.ts` Hexagon parsing + effective-backend arms | DONE | bdd217c | WHAT §1d, §4i, §8 D2 |
| Step 3 — Settings axes plumbing in `e2e/fixtures/benchmark-models.ts` | DONE | f6e5803 | WHAT §4b |
| Step 4 — `e2e/helpers/bench-runner.ts:buildConfig` + matrix shape changes | DONE | 7a2e181 | WHAT §4b, §1b |
| Step 5 — `e2e/scripts/build-bench-config.ts` env-var validation + summary | DONE | 6a7c0c6 | WHAT §4b, §9e |
| Step 6 — `BenchmarkRunnerScreen.runMatrix`: cell expansion + apply/restore + Hexagon path | DONE | c3904e5 | WHAT §2, §4a, §4c, §4h I4/I5/I7 |
| Step 7 — Settings fingerprint helper (success + failure constructions) | DONE | e50b9aa | WHAT §4d, §9c, §9d |
| Step 8 — Row writer extensions (overrides, fingerprint, status `<tag>`) | DONE | 6a0c41b | WHAT §3, §4a, §4i, §8 D9 |
| Step 9 — `merge-bench-reports.ts` 4-tuple key + version refusal | DONE | 0812f09 | WHAT §4f, §4h I1/I8, §9g |
| Step 10 — `benchmark-compare.ts` 4-tuple key + Hexagon arms | DONE | 777b22b | WHAT §4g |
| Step 11 — One-shot v1.0 → v1.1 baseline migration script + run on three baselines | DONE | ff87c21 (script), 7ce62c4 (baselines) | WHAT §4f.2, §8 D8 |
| Step 12 — Bootstrap `context/architecture/benchmark-matrix.md` from WHAT | DONE | 6403fd6 (dev-team repo) | AGENTS.md "absorb delta into flow doc in same PR" |
| Cleanup reminders applied | DONE | n/a | none — WHAT §10 declares no diagnostic / temporary code |

---

## Affected Files

| Path | Change kind | WHAT reference |
| --- | --- | --- |
| `src/__automation__/screens/BenchmarkRunnerScreen.tsx` | edit | §1a, §1b, §1c, §2, §4a, §4c, §4h, §3, §9c, §9d |
| `src/__automation__/logSignals.ts` | edit | §1d, §4i, §8 D2 |
| `e2e/scripts/build-bench-config.ts` | edit | §4b, §9e |
| `e2e/helpers/bench-runner.ts` | edit | §4b, §1b |
| `e2e/fixtures/benchmark-models.ts` | edit | §4b |
| `e2e/scripts/merge-bench-reports.ts` | edit | §4f, §4h I1/I8, §9g |
| `e2e/scripts/benchmark-compare.ts` | edit | §4g |
| `e2e/scripts/migrate-baseline-v1-to-v1_1.ts` | add | §4f.2, §8 D8 |
| `e2e/baselines/benchmark/poco-myron.json` | edit (migrated) | §4f.2 |
| `e2e/baselines/benchmark/poco-x7-klee.json` | edit (migrated) | §4f.2 |
| `e2e/baselines/benchmark/samsung-s23.json` | edit (migrated) | §4f.2 |
| `scripts/__tests__/logSignals.test.ts` | edit | tests for §1d/§8 D2 |
| `scripts/__tests__/build-bench-config.test.ts` | edit | tests for §4b/§9e |
| `scripts/__tests__/merge-bench-reports.test.ts` | edit | tests for §4f/§4h/§9g |
| `scripts/__tests__/benchmark-compare.test.ts` | edit | tests for §4g |
| `src/__automation__/screens/__tests__/BenchmarkRunnerScreen.test.tsx` | edit | tests for §4a, §4c, §4h, §9c, §9d |
| `scripts/__tests__/migrate-baseline-v1-to-v1_1.test.ts` | add | tests for §4f.2 idempotency |
| `context/architecture/benchmark-matrix.md` | add (in dev-team repo) | seeds the new flow doc from WHAT |

---

## Implementation Steps

### Step 1: Widen type definitions in `BenchmarkRunnerScreen.tsx`

**Implements**: WHAT §1a, §1b, §1c.

**Files**:

- `src/__automation__/screens/BenchmarkRunnerScreen.tsx` — type-only edit; runtime behaviour unchanged so far.

**Approach**:

1. Define and export `type Backend = 'cpu' | 'gpu' | 'hexagon'` (replaces inline `'cpu' | 'gpu'` literals).
2. Define and export the closed `type SettingsKnob = 'cache_type_k' | 'cache_type_v' | 'flash_attn_type' | 'no_extra_bufts' | 'use_mmap' | 'n_threads'` and `type SettingsValue = string | number | boolean`.
3. Add `interface SettingsAxis { name: SettingsKnob; values: SettingsValue[] }`.
4. Extend `BenchConfig` with `backends: Backend[]` and an optional `settings_axes?: SettingsAxis[]`.
5. Extend `BenchmarkRunRow` with `requested_backend: Backend`, `effective_backend: 'cpu' | 'opencl' | 'cpu+opencl-partial' | 'hexagon' | 'cpu+hexagon-partial' | 'unknown'`, `settings_overrides: Partial<Record<SettingsKnob, SettingsValue>>`, and `settings_fingerprint: string`.
6. Bump `BenchmarkReport.version` literal type from `'1.0'` to `'1.1'` and add `settings_axes_used?: SettingsAxis[]`.

**Verification**:

- `cd worktrees/TASK-20260505-1612 && yarn tsc --noEmit` (or equivalent typecheck script) passes — type errors flag every downstream reference that still hardcodes `'cpu' | 'gpu'`. Those are repaired in Steps 2/4/9/10.
- `yarn lint src/__automation__/screens/BenchmarkRunnerScreen.tsx` passes.

### Step 2: Extend `logSignals.ts` with Hexagon parsing and effective-backend arms

**Implements**: WHAT §1d, §4i, §8 D2 (verified strings: `ggml-hex: Hexagon backend ... allocating new registry : ndev N`, `ggml-hex: new session: HTPN`, `ggml-hex: Hexagon Arch version vN`; the generic `offloaded N/M layers to GPU` is reused for partial classification).

**Files**:

- `src/__automation__/logSignals.ts` — extend `BENCH_LOG_RE`, `LogSignals`, `EffectiveBackend`, `emptyLogSignals`, `deriveLogSignals`, `deriveEffectiveBackend`.

**Approach**:

1. Extend `BENCH_LOG_RE` to also match `ggml-hex` / `ggml_hexagon` / `Hexagon backend` / `new session: HTP` / `Hexagon Arch version` so the listener captures the three Hexagon log shapes.
2. Add to `LogSignals`: `hexagon_init: boolean`, `hexagon_device_name: string | null`. Update `emptyLogSignals()` to seed them as `false` / `null`.
3. In `deriveLogSignals`, add three regex parses (literals, NOT line numbers — strings are stable per WHAT §8 D2):
   - `/ggml-hex:\s+Hexagon backend.*allocating new registry/` → set `hexagon_init = true`.
   - `/ggml-hex:\s+new session:\s+(HTP\d+)/` → set `hexagon_device_name` (first match wins, mirrors `opencl_device_name` semantic).
   - Reuse the existing `offloaded N/M layers to GPU` parse for partial-vs-full classification (the line is backend-agnostic per WHAT §8 D2).
4. Extend `EffectiveBackend` union to include `'hexagon' | 'cpu+hexagon-partial'`.
5. Extend `deriveEffectiveBackend`:
   - If `!opencl_init && !hexagon_init` → `'cpu'` (current behaviour preserved).
   - If `hexagon_init` and `offloaded_layers === total_layers` → `'hexagon'`.
   - If `hexagon_init` and `offloaded_layers < total_layers` → `'cpu+hexagon-partial'`.
   - If `hexagon_init` and offload counts unknown → `'unknown'` (the `unknown` fallback called out in WHAT §8 D2).
   - OpenCL arms unchanged. Order: check Hexagon BEFORE OpenCL because both can in theory init, though by construction only one device set is dispatched per cell.

**Verification**:

- `yarn jest scripts/__tests__/logSignals.test.ts` passes after the tester adds coverage per the Testable-Contract Coverage table (rows §6.D).
- `yarn lint src/__automation__/logSignals.ts` passes.

### Step 3: Add settings-axes env-var resolution to `e2e/fixtures/benchmark-models.ts`

**Implements**: WHAT §4b.

**Files**:

- `e2e/fixtures/benchmark-models.ts` — extend `getBenchmarkMatrix()` so the matrix returns `settings_axes` alongside models / quants / backends.

**Approach**:

1. Reuse the existing `parseCsv` helper to read `BENCH_CACHE_TYPE_K`, `BENCH_CACHE_TYPE_V`, `BENCH_FLASH_ATTN_TYPE`, `BENCH_NO_EXTRA_BUFTS`, `BENCH_USE_MMAP`, `BENCH_N_THREADS`.
2. Build `settings_axes: SettingsAxis[]` in the fixed order WHAT §4b.3 mandates: `cache_type_k, cache_type_v, flash_attn_type, no_extra_bufts, use_mmap, n_threads`. Within each axis, emit the values in env-var order.
3. Type coercion (per knob domain — coerce ONCE here so `buildConfig` and the screen never deal with raw strings):
   - `cache_type_k`, `cache_type_v` → string, validated against `Object.values(CacheType)` from `src/utils/types.ts`.
   - `flash_attn_type` → string, validated against `['auto', 'on', 'off']`.
   - `no_extra_bufts` → `'true'|'false'` → boolean.
   - `use_mmap` → string, validated against `['true', 'false', 'smart']`.
   - `n_threads` → integer, validated `> 0`.
4. Invalid value → throw with a descriptive message; the CLI's outer `main()` catches and exits non-zero (WHAT §9e).
5. Widen `BenchmarkMatrixBackend = 'cpu' | 'gpu' | 'hexagon'`. Backend filter still works the same.
6. Return signature gains `settings_axes: SettingsAxis[]` (always present; empty array means "no axes" for downstream — Step 4 maps empty → omit).

**Verification**:

- `yarn jest scripts/__tests__/build-bench-config.test.ts` passes after the tester adds coverage per the Testable-Contract Coverage table (row §9e).
- Manual: `BENCH_CACHE_TYPE_K=q8_0,f16 yarn build:bench-config --out /tmp/c.json && cat /tmp/c.json | jq .settings_axes` shows the expected axis.
- Manual: `BENCH_CACHE_TYPE_K=bogus yarn build:bench-config` exits non-zero with a message.

### Step 4: Update `e2e/helpers/bench-runner.ts:buildConfig` to thread settings_axes

**Implements**: WHAT §4b, §1b.

**Files**:

- `e2e/helpers/bench-runner.ts` — `buildConfig(matrix)` now consumes `matrix.settings_axes` and `matrix.backends: Backend[]`.

**Approach**:

1. Extend `buildConfig`'s return type to include `settings_axes?: SettingsAxis[]` — emit only when non-empty (WHAT §9a: empty array MUST be omitted, not emitted as `[]`).
2. Pass through `matrix.settings_axes` verbatim — no further validation here (Step 3 already validated).
3. Backend list flows through unchanged; widening to `Backend[]` is type-only.
4. No new functions; keep the existing single export shape.

**Verification**:

- `yarn jest scripts/__tests__/build-bench-config.test.ts` passes after the tester adds coverage per the Testable-Contract Coverage table (row §9e).
- `yarn tsc --noEmit` passes — the expanded `BenchConfig` shape now matches the screen's expected shape end-to-end.

### Step 5: Wire CLI summary + push to surface the new axes

**Implements**: WHAT §4b.

**Files**:

- `e2e/scripts/build-bench-config.ts` — extend `summarize()` and `--help` text. No behaviour changes beyond surfacing the new env vars.

**Approach**:

1. Extend `summarize()` to print `settings_axes=N` and one line per axis (`name=value1,value2`) so operators see the sweep before a 30-min run.
2. Extend `--help` text with the six new env vars and one example (`BENCH_CACHE_TYPE_K=q8_0,f16 BENCH_FLASH_ATTN_TYPE=on yarn build:bench-config --push`).
3. Cell-count formula in `summarize()` becomes `models × backends × prod(axis lengths || 1)` — keep the trivial case (no axes → unchanged) producing the same number as today.

**Verification**:

- Manual: `BENCH_CACHE_TYPE_K=q8_0 yarn build:bench-config --out /tmp/c.json` prints `settings_axes=1` and the cell count is doubled when an axis has 2 values.

### Step 6: Refactor `runMatrix` — cell expansion, apply/restore, Hexagon path

**Implements**: WHAT §2, §4a, §4c, §4h I4/I5/I7, §3.

**Files**:

- `src/__automation__/screens/BenchmarkRunnerScreen.tsx` — most of the change lands here.

**Approach**:

1. **Pre-run snapshot (4c.1)**: at the top of `runMatrix`, before the cell loop, capture the matrix-level snapshot of the six fingerprint knobs from `modelStore.contextInitParams`:
   ```ts
   const preRunSnapshot = {
     cache_type_k: modelStore.contextInitParams.cache_type_k,
     cache_type_v: modelStore.contextInitParams.cache_type_v,
     flash_attn_type: modelStore.contextInitParams.flash_attn_type,
     no_extra_bufts: modelStore.contextInitParams.no_extra_bufts,
     use_mmap: modelStore.contextInitParams.use_mmap,
     n_threads: modelStore.contextInitParams.n_threads,
   };
   ```
   This is the matrix-level fixed point used for both restoration (4c.3) and failure-path fingerprint construction (9c).
2. **`expandAxes` helper** (module-private, pure): `expandAxes(axes: SettingsAxis[]): Array<Partial<Record<SettingsKnob, SettingsValue>>>`. When `axes` is undefined / empty returns `[{}]` (one cell, empty overrides — WHAT §2). Otherwise produces the cartesian product preserving axis order.
3. **Cell list**: replace the current 3-deep loop with `for model × variant × backend × overrides` (WHAT §2). Backend list is now `Backend[]`; cells track an `overrides` field of type `Partial<Record<SettingsKnob, SettingsValue>>`.
4. **Hexagon device resolution**: at run start (mirroring the existing GPU resolution), if `config.backends.includes('hexagon')`, call `getDeviceOptions()` once and find the `id === 'hexagon'` option's `devices`. Store as `hexagonDevices: string[] | null`. NOT `isHexagonAvailable()` — `getDeviceOptions()` is the single source of truth per WHAT §8 D3.
5. **Hexagon pre-check (per cell, mirror of GPU pre-check)**: if `backend === 'hexagon' && !hexagonDevices`, write `status: 'failed'`, `error: 'Hexagon device not available'`, `effective_backend: 'unknown'`, `settings_overrides: <requested>`, `settings_fingerprint: <built per Step 7>`, `init_settings: {}`, then `continue` to the next cell. (WHAT §4a.7, §4h I7, §6.C)
6. **`applySettingsOverrides(overrides)` helper** (module-private):
   - For each entry in `overrides`, call the matching existing setter on `modelStore`:
     - `cache_type_k` → `modelStore.setCacheTypeK(value as CacheType)`
     - `cache_type_v` → `modelStore.setCacheTypeV(value as CacheType)`
     - `flash_attn_type` → `modelStore.setFlashAttnType(value as 'auto' | 'on' | 'off')`
     - `no_extra_bufts` → `modelStore.setNoExtraBufts(value as boolean)`
     - `use_mmap` → `modelStore.setUseMmap(value as 'true' | 'false' | 'smart')`
     - `n_threads` → `modelStore.setNThreads(value as number)`
   - **Order matters**: apply `flash_attn_type` BEFORE `cache_type_k` / `cache_type_v` so the constraint state matches the cell's requested intent BEFORE the cache-type setters run. Reasoning: when the cell's `flash_attn_type` resolves to `'auto'` or `'on'`, the cache-type setters take effect (the requested override lands as expected). When it resolves to `'off'`, the cache-type setters still no-op silently per WHAT §4e and D11 — applying `flash_attn_type` first makes that no-op correctly attributable to the declared intent, not to stale state from a prior cell. The silent no-op stays the documented behaviour and surfaces in the report as a divergence between `settings_overrides` (the request) and `init_settings` (the post-init reality), which the operator can inspect (WHAT §4e final paragraph). Within the same cell, axes-order from WHAT §4b.3 places `cache_type_k`/`cache_type_v` before `flash_attn_type`, so the helper MUST iterate in a different order than axis ingestion: iterate `flash_attn_type` first, then everything else.
   - **No direct mutation of `contextInitParams`** (WHAT §4h I4).
7. **`restoreSettingsSnapshot(snapshot)` helper** (module-private):
   - Calls each setter with the snapshot value, wrapped in per-setter try/catch so a single setter throw does not mask the matrix's own outcome (WHAT §4c.3).
   - Apply order: same as `applySettingsOverrides` (`flash_attn_type` first) so the restore deterministically lands the snapshot values regardless of the current (post-cell) state.
8. **Per-cell apply call site**: invoke `applySettingsOverrides(overrides)` AFTER the GPU/Hexagon pre-check and AFTER the model resolve/download, BUT BEFORE `modelStore.setDevices(...)` and `modelStore.initContext(...)`. Reasoning: model download can take 30 min; applying the overrides earlier than necessary widens the window where stale settings are visible if the run aborts.
9. **Post-init snapshot hoist (WHAT §9d)**: hoist the `initSettings = JSON.parse(JSON.stringify(modelStore.contextInitParams))` capture into a `let postInitSnapshot: typeof modelStore.contextInitParams | null = null;` declared BEFORE the inner try, and assign it immediately after `await modelStore.initContext(resolvedModel)` resolves. The success path uses it for `init_settings`; the catch path reads it (or null) to choose between standard fingerprint and `req:`-prefixed fingerprint per Step 7.
10. **Outer matrix-level finally**: in the OUTER finally (after `toggleNativeLog(false)`), call `restoreSettingsSnapshot(preRunSnapshot)`. Success and failure paths converge here; no per-path restore is needed. Restoration must run on every exit path — that is the I5 invariant. Order inside the finally: log toggle off → restore snapshot. Both wrapped in try/catch so neither blocks the other.

**Verification**:

- `yarn lint src/__automation__/screens/BenchmarkRunnerScreen.tsx` passes.
- `yarn tsc --noEmit` passes.
- `yarn jest src/__automation__/screens/__tests__/BenchmarkRunnerScreen.test.tsx` passes after the tester adds coverage per the Testable-Contract Coverage table (rows §6.A, §6.B, §6.C, §6.E, §4h I4/I5/I7, §9d).
- Manual: `BENCH_CACHE_TYPE_K=q8_0 BENCH_FLASH_ATTN_TYPE=on adb push <config> ...` then deep-link launch — observe the screen status `running:1/2:.../cache_type_k=q8_0;flash_attn_type=on` etc (Step 8 wires the tag string).

### Step 7: Fingerprint helper — success and failure-path constructions

**Implements**: WHAT §4d (steps 1–6), §9c, §9d, §4h I2/I3.

**Files**:

- `src/__automation__/screens/BenchmarkRunnerScreen.tsx` — co-locate with the runner. Helper is module-private, exported for tests via the existing `__runner` test seam.

**Approach**:

1. Define module-private constant `FINGERPRINT_KEYS: readonly SettingsKnob[] = ['cache_type_k', 'cache_type_v', 'flash_attn_type', 'no_extra_bufts', 'use_mmap', 'n_threads']` (WHAT §4d.1, fixed contract).
2. **Canonicalisation** (`canonicalise(record): string`):
   - For each key in `FINGERPRINT_KEYS`, look up the value in `record`.
   - Missing key → literal `"-"` (WHAT §4d.2 — covers iOS-missing `no_extra_bufts`).
   - Booleans → `'true' | 'false'`. Numbers → `String(n)`. Strings → `String(s).toLowerCase()`.
   - Join `key=value` pairs with `;`.
3. **`buildSuccessFingerprint(postInitSnapshot, hadAxesInConfig, isEmptyOverrides)`** (WHAT §4d, §4h I2):
   - If `!hadAxesInConfig && isEmptyOverrides` → return literal `'app-default'` (the only path that mints this literal at runtime; D7).
   - Otherwise return `canonicalise(postInitSnapshot)`.
4. **`buildFailureFingerprint(preRunSnapshot, requestedOverrides, hadAxesInConfig)`** (WHAT §9c):
   - If `!hadAxesInConfig && Object.keys(requestedOverrides).length === 0` → return `'app-default'` (so a failed `app-default` cell still buckets correctly — WHAT §6.C).
   - Otherwise `merged = {...preRunSnapshot, ...requestedOverrides}` (object spread, no constraint replay — WHAT §9c.2).
   - Return `'req:' + canonicalise(merged)` (WHAT §9c.4, §4h I3 exception (b)).
5. Export the canonicaliser and both builders as named exports from the module (alongside `runMatrix`) so unit tests can import them directly without the React tree. (`__runner` is a runtime prop override on the screen component; it does NOT cover importing helpers from the module under test.)
6. **Caller wiring**:
   - Success path (Step 8 row writer): `buildSuccessFingerprint(postInitSnapshot, hadAxesInConfig, isEmptyOverrides)`.
   - Failure path BEFORE `initContext` resolved (post-init snapshot is null): `buildFailureFingerprint(preRunSnapshot, overrides, hadAxesInConfig)`.
   - Failure path AFTER `initContext` resolved (post-init snapshot is non-null per Step 6.9): `buildSuccessFingerprint(postInitSnapshot, hadAxesInConfig, isEmptyOverrides)` — WHAT §9d explicitly says no `req:` prefix.

**Verification**:

- `yarn jest src/__automation__/screens/__tests__/BenchmarkRunnerScreen.test.tsx` passes after the tester adds coverage per the Testable-Contract Coverage table (rows §4h I2/I3, §9b, §9c).
- The five fingerprint examples from WHAT §4d render byte-identically in tests.

### Step 8: Row writer — overrides, fingerprint, status `<tag>` extension

**Implements**: WHAT §3 (state machine `<tag>` extension), §4a steps 4–6, §4i (component contract).

**Files**:

- `src/__automation__/screens/BenchmarkRunnerScreen.tsx` — extend the success and failure row builders.

**Approach**:

1. Track `hadAxesInConfig: boolean = !!(config.settings_axes && config.settings_axes.length > 0)` once per run (the screen never sees `[]` per Step 4 / WHAT §9a — but defend anyway).
2. Build a short `fingerprintTag` string for the status line (WHAT §3, §8 D9):
   - `'app-default'` → empty string (legacy status format).
   - Otherwise, render the overrides map as `;`-joined `key=value` pairs (the requested map, NOT the post-init canonicalisation, so the operator sees what they ASKED for in the status). Truncate to 60 chars.
   - Status line becomes `running:${i+1}/${cells.length}:${model.id}/${variant.quant}/${backend}${tagSuffix}` where `tagSuffix = fingerprintTag ? `/${fingerprintTag}` : ''`.
3. **Success row builder**: extend the existing `BenchmarkRunRow` literal with `settings_overrides: overrides`, `settings_fingerprint: buildSuccessFingerprint(postInitSnapshot, hadAxesInConfig, isEmptyOverrides)`. `init_settings` continues to be the post-init `JSON.parse(JSON.stringify(modelStore.contextInitParams))` (Step 6.9 captures it once into `postInitSnapshot`).
4. **Catch (failure) row builder**: extend with `settings_overrides: overrides` (always present even on failure — WHAT §4h I1 + §5 single-writer rule). Fingerprint construction:
   - `if (postInitSnapshot != null)` → `buildSuccessFingerprint(postInitSnapshot, hadAxesInConfig, isEmptyOverrides)` (WHAT §9d).
   - else → `buildFailureFingerprint(preRunSnapshot, overrides, hadAxesInConfig)` (WHAT §9c).
5. **GPU/Hexagon pre-check failure rows** (the early `continue` paths from Step 6): construct the row using the `buildFailureFingerprint` path — `postInitSnapshot` is null at that point and `init_settings: {}` is the existing convention (WHAT §6.C).
6. **Report shell update**: bump `report.version` from `'1.0'` to `'1.1'` literal. Add `settings_axes_used: config.settings_axes` to the report shell ONLY when `hadAxesInConfig` (WHAT §1e, §9a).

**Verification**:

- `yarn jest src/__automation__/screens/__tests__/BenchmarkRunnerScreen.test.tsx` passes.
- `yarn lint` passes.
- Manual: an `app-default` run still produces status strings that match the existing E2E spec's regex (legacy match preserved).

### Step 9: `merge-bench-reports.ts` — 4-tuple key + version refusal

**Implements**: WHAT §4f, §4h I1/I8, §9g.

**Files**:

- `e2e/scripts/merge-bench-reports.ts`

**Approach**:

1. Extend `RunRow` interface with `settings_fingerprint: string`, `settings_overrides: Record<string, unknown>`. Extend `requested_backend: 'cpu' | 'gpu' | 'hexagon'`. Extend `effective_backend` string union to include `hexagon | cpu+hexagon-partial`.
2. **`rowKey(r)`** (WHAT §4f.1) becomes `${r.model_id}::${r.quant}::${r.requested_backend}::${r.settings_fingerprint}`.
3. **Version-mixing refusal** (WHAT §4f.2, §4h I8): in `mergeReports`, before the dedupe loop, collect `versions = new Set(reports.map(r => r.version ?? '1.0'))`. If `versions.size > 1`, throw `Error('inconsistent baseline versions: <v1>,<v2>; run migrate-baseline-v1-to-v1_1 first')` — non-zero exit at the CLI level.
4. **I1 row validation** (WHAT §4h I1): on a v1.1 report, every row MUST have non-null `settings_fingerprint` (string) and `settings_overrides` (object). If a row violates this, throw `Error('row missing settings_fingerprint/settings_overrides — input is malformed')` so silent legacy bleeds are surfaced.
5. **`compareRuns`** sort: extend tie-break to include `settings_fingerprint` after `requested_backend` (WHAT §4f.4) — keeps baseline diffs stable.
6. **Output baseline `version`**: the merger output should now use the highest input version (which after the version-mixing guard is a single value). Update the `pickFirst<string>(reports, 'version') ?? '1.0'` line accordingly — fall back to `'1.1'` because the runner now always emits 1.1.
7. **`settings_axes_used`** propagation (WHAT §1f, §4f.5): in the baseline output, set `settings_axes_used` to the union (deduped by `name`) of `settings_axes_used` from input reports, when any input has them. When two reports declare the same axis name with different value lists, take the union of values, preserving WHAT §4b.3 axis order (between axes) and env-var-order within each axis's values (within an axis: keep the first-seen order from the earliest input, then append values from later inputs that were not already present). This is allowed per WHAT §4f.5 even when inputs disagree on axes.
8. **`reconcileBench` unchanged** — settings axes are NOT a `bench` protocol field (WHAT §4f.5).

**Verification**:

- `yarn jest scripts/__tests__/merge-bench-reports.test.ts` passes after the tester adds coverage per the Testable-Contract Coverage table (rows §4h I1, §4h I8).
- Manual: pointing the merger at a mix of v1.0 + v1.1 baselines exits non-zero with the migration hint.

### Step 10: `benchmark-compare.ts` — 4-tuple key + Hexagon arms

**Implements**: WHAT §4g.

**Files**:

- `e2e/scripts/benchmark-compare.ts`

**Approach**:

1. Extend `BenchmarkRunReport` with `settings_fingerprint?: string` and `settings_overrides?: Record<string, unknown>` (optional in the type to keep the script tolerant of legacy v1.0 inputs that bypass the merger; the comparison itself still keys on the field).
2. Widen `requested_backend` and `effective_backend` to match the v1.1 unions from Step 1.
3. Extend `RowDelta` with `settings_fingerprint?: string`. Surface it in console output between `quant` and `requested_backend` for readability.
4. **`rowKey(r)`** (WHAT §4g.1) becomes `${r.model_id}::${r.quant}::${r.requested_backend}::${r.settings_fingerprint ?? 'app-default'}` — the `?? 'app-default'` is defensive so a stray legacy report does not crash the script (the merger blocks the v1.0 mixing path; this fallback handles a bare baseline file passed in directly).
5. **`bench_protocol_mismatch`** unchanged (WHAT §4g.2). Settings differences are NOT a protocol mismatch.
6. **`missing_in_current` / `missing_in_baseline`** semantics extend cleanly — no code change beyond the new `rowKey` (WHAT §4g.3).
7. **Effective-backend mismatch flag** (WHAT §4g.4): no change — the existing `baseRow.effective_backend !== curRow.effective_backend` check already covers `hexagon` / `cpu+hexagon-partial` because the comparison is string equality.
8. Update the printed table column widths so the new fingerprint column does not overflow on terminals — adjust via existing `padEnd` calls.

**Verification**:

- `yarn jest scripts/__tests__/benchmark-compare.test.ts` passes after the tester adds coverage per the Testable-Contract Coverage table (the §4g rowKey + Hexagon-arm rows surfaced via the §6.D effective-backend assertions).

### Step 11: One-shot v1.0 → v1.1 baseline migration script + run on three baselines

**Implements**: WHAT §4f.2, §8 D8.

**Files**:

- `e2e/scripts/migrate-baseline-v1-to-v1_1.ts` (new) — pure, idempotent migration.
- `e2e/baselines/benchmark/poco-myron.json` — migrated in this PR.
- `e2e/baselines/benchmark/poco-x7-klee.json` — migrated.
- `e2e/baselines/benchmark/samsung-s23.json` — migrated.

**Approach**:

1. CLI shape mirrors `merge-bench-reports.ts`: `--input <glob>`, optional `--in-place`, `--out-dir <dir>`. `--help` describes the v1.0 → v1.1 stamping semantic.
2. Pure helper `migrateReport(report: any): any`:
   - If `report.version === '1.1'` already: return `report` unchanged (idempotent — WHAT D8 implies idempotency for replay safety).
   - If `report.version === '1.0'` (or missing — treat as 1.0 for legacy):
     - For every row in `report.runs`: stamp `settings_overrides: {}` and `settings_fingerprint: 'app-default'` (the only path that mints this literal retroactively — WHAT §4f.2, D7, D8).
     - Set `report.version = '1.1'`.
     - Do NOT add `settings_axes_used` (those baselines were captured without sweeps, by construction).
   - Else: throw `Error('unsupported version: <v>')` so unknown formats fail loud.
3. CLI iterates the input files, applies `migrateReport`, writes back (or to `--out-dir`).
4. **Run the script** on the three checked-in baselines:
   ```bash
   cd worktrees/TASK-20260505-1612
   npx ts-node e2e/scripts/migrate-baseline-v1-to-v1_1.ts \
     --input 'e2e/baselines/benchmark/*.json' --in-place
   ```
5. Commit the migrated baselines in this same PR (WHAT §8 D8: "one-shot migration ... in the same PR").

**Verification**:

- `yarn jest scripts/__tests__/migrate-baseline-v1-to-v1_1.test.ts` passes after the tester adds coverage per the Testable-Contract Coverage table (row §9g).
- `git diff e2e/baselines/benchmark/` shows three baselines bumped to `"version": "1.1"` and every row now carries `"settings_fingerprint": "app-default"` and `"settings_overrides": {}`.
- Re-running the migration on the migrated files leaves them unchanged (idempotency).

### Step 12: Bootstrap `context/architecture/benchmark-matrix.md` from WHAT

**Implements**: AGENTS.md "Architecture library" rule — "the implementer absorbs the approved delta into the flow doc in the same PR that lands the code". This story SEEDS the file (none exists pre-merge per WHAT preamble).

**Files**:

- `context/architecture/benchmark-matrix.md` — new file in the dev-team repo (NOT the worktree). The WHAT preamble explicitly states it "seeds a new flow doc on merge".

**Approach**:

1. Copy the full body of `workflows/stories/TASK-20260505-1612/what.md` into the new flow doc, removing the story-scoped header and the Review History section.
2. Convert markers per `context/architecture/README.md`:
   - All `(P)` markers → `(C)` (the proposal IS the new current truth as of this merge).
   - All `(D)` markers stay `(D)` (decisions remain decisions; the rationale is preserved).
   - Verify zero `(?)` markers remain (none in WHAT — already (D)).
3. Title the doc `# Benchmark Matrix Flow` and add the standard preamble naming the bootstrapping story (mirror `chat-flow.md`'s "Bootstrapped from ..." line).
4. Leave the story-scoped `what.md` in place for archival (per AGENTS.md: "story-scoped what.md is left intact for archival").
5. Verify against the architecture README's required-sections list (data model, external shape, state machine, contract, single-writer rule, canonical scenarios, edge cases, decisions) — WHAT already follows the same template, so this is a marker conversion + title pass.

**Verification**:

- `grep -n '(P)' context/architecture/benchmark-matrix.md` → no matches.
- `grep -n '(?)' context/architecture/benchmark-matrix.md` → no matches.
- `grep -nc '(C)' context/architecture/benchmark-matrix.md` ≥ ~30 (matches WHAT's count).
- The doc has all eight standard sections.

---

## Testable-Contract Coverage

Mapping every canonical scenario from WHAT §6 plus every invariant from §4h that is testable in unit form.

| Contract item | Verified by |
| --- | --- |
| §6.A — backwards compatibility (no axes → `app-default`, v1.1) | `BenchmarkRunnerScreen.test.tsx`: "no settings_axes in config produces single cell with `settings_fingerprint:app-default` and `report.version:'1.1'`" |
| §6.B — cache_type_k sweep on iOS (cartesian product, post-init fingerprint) | `BenchmarkRunnerScreen.test.tsx`: "cache_type_k axis [f16,q8_0] × 2 backends produces 4 cells with distinct post-init fingerprints" |
| §6.C — Hexagon on klee (no Hexagon → fail-fast row, status:failed) | `BenchmarkRunnerScreen.test.tsx`: "backend=hexagon when getDeviceOptions has no hexagon entry writes status:'failed', error:'Hexagon device not available', effective_backend:'unknown', fingerprint:'app-default' (no axes)" |
| §6.D — Hexagon on POCO (hexagon_init parsed, effective_backend hexagon) | `logSignals.test.ts`: "deriveLogSignals parses ggml-hex registry-allocation + new session: HTP0 lines and reports hexagon_init=true, hexagon_device_name='HTP0'"; "deriveEffectiveBackend returns 'hexagon' on full offload + hexagon_init"; "...returns 'cpu+hexagon-partial' on partial offload + hexagon_init" |
| §6.E — restoration after run (snapshot before == settings after) | `BenchmarkRunnerScreen.test.tsx`: "after a successful matrix run, modelStore.cache_type_k / use_mmap / n_threads equal the pre-run snapshot values" + a parallel test for the throw path |
| §4h I1 — every v1.1 row carries non-null fingerprint + overrides | `merge-bench-reports.test.ts`: "rejects row missing settings_fingerprint" + "rejects row missing settings_overrides" |
| §4h I2 — `app-default` literal reserved for no-axes empty-overrides | `BenchmarkRunnerScreen.test.tsx` fingerprint helper unit tests: "buildSuccessFingerprint(snapshot, hadAxes=false, emptyOverrides=true) returns literal 'app-default'"; "...returns canonicalised string when hadAxes=true even with empty overrides" |
| §9b — one-value axis still emits a canonical fingerprint, NOT `app-default` | fingerprint helper unit tests: "buildSuccessFingerprint(snapshot, hadAxesInConfig=true, isEmptyOverrides=true) returns the canonicalised semicolon-joined string, NOT the literal 'app-default' (the §4h I2 boundary load-bearing for §4d D7)" |
| §4h I3 — fingerprint pure function + 2 enumerated exceptions | fingerprint helper unit tests: byte-equality of the five examples in WHAT §4d; "buildFailureFingerprint produces 'req:' prefix"; "post-init failure path uses non-`req:` fingerprint" |
| §4h I4 — apply uses only existing setters | `BenchmarkRunnerScreen.test.tsx`: "applySettingsOverrides calls modelStore.setCacheTypeK / setUseMmap / setNThreads exactly once each per cell — never assigns to contextInitParams directly" (jest.spyOn on the setter) |
| §4h I5 — restore runs on every exit path | `BenchmarkRunnerScreen.test.tsx`: parallel tests for the success path, mid-cell throw path, and outer-thrown path |
| §4h I7 — backend-unavailable cell does not abort the matrix | `BenchmarkRunnerScreen.test.tsx`: "when cell 1/3 is hexagon-on-klee, cells 2/3 and 3/3 still run" |
| §4h I8 — mixed-version baseline merge is fatal | `merge-bench-reports.test.ts`: "throws when input reports mix version:'1.0' and version:'1.1'" |
| §9c — pre-init failure path constructs `req:` fingerprint from pre-run snapshot + virtual override apply | fingerprint helper unit tests: "buildFailureFingerprint(preRunSnapshot, {cache_type_k:'q8_0'}) yields 'req:cache_type_k=q8_0;...rest from snapshot'" |
| §9d — post-init failure path uses standard (non-`req:`) fingerprint | `BenchmarkRunnerScreen.test.tsx`: "cell that throws inside ctx.bench() but after initContext writes a standard (no `req:`) fingerprint derived from postInitSnapshot" |
| §9e — invalid env-var value rejected at config-build time | `build-bench-config.test.ts`: "BENCH_CACHE_TYPE_K=bogus throws"; "BENCH_FLASH_ATTN_TYPE=invalid throws"; "BENCH_N_THREADS=0 throws" |
| §9g — migration script idempotency | `migrate-baseline-v1-to-v1_1.test.ts`: "running migrateReport twice produces the same output as running it once" + "migrateReport stamps every row with app-default + empty overrides" + "migrateReport throws on unknown version" |

The implementer hands the test enumeration list above to `pocketpal-tester` after Steps 1–11 land. The tester writes the unit/integration tests against named exports (canonicaliser, `buildSuccessFingerprint`, `buildFailureFingerprint`) and the `__runner` test seam where a React tree is required; no separate "Step 13" exists in the implementation steps because tests are added by the tester stage, anchored to this coverage table.

---

## Native Verification

`NATIVE_CHANGES=NO`. No `package.json`, native modules, `ios/`, `android/`, Podfile, or `build.gradle` changes — everything is JS / TS / JSON. **No `pod install`, no iOS build, no Android build is required for this PR**, and the pipeline-reviewer should NOT block on missing native verification (per AGENTS.md "Native verification" rule applied negatively).

The runtime change DOES exercise the existing native path (`getDeviceOptions()`, `getBackendDevicesInfo()` from llama.rn, `addNativeLogListener`), but only via existing APIs that ship in the current native binary. Validation via E2E baseline run on at least one device family (POCO Myron for the cpu+gpu+app-default coverage; preferably also one Hexagon-capable device) is recommended pre-merge but not gated by the AGENTS.md native-verification rule.

---

## Visual Confirmation

`Visual Confirmation=NO`. The screen is `__automation__`-flagged, not a user-facing surface; status changes are observable via Appium / E2E only. No screenshots required.

---

## Deferred Items

None additionally deferred by this story. The WHAT explicitly defers:

- **§5 Deferred cleanup (D11)** — explicit warning when `setCacheTypeK/V` no-op silently because flash_attn is off. Documentation only; the report's `settings_overrides` field already surfaces the discrepancy. Out of scope here. Tracked as a follow-up.

---

## What this plan is NOT

- not a design doc — design lives in `what.md`
- not a justification — `intent-brief.md` has the request
- not exhaustive — only the steps the implementer needs; if a step would just be "obey WHAT §N", it references WHAT instead of restating
- not an architecture rewrite — Step 12 is a marker-conversion pass, not a redesign


---

## Review History

### Round 1 — plan-critic (HAS_CONCERNS)

| Finding | Severity | Resolution |
| --- | --- | --- |
| C1: Eight references to non-existent "Step 13" in verification blocks | CONCERN | **FIXED**: chose option (b) — re-anchored every "after Step 13 test additions" verification line to the Testable-Contract Coverage table with the specific row(s) each step exercises. The codebase convention (line 431) is that the tester writes the tests post-implementation; there is no Step 13. The handoff sentence at line 432 was extended to make this explicit ("no separate 'Step 13' exists in the implementation steps because tests are added by the tester stage, anchored to this coverage table"). All eight verification blocks updated: Step 2 (§6.D), Step 3 (§9e), Step 4 (§9e), Step 6 (§6.A/B/C/E + §4h I4/I5/I7 + §9d), Step 7 (§4h I2/I3 + §9b + §9c), Step 9 (§4h I1 + §4h I8), Step 10 (§4g rowKey + §6.D), Step 11 (§9g). |
| C2: §9b ("one-value axis") not in test coverage | CONCERN | **FIXED**: added a fingerprint-helper unit-test row to the Testable-Contract Coverage table (between §4h I2 and §4h I3). Test asserts `buildSuccessFingerprint(snapshot, hadAxesInConfig=true, isEmptyOverrides=true)` returns the canonicalised semicolon-joined string and NOT the literal `'app-default'` — the boundary that load-bears WHAT §4h I2 / §4d D7. |
| C3: Step 6.6 apply-order reasoning partially wrong (cache setters STILL no-op when flash_attn=off) | CONCERN | **FIXED**: tightened Step 6.6's reasoning. The order rule is now correctly motivated as "ensure the constraint state matches the requested intent BEFORE cache-type setters run, so the no-op behaviour in the `'off'` case is correctly attributable to the declared intent, not to stale state from a prior cell." The silent no-op (WHAT §4e + D11) is preserved as documented expected behaviour, surfacing in the `settings_overrides` vs `init_settings` divergence the operator can inspect. WHAT not modified. |
| S4: Step 7.5 "test seam" wording (`__runner` is not how unit tests import helpers) | SUGGESTION | **FIXED**: Step 7 item 5 reworded to "Export the canonicaliser and both builders as named exports from the module (alongside `runMatrix`) so unit tests can import them directly without the React tree", with an inline note clarifying that `__runner` is a runtime prop override on the screen component and does NOT cover importing helpers from the module under test. Verified at `BenchmarkRunnerScreen.tsx:469,474,502,509` that `__runner` is a screen-prop runtime override, not a module-export bag. |
| S5: Step 6.10 outer-finally restore wording (duplicate-restore reading) | SUGGESTION | **FIXED**: reworded to "in the OUTER finally (after `toggleNativeLog(false)`), call `restoreSettingsSnapshot(preRunSnapshot)`. Success and failure paths converge here; no per-path restore is needed." Removes the duplicate-restore implication while keeping the I5 ordering note (log toggle off → restore snapshot, both wrapped in try/catch). |
| S6: Step 9.7 `settings_axes_used` union semantics for two-axis-name conflict | SUGGESTION | **FIXED**: Step 9.7 now specifies the value-list merge rule: "when two reports declare the same axis name with different value lists, take the union of values, preserving WHAT §4b.3 axis order (between axes) and env-var-order within each axis's values (within an axis: keep the first-seen order from the earliest input, then append values from later inputs that were not already present)." |
