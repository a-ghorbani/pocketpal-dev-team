# Bench infrastructure

Read from `skills/bench/SKILL.md` when you need the driver, scripts, baselines, device filters, or what an `effective_backend` value means.

## In-app driver (preferred, no WDIO)

- `BenchmarkRunnerScreen` (in `src/__automation__/screens/`) runs the matrix entirely in-app.
- Reached via deep link: `pocketpal://e2e/benchmark` (E2E flavor only).
- On-device backend detection: `addNativeLogListener` captures llama.cpp log lines per cell; `src/__automation__/logSignals.ts` parses them into a `LogSignals` struct and an `effective_backend` enum (states under "Effective backend" in this file).
- Reads `bench-config.json` from the e2e flavor's external files dir. Writes `benchmark-report-<timestamp>.json` next to it.

## WDIO spec (fallback / CI)

- `e2e/specs/benchmark-matrix.spec.ts` — thin wrapper that triggers the screen via deep link and polls for `bench-runner-screen-status="complete"`. Use when running through the unified E2E pipeline.

## Scripts (in `e2e/scripts/`)

- `build-bench-config.ts` — reads `BENCH_TIER` + filters, writes `bench-config.json`, optional `--push <udid>`.
- `benchmark-compare.ts` — compares two reports row-by-row. Regression trigger: `|delta%| > --pct` (default 15) on **either** `pp_avg` or `tg_avg`, **or** `effective_backend` mismatch. Exit 1 on regression.
- `merge-bench-reports.ts` — merges raw report glob into a canonical baseline. Dedupes by `(model_id, quant, requested_backend)`, prefers `status:ok`, latest timestamp wins, sorts deterministically, strips `log_signals.raw_matches`.

## Baselines (in `e2e/baselines/benchmark/`)

Named `<device-slug>.json`, one per device class (all backends × quants × models in one report); the current set is the per-device files in `e2e/baselines/benchmark/` (see its `README.md`). Sibling `e2e/baselines/memory/` holds the unrelated memory-profile baselines.

## Devices & filter mapping

Low-RAM phones cannot run the full quant ladder for every model — heavy combos (phi-4-mini q8_0, gemma-4-e2b q8_0) get OS-killed. Filter with `BENCH_MODELS=`/`BENCH_QUANTS=` for those devices instead of letting the matrix OOM mid-run.

Device IDs and UDIDs come from the worktree's local `e2e/devices.json`. Examples:

| Device | RAM tier | Notes |
| --- | --- | --- |
| POCO X9 Pro (`poco-myron` baseline) | high (16 GB) | Adreno 840; runs full matrix; canonical GPU device |
| `pixel-9-real` | high (16 GB) | Tensor G4; runs full matrix |
| `oneplus-a6003-real` | low (~6 GB) | Skip phi-4-mini and gemma-4-e2b q8_0 cells |
| an emulator | n/a | Smoke only; no GPU; for spec-shape verification |

> **Don't change the slug of a tracked baseline** without also re-running against the new slug — comparison is filename-keyed.

## Effective backend — what `unknown` means

`effective_backend` is derived from native log lines captured during context init (`deriveEffectiveBackend` in `src/__automation__/logSignals.ts`). The states:

- `cpu` — no GPU or NPU weight buffer; everything ran on CPU as requested. The iOS simulator lands here (0 layers offloaded).
- `opencl` — OpenCL init succeeded, all layers offloaded to GPU.
- `cpu+opencl-partial` — OpenCL initialized but some layers stayed on CPU (large-buffer regression, partial offload).
- `hexagon` / `cpu+hexagon-partial` — weights on an `HTP*` buffer, fully or partially offloaded.
- `metal` / `cpu+metal-partial` — weights on an `MTL*` buffer (iOS), fully or partially offloaded.
- `unknown` — logs were captured but the parser couldn't classify them. Treat as a real signal: either the log format changed (new llama.rn version) or no logs were captured (init crashed before the listener attached). Investigate; don't merge into a baseline.

A GPU cell reporting `cpu` is a silent fallback — the comparison script flags this as a regression independent of pp/tg deltas.
