# Benchmark Matrix Flow

**Purpose**: cumulative architecture truth for the on-device benchmark
matrix runner — the `BenchmarkRunnerScreen` plus its CLI / spec / merge /
compare toolchain. Bootstrapped from TASK-20260505-1612 (settings-sweep +
Hexagon backend, v1.1 schema). Meant to fit in your head.

Convention used in this doc:

- **(C)** = current behaviour, documented from code
- **(D)** = decision (was an open question, now resolved)

---

## 1. Data model

### 1a. `BenchConfig` (on-device JSON, read by BenchmarkRunnerScreen)

```
BenchConfig
  models: BenchModelEntry[]
    id: string
    hfModelId: string
    quants: BenchVariant[]
      quant: string
      filename: string
      size?: number
  backends: Backend[]                          # (C) widened from 'cpu' | 'gpu'
  bench?: { pp, tg, pl, nr }                   # (C)
  settings_axes?: SettingsAxis[]               # (C) sweep dimensions
    name: SettingsKnob                         # which knob to vary
    values: SettingsValue[]                    # ordered list (>= 1)
```

```
type Backend = 'cpu' | 'gpu' | 'hexagon'       # (C) hexagon added
type SettingsKnob =                            # (C) closed enum
  | 'cache_type_k' | 'cache_type_v'
  | 'flash_attn_type'
  | 'no_extra_bufts'
  | 'use_mmap'
  | 'n_threads'
type SettingsValue = string | number | boolean # values match the knob's domain
```

Stored on disk: `bench-config.json` at the e2e flavor's
`ExternalDirectoryPath`. Computed at runtime: cell list (cartesian product
`model x quant x backend x settings_axes`) — never persisted in config.

### 1b. `BenchmarkRunRow` (per-cell row, written into the report)

```
BenchmarkRunRow
  model_id: string                             # (C)
  quant: string                                # (C)
  requested_backend: Backend                   # (C) widened to include 'hexagon'
  effective_backend: EffectiveBackend          # (C) widened (see 1c)
  pp_avg: number | null                        # (C) null on failed/skipped
  tg_avg: number | null                        # (C)
  wall_ms: number                              # (C)
  peak_memory_mb: number | null                # (C)
  log_signals: LogSignals                      # (C, extended — see 1d)
  init_settings: Record<string, unknown>       # (C) post-init snapshot of contextInitParams
  settings_overrides: Partial<SettingsKnob->Value>  # (C) what the cell asked for
  settings_fingerprint: string                 # (C) canonical hash key (see 4d)
  status: 'ok' | 'skipped' | 'failed'          # (C)
  reason?: string                              # (C)
  error?: string                               # (C)
  timestamp: string                            # (C)
```

### 1c. `EffectiveBackend` (extended)

```
type EffectiveBackend =                        # (C)
  | 'cpu'
  | 'opencl' | 'cpu+opencl-partial'
  | 'hexagon' | 'cpu+hexagon-partial'
  | 'unknown'
```

### 1d. `LogSignals` (extended)

Existing fields stay. Added:

```
LogSignals (extension)
  hexagon_init: boolean                        # (C)
  hexagon_device_name: string | null           # (C)  e.g. "HTP0" or fused list
```

### 1e. `BenchmarkReport` (file-level)

```
BenchmarkReport
  version: '1.1'                               # (C) bumped from '1.0'
  platform: 'android'                          # (C)
  timestamp: string                            # (C)
  preseeded: boolean                           # (C)
  bench: { pp, tg, pl, nr }                    # (C)
  settings_axes_used?: SettingsAxis[]          # (C) echo of config.settings_axes
  runs: BenchmarkRunRow[]                      # (C)
```

### 1f. Baseline (post-merge) — `e2e/baselines/benchmark/<device>.json`

Same shape as `BenchmarkReport`, plus the merge metadata already present
(`device`, `soc`, `commit`, `llama_rn_version`, `os_version`,
`generated_by`, `source_files`). The merger writes `version: '1.1'` and
`settings_axes_used` if any input had them.

**Glossary** (terms used elsewhere):

- **Cell** — one element of the cartesian product the runner walks: `(model, variant, backend, settings_overrides)`.
- **Settings axis** — one knob (e.g. `cache_type_k`) plus its sweep values (e.g. `['f16', 'q8_0']`).
- **Settings overrides** — the concrete `(knob -> value)` map applied to one cell. The cartesian product of all axes' values.
- **Settings fingerprint** — canonical string identifying a cell's settings configuration. Used as the fourth axis of the dedupe key.
- **App-default fingerprint** — the fingerprint emitted when `settings_axes` is empty / absent. Reserved string `"app-default"` (D7).

---

## 1b. External shape

The `bench-config.json` shape is consumed by the screen (in-process JSON
parse, C) and produced by the CLI (`build-bench-config.ts`, C) and the
spec (`bench-runner.ts:buildConfig`, C). Both producers MUST emit the
same `BenchConfig` shape — same `settings_axes` rules apply on either
side. No external API / wire format outside the device-local JSON.

---

## 2. Event flow

The runner is a synchronous-style for-loop. With sweep axes it is a
4-deep loop:

```
for model in config.models
  for variant in model.quants
    for backend in config.backends
      for overrides in expandAxes(config.settings_axes)  # (C) at least one entry
        runCell(model, variant, backend, overrides)
```

`expandAxes` returns `[{}]` (one cell, empty overrides) when
`settings_axes` is absent or empty — this is the only path that
produces the `app-default` fingerprint (D7).

---

## 3. State machine

No state-machine changes. The screen status enum (`idle | running:<tag> |
downloading:<f> | cell-failed:<n>:<msg> | complete | error:<msg>`)
stays as-is. The `<tag>` substring grows to include the fingerprint
(D9).

---

## 4. Contract

### 4a. `BenchmarkRunnerScreen.runMatrix`

1. Validates config; throws on missing file. (C)
2. Resolves `settings_axes`. If absent / empty, treats matrix as `[{}]` — one cell per (model, variant, backend), `app-default` fingerprint. (C)
3. Per cell: calls **applySettingsOverrides** (see 4c) BEFORE `setDevices` and `initContext`. This is the only place that mutates `modelStore.contextInitParams` for the bench run. (C)
4. Per cell: after `initContext` resolves, snapshots `init_settings` from `modelStore.contextInitParams` (the post-init source of truth — operator-facing values like `use_mmap='smart'` are preserved, NOT engine-resolved booleans). MUST also write: (C)
   - `settings_overrides`: the exact `(knob, value)` map applied for this cell (or `{}`).
   - `settings_fingerprint`: the canonical fingerprint (4d).
5. Per cell: in `finally`, calls **restoreSettingsSnapshot** (see 4c). Restoration runs even when the cell threw before / during init. This guarantees no pre-bench user setting leaks across cells or persists after the run. (C)
6. `releaseContext` and listener detach happen exactly once per cell that initialized. (C)
7. Hexagon backend: same fail-fast shape as the `gpu`-not-available path. When `backend === 'hexagon'` and Hexagon is unavailable, write `status: 'failed'`, `error: 'Hexagon device not available'`, `effective_backend: 'unknown'`, then continue to next cell. (C)

### 4b. `build-bench-config.ts` (CLI) and `bench-runner.ts:buildConfig` (spec helper)

Both producers MUST:

1. Continue to honour `BENCH_TIER`, `BENCH_MODELS`, `BENCH_QUANTS`, `BENCH_BACKENDS`. Existing behaviour with no settings env-vars MUST emit a config without `settings_axes` (the absence-means-app-default semantic, D7). (C)
2. Honour the settings env vars — comma-separated value lists, lowercase, trimmed: (C)
   - `BENCH_CACHE_TYPE_K`, `BENCH_CACHE_TYPE_V` (e.g. `f16,q8_0`)
   - `BENCH_FLASH_ATTN_TYPE` (e.g. `auto,off`)
   - `BENCH_NO_EXTRA_BUFTS` (e.g. `true,false`)
   - `BENCH_USE_MMAP` (e.g. `true,false,smart`)
   - `BENCH_N_THREADS` (e.g. `4,6,8`)
   - `BENCH_BACKENDS` accepts `hexagon` as a third value.
3. For each env var present and non-empty, append a `SettingsAxis` to `config.settings_axes`. Axes are emitted in a **stable, deterministic order** (D5): `cache_type_k, cache_type_v, flash_attn_type, no_extra_bufts, use_mmap, n_threads`. Within an axis, values are emitted in env-var order. (C)
4. Validate value domains at config-build time (cache types subset of `CacheType` enum, flash_attn_type subset of `auto|on|off`, booleans, etc.). Invalid value -> error exit, no config written. The CLI must not push a bench-config that the screen cannot apply. (C)

### 4c. `applySettingsOverrides` / `restoreSettingsSnapshot`

These are the **runner-internal** helpers (no new public surface on
`modelStore`). They MUST:

1. Snapshot the current values of all sweep-eligible knobs from `modelStore.contextInitParams` ONCE at run start (before the first cell). The snapshot is the matrix-level fixed point for restoration. (C)
2. Per cell, apply overrides by calling the EXISTING setters: `setCacheTypeK`, `setCacheTypeV`, `setFlashAttnType`, `setNoExtraBufts`, `setUseMmap`, `setNThreads`. No direct mutation of `contextInitParams`. Reasoning: those setters carry constraints (e.g. `setCacheTypeK` is a no-op when flash_attn is off — see 4e for why this matters). (C)
3. On run end (success or fatal throw of the loop body), restore by calling the same setters with the snapshot's values. Restoration is best-effort (per-setter try/catch); a restore failure does not re-fail the matrix. (C)

### 4d. Settings fingerprint contract

The fingerprint MUST be derived from the post-init `init_settings`
snapshot, NOT from the requested `settings_overrides`. The post-init
snapshot is the source of truth because the **setters** (`setCacheTypeK/V`,
`setFlashAttnType`) carry constraint logic — `setCacheTypeK` is a no-op
when flash_attn is off (ModelStore.ts:300-316), and `setFlashAttnType('off')`
resets cache types to F16 (ModelStore.ts:2317-2331). `initContext` itself
does NOT mutate the params; it only reads them via
`getEffectiveContextInitParams` (ModelStore.ts:1559-1560). The mutations
land at apply time, before `initContext` runs. Using the post-init values
means two requested-different-but-effectively-same configurations dedupe
correctly.

The fingerprint snapshots from `modelStore.contextInitParams` directly,
NOT from `getEffectiveContextInitParams(filePath)`. This means
`use_mmap='smart'` is preserved as the operator-facing string `'smart'` in
the fingerprint, even though it resolves to a concrete boolean at
native-call time (ModelStore.ts:430-434). Trade-off (D6, expanded): the
fingerprint preserves operator INTENT over engine-effective behaviour. Two
cells where one was set to `use_mmap='smart'` and the other to
`use_mmap='true'` produce different fingerprints even when
`resolveUseMmap('smart', filePath)` returns `true`. Reasoning: (a)
`init_settings` already captures `contextInitParams` directly
(BenchmarkRunnerScreen.tsx:329-330), so the fingerprint should match what
the operator can read in the report; (b) `'smart'` resolution depends on
filePath state and could flip between runs on the same model — burning
that into a fingerprint would make baselines fragile.

Fingerprint canonical form (D6):

1. Pick a **fixed, ordered key list**: `['cache_type_k', 'cache_type_v', 'flash_attn_type', 'no_extra_bufts', 'use_mmap', 'n_threads']`. This is the closed contract — adding a knob is a fingerprint-version bump.
2. For each key, take the value from the post-init `init_settings` snapshot (i.e. `modelStore.contextInitParams` AFTER setters but BEFORE engine-side resolution). Missing keys -> literal string `"-"` (e.g. iOS reports omit `no_extra_bufts`).
3. Coerce: booleans -> `true|false`, numbers -> decimal string, strings -> as-is, lowercased.
4. Join: `key1=val1;key2=val2;...` in the fixed key order.
5. Special case (D7): if `settings_overrides` is empty AND no `settings_axes` was passed in config, the fingerprint is the literal string `app-default` regardless of canonicalised content.
6. Failure-path special case (9c construction): when no post-init snapshot exists, the fingerprint is built from a synthesised init_settings-shaped record — the matrix-level pre-run snapshot from 4c.1 with the cell's requested overrides applied virtually (object spread, no constraint replay). The same canonical-form rules (steps 1-4) apply. The result is then prefixed with `req:` to mark "derived from intent, not from applied state" (per I3 exception 2). See 9c for full construction.

Examples:

```
overrides {} (no axes in config)             -> "app-default"
overrides {cache_type_k: 'q8_0'}             -> "cache_type_k=q8_0;cache_type_v=f16;flash_attn_type=off;no_extra_bufts=false;use_mmap=false;n_threads=6"
overrides {use_mmap: 'true'} on iOS          -> "cache_type_k=f16;cache_type_v=f16;flash_attn_type=auto;no_extra_bufts=-;use_mmap=true;n_threads=4"
failure path, pre-init snapshot {cache_type_k:'f16', cache_type_v:'f16', flash_attn_type:'off', no_extra_bufts:false, use_mmap:'smart', n_threads:6}, requested {cache_type_k:'q8_0'}
                                             -> "req:cache_type_k=q8_0;cache_type_v=f16;flash_attn_type=off;no_extra_bufts=false;use_mmap=smart;n_threads=6"
```

### 4e. Constraint-aware override behaviour (informational, ties to 4c)

`setCacheTypeK` / `setCacheTypeV` are **no-ops** when flash_attn is `off`
(ModelStore.ts:300-334). `setFlashAttnType('off')` resets cache types to
`F16` (ModelStore.ts:2317-2331). Implications:

- (D11) When sweeping cache_type_k with flash_attn_type still `off`, the post-init snapshot will show `cache_type_k=f16` regardless of requested override. The fingerprint reflects this — multiple requested cache types collapse to one fingerprint. This is **correct**: the fingerprint describes what was actually applied. But it means the report-writing path MUST also surface `settings_overrides` (the requested map) so an operator inspecting a baseline can see "I asked for q8_0; the engine ignored it because flash_attn was off."
- The CLI / spec config builder MAY emit a `flash_attn_type` axis alongside a `cache_type_k` axis to make the cache-type sweep meaningful; this is an authoring concern, not a contract concern.

### 4f. `merge-bench-reports.ts` (dedupe contract)

1. `rowKey` is `${model_id}::${quant}::${requested_backend}::${settings_fingerprint}` (4-tuple). (C)
2. Merger reads `version` from each input report. Mixing `1.0` and `1.1` reports is an **error** (refuse to merge silently). To upgrade legacy `1.0` reports, run a one-shot migration (D8) that stamps every row with `settings_fingerprint: 'app-default'` and `settings_overrides: {}` and bumps the file's `version` to `1.1`. This is the only path that legitimately mints `app-default` fingerprints retroactively. (C)
3. `preferLatest` semantics unchanged (status:'ok' wins, then later timestamp). (C)
4. `compareRuns` ordering: tie-break extends to fingerprint after backend so baseline diffs stay stable. (C)
5. `reconcileBench` stays unchanged. Settings axes are NOT a `bench` protocol field; mixing reports with different `settings_axes_used` is allowed (the union of fingerprints is just more rows). (C)

### 4g. `benchmark-compare.ts` (regression contract)

1. `rowKey` matches merger (4-tuple including fingerprint). (C)
2. `bench_protocol_mismatch` check unchanged. Settings differences are NOT a protocol mismatch — different fingerprints just produce different rows (compare them or don't). (C)
3. `missing_in_current` / `missing_in_baseline` semantics extend cleanly to the 4-tuple. A baseline `app-default` row missing in a current report that swept `cache_type_k` will appear as missing — this is a real signal to the operator that the current run did not include the app-default cell. (C)
4. `effective_backend` mismatch flag extends to the new `hexagon` / `cpu+hexagon-partial` values without other changes. (C)

### 4h. Hard invariants

- **I1**: Every row in a `1.1` report carries non-null `settings_fingerprint` and non-null `settings_overrides` (object, possibly empty). Rows missing either field MUST be rejected by the merger.
- **I2**: A row with `settings_overrides == {}` AND emitted from a config with no `settings_axes` MUST carry `settings_fingerprint == "app-default"`. No other row may carry that literal.
- **I3**: The fingerprint is a pure function of an init_settings-shaped record, with two enumerated exceptions. (a) **app-default literal** (I2): an empty-overrides cell from a no-axes config emits `"app-default"`. (b) **`req:` prefix** (9c): a cell that fails before `initContext` resolves has no post-init snapshot, so the canonical-form input is built from the matrix-level pre-run snapshot (4c.1) overlaid with the requested overrides; the result is prefixed `req:` to mark its provenance. In all other cases (success path AND post-init failure path 9d), the input is the post-init `modelStore.contextInitParams` snapshot. Two cells with byte-identical inputs and the same provenance MUST produce the same fingerprint.
- **I4**: `applySettingsOverrides` only ever calls existing `modelStore.setX` setters. No code path in the runner mutates `contextInitParams` directly.
- **I5**: On matrix end (any path), `restoreSettingsSnapshot` runs. The persisted user settings observable AFTER the run equals the snapshot taken BEFORE the run (modulo setter constraint side-effects, which are deterministic).
- **I6**: `status:'ok'` rows always carry non-null `pp_avg` and `tg_avg` (BenchmarkRunnerScreen.tsx:371-375).
- **I7**: A cell whose requested backend is unavailable on the device (no GPU, no Hexagon) writes `status:'failed'` and continues; it does NOT abort the matrix.
- **I8**: Mixing reports with different `version` fields is fatal (4f.2). The merger refuses and exits non-zero.

### 4i. What each component renders / produces

| Component | Produces | Does NOT produce |
| --- | --- | --- |
| `build-bench-config.ts` | `bench-config.json` with optional `settings_axes` | the in-app screen status; the report file |
| `bench-runner.ts:buildConfig` | identical JSON shape via spec invocation | anything new — schema parity is mandatory |
| `BenchmarkRunnerScreen.runMatrix` | per-cell row (incl. `settings_fingerprint`, `settings_overrides`); writes `report.version='1.1'` | top-level `device`, `soc`, `commit`, `llama_rn_version`, `os_version` (the spec fills these) |
| `applySettingsOverrides` | mutations on `modelStore.contextInitParams` via existing setters | the snapshot, the fingerprint, the row |
| `merge-bench-reports.ts` | merged baseline keyed by 4-tuple; refuses mixed versions | regression verdict |
| `benchmark-compare.ts` | regression rows + missing-row diagnostics keyed by 4-tuple | merging |

---

## 5. Layer ownership (single-writer rule)

| Field | Single writer | Rationale |
| --- | --- | --- |
| `modelStore.contextInitParams.cache_type_k/v` | per-cell `applySettingsOverrides` (during run) + persistent UI setters (between runs) | The runner is the only writer DURING a matrix run. After the run, restoration hands ownership back to the UI. There is no concurrent overlap because the runner serialises cells. |
| `modelStore.contextInitParams.flash_attn_type` | same | Same as above. |
| `modelStore.contextInitParams.no_extra_bufts` | same | Same. |
| `modelStore.contextInitParams.use_mmap` | same | Same. |
| `modelStore.contextInitParams.n_threads` | same | Same. |
| `BenchmarkRunRow.settings_fingerprint` | `BenchmarkRunnerScreen.runMatrix`: success path uses post-init snapshot; pre-init failure path uses pre-run snapshot + virtual override apply, prefixed `req:` (per 9c, I3) | Single writer. |
| `BenchmarkRunRow.settings_overrides` | `BenchmarkRunnerScreen.runMatrix` (always — present even on failure) | Single writer. |
| `BenchmarkReport.version` | `BenchmarkRunnerScreen.runMatrix` (writer of the in-flight report); merger preserves and validates | Two writers but disjoint phases — the screen sets `'1.1'` once, the merger only reads. |
| `BaselineReport.settings_axes_used` | `merge-bench-reports.ts` (computed from inputs) | Single writer. |

Past pain: the screen used to set device tier via `modelStore.setDevices`
before the GPU pre-check ran (PR #702 fix). The same shape is used here —
fail-fast pre-check BEFORE any setter, so a failed cell does not leave
stale state.

**Deferred cleanups**: 1) `setCacheTypeK/V` no-op behaviour when
flash_attn is off is surprising in the bench context; consider an
explicit warning log when an override is silently swallowed. Out of
scope here; tracked as documentation only (D11).

---

## 6. Canonical scenarios

### A. Backwards compatibility — no settings axes

```
config.settings_axes = absent
config.backends = ['cpu', 'gpu']
config.models = [{ id: 'qwen3-1.7b', quants: [{quant:'q4_0',...}] }]
-----------------------------------------
report.version = '1.1'
report.settings_axes_used = absent
report.runs[0] = { model_id:'qwen3-1.7b', quant:'q4_0', requested_backend:'cpu',
                   settings_overrides: {}, settings_fingerprint: 'app-default', ... }
report.runs[1] = { ..., requested_backend:'gpu',
                   settings_overrides: {}, settings_fingerprint: 'app-default', ... }

Merger consuming this against the existing v1.0 POCO baseline -> fatal error (mixed versions).
After running the v1.0->v1.1 stamping migration on the legacy baseline, merge succeeds; existing
rows now carry settings_fingerprint:'app-default' and dedupe cleanly with the new run.
```

### B. cache_type_k sweep on iOS, flash_attn_type=on already set

```
BENCH_CACHE_TYPE_K=f16,q8_0
config.backends = ['cpu', 'gpu']    # iOS: cpu + Metal-via-gpu
config.settings_axes = [{name:'cache_type_k', values:['f16','q8_0']}]
-----------------------------------------
4 cells (1 model x 1 quant x 2 backends x 2 cache values).
Each cell's post-init snapshot reflects the applied cache_type_k.
Fingerprint examples:
  cell #1 (cpu, f16): "cache_type_k=f16;cache_type_v=f16;flash_attn_type=auto;no_extra_bufts=-;use_mmap=true;n_threads=4"
  cell #2 (cpu, q8_0): "cache_type_k=q8_0;cache_type_v=f16;flash_attn_type=auto;no_extra_bufts=-;use_mmap=true;n_threads=4"
All four rows coexist in the report; merger keeps them keyed by 4-tuple.
```

### C. Hexagon on a non-Hexagon device (klee = MediaTek)

```
config.backends = ['cpu', 'hexagon']
-----------------------------------------
- 'cpu' cells run normally (matches today's GPU-not-available pattern).
- 'hexagon' cells, on first dispatch, getDeviceOptions() returns no 'hexagon' option.
  Each hexagon cell emits status:'failed', error:'Hexagon device not available',
  effective_backend:'unknown', settings_fingerprint:'app-default' (no axes in config, per I2/D7).
- Matrix completes; spec's per-row pass gate fails the test, surfacing the failed
  cells. This is the correct shape — klee should never silently produce empty rows.
```

### D. Hexagon on a POCO-class Adreno+HTP device

```
config.backends = ['hexagon']
config.settings_axes = absent
-----------------------------------------
Cell selects devices = ['HTP*'] via getDeviceOptions().
Native log capture observes hexagon_init=true; layer-offload count derives partial vs full
the same way OpenCL does (deriveEffectiveBackend extended with hexagon arms).
Row: requested_backend:'hexagon', effective_backend:'hexagon' or 'cpu+hexagon-partial',
settings_fingerprint:'app-default'.
```

### E. Settings restoration after the run

```
Before run:  modelStore.contextInitParams = { ..., cache_type_k:'f16', use_mmap:'smart', n_threads:8 }
During run:  cells set cache_type_k to 'q8_0', use_mmap to 'false', n_threads to 4.
On 'complete': restoreSettingsSnapshot calls setCacheTypeK('f16'), setUseMmap('smart'), setNThreads(8).
Post-run:    modelStore.contextInitParams = { ..., cache_type_k:'f16', use_mmap:'smart', n_threads:8 }.
```

---

## 7. State signals

| Signal | Set by | Read by | True when |
| --- | --- | --- | --- |
| `report.version === '1.1'` | runner (write) | merger (validate), compare (read) | always for new reports |
| `row.settings_fingerprint === 'app-default'` | runner | merger, compare, operator | the cell ran from a config without `settings_axes` |
| `effective_backend === 'hexagon'` | `deriveEffectiveBackend` | compare, operator | Hexagon init succeeded AND all layers offloaded |
| `effective_backend === 'cpu+hexagon-partial'` | same | same | Hexagon init succeeded AND offloaded < total |

No long-lived state added to `modelStore`. The matrix-level pre-run
snapshot is local to `runMatrix` (closure variable).

---

## 8. Decisions

- **D1**: **Hexagon as a third `requested_backend` value, not a flag on existing values.** Reasoning: matches `getDeviceOptions()`'s existing closed enum (`'auto' | 'gpu' | 'hexagon' | 'cpu'`), keeps the report shape closed, lets the dedupe key stay flat. Alternative (`backend:'gpu'` + `accelerator:'hexagon'`) would force a row-shape migration twice and pollutes the OpenCL path's invariants.
- **D2**: **Effective backend gets `hexagon` and `cpu+hexagon-partial` arms** (mirror of the OpenCL pair). Reasoning: same partial-offload shape applies; symmetrical naming makes the compare script's flag string readable. **Log-signal verification** (llama.rn 0.12.0-rc.9 at HEAD; lines drift across rc bumps, strings are stable): hexagon emits parseable init lines — `ggml-hex: Hexagon backend (experimental) : allocating new registry : ndev N` (cpp/ggml-hexagon/ggml-hexagon.cpp:3226), `ggml-hex: new session: HTPN : ...` (cpp/ggml-hexagon/ggml-hexagon.cpp:1978), `ggml-hex: Hexagon Arch version vN` (cpp/ggml-hexagon/ggml-hexagon.cpp:3243). The generic `offloaded N/M layers to GPU` line (cpp/llama-model.cpp:8010) is backend-agnostic — it prints for any non-CPU backend that received layers, including Hexagon — so partial-vs-full classification reuses the existing offload counter without a Hexagon-specific log shape. **Accepted limitation**: if Hexagon init aborts before the registry-allocation line prints, no parseable signal exists and the cell falls back to `effective_backend: 'unknown'`. This is symmetrical with the OpenCL path's `unknown` fallback (logSignals.ts:154-158) and is the documented behaviour for I7 failure cells.
- **D3**: **Hexagon detection via the existing `getDeviceOptions()` helper.** Reasoning: single source of truth in `src/utils/deviceSelection.ts`. The runner already uses this helper for GPU resolution; no new probe needed.
- **D4**: **Apply overrides via existing setters, not direct mutation.** Reasoning: the setters carry constraint logic (`setCacheTypeK` no-op when flash_attn off, `setFlashAttnType('off')` resets cache types). Bypassing them would diverge bench behaviour from app behaviour and silently invalidate sweeps. Trade-off: some sweeps can become silent no-ops (covered by D11 + report's `settings_overrides` field).
- **D5**: **Sweep axes have a fixed ordering at config-build time** (`cache_type_k, cache_type_v, flash_attn_type, no_extra_bufts, use_mmap, n_threads`). Reasoning: stable cell order across runs makes diffs and crash-recovery (cells N..end after a process kill) reproducible.
- **D6**: **Fingerprint derived from the post-init `init_settings` snapshot, not from requested overrides.** Reasoning: `init_settings` is already the source of truth. Using it means two cells that requested differently but ended up identical (because of a constraint) dedupe correctly — which is what the operator wants.
- **D7**: **Reserved literal `"app-default"` for the no-axes case.** Reasoning: distinguishes "no settings sweep was active" from "the canonicalised default fingerprint happens to match." Without this literal, the migration story (D8) would be ambiguous: a v1.0 row stamped with the canonical defaults could not be told apart from a v1.1 cell that explicitly swept and landed on defaults.
- **D8**: **One-shot v1.0->v1.1 migration script that stamps `app-default` on every legacy row.** Reasoning: keeps a single baseline file per device, preserves the existing comparison surface, and makes the version invariant (I8) enforceable cleanly. Alternatives — separate baseline files per fingerprint (excessive churn for the common case where 99% of cells are app-default) and "missing fingerprint = app-default" magic (a silent semantic, fails I8) — both strictly worse.
- **D9**: **Status `<tag>` includes a short fingerprint identifier** (e.g. `running:5/24:qwen3-1.7b/q4_0/cpu/cache_type_k=q8_0`). Reasoning: the WDIO spec polls status; without a fingerprint hint, identical (model,quant,backend) cells with different settings look like duplicates in the log.
- **D10**: **`hexagon` is gated by the same fail-fast pattern as `gpu`** (no probe, no scan beyond the existing helper). Reasoning: matches the existing gate; no new code path for "is the NPU usable for this quant," which is a llama.rn concern, not a runner concern.
- **D11**: **Constraint side-effects are documented, not warned.** Reasoning: silent collapse of e.g. `cache_type_k=q8_0` to `f16` because flash_attn was off is surprising but visible in the report (`settings_overrides` differs from `init_settings`). Adding a runtime warning is out of scope here; the report shape is the ground truth and an inspecting operator can spot it. Tracked as a deferred cleanup.
- **D12**: **Settings sweep + Hexagon are bundled in one schema bump, sharing the v1.0->v1.1 transition.** Reasoning: both changes touch the same row identity (`requested_backend` widens; `settings_fingerprint` is added) and both force the same merger / compare update. Splitting would require either (a) two sequential v1.0->v1.1->v1.2 migrations of every device baseline (POCO Myron, klee, Samsung S23) and two merger version-mismatch refuse cycles, or (b) shipping Hexagon under v1.0 with an Adreno-specific row-shape exception — which violates the closed `EffectiveBackend` enum (D2). One bump is cheaper and keeps the dedupe key contract evolving in one place. Trade-off: a Hexagon-specific bug delays the settings-sweep landing too; mitigated because Hexagon is gated by `getDeviceOptions()` (D3, D10) — devices without Hexagon never exercise the new code path.

---

## 9. Edge cases

### 9a. Empty `settings_axes` in the config

Treated as absent (D7 path). Single-cell behaviour, `app-default`
fingerprint, `report.settings_axes_used` omitted. Producers (CLI / spec
helper) MUST omit the key entirely rather than emit `[]`, so the wire
format has one canonical shape per case.

### 9b. Axis with one value (`BENCH_CACHE_TYPE_K=q8_0` only)

Valid. Produces a single cell per (model, variant, backend), but the
fingerprint is canonical (NOT `app-default`) because `settings_axes` was
non-empty. This is intentional — the operator opted in to settings-aware
reporting, so the legacy row dedupe is OFF.

### 9c. Cell throws before initContext (download timeout, GPU/Hexagon unavailable)

Catch path writes the failure row with `init_settings: {}`. For
sweep-aware reports, also write `settings_overrides: <requested>` and a
fingerprint constructed as follows (per I3 exception (b) and 4d.6):

1. Start with the **matrix-level pre-run snapshot** taken in 4c.1 — that is, the values of all six fingerprint keys (`cache_type_k`, `cache_type_v`, `flash_attn_type`, `no_extra_bufts`, `use_mmap`, `n_threads`) read from `modelStore.contextInitParams` once before the first cell runs. Keys missing on the platform stay missing (e.g. iOS `no_extra_bufts`).
2. Apply the cell's `settings_overrides` virtually via object spread: `{...preRunSnapshot, ...requestedOverrides}`. No constraint replay (no setter calls); the spread is mechanical so the result is reproducible without re-running setter logic.
3. Canonicalise the merged record using the same rules as the success path (4d steps 1-4): fixed key order, missing keys -> `"-"`, type coercion, semicolon-joined.
4. Prefix the result with `req:` to mark "derived from intent + pre-run snapshot, not from applied state."

The fingerprint is reproducible from the report alone (the pre-run
snapshot is recoverable as `runs[0].init_settings` for the matrix's first
successful cell, or absent that, can be reconstructed from any v1.1 row's
`init_settings` for unset axes). Reasoning: the operator still needs to
bucket the failure with other cells of the same intended config; using
the pre-run snapshot for un-overridden keys (rather than `"-"`
everywhere) makes failure-row fingerprints comparable to success-row
fingerprints from the same matrix run.

### 9d. Cell throws after initContext

Snapshot is available; post-init fingerprint is derivable. Write the
standard fingerprint (no `req:` prefix). The catch path's
`init_settings: {}` becomes a snapshot of the captured params: the
runner MUST hoist the post-init snapshot capture into a local variable
BEFORE the bench step, so post-init throws can produce a non-`req:`
fingerprint.

### 9e. Invalid sweep value in env var (e.g. `BENCH_CACHE_TYPE_K=bogus`)

Config builder validates and exits non-zero before pushing. The screen
never sees an invalid config. (Defensive: if the screen DOES see an
unknown value, it skips the cell with `status:'failed',
reason:'invalid-override-value'` — but this is a redundancy, not the
primary line of defence.)

### 9f. Race: two settings axes whose constraints collide (`cache_type_k=q8_0 x flash_attn_type=off`)

No race — cells are serial. The constraint applies deterministically
inside `setCacheTypeK`. The fingerprint reflects the post-init reality
(D6); the requested overrides reflect the intent. Operator can read both.

### 9g. Mixed-version baseline merge

Fatal (I8). The merger refuses; the operator runs the v1.0->v1.1 stamping
migration first, then re-runs merge. This is the only acceptable upgrade
path because silent stamping during merge would erase the `app-default`
reservation (D7).

### 9h. iOS reports lacking `no_extra_bufts`

iOS path doesn't populate `no_extra_bufts` (an Android-specific
repacking knob). Fingerprint canonicalisation uses `"-"` as the marker
(4d.2), so iOS and Android fingerprints are not confused. Cross-platform
comparison is intentionally not supported by this contract — baselines
are per-device, per-platform.

---

## 10. What this doc is NOT

- Not a list of files to edit (planner's job).
- Not a proposal to change runtime defaults — the existing POCO Myron, klee, Samsung S23 baselines stay canonical for the `app-default` fingerprint after the v1.0->v1.1 migration. New sweep configurations produce ADDITIONAL rows in those same baseline files, never replacements.
- Not a migration plan for the in-app benchmark UI (`src/screens/BenchmarkScreen`). That screen consumes a different data shape (`BenchmarkResult` table in MMKV) and is not part of this flow.
