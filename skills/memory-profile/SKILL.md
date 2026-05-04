---
name: memory-profile
description: Run memory profiling on physical devices and compare against baselines.
user-invocable: true
argument-hint: "[ios|android|both] [options]"
---

# Memory Profiling

You are running the memory profiling pipeline for PocketPal AI.

## Input

Request: $ARGUMENTS

## What This Pipeline Does

Profiles memory usage across 7 app lifecycle checkpoints (app_launch, models_screen, chat_screen, model_loaded, chat_active, post_chat_idle, model_unloaded), then compares results against stored baselines to detect regressions.

## Infrastructure

### E2E Spec

- `e2e/specs/memory-profile.spec.ts` — the E2E test that drives the profiling
- Uses `TEST_MODELS` env var to select the model (default: smollm2-135m)
- Writes report to `<report-dir>/memory-profile.json`

### Scripts (in `e2e/scripts/`)

- `memory-profile.sh` — orchestration script (build → run spec → compare)
- `memory-compare.ts` — compares two reports, flags regressions (exit 1 if >10% AND >200 MB)

### Baselines (in `e2e/baselines/memory/`)

Named `<device_id>-<model_id>.json`. (Sibling `e2e/baselines/benchmark/` holds the unrelated benchmark-matrix baselines.) Current baselines:

- `iphone-13-pro-qwen3-1.7b.json` — iPhone 13 Pro (device ID: `agh`) — **tracked**
- `pixel-9-qwen3-1.7b.json` — Pixel 9 (device ID: `pixel-9-real`) — **tracked**
- `xiaomi-22126rn91y-qwen3-0.6b.json` — Xiaomi 22126RN91Y — **not yet captured**, see "Capturing a new baseline" below

### Devices & model mapping

Different phones need different baseline models so the baseline is neither RAM-starved (Xiaomi with a 1.7B model OOMs) nor noise-floored (Pixel 9 with a 135M model is dominated by runtime jitter). Mapping:

| Device ID                | Platform | RAM tier    | Model for baseline |
| ------------------------ | -------- | ----------- | ------------------ |
| `agh` (iPhone 13 Pro)    | ios      | 6 GB        | `qwen3-1.7b`       |
| `pixel-9-real`           | android  | 16 GB       | `qwen3-1.7b`       |
| `xiaomi-22126rn91y-real` | android  | ~4 GB (low) | `qwen3-0.6b`       |

> **Do not change the existing iPhone/Pixel mappings** — they've been tracked against these models for a while; swapping models invalidates all historical baselines. Any new device gets its own row.

Override per-run with `--model <id>` if needed; available model IDs are in `e2e/fixtures/models.ts`.

### Builds Required

- iOS real device: `yarn ios:build:ipa` (outputs `ios/build/PocketPal.ipa`)
- Android: `cd android && ./gradlew assembleRelease` (outputs APK)
- iOS simulator: `yarn ios:build:e2e` (outputs .app)

These can be built in parallel. Use `--skip-build` if binaries already exist.

## How to Run

### Via the E2E runner (preferred)

Use the device→model mapping from the table above. One invocation per device:

```bash
cd <worktree>/e2e
TEST_MODELS=qwen3-1.7b yarn e2e:ios --skip-build --spec memory-profile --devices agh
TEST_MODELS=qwen3-1.7b yarn e2e:android --skip-build --spec memory-profile --devices pixel-9-real
TEST_MODELS=qwen3-0.6b yarn e2e:android --skip-build --spec memory-profile --devices xiaomi-22126rn91y-real
```

Reports land in timestamped dirs under `e2e/reports/<timestamp>/<device-id>/memory-profile.json`.

### Via the orchestration script

```bash
cd <project-root>
e2e/scripts/memory-profile.sh --platform ios --skip-build --model qwen3-1.7b --baseline e2e/baselines/memory/iphone-13-pro-qwen3-1.7b.json
```

### Comparing results

```bash
npx tsx e2e/scripts/memory-compare.ts <baseline.json> <current.json>
```

## Typical Workflow

1. Check if physical devices are connected: `adb devices` and `xcrun xctrace list devices`
2. For each device you'll run against, look up the model from the mapping table and ensure LM Studio has it loaded (if relevant): `./tools/lmstudio.sh ensure "qwen/qwen3-1.7b"` (etc.) (requires `REMOTE_SERVER_API_KEY` or `LMSTUDIO_API_KEY` env var — sourced from the worktree's `e2e/.env`)
3. Build IPA and APK (in parallel if both platforms needed, skip if already built)
4. Run profiling on each device with the **device's** `TEST_MODELS` from the mapping (do not use a single global model)
5. Compare each result against the matching baseline in `e2e/baselines/memory/`
6. Present results side by side (baseline vs current, per checkpoint, deltas)

## Capturing a new baseline (e.g. new device or new model)

Baselines are committed to the pocketpal-ai repo (`e2e/baselines/memory/` is tracked). Adding one is a small task, not a one-off local capture:

1. `/start-task "Capture memory-profile baseline for <device>"` — gets a worktree and task branch.
2. In the worktree, run the memory-profile spec against the target device with that device's mapped model:
   ```bash
   cd worktrees/TASK-xxx/e2e
   TEST_MODELS=<model-id> yarn e2e:android --skip-build \
     --spec memory-profile --devices <device-id>
   ```
3. Sanity-check the produced `reports/<ts>/<device-id>/memory-profile.json`:
   - Peak memory should be well under the device's RAM.
   - No checkpoint should be zero or absurdly large.
   - Run twice; per-checkpoint deltas should be <10% (if not, something is unstable — investigate before committing).
4. Copy the clean report to `e2e/baselines/memory/<device-id>-<model-id>.json`, commit, open a PR to pocketpal-ai.

Do this on a device under its **normal load profile** (screen on, typical background apps) — not a freshly-rebooted, zero-background state — so the baseline reflects what users will actually see.

## Presenting Results

Show a table with both platforms:

| Checkpoint | iOS Baseline | iOS Current | iOS Delta | Android Baseline | Android Current | Android Delta |
| --- | --- | --- | --- | --- | --- | --- |

Include peak memory summary and PASS/FAIL status from the comparison script.

## LM Studio Model Manager

`tools/lmstudio.sh` manages models on the LM Studio server. Key commands:

- `status` — show loaded models
- `list` — list all downloaded models
- `ensure <model-key>` — load model if not already loaded (unloads others first)
- `load <model-key>` — force load (unloads all first)

Requires `REMOTE_SERVER_API_KEY` or `LMSTUDIO_API_KEY`. Source from worktree `e2e/.env`:

```bash
export $(grep REMOTE_SERVER_API_KEY worktrees/TASK-xxx/e2e/.env | xargs)
./tools/lmstudio.sh ensure "qwen/qwen3-1.7b"
```

## Notes

- Always kill stale Appium first: `lsof -ti:4723 | xargs kill -9 2>/dev/null || true`
- Always ensure the correct model is loaded on LM Studio before running remote-server tests
- iOS and Android runs are independent — run them in parallel or sequentially
- `yarn install` and `pod install` may be needed after merges that change native deps
- The comparison script exits 0 (pass) or 1 (regression) — both thresholds must be exceeded to fail
