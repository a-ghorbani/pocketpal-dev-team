# Refreshing a bench baseline

Read from `skills/bench/SKILL.md` when refreshing a baseline or topping up OS-killed cells.

## Refresh (after llama.rn upgrade, native change, or new device)

Baselines are committed to the pocketpal-ai repo. Refreshing one is a focused task:

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
5. Commit, open a PR to pocketpal-ai. Include a one-paragraph summary of why the baseline shifted (llama.rn version, native change, device, etc.).

Run on the device under its **normal load profile** (screen on, typical background apps), not freshly rebooted, so the baseline reflects what users actually see.

## Heavy-model OS-kill pattern

phi-4-mini and gemma-4-e2b at `q8_0` get OS-killed mid-init on most phones. The matrix is ordered to put heavy combos last so partial-row data from earlier cells survives in the JSON report. After the main run finishes (or gets killed), top-up the missing cells:

```bash
BENCH_TIER=full BENCH_MODELS=phi-4-mini BENCH_QUANTS=q8_0 \
  yarn build:bench-config --push <udid>
# … re-run the deep link, pull a second report, merge both via merge-bench-reports
```

The model file is cached on disk, so the top-up runs in minutes.
