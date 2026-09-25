# Benchmark Matrix

## Purpose

This doc covers the E2E-only on-device benchmark matrix on Android and iOS: the `pocketpal://e2e/benchmark` trigger, `runMatrix`'s isolated native lifecycle, the report schema (v1.1), and the host-side config / merge / compare toolchain. The in-app `BenchmarkScreen` is a separate flow. Normal-app device selection and model loading are in `model-loading.md`.

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
| `e2e/helpers/bench-runner.ts` | shared `buildConfig`, `expectedCellCount`, `stampReportMetadata`, `assertRowsPass`; Android `pushConfig`, `deepLinkLaunch`, `pullLatestReport` |
| `e2e/scripts/build-bench-config.ts` | CLI around the shared `buildConfig` (`yarn build:bench-config` in `e2e/`) |
| `e2e/scripts/merge-bench-reports.ts` | raw reports to per-device baseline |
| `e2e/scripts/benchmark-compare.ts` | baseline vs current regression check |
| `e2e/scripts/migrate-baseline-v1-to-v1_1.ts` | one-shot v1.0 to v1.1 stamping |
| `e2e/specs/benchmark-matrix.spec.ts` | WDIO driver, Android only |
| `e2e/scripts/run-bench-ios.ts` | iOS driver over `xcrun devicectl` (`yarn bench:ios` in `e2e/`): `buildPlan`, `evaluatePoll`, `run` |
| `e2e/baselines/benchmark/*.json` | per-device baselines |

## How it works

The host builds `bench-config.json` and puts it in the bench dir: Android's `ExternalDirectoryPath` via adb, or the iOS app's `Documents` via `devicectl device copy to --domain-type appDataContainer`. It then fires `pocketpal://e2e/benchmark?autostart=1` (on iOS, `devicectl device process launch --payload-url` to the running app). The screen's autostart effect calls the same `onRun` the `bench-run-button` uses. `onRun` runs `loadConfig` then `runMatrix`.

`runMatrix`:
1. Resolve `benchBase` (`DEFAULT_BENCH_BASE_PARAMS` with `n_threads` from `getRecommendedThreadCount()`) and GPU/Hexagon device names once through `getDeviceOptions()`.
2. Expand cells over model × quant × backend × `expandAxes(settings_axes)`.
3. Turn on native logging, call `modelStore.enterBenchmarkMode()`, claim keep-awake, and write the report shell.
4. For each cell: a backend pre-check, then download if needed through `modelStore.downloadHFModel` (30-minute deadline), then `composeCellParams`, a direct `initLlama`, backend validation from native-log signals, `ctx.bench(pp, tg, pl, nr)`, and a row appended. The report file is rewritten after every cell.
5. In the per-cell `finally`: `ctx.release()`, `purgeNativeAllocator()`, then sleep `inter_cell_settle_ms`.

After the loop the runner writes `outcome: 'complete'`; a matrix-level throw after the shell writes `outcome: 'error:<msg>'` and rethrows. The matrix-level `finally` releases keep-awake if claimed, turns native logging off, and calls `exitBenchmarkMode()`. The WDIO spec polls `bench-runner-screen-status` for `complete` or `error:*`, then pulls the newest `benchmark-report-*.json`. The iOS driver instead polls `Documents` for a report absent from its pre-launch snapshot, pulls it, and lets `evaluatePoll` decide the state.

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
- **One config producer, count, stamper and gate.** The CLI, the spec and the iOS driver share `bench-runner.ts` `buildConfig`, `expectedCellCount` (the `runMatrix` loop: Σ quants × backends × axis value counts), `stampReportMetadata` and `assertRowsPass`. The CLI also adds a `tier` field, which the screen ignores. Env values are validated in `getBenchmarkMatrix`, and an invalid value throws before any config is written. The axis order is fixed so cell order is stable across runs.
- **Row identity is `model_id::quant::requested_backend::settings_fingerprint`** in both merge and compare. Differing fingerprints are different rows, never a protocol mismatch.
- **Merge rules.** Mixed `version` inputs are fatal (run the migration first), and so are mixed `platform` inputs (absent reads as `android`). Differing `bench` blocks are fatal. `preferLatest` makes an `ok` row win, then the later `timestamp`. `settings_axes_used` is unioned. `log_signals` are re-derived from `raw_matches`, then `raw_matches` is emptied.
- **Compare flags.** A pp or tg regression beyond `--pct` (default 15) is flagged when either one crosses. Also flagged: an `ok` row turning into anything else, a null metric on an `ok` pair, any `effective_backend` change, and a baseline row missing from the current report. Rows only in the current report are listed as new, not failed. Exit 0 means pass, 1 means regression, and 2 means bad input, a `bench` protocol mismatch, or a cross-platform pair (`checkPlatforms`; absent reads as `android`).
- **Bench dir and `report.platform` come from `Platform.OS`,** never `ExternalDirectoryPath || DocumentDirectoryPath`: Android must not fall back to a directory adb cannot reach.
- **Metal classification** (`deriveEffectiveBackend`): after HTP and OpenCL, any `MTL*` weight key gives `metal`, or `cpu+metal-partial` when offloaded < total; without one a row is never Metal. `requestSatisfiedBy('gpu')` accepts both OpenCL and Metal pairs. `EffectiveBackend` is declared only in `logSignals.ts`.
- **`init_ms`** is the wall time of the `initLlama` await alone. Every `ok` row has it; a failed row has it only when `initLlama` resolved.
- **Terminal `outcome`** (raw reports only; the merger drops it) is written at most once: `complete` after the loop, or `error:<msg>` from the matrix-level catch only when the shell exists and no outcome is set. Both writes are best-effort; the driver's row-count cross-check covers a lost one.
- **Keep-awake is runner-owned for the matrix:** claimed only after `enterBenchmarkMode` resolves (a local chat's release has run by then), released in the outer `finally` only when claimed, and never fatal. The native flag is global and not ref-counted; a remote-model chat (not gated by `benchmarkActive`) could clear it, accepted because automated runs generate no chat.
- **iOS driver poll order:** outcome (`complete` needs rows == `expectedCellCount`), then process gone (`app-exited` even with every row), then the count fallback (two more stable polls), then time limits. Exits after `starting` stamp the report; `done` runs `assertRowsPass`.
- **iOS driver mutations:** install only with `--app`; on the device it writes only `Documents/bench-config.json` and deletes nothing (stale reports are skipped by name snapshot); `--dry-run` runs no `devicectl` or `unzip`. Calls are argv-style `execFileSync`.
- **All autostart and deep-link code is `__E2E__`-gated or lives in `src/__automation__/`.** Only `App.tsx` and `useDeepLinking.ts` may import it (`.eslintrc.js` `no-restricted-imports`). CI's DCE sanity check greps the prod APK for markers such as `BENCH_RUN_MATRIX`.

## Traps and decisions

- **Autostart exists because HyperOS / MediaTek devices silently drop injected taps** (`adb input tap` and WDIO `.click()`). It is true only for `autostart=1` or `true` (case-insensitive), so `autostart=0` never starts. `parseBenchmarkAutostart` is the single parser for both delivery sites, and it fires at most once per mount (`autostartFiredRef`). The `runningRef` plus status guard in `onRun` stays authoritative.
- **Prod also registers `pocketpal://`, but only for the `hub` and `checkout` hosts.** The bare `e2e/benchmark` route resolves only in the e2e flavor, and only through `__E2E__` code.
- **`devices=['CPU']` alone does not keep layers off other registered backends.** With `n_gpu_layers > 0` and Hexagon registered, ggml offloaded to Hexagon on Snapdragon 8 Elite Gen 5, which is why the slot pins both.
- **`purgeNativeAllocator` between cells.** On Android it calls `mallopt(M_PURGE_ALL)`; on iOS it is a no-op. It runs only after a cell that created a context, because Scudo otherwise hoards freed pages and long matrices get OOM-killed on low-RAM devices. The settle also covers deferred driver teardown (OpenCL, HTP FastRPC) and thermal recovery. Raise `inter_cell_settle_ms` in the pushed config for thermally stable sweeps, with no rebuild.
- **Hexagon uses the same canonical pick as the app,** the first exact wildcard-free `HTP*` name (`model-loading.md`, Contracts and invariants). Several registered HTP sessions do not prove multi-session execution. Compare `effective_init_params` with the model/compute allocation logs.
- **`use_mmap:'smart'` as an override resolves to the platform default** (iOS `true`, Android `false`), because no file is open at compose time. `init_settings` and the fingerprint show the resolved boolean.
- **Baselines are per device and per platform,** and merge/compare enforce it: the iOS base differs (`flash_attn_type` defaults to `auto`, not `off`). Top-level `device` / `soc` / `commit` / `llama_rn_version` come from the host (`stampReportMetadata`), and the merger's CLI flags override them. Without `--app`, the stamped `commit` is the host checkout, not the installed build (Android is the same).
- **iOS uses `devicectl`, not Appium** (WDA failed repeatedly on iOS 26.7). A cold-launch payload URL is dropped, so the driver launches, settles, then delivers the link warm.
- **iOS has no separate e2e bundle id,** so `--app` replaces the App Store `ai.pocketpal` and wipes its data; hence the explicit flag.
- **iOS CPU rows ride the fallback.** Their weights are `CPU_Mapped`, which `hasOnlyCPU` (`CPU` / `CPU_REPACK` only) does not admit, so they reach `!opencl_init` → `cpu`. Widening `hasOnlyCPU` would reclassify Android mmap rows.
- **The iOS simulator is `cpu`, not Metal:** it lists `MTL0` with 0 MiB free and offloads 0 layers, so no `MTL*` weight buffer appears and a GPU cell (still pinned `['Metal']`, 99 layers) fails `backend-mismatch:gpu:cpu`.
- **A suspended iOS app stays in the process list,** so a lock or app switch mid-run ends `failed:timeout`. Operators keep the iPhone unlocked and on power; Auto-Lock can stay on (keep-awake).
- **A config error or a production build writes no report,** so on iOS both surface as `failed:autostart`.
- **Re-deriving `log_signals` on merge backfills new structured fields from old reports,** but only for lines `BENCH_LOG_RE` already captured. A new signal needs a widened regex and a re-run on device.
- **The v1.1 bump bundled the settings sweep and Hexagon.** Both change row identity, and one migration beat two.

## Verification

- Unit: `src/__automation__/__tests__/` (`benchmarkRoute`, `deepLink`), `src/__automation__/screens/__tests__/BenchmarkRunnerScreen.test.tsx`, `scripts/__tests__/{logSignals,build-bench-config,merge-bench-reports,benchmark-compare,run-bench-ios}.test.ts`.
- Device: the dev-team `bench` skill, or run `yarn build:bench-config --push` (in `e2e/`) followed by `e2e/specs/benchmark-matrix.spec.ts`, then `merge-bench-reports.ts` and `benchmark-compare.ts` against `e2e/baselines/benchmark/<device>.json`.
- By hand: `adb shell am start -a android.intent.action.VIEW -d "pocketpal://e2e/benchmark?autostart=1"` on an e2e build with a pushed config. The status should leave `idle` within seconds.
- iOS: `BENCH_TIER=smoke yarn bench:ios --device <udid> --dry-run` (in `e2e/`) prints the cell count and the `devicectl` plan without touching a device. A real run (`--app ../ios/build/PocketPal.ipa` after `yarn ios:build:ipa`) needs the user's OK because of the install.
