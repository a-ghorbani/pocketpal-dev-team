# Intent: Add settings sweep dimensions to BenchmarkRunnerScreen

## Metadata

- **Task ID**: TASK-20260505-1612
- **Source**: prompt (follow-up surfaced during PR #702 baseline refresh)
- **Worktree**: `./worktrees/TASK-20260505-1612`
- **Branch**: `feature/TASK-20260505-1612`
- **Complexity**: standard
- **Native Changes**: YES (added during implementation — Android JNI shim for `mallopt(M_PURGE_ALL)` + iOS no-op for `purgeNativeAllocator`)
- **Visual Confirmation**: NO
- **Created**: 2026-05-05
- **Status**: Merged in #713 (f34c6bf) on 2026-05-11

---

## Request

Today the bench runner sweeps `model × quant × backend (cpu/gpu) × nr` only. Per-cell context init params (KV cache types, flash_attn, repacking via `no_extra_bufts`, `use_mmap`, `n_threads`, `n_ctx`/`n_batch`/`n_ubatch`) come from `modelStore.contextInitParams` — i.e. whatever the persisted user settings happen to be when the run launches. They are captured into `init_settings` per row but cannot be varied as a sweep dimension.

We need to compare app-default vs. alternative configurations (e.g. `cache_type_k=q8_0` vs `f16`, `flash_attn_type=on` vs `off` on iOS, `no_extra_bufts=true` (repack OFF) vs `false` (repack ON), `use_mmap='true'` vs `'false'`) on the same matrix without manual settings dance.

Concretely, extend `bench-config.json` and the runner to support per-cell overrides for at least:

- `cache_type_k`, `cache_type_v`
- `flash_attn_type` (iOS-meaningful)
- `no_extra_bufts` (Android repacking)
- `use_mmap` (`'true' | 'false' | 'smart'`)
- `n_threads` (sometimes useful for CPU sweeps)

Add matching env-var knobs in `e2e/scripts/build-bench-config.ts` so the existing `BENCH_*` workflow keeps working (e.g. `BENCH_CACHE_TYPE_K=q8_0,f16` produces a sweep × that axis).

The runner should call the existing `modelStore.setUseMmap()` / `setNoExtraBufts()` / `setCacheType*()` setters before each cell's `initContext`, then snapshot `init_settings` AFTER (the existing post-init snapshot stays — it's the source of truth on what was actually applied).

`logSignals.ts` and the merge / compare scripts already key by `(model_id, quant, requested_backend)`; the dedupe key needs to be extended to include the swept settings (or the baseline format needs a settings-fingerprint per row) so multiple settings configurations can coexist in one baseline.

Also follow-up (separate or bundled, the architect/planner decides): wire **Hexagon** (`HTP*`) as a third backend value alongside `'cpu' | 'gpu'`. Plumbing already exists in `src/utils/deviceSelection.ts` (`isHexagonAvailable`, `devices: ['HTP*']`) and `llama.rn` (`LM_GGML_HEXAGON_NDEV`). Bench runner is hardcoded to `'cpu' | 'gpu'` only; `effective_backend` enum and `logSignals` need a hexagon classification.

Out of scope: changing the actual runtime defaults — the baselines we just refreshed (POCO Myron, klee, Samsung S23) are the app-default config and we want to keep them as the canonical reference point. Sweeps would be additional baselines, not replacements.

---

## Clarifications

none — request is unambiguous; treat as standard story (touches contract: bench-config schema, baseline row identity, merge dedupe key).

---

## Notes for the architect

The most consequential design decision is the **dedupe key**. Today rows are identified by `(model_id, quant, requested_backend)`. If we add a settings fingerprint, every existing baseline becomes ambiguous (which fingerprint did the legacy rows use?). Options:
- Treat missing fingerprint as "app-default" and stamp existing baselines accordingly (one-time migration).
- Versioned baseline format with `settings_fingerprint` field; merge tool refuses to mix versions silently.
- Keep separate baseline files per settings configuration; never mix.

The Hexagon-as-third-backend addition has its own subtlety: not every device has Hexagon (klee = MediaTek = no Hexagon), so cells need fail-fast similar to the current GPU-not-available path on Mali devices.
