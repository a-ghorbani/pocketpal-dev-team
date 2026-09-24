# Benchmark Matrix

## Purpose

This doc covers the E2E-only on-device benchmark matrix: the `pocketpal://e2e/benchmark` trigger, `runMatrix`'s isolated native lifecycle, the report schema (v1.1), and the host-side config / merge / compare toolchain. The in-app `BenchmarkScreen` is a separate flow. Normal-app device selection and model loading are in `model-loading.md`.

## Code map

| Path | Role |
| --- | --- |
| `src/__automation__/screens/BenchmarkRunnerScreen.tsx` | `runMatrix`, `expandAxes`, fingerprint helpers (`FINGERPRINT_KEYS`, `canonicaliseFingerprint`, `buildSuccessFingerprint`, `buildFailureFingerprint`), report types, screen with `onRun` / autostart |
| `src/__automation__/benchParams.ts` | `DEFAULT_BENCH_BASE_PARAMS`, `buildOverridesParams`, `composeCellParams` (pure) |
| `src/__automation__/logSignals.ts` | `BENCH_LOG_RE`, `deriveLogSignals`, `deriveEffectiveBackend`, `requestSatisfiedBy` |
| `src/__automation__/benchmarkRoute.ts` | `BENCHMARK_RUNNER_URL_PREFIX`, `isBenchmarkRunnerUrl`, `parseBenchmarkAutostart` |
| `src/__automation__/deepLink.ts`, `src/hooks/useDeepLinking.ts` | the two `__E2E__`-gated delivery sites that navigate to `ROUTES.BENCHMARK_RUNNER` |
| `android/app/src/e2e/AndroidManifest.xml` | e2e-flavor bare `pocketpal://` intent-filter |
| `e2e/fixtures/benchmark-models.ts` | `getBenchmarkMatrix`: tiers, `BENCH_*` env parsing and validation, fixed axis order |
| `e2e/helpers/bench-runner.ts` | shared `buildConfig`, `pushConfig`, `deepLinkLaunch`, `pullLatestReport` |
| `e2e/scripts/build-bench-config.ts` | CLI around the shared `buildConfig` (`yarn build:bench-config` in `e2e/`) |
| `e2e/scripts/merge-bench-reports.ts` | raw reports to per-device baseline |
| `e2e/scripts/benchmark-compare.ts` | baseline vs current regression check |
| `e2e/scripts/migrate-baseline-v1-to-v1_1.ts` | one-shot v1.0 to v1.1 stamping |
| `e2e/specs/benchmark-matrix.spec.ts` | WDIO driver |
| `e2e/baselines/benchmark/*.json` | per-device baselines |

## How it works

The host builds `bench-config.json` and pushes it to the e2e app's `ExternalDirectoryPath`. It then fires `pocketpal://e2e/benchmark?autostart=1`. The screen's autostart effect calls the same `onRun` the `bench-run-button` uses. `onRun` runs `loadConfig` then `runMatrix`.

`runMatrix`:
1. Resolve `benchBase` (`DEFAULT_BENCH_BASE_PARAMS` with `n_threads` from `getRecommendedThreadCount()`) and GPU/Hexagon device names once through `getDeviceOptions()`.
2. Expand cells over model × quant × backend × `expandAxes(settings_axes)`.
3. Turn on native logging and call `modelStore.enterBenchmarkMode()`.
4. For each cell: a backend pre-check, then download if needed through `modelStore.downloadHFModel` (30-minute deadline), then `composeCellParams`, a direct `initLlama`, backend validation from native-log signals, `ctx.bench(pp, tg, pl, nr)`, and a row appended. The report file is rewritten after every cell.
5. In the per-cell `finally`: `ctx.release()`, `purgeNativeAllocator()`, then sleep `inter_cell_settle_ms`.

The matrix-level `finally` turns native logging off and calls `exitBenchmarkMode()`. The WDIO spec polls `bench-runner-screen-status` for `complete` or `error:*`, then pulls the newest `benchmark-report-*.json`.

Screen status values are `idle`, `running:<i/n:model/quant/backend[/overrides]>`, `downloading:<file>`, `cell-failed:<i/n>:<msg>`, `complete`, and `error:<msg>`. A matrix whose every cell failed still ends `complete`, so the per-row status is the pass gate.

## Contracts and invariants

- **Isolation.** The runner never reads or writes `modelStore.contextInitParams`, calls no `set*` setter, and never assigns `modelStore.context`. It does read `modelStore.models` and uses the download path. While `benchmarkActive` is true, `initContext` throws. `enterBenchmarkMode` sets the flag synchronously, then releases any context under the mutex. The matrix `finally` always clears it.
- **Per-cell params are a pure literal.** `composeCellParams` builds base ⊕ `buildOverridesParams(overrides)` ⊕ `{model, devices, n_gpu_layers}`. Setter constraints (for example, cache type vs flash attention) are not replayed, so a sweep can hit combinations Settings never would. Operators constrain configs themselves.
- **Backend slots pin both `devices` and `n_gpu_layers`.** CPU is `['CPU']` with 0; GPU and Hexagon are the discovered name with 99.
- **An unavailable backend fails, it does not fall back.** A missing GPU or Hexagon option writes a `status:'failed'` row with `error:'<GPU|Hexagon> device not available'` and `effective_backend:'unknown'`, and the matrix continues. The cell must never silently measure CPU. `initLlama` results that do not satisfy the request (`requestSatisfiedBy`: exact match or same-backend partial offload) throw `backend-mismatch` and fail the row.
- **`status:'ok'` implies non-null `pp_avg` / `tg_avg`.** A null bench metric throws and the row fails.
- **Every row carries `settings_overrides`** (possibly `{}`) **and `settings_fingerprint`.** The merger rejects v1.1 rows missing either.
- **Fingerprint canonical form.** Keys go in `FINGERPRINT_KEYS` order (`cache_type_k, cache_type_v, flash_attn_type, no_extra_bufts, use_mmap, n_threads`). A missing key becomes `-`, booleans are `true`/`false`, numbers are decimal, strings are lowercased, and pairs join as `k=v;…`. Adding a knob means a fingerprint-version bump.
- **Fingerprint source.**
  - When the config has no axes and the cell's overrides are empty, the fingerprint is the literal `app-default`, on success and failure alike. No other row uses that literal.
  - After `composeCellParams`, including a later throw, the fingerprint is canonical over the composed snapshot (`init_settings`).
  - Before compose (pre-check or download failure), it is `req:` plus canonical over `benchBase`'s knobs overlaid with the requested overrides, and `init_settings` is `{}`.
- **`init_settings` vs `effective_init_params`.** `init_settings` holds only the fingerprint knobs. `effective_init_params` is the full composed dict minus `model`, which includes devices and layers.
- **Absent, not empty.** Producers omit `settings_axes` rather than emit `[]`. The report sets `settings_axes_used` only when axes were present. `inter_cell_settle_ms` is always echoed, defaulting to 2000, and a non-finite or negative value falls back to the default.
- **One config producer.** The CLI and the spec both call `bench-runner.ts:buildConfig`. The CLI also adds a `tier` field, which the screen ignores. Env values are validated in `getBenchmarkMatrix`, and an invalid value throws before any config is written. The axis order is fixed so cell order is stable across runs.
- **Row identity is `model_id::quant::requested_backend::settings_fingerprint`** in both merge and compare. Differing fingerprints are different rows, never a protocol mismatch.
- **Merge rules.** Mixed `version` inputs are fatal (run the migration first). Differing `bench` blocks are fatal. `preferLatest` makes an `ok` row win, then the later `timestamp`. `settings_axes_used` is unioned. `log_signals` are re-derived from `raw_matches`, then `raw_matches` is emptied.
- **Compare flags.** A pp or tg regression beyond `--pct` (default 15) is flagged when either one crosses. Also flagged: an `ok` row turning into anything else, a null metric on an `ok` pair, any `effective_backend` change, and a baseline row missing from the current report. Rows only in the current report are listed as new, not failed. Exit 0 means pass, 1 means regression, and 2 means bad input or a `bench` protocol mismatch.
- **All autostart and deep-link code is `__E2E__`-gated or lives in `src/__automation__/`.** Only `App.tsx` and `useDeepLinking.ts` may import it (`.eslintrc.js` `no-restricted-imports`). CI's DCE sanity check greps the prod APK for markers such as `BENCH_RUN_MATRIX`.

## Traps and decisions

- **Autostart exists because HyperOS / MediaTek devices silently drop injected taps** (`adb input tap` and WDIO `.click()`). It is true only for `autostart=1` or `true` (case-insensitive), so `autostart=0` never starts. `parseBenchmarkAutostart` is the single parser for both delivery sites, and it fires at most once per mount (`autostartFiredRef`). The `runningRef` plus status guard in `onRun` stays authoritative.
- **Prod also registers `pocketpal://`, but only for the `hub` and `checkout` hosts.** The bare `e2e/benchmark` route resolves only in the e2e flavor, and only through `__E2E__` code.
- **`devices=['CPU']` alone does not keep layers off other registered backends.** With `n_gpu_layers > 0` and Hexagon registered, ggml offloaded to Hexagon on Snapdragon 8 Elite Gen 5, which is why the slot pins both.
- **`purgeNativeAllocator` between cells.** On Android it calls `mallopt(M_PURGE_ALL)`; on iOS it is a no-op. It runs only after a cell that created a context, because Scudo otherwise hoards freed pages and long matrices get OOM-killed on low-RAM devices. The settle also covers deferred driver teardown (OpenCL, HTP FastRPC) and thermal recovery. Raise `inter_cell_settle_ms` in the pushed config for thermally stable sweeps, with no rebuild.
- **Hexagon uses the same canonical pick as the app,** the first exact wildcard-free `HTP*` name (`model-loading.md`, Contracts and invariants). Several registered HTP sessions do not prove multi-session execution. Compare `effective_init_params` with the model/compute allocation logs.
- **`use_mmap:'smart'` as an override resolves to the platform default** (iOS `true`, Android `false`), because no file is open at compose time. `init_settings` and the fingerprint show the resolved boolean.
- **Report `platform` is hard-coded `'android'`,** and top-level `device` / `soc` / `commit` / `llama_rn_version` are filled by the merger's CLI flags, not the device. Baselines are per device and per platform, and the iOS base differs (`flash_attn_type` defaults to `auto`, not `off`), so cross-platform comparison is unsupported.
- **Re-deriving `log_signals` on merge backfills new structured fields from old reports,** but only for lines `BENCH_LOG_RE` already captured. A new signal needs a widened regex and a re-run on device.
- **The `ggml_opencl:` large-buffer anchors are prefix-agnostic,** because merge re-derives signals from old raw reports whose lines carry the pre-0.13.0-rc.5 `lm_` prefix. The legacy `lm_ggml_opencl: Initializing` and `lm_ggml_opencl: device <name>` anchors must stay prefixed: a bare `ggml_opencl: device` matches the `device FP16 support: true` line and records it as the device name.
- **A clean compare does not prove large-buffer mode.** `large_buffer_*` is not a compare flag, so read it on GPU rows: on an Adreno A7X/A8X device one of `large_buffer_enabled` / `large_buffer_unsupported` must be true, and both false means the env var never reached native. The large-buffer lines print on every OpenCL context init, inside the capture window. The Hexagon registry line fires in `getDeviceOptions()`, before the window opens, which is why `hexagon_init` is false on every baseline row.
- **The committed baselines (llama.rn 0.12.0-rc.9) predate the large-buffer env var** (#699). On a driver that lacks `cl_qcom_large_buffer`, `opencl` → `cpu+opencl-partial` is that change, not a regression: check `large_buffer_unsupported` first.
- **The v1.1 bump bundled the settings sweep and Hexagon.** Both change row identity, and one migration beat two.

## Verification

- Unit: `src/__automation__/__tests__/` (`benchmarkRoute`, `deepLink`), `src/__automation__/screens/__tests__/BenchmarkRunnerScreen.test.tsx`, `scripts/__tests__/{build-bench-config,merge-bench-reports,benchmark-compare}.test.ts`.
- Device: the dev-team `bench` skill, or run `yarn build:bench-config --push` (in `e2e/`) followed by `e2e/specs/benchmark-matrix.spec.ts`, then `merge-bench-reports.ts` and `benchmark-compare.ts` against `e2e/baselines/benchmark/<device>.json`.
- By hand: `adb shell am start -a android.intent.action.VIEW -d "pocketpal://e2e/benchmark?autostart=1"` on an e2e build with a pushed config. The status should leave `idle` within seconds.
