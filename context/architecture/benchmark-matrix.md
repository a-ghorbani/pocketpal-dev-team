# Benchmark Matrix Flow

**Purpose**: cumulative architecture truth for the on-device benchmark matrix runner (`BenchmarkRunnerScreen` + its CLI / spec / merge / compare toolchain). Bootstrapped from TASK-20260505-1612 (settings-sweep, Hexagon backend, isolated lifecycle, v1.1 schema). Meant to fit in your head.

Convention: **(C)** = current behaviour from code, **(D)** = decision.

---

## 1. Data model

### 1a. `BenchConfig` (on-device JSON; read by the screen, produced by the CLI / spec)

```
BenchConfig
  models:    BenchModelEntry[]         # id, hfModelId, quants:[{quant, filename, size?}]
  backends:  Backend[]                 # 'cpu' | 'gpu' | 'hexagon'
  bench?:    { pp, tg, pl, nr }
  inter_cell_settle_ms?: number        # default 2000, ≥0
  settings_axes?: SettingsAxis[]       # sweep dimensions
    name:   SettingsKnob               # closed enum (see below)
    values: SettingsValue[]            # >= 1 entry; matches knob domain

SettingsKnob =
  | 'cache_type_k' | 'cache_type_v' | 'flash_attn_type'
  | 'no_extra_bufts' | 'use_mmap' | 'n_threads'
SettingsValue = string | number | boolean
```

Stored at the e2e flavor's `ExternalDirectoryPath`. The cell list (cartesian product `model × quant × backend × settings_axes`) is computed at runtime, never persisted.

### 1b. `BenchmarkRunRow` (per-cell row)

```
BenchmarkRunRow
  model_id, quant, requested_backend          # closed enums
  effective_backend                           # see 1c
  pp_avg, tg_avg: number | null               # null on failed/skipped
  wall_ms, peak_memory_mb
  log_signals: LogSignals                     # 1d
  init_settings: Record<string, unknown>      # composed cellParams snapshot (post-compose, pre-initLlama)
  effective_init_params: Record<string, unknown>  # composed cellParams, minus `model` filePath
  settings_overrides: Partial<SettingsKnob->Value>
  settings_fingerprint: string                # canonical key (4d)
  status: 'ok' | 'skipped' | 'failed'
  reason?, error?, timestamp
```

### 1c. `EffectiveBackend`

```
'cpu' | 'opencl' | 'cpu+opencl-partial' | 'hexagon' | 'cpu+hexagon-partial' | 'unknown'
```

### 1d. `LogSignals`

Includes `opencl_init`, `opencl_device_name`, `adreno_gen`, `large_buffer_enabled`, `hexagon_init`, `hexagon_device_name`, `offloaded_layers`, `total_layers`, `memory_buffers`, `raw_matches[]`. Baselines ship with `raw_matches` empty (debug-only field; canonical merge path strips it).

### 1e. `BenchmarkReport` (file-level)

```
BenchmarkReport
  version: '1.1', platform: 'android', timestamp, preseeded
  bench: { pp, tg, pl, nr }
  inter_cell_settle_ms: number                # top-level echo from config (default 2000)
  settings_axes_used?: SettingsAxis[]         # echo of config.settings_axes; absent when empty
  runs: BenchmarkRunRow[]
```

### 1f. Baseline (post-merge) — `e2e/baselines/benchmark/<device>.json`

Same shape as `BenchmarkReport` plus merge metadata: `device`, `soc`, `commit`, `llama_rn_version`, `os_version`, `generated_by`, `source_files`. Optional agent operational fields (`tier`, `stats`) may be present and are ignored by consumers.

**Glossary**: **Cell** = element of `(model, variant, backend, settings_overrides)`. **Settings axis** = one knob + its sweep values. **Settings fingerprint** = canonical string identifying a cell's settings config; fourth axis of the dedupe key. **App-default fingerprint** = literal `"app-default"`, emitted when `settings_axes` is absent (D7).

---

## 2. Event flow

```
for model in config.models
  for variant in model.quants
    for backend in config.backends
      for overrides in expandAxes(config.settings_axes)   # [{}] when absent
        runCell(model, variant, backend, overrides)
```

---

## 3. State machine

Screen status: `idle | running:<tag> | downloading:<f> | cell-failed:<n>:<msg> | complete | error:<msg>`. The `<tag>` substring includes a short fingerprint hint to disambiguate identical `(model,quant,backend)` cells with different settings (D9).

---

## 4. Contract

### 4a. `runMatrix` (the runner)

1. Validate config (throws on missing file). Resolve `settings_axes`; absent → `[{}]` (single cell, `app-default`). (C)
2. **Acquire exclusive context lifecycle**: `modelStore.enterBenchmarkMode()` sets `benchmarkActive=true` synchronously and releases any pre-existing context. While the flag is true, `modelStore.initContext` / `selectModel` reject — non-bench code cannot race the matrix. (C)
3. Per cell: `composeCellParams({base: benchBase, overrides, devices, n_gpu_layers, filePath})` → `cellParams` (pure dict; no setter calls, no store mutation). (C)
4. Per cell: `snapshotCellInitSettings(cellParams)` → `init_settings`. The fingerprint is derived from this snapshot (4d). `settings_overrides` and `settings_fingerprint` are written on EVERY row, success or failure. (C)
5. Per cell: `initLlama(cellParams)` directly. After it resolves, validate `effective_backend` satisfies the requested backend (`backend === effective` OR partial-offload of the same backend). Backend-mismatch → throw → row recorded as failed. (C)
6. Per cell `finally`: release the runner-owned `LlamaContext` and detach the native-log listener (each at most once if the cell initialised). (C)
7. Matrix-level inter-cell: `purgeNativeAllocator()` (Android `mallopt(M_PURGE_ALL)`; iOS no-op) then sleep `inter_cell_settle_ms` so allocator and driver teardown settle before the next cell. (C)
8. Matrix-level `finally`: `toggleNativeLog(false)` + `modelStore.exitBenchmarkMode()`. Both idempotent (safe even if their setup never ran). No "restore user settings" step — the runner never wrote to `modelStore.contextInitParams`. (C)
9. Hexagon (or GPU) unavailable on the device: write `status:'failed'`, `error:'<Backend> device not available'`, `effective_backend:'unknown'`; continue. (C)

### 4b. `build-bench-config.ts` (CLI) and `bench-runner.ts:buildConfig` (spec helper)

Both producers MUST emit identical JSON:

1. Honour `BENCH_TIER` (smoke/focused/full), `BENCH_MODELS`, `BENCH_QUANTS`, `BENCH_BACKENDS` (includes `hexagon`). With no settings env vars, emit a config WITHOUT `settings_axes` (the absence semantic; D7). (C)
2. Settings env vars (comma-separated, lowercase, trimmed): `BENCH_CACHE_TYPE_K`, `BENCH_CACHE_TYPE_V`, `BENCH_FLASH_ATTN_TYPE`, `BENCH_NO_EXTRA_BUFTS`, `BENCH_USE_MMAP`, `BENCH_N_THREADS`. Append a `SettingsAxis` per non-empty var in the **fixed order** `[cache_type_k, cache_type_v, flash_attn_type, no_extra_bufts, use_mmap, n_threads]` (D5). (C)
3. Validate value domains at config-build time. Invalid → non-zero exit; no config written. (C)

### 4c. `composeCellParams` (runner-internal)

```ts
composeCellParams({filePath, base: benchBase, overrides, devices, n_gpu_layers})
  → ContextParams       // the dict passed to initLlama
```

Pure: object-spread `overrides` over `benchBase`, add `{model: filePath, devices, n_gpu_layers}`. `benchBase` is `DEFAULT_BENCH_BASE_PARAMS` with `n_threads` resolved once at run start from `getRecommendedThreadCount()`. `use_mmap: 'smart'` resolves to a platform-default boolean inside this helper, so `init_settings` and the fingerprint reflect the resolved value. There is no `restoreSettingsSnapshot`: the runner never writes to `contextInitParams`.

### 4d. Settings fingerprint contract

Derived from the **composed cell params snapshot** (post-`composeCellParams`, pre-`initLlama`). Captured before `initLlama` so a post-init throw still produces a standard (non-`req:`) fingerprint. The composed dict is the only source of truth for what the cell ran.

Canonical form (D6):

1. Fixed key order: `[cache_type_k, cache_type_v, flash_attn_type, no_extra_bufts, use_mmap, n_threads]`. Adding a knob = fingerprint-version bump.
2. Missing keys → `"-"` (e.g. iOS reports omit `no_extra_bufts`).
3. Coerce: bool → `true|false`, number → decimal, string → as-is lowercased.
4. Join: `k1=v1;k2=v2;...` in key order.
5. **Special case** (D7): `settings_overrides == {}` AND config has no `settings_axes` → literal `"app-default"`.
6. **Failure-path special case** (9c, I3.b): cell fails before `composeCellParams` runs. Use the matrix-level pre-run snapshot of `benchBase` overlaid with the cell's requested overrides (object spread, no setter replay). Run canonical-form steps 1-4 on that record and prefix the result with `req:`.

Examples:

```
overrides {}                    → "app-default"
overrides {cache_type_k:'q8_0'} → "cache_type_k=q8_0;cache_type_v=f16;flash_attn_type=off;no_extra_bufts=false;use_mmap=false;n_threads=6"
pre-compose failure              → "req:cache_type_k=q8_0;cache_type_v=f16;flash_attn_type=off;no_extra_bufts=false;use_mmap=false;n_threads=6"
```

### 4e. Setter-constraint independence (intentional)

The bench bypasses `modelStore.setX` setters entirely; `composeCellParams` does not replay their constraint logic (e.g. `setCacheTypeK` no-op when flash_attn off, `setFlashAttnType('off')` resetting cache types). The composed params reflect the operator's request verbatim — that's what hits `initLlama`. Trade-off: bench numbers stay reproducible from `bench-config.json` alone and aren't perturbed by drift in setter constraints; a sweep can therefore exercise combinations the in-app settings UI would never reach. Operators wanting app-state-realistic baselines must constrain their sweep configs by hand (e.g. pair `cache_type_k` with `flash_attn_type=on`). (D4 revised — see §8.)

### 4f. `merge-bench-reports.ts` (dedupe)

- `rowKey = ${model_id}::${quant}::${requested_backend}::${settings_fingerprint}` (4-tuple). (C)
- Mixing `version: '1.0'` and `'1.1'` reports is fatal. Upgrade legacy `1.0` reports via a one-shot migration (D8) that stamps every row with `settings_fingerprint:'app-default'`, `settings_overrides:{}`, bumps version to `1.1`. (C)
- `preferLatest`: `status:'ok'` wins; tie-break on later `timestamp`. (C)
- `reconcileBench`: settings axes are NOT a bench protocol field; mixing reports with different `settings_axes_used` is allowed (union of fingerprints = more rows). (C)
- Merger strips `log_signals.raw_matches` from output (debug-only field; baselines must not carry it).

### 4g. `benchmark-compare.ts` (regression)

- `rowKey` matches the merger (4-tuple). (C)
- Different fingerprints produce different rows; settings differences are NOT a `bench_protocol_mismatch`. (C)
- `missing_in_current` / `missing_in_baseline` extends cleanly to the 4-tuple — a baseline `app-default` row missing in a current sweep run surfaces as a real gap. (C)
- `effective_backend` mismatch flag extends to `hexagon` / `cpu+hexagon-partial`. (C)

### 4h. Hard invariants

- **I1**: Every row in a 1.1 report has non-null `settings_fingerprint` and non-null `settings_overrides` (object, possibly empty). Merger rejects rows missing either field.
- **I2**: A row with `settings_overrides == {}` AND from a config with no `settings_axes` MUST carry `settings_fingerprint == "app-default"`. No other row uses that literal.
- **I3**: The fingerprint is a pure function of an init_settings-shaped record, with two exceptions: (a) **app-default** literal (I2); (b) **`req:` prefix** for cells that fail before `composeCellParams` runs (input = pre-run snapshot + virtual override spread). Otherwise the input is the composed `cellParams` snapshot.
- **I4**: The runner does NOT read from or write to `modelStore.contextInitParams` during the matrix run. Per-cell params come from `composeCellParams`; no `modelStore.setX` setter is called.
- **I5**: `modelStore.benchmarkActive == true` for the entire span from `enterBenchmarkMode()` to `exitBenchmarkMode()`. While true, `modelStore.initContext` rejects synchronously. The matrix-level `finally` always flips it back.
- **I6**: `status:'ok'` rows always carry non-null `pp_avg` and `tg_avg`. If `ctx.bench()` resolves with a null metric, the row is forced to `status:'failed'`.
- **I7**: Requested-backend-unavailable cells write `status:'failed'` and continue; they do NOT abort the matrix.
- **I8**: Mixing reports with different `version` values is fatal in the merger.

### 4i. What each component produces

| Component | Produces | Does NOT produce |
| --- | --- | --- |
| `build-bench-config.ts` | `bench-config.json` with optional `settings_axes` | screen status, report file |
| `bench-runner.ts:buildConfig` | identical JSON shape | anything new — schema parity is mandatory |
| `runMatrix` | per-cell row (incl. fingerprint + overrides), `report.version='1.1'`; acquires/releases benchmark-mode flag | top-level `device`, `soc`, `commit`, `llama_rn_version`, `os_version` (spec fills these) |
| `composeCellParams` | the `ContextParams` dict passed to `initLlama` | snapshot, fingerprint, row |
| `merge-bench-reports.ts` | merged baseline keyed by 4-tuple; refuses mixed versions; strips `raw_matches` | regression verdict |
| `benchmark-compare.ts` | regression rows + missing-row diagnostics keyed by 4-tuple | merging |

---

## 5. Layer ownership (single-writer)

| Field | Single writer | Notes |
| --- | --- | --- |
| `modelStore.contextInitParams.*` | persistent UI setters only | The runner never reads or writes; bench compute knobs live in `benchBase` (runMatrix closure) and `cellParams` (cell closure). UI keeps ownership even while a matrix runs. |
| `modelStore.benchmarkActive` | `enterBenchmarkMode` / `exitBenchmarkMode` (only ever called from `runMatrix`) | Gates `modelStore.initContext` and downstream callers (ChatView auto-load, header loader) while the matrix runs. |
| `benchBase` (runMatrix closure) | `runMatrix` at init | Read-only after init; per-cell overrides spread into `cellParams`. |
| `cellParams` (cell closure) | `composeCellParams` | Fresh per cell; passed to `initLlama` immediately. |
| `BenchmarkRunRow.settings_fingerprint` | `runMatrix`: composed-params snapshot (success/post-compose); pre-run snapshot + virtual overrides + `req:` (pre-compose failure) | Single writer. |
| `BenchmarkRunRow.settings_overrides` | `runMatrix` (always — present even on failure) | Single writer. |
| `BenchmarkReport.version` | `runMatrix` writes `'1.1'`; merger reads and validates | Disjoint phases. |
| `BaselineReport.settings_axes_used` | `merge-bench-reports.ts` | Single writer. |

---

## 6. Canonical scenarios

**A. No settings axes.** `settings_axes` absent. Each cell emits `settings_overrides:{}`, `settings_fingerprint:'app-default'`. Merging against a legacy v1.0 baseline requires running the v1.0→v1.1 stamping migration first (D8).

**B. cache_type_k sweep on iOS, flash_attn_type=on.** Two values × two backends = four cells per (model,quant). Each cell's `init_settings` reflects the applied `cache_type_k`. All four rows coexist in the report, keyed by the 4-tuple.

**C. Hexagon on a non-Hexagon device (Klee).** `cpu` cells run normally. `hexagon` cells fail at the pre-check with `status:'failed'`, `error:'Hexagon device not available'`, `effective_backend:'unknown'`, `settings_fingerprint:'app-default'` (per I2/D7 when no axes set). Matrix completes; the per-row pass gate surfaces the failures.

**D. Hexagon on a POCO-class device (Adreno + HTP).** `getDeviceOptions()` returns `HTP*` devices. Native log capture observes `hexagon_init=true`; `deriveEffectiveBackend` returns `'hexagon'` or `'cpu+hexagon-partial'` based on the offloaded-layer count.

**E. Pre-compose failure (download timeout).** `postInitSnapshot` is null. The catch path builds the fingerprint from `preRunSnapshot ⊕ requestedOverrides` and prefixes `req:` (per 9c). `init_settings` is `{}`; `settings_overrides` carries the requested map.

---

## 7. State signals

| Signal | Set by | Read by | True when |
| --- | --- | --- | --- |
| `report.version === '1.1'` | runner | merger, compare | always for new reports |
| `row.settings_fingerprint === 'app-default'` | runner | merger, compare, operator | cell ran from a config without `settings_axes` |
| `row.settings_fingerprint.startsWith('req:')` | runner | merger, compare, operator | cell failed before `composeCellParams` ran |
| `effective_backend === 'hexagon'` | `deriveEffectiveBackend` | compare, operator | Hexagon init succeeded AND all layers offloaded |
| `effective_backend === 'cpu+hexagon-partial'` | same | same | Hexagon init succeeded AND offloaded < total |
| `modelStore.benchmarkActive` | enter/exitBenchmarkMode | initContext gate, ChatView auto-load gate | between `enterBenchmarkMode()` and `exitBenchmarkMode()` |

No long-lived state added to `modelStore` beyond the existing `benchmarkActive` flag.

---

## 8. Decisions

| # | Decision | Reasoning (short) |
| --- | --- | --- |
| D1 | Hexagon = third `requested_backend` value (not a flag on `gpu`) | Matches `getDeviceOptions()` enum; keeps row shape closed. |
| D2 | `effective_backend` gets `hexagon` + `cpu+hexagon-partial` arms | Mirror of OpenCL pair; partial-offload classification reuses the existing offload counter (init logs verified on llama.rn 0.12.0-rc.9: `ggml-hex: Hexagon backend ... allocating new registry`, `new session: HTPN`, `Hexagon Arch version vN`). |
| D3 | Hexagon detection via existing `getDeviceOptions()` | Single source of truth; no new probe. |
| D4 (revised) | Bench is **isolated** from `modelStore.contextInitParams`. `composeCellParams` is pure; setter constraints are NOT replayed. | Original D4 (call setters) was superseded once the bench-isolation redesign landed (`runMatrix` owns context lifecycle via `enterBenchmarkMode`). Bench numbers stay reproducible from `bench-config.json` alone; trade-off documented in 4e. |
| D5 | Sweep axes have a fixed order in config-build | Stable cell order across runs; reproducible diffs / crash recovery. |
| D6 | Fingerprint from the composed `cellParams` snapshot (pre-`initLlama`) | The composed dict is the only source of truth for what the cell ran — `initLlama` does not mutate it. |
| D7 | Reserved literal `"app-default"` for the no-axes case | Distinguishes "no sweep active" from "canonicalised default happened to match"; keeps the v1.0→v1.1 migration unambiguous. |
| D8 | One-shot v1.0→v1.1 migration stamps `app-default` on legacy rows | Single baseline file per device; I8 enforceable. |
| D9 | Status `<tag>` includes a short fingerprint hint | Without it, identical `(model,quant,backend)` cells with different settings look like duplicates in the WDIO poll log. |
| D10 | Hexagon gated by the same fail-fast pattern as GPU | No new code path; matches the existing gate. |
| D11 | Constraint side-effects (where they exist in app paths) are not warned at bench time | Bench bypasses setters (D4 revised), so the original D11 surprise no longer applies in the bench context. |
| D12 | Settings sweep + Hexagon bundled in one v1.0→v1.1 bump | Both changes touch row identity; splitting would force two sequential migrations of every device baseline. |
| D13 | `inter_cell_settle_ms` is a top-level config knob with a 2000ms default | Long thermal-stable sweeps want 15–30s; the bench harness wants 0 for fast tests; the prod default is the conservative middle. |
| D14 | `purgeNativeAllocator` runs between cells on Android (NDK `mallopt(M_PURGE_ALL)` via `dlsym`) | Scudo otherwise hoards freed pages across cells, OOM-killing long matrices on tight-RAM devices. iOS resolves no-op for caller parity. |

---

## 9. Edge cases

- **9a. Empty `settings_axes`** — treated as absent (D7). Producers MUST omit the key rather than emit `[]`.
- **9b. Axis with one value** (`BENCH_CACHE_TYPE_K=q8_0`) — valid. Produces one cell per (model,variant,backend) with a canonical (NOT `app-default`) fingerprint. Operator opted in.
- **9c. Cell fails before `composeCellParams` runs** (download timeout, GPU/Hexagon pre-check fails). `init_settings: {}`. The fingerprint is built from `preRunSnapshot ⊕ requestedOverrides` via the canonical form, prefixed `req:` (per I3.b, 4d.6). Operator can still bucket the failure with same-intent successes.
- **9d. Cell fails after `composeCellParams` resolves** (initLlama throws, `ctx.bench` throws, backend-mismatch). The composed-params snapshot exists; the standard (non-`req:`) fingerprint applies. `init_settings` carries the snapshot.
- **9e. Invalid sweep value in env var** — config builder rejects with non-zero exit before pushing. Screen never sees an invalid config. Defensive backstop in the runner skips the cell with `status:'failed', reason:'invalid-override-value'`.
- **9f. Two axes with conflicting constraints** (`cache_type_k=q8_0 × flash_attn_type=off`) — no constraint replay; both values land in `cellParams` verbatim (4e). Operator sees what they asked for in `settings_overrides` and what hit native in `init_settings`.
- **9g. Mixed-version baseline merge** — fatal (I8). Operator runs the v1.0→v1.1 stamping migration first.
- **9h. iOS reports lacking `no_extra_bufts`** — fingerprint uses `"-"` for missing keys; iOS and Android fingerprints don't collide. Cross-platform comparison is intentionally not supported (baselines are per-device, per-platform).

---

## 10. What this doc is NOT

- Not a list of files to edit (planner's job).
- Not a proposal to change runtime defaults — existing per-device baselines stay canonical after migration.
- Not a migration plan for the in-app `BenchmarkScreen` (consumes `BenchmarkResult` table in MMKV; separate flow).
