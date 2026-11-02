---
name: bench
description: Run the benchmark matrix on physical Android and iOS devices and compare against baselines.
user-invocable: true
argument-hint: "[smoke|focused|full] [--devices id1,id2] [--models id1,id2] [--quants q4_0,q6_k] [--skip-build]"
---

# Benchmark Matrix

You are running the benchmark-matrix pipeline for PocketPal AI.

## Input

Request: $ARGUMENTS

## What This Pipeline Does

Sweeps `(model × quant × backend)` cells through llama.rn on a real device, recording prompt-processing tok/s (`pp_avg`), token-generation tok/s (`tg_avg`), wall time, peak memory, and the **effective backend** (`cpu` / `opencl` / `cpu+opencl-partial` / `hexagon` / `cpu+hexagon-partial` / `metal` / `cpu+metal-partial` / `unknown`) derived live from native log lines. Compares the resulting report against the device's committed baseline to flag perf regressions or silent backend fallbacks.

Claim a phone through agistry before driving it and release it after (a pipeline stage uses the `DEVICE` its orchestrator claimed). This host has no iOS toolchain: iOS runs go through `ios-router`.

Android runs through the WDIO spec or `yarn build:bench-config --push` below. On a physical iPhone, run `yarn bench:ios --device <udid> [--app ../ios/build/PocketPal.ipa]` from the app worktree's `e2e/` (build with `yarn ios:build:ipa`; `--dry-run` first). It drives the same matrix with `xcrun devicectl` only and pulls, stamps and pass-gates the report itself (`e2e/README.md`, "iOS (physical iPhone)").

**`--app` replaces the App Store PocketPal** (same bundle id `ai.pocketpal`) and wipes its data. Get the user's explicit OK before installing. Keep the iPhone unlocked and on power, and do not lock it mid-run. iOS baselines are separate from Android ones: merge and compare refuse cross-platform input.

**iOS speed swings 2–3x with heat and charging**, so a block-ordered run (all A, then all B) or a comparison against the baseline alone decides nothing. Before calling an iOS regression or speed-up:

- run baseline and candidate interleaved in one session (A B B A), with a cool-down between phases;
- check `thermalState` is nominal before each phase (WDA `mobile: deviceInfo`);
- drop the cold first phase and compare means;
- rerun the baseline last as a drift control. A gap that grows with a model's position in the run is drift: reverse the model order to confirm.

## Tiers

Single source of truth: `BENCHMARK_FULL_MODELS` in `e2e/fixtures/benchmark-models.ts` (in the app worktree). Smaller tiers are derived as id filters from that list.

| Tier | Models × quants × backends | Cells | Runtime | When |
| --- | --- | --: | --- | --- |
| `smoke` (default) | 3 × 3 × 2 | 18 | ~10–15 min | Regression gate; PR + every llama.rn nightly |
| `focused` | 6 × 6 × 2 | ~60 | ~30–45 min | llama.rn bumps and inference changes; investigating a smoke flag |
| `full` | 11 × 8 × 2 | ~165 | ~3 hr/device | Recalibrating defaults, adding device class |

Pick based on the trigger:

- llama.rn bump, backend selection, or inference code → `smoke` and `focused`; `full` only to refresh the baseline
- Any other native change (model loading, native dependencies, build flags) → `smoke`
- Smoke regression on one cell → `focused` with `BENCH_MODELS=` narrowed to that family
- New device → `full` once to seed a baseline, then `smoke` thereafter

## Infrastructure

Read `references/infrastructure.md` for the in-app driver (`BenchmarkRunnerScreen`, deep link `pocketpal://e2e/benchmark`), the WDIO spec `e2e/specs/benchmark-matrix.spec.ts`, the `e2e/scripts/` tools (`build-bench-config.ts`, `benchmark-compare.ts`, `merge-bench-reports.ts`), baselines in `e2e/baselines/benchmark/<device-slug>.json`, the device/RAM filter table, and the `effective_backend` states. Rules:

- Device IDs and UDIDs come from the worktree's local `e2e/devices.json`. On low-RAM phones filter with `BENCH_MODELS=`/`BENCH_QUANTS=` instead of letting the matrix OOM.
- Don't change the slug of a tracked baseline without re-running against the new slug; comparison is filename-keyed.
- `unknown` backend is a real signal (log format changed or init crashed before the listener attached): investigate, never merge it into a baseline. A GPU cell reporting `cpu` is a silent fallback and a regression regardless of pp/tg.

## Builds Required

- Android E2E APK: `yarn android:build:e2e` (installs as `com.pocketpalai.e2e`, ships the automation bridge).
- The `prod` flavor has no automation bridge; it cannot run this pipeline.

Use `--skip-build` when the APK is already installed and the bench-config script hasn't changed.

## On the PR's CI APK

CI-APK rows run post-PR on the draft PR's bridge APK from `e2e-tests.yml`: `tools/fetch-pr-apk.sh --e2e <PR>` into the `PR-<N>-e2e` worktree (or `tools/run-pr-e2e.sh <PR> --e2e --specs benchmark-matrix`; `/run-pr-e2e`), then install it and run as below. If `e2e-tests.yml` has not run for the PR's head branch, dispatch it: `tools/ghb workflow run e2e-tests.yml --repo a-ghorbani/pocketpal-ai --ref <head-branch>`.

## How to Run

### Direct (preferred for ad-hoc runs)

One device at a time. Replace `<udid>` with the value from `e2e/devices.json`.

```bash
cd <worktree>/e2e

# 1. Generate config + adb push to device
BENCH_TIER=smoke yarn build:bench-config --push <udid>

# (optional filters narrow the chosen tier — they can't widen it)
BENCH_TIER=full BENCH_MODELS=qwen3-1.7b,gemma-3-1b BENCH_QUANTS=q4_0,q6_k \
  yarn build:bench-config --push <udid>

# 2. Cold-launch the runner via deep link
adb -s <udid> shell am start -a android.intent.action.VIEW \
  -d 'pocketpal://e2e/benchmark' -p com.pocketpalai.e2e

# 3. Tap "Run benchmark matrix" on the screen.
#    Wait for the status footer to read "complete".
#    Smoke ≈ 10–15 min, full ≈ 3 hr — keep the screen on.

# 4. Pull the report
adb -s <udid> pull \
  /sdcard/Android/data/com.pocketpalai.e2e/files/benchmark-report-*.json \
  /tmp/bench/<device>/
```

### Via the unified E2E runner

When invoking through the multi-device pipeline (e.g. CI):

```bash
BENCH_TIER=smoke yarn e2e:android --skip-build \
  --spec benchmark-matrix --devices <device-id>   # id from e2e/devices.json
```

Reports land in `e2e/reports/<timestamp>/<device-id>/`.

### Comparing results

```bash
npx tsx e2e/scripts/benchmark-compare.ts \
  e2e/baselines/benchmark/<device>.json /tmp/bench/<device>/benchmark-report-*.json
```

Default regression threshold is `--pct 15`. Effective-backend changes are flagged independent of the numeric deltas — a silent OpenCL→CPU fallback is a regression even if the cell got faster.

## Typical Workflow

1. Check connected devices: `adb devices -l`.
2. Confirm the E2E APK is installed: `adb -s <udid> shell pm list packages com.pocketpalai.e2e`. If missing, `yarn android:build:e2e`.
3. Pick the tier (see "Tiers" above).
4. Per device: generate + push config → deep-link the runner → tap Run → wait for `complete` → adb pull the JSON.
5. Compare each pulled report against `e2e/baselines/benchmark/<device>.json`.
6. Present results: per-cell deltas, peak memory, effective_backend, PASS/FAIL from the comparison script.

## Baselines and OS-killed cells

Read `references/baseline-refresh.md` when refreshing a baseline (full tier, sanity checks, `merge-bench-reports.ts` command, PR to pocketpal-ai) or topping up cells OS-killed mid-run (phi-4-mini / gemma-4-e2b `q8_0`). Run baselines under the device's normal load profile, not freshly rebooted.

## Presenting Results

Per device, a per-cell table:

| Model | Quant | Backend | Baseline pp/tg | Current pp/tg | Δpp% | Δtg% | Effective | Status |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |

Plus the comparison script's PASS/FAIL summary and a one-line note on the worst regression and the worst improvement.

## Notes

- Keep the screen on during a `full` run — Android dozes the e2e flavor under doze, which corrupts cell timing.
- A cell with `status: 'failed'` and a `reason` field is benign (skipped quant, missing download); a cell with `status: 'failed'` and an `error` field is a real failure.
- `bench-config.json` lives in the device's external files dir; surviving across uninstalls only if you reinstall the same `e2e` flavor. Re-push after every fresh APK install.
- The merge script's `--drop-models` flag exists for fixture-renames (e.g. `lfm2-1.2b` → `lfm2.5-1.2b-instruct`); use it instead of hand-editing the merged JSON.
- If a `full` run takes longer than 4 hours, something is wrong — usually thermal throttling or a model file that didn't pre-download. Stop and investigate rather than waiting it out.
