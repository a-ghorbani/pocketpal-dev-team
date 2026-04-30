---
name: bench
description: Run the benchmark matrix on physical Android devices and compare against baselines.
user-invocable: true
argument-hint: "[smoke|focused|full] [--devices id1,id2] [--models id1,id2] [--quants q4_0,q6_k] [--skip-build]"
---

# Benchmark Matrix

You are running the benchmark-matrix pipeline for PocketPal AI.

## Input
Request: $ARGUMENTS

## What This Pipeline Does

Sweeps `(model × quant × backend)` cells through llama.rn on a real device,
recording prompt-processing tok/s (`pp_avg`), token-generation tok/s
(`tg_avg`), wall time, peak memory, and the **effective backend**
(`cpu` / `opencl` / `cpu+opencl-partial` / `unknown`) derived live from
native log lines. Compares the resulting report against the device's
committed baseline to flag perf regressions or silent backend fallbacks.

Android-only. iOS bench is not part of this pipeline.

## Tiers

Single source of truth: `BENCHMARK_FULL_MODELS` in
[`e2e/fixtures/benchmark-models.ts`](../../e2e/fixtures/benchmark-models.ts).
Smaller tiers are derived as id filters from that list.

| Tier | Models × quants × backends | Cells | Runtime | When |
|------|----------------------------|------:|---------|------|
| `smoke` (default) | 3 × 3 × 2 | 18 | ~10–15 min | Regression gate; PR + every llama.rn nightly |
| `focused` | 6 × 6 × 2 | ~60 | ~30–45 min | Investigation when smoke flags something |
| `full` | 11 × 8 × 2 | ~165 | ~3 hr/device | Recalibrating defaults, adding device class |

Pick based on the trigger:
- PR touching inference / native code → `smoke`
- Smoke regression on one cell → `focused` with `BENCH_MODELS=` narrowed to that family
- llama.rn upgrade → `smoke` first; `full` only if you intend to refresh the baseline
- New device → `full` once to seed a baseline, then `smoke` thereafter

## Infrastructure

### In-app driver (preferred, no WDIO)
- `BenchmarkRunnerScreen` (in `src/__automation__/screens/`) runs the matrix entirely in-app.
- Reached via deep link: `pocketpal://e2e/benchmark` (E2E flavor only).
- On-device backend detection: `addNativeLogListener` captures llama.cpp log lines per cell; `src/__automation__/logSignals.ts` parses them into a `LogSignals` struct and a 4-state `effective_backend` enum.
- Reads `bench-config.json` from the e2e flavor's external files dir. Writes
  `benchmark-report-<timestamp>.json` next to it.

### WDIO spec (fallback / CI)
- `e2e/specs/benchmark-matrix.spec.ts` — thin wrapper that triggers the screen via deep link and polls for `bench-runner-screen-status="complete"`. Use when running through the unified E2E pipeline.

### Scripts (in `e2e/scripts/`)
- `build-bench-config.ts` — reads `BENCH_TIER` + filters, writes `bench-config.json`, optional `--push <udid>`.
- `benchmark-compare.ts` — compares two reports row-by-row. Regression trigger: `|delta%| > --pct` (default 15) on **either** `pp_avg` or `tg_avg`, **or** `effective_backend` mismatch. Exit 1 on regression.
- `merge-bench-reports.ts` — merges raw report glob into a canonical baseline. Dedupes by `(model_id, quant, requested_backend)`, prefers `status:ok`, latest timestamp wins, sorts deterministically, strips `log_signals.raw_matches`.

### Baselines (in `e2e/baselines/benchmark/`)
Named `<device-slug>.json`. (Sibling `e2e/baselines/memory/` holds the
unrelated memory-profile baselines.) One file per device class; all backends
× quants × models live in one report. Current baselines:
- `poco-myron.json` — POCO X9 Pro Myron / Snapdragon 8 Elite Gen 5 / Adreno 840 — **tracked**

When new devices come online, add a row here and a slug for their baseline file.

### Devices & filter mapping

Low-RAM phones cannot run the full quant ladder for every model — heavy
combos (phi-4-mini q8_0, gemma-4-e2b q8_0) get OS-killed. Filter with
`BENCH_MODELS=`/`BENCH_QUANTS=` for those devices instead of letting the
matrix OOM mid-run.

| Device ID | UDID | RAM tier | Notes |
|---|---|---|---|
| `poco-myron` | `df8fc5ef` | high (16 GB) | Adreno 840; runs full matrix; canonical GPU device |
| `pixel-9-real` | `45300DLAQ004DH` | high (16 GB) | Tensor G4; runs full matrix |
| `oneplus-6-real` | `ba5702bf` | low (~6 GB) | Skip phi-4-mini and gemma-4-e2b q8_0 cells |
| `android-emu` | `emulator-5554` | n/a | Smoke only; no GPU; for spec-shape verification |

> **Don't change the slug of a tracked baseline** without also re-running
> against the new slug — comparison is filename-keyed.

### Builds Required
- Android E2E APK: `yarn android:build:e2e` (installs as `com.pocketpalai.e2e`, ships the automation bridge).
- The `prod` flavor has no automation bridge; it cannot run this pipeline.

Use `--skip-build` when the APK is already installed and the bench-config
script hasn't changed.

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
  --spec benchmark-matrix --devices <device-id>
```

Reports land in `e2e/reports/<timestamp>/<device-id>/`.

### Comparing results
```bash
npx tsx e2e/scripts/benchmark-compare.ts \
  e2e/baselines/benchmark/<device>.json /tmp/bench/<device>/benchmark-report-*.json
```

Default regression threshold is `--pct 15`. Effective-backend changes are
flagged independent of the numeric deltas — a silent OpenCL→CPU fallback is a
regression even if the cell got faster.

## Typical Workflow

1. Check connected devices: `adb devices -l`.
2. Confirm the E2E APK is installed: `adb -s <udid> shell pm list packages com.pocketpalai.e2e`. If missing, `yarn android:build:e2e`.
3. Pick the tier (see "Tiers" above).
4. Per device: generate + push config → deep-link the runner → tap Run → wait for `complete` → adb pull the JSON.
5. Compare each pulled report against `e2e/baselines/benchmark/<device>.json`.
6. Present results: per-cell deltas, peak memory, effective_backend, PASS/FAIL from the comparison script.

## Refreshing a baseline (after llama.rn upgrade, native change, or new device)

Baselines are committed to the pocketpal-ai repo. Refreshing one is a focused
task:

1. `/start-task "Refresh bench baseline for <device> (llama.rn <ver>)"` — gets a worktree and task branch.
2. Run the **full** tier on the device (use filters only if RAM forces it). Capture multiple raw reports if you need to top-up cells the OS killed mid-run — the same model file is cached, so re-runs are fast.
   ```bash
   cd worktrees/TASK-xxx/e2e
   BENCH_TIER=full yarn build:bench-config --push <udid>
   adb -s <udid> shell am start -a android.intent.action.VIEW \
     -d 'pocketpal://e2e/benchmark' -p com.pocketpalai.e2e
   # … wait for complete, pull, then top-up missing cells with BENCH_QUANTS=
   ```
3. Sanity-check the raw reports:
   - Every cell has `status: 'ok'` (or a documented `skipped` reason).
   - GPU cells show `effective_backend: 'opencl'`; CPU cells show `'cpu'`. Any `'unknown'` on a non-GPU device means the parser missed a log line — investigate before merging.
   - Per-cell `pp_avg`/`tg_avg` within ~10% of the prior baseline (modulo the change you're absorbing).
4. Merge into a canonical baseline:
   ```bash
   npx tsx scripts/merge-bench-reports.ts \
     --input '/tmp/bench/<device>/benchmark-report-*.json' \
     --out baselines/benchmark/<device>.json \
     --device '<full device label>' \
     --soc '<soc + gpu>' \
     --commit "$(git rev-parse --short HEAD)" \
     --llama-rn-version "$(node -p 'require(\"../package.json\").dependencies[\"llama.rn\"]')" \
     --drop-models <stale-model-id-if-any>
   ```
5. Commit, open a PR to pocketpal-ai. Include a one-paragraph summary of why
   the baseline shifted (llama.rn version, native change, device, etc.).

Run on the device under its **normal load profile** (screen on, typical
background apps), not freshly rebooted, so the baseline reflects what users
actually see.

## Heavy-model OS-kill pattern

phi-4-mini and gemma-4-e2b at `q8_0` get OS-killed mid-init on most phones.
The matrix is ordered to put heavy combos last so partial-row data from
earlier cells survives in the JSON report. After the main run finishes (or
gets killed), top-up the missing cells:

```bash
BENCH_TIER=full BENCH_MODELS=phi-4-mini BENCH_QUANTS=q8_0 \
  yarn build:bench-config --push <udid>
# … re-run the deep link, pull a second report, merge both via merge-bench-reports
```

The model file is cached on disk, so the top-up runs in minutes.

## Effective backend — what `unknown` means

`effective_backend` is derived from native log lines captured during context
init. The 4 states:

- `cpu` — no OpenCL init line; everything ran on CPU as requested.
- `opencl` — OpenCL init succeeded, all layers offloaded to GPU.
- `cpu+opencl-partial` — OpenCL initialized but some layers stayed on CPU (large-buffer regression, partial offload).
- `unknown` — logs were captured but the parser couldn't classify them. Treat as a real signal: either the log format changed (new llama.rn version) or no logs were captured (init crashed before the listener attached). Investigate; don't merge into a baseline.

A GPU cell reporting `cpu` is a silent fallback — the comparison script flags
this as a regression independent of pp/tg deltas.

## Presenting Results

Per device, a per-cell table:

| Model | Quant | Backend | Baseline pp/tg | Current pp/tg | Δpp% | Δtg% | Effective | Status |
|---|---|---|---|---|---|---|---|---|

Plus the comparison script's PASS/FAIL summary and a one-line note on the
worst regression and the worst improvement.

## Notes

- Keep the screen on during a `full` run — Android dozes the e2e flavor under doze, which corrupts cell timing.
- A cell with `status: 'failed'` and a `reason` field is benign (skipped quant, missing download); a cell with `status: 'failed'` and an `error` field is a real failure.
- `bench-config.json` lives in the device's external files dir; surviving across uninstalls only if you reinstall the same `e2e` flavor. Re-push after every fresh APK install.
- The merge script's `--drop-models` flag exists for fixture-renames (e.g. `lfm2-1.2b` → `lfm2.5-1.2b-instruct`); use it instead of hand-editing the merged JSON.
- If a `full` run takes longer than 4 hours, something is wrong — usually thermal throttling or a model file that didn't pre-download. Stop and investigate rather than waiting it out.
