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

### Baselines (in `e2e/baselines/`)
Named `<device>-<model>.json`. Current baselines:
- `iphone-13-pro-qwen3-1.7b.json` — iPhone 13 Pro (device ID: `agh`)
- `pixel-9-qwen3-1.7b.json` — Pixel 9 (device ID: `pixel-9-real`)

### Devices (in `e2e/devices.json`)
Physical devices used for profiling:
- `agh` — iPhone 13 Pro (real, iOS, USB)
- `pixel-9-real` — Pixel 9 (real, Android, USB)

### Model
Default profiling model: `qwen3-1.7b` (matches baselines). Override with `--model <id>`.
Available models are defined in `e2e/fixtures/models.ts`.

### Builds Required
- iOS real device: `yarn ios:build:ipa` (outputs `ios/build/PocketPal.ipa`)
- Android: `cd android && ./gradlew assembleRelease` (outputs APK)
- iOS simulator: `yarn ios:build:e2e` (outputs .app)

These can be built in parallel. Use `--skip-build` if binaries already exist.

## How to Run

### Via the E2E runner (preferred)
```bash
cd <project-root>/e2e
TEST_MODELS=qwen3-1.7b yarn e2e:ios --skip-build --spec memory-profile --devices agh
TEST_MODELS=qwen3-1.7b yarn e2e:android --skip-build --spec memory-profile --devices pixel-9-real
```

Reports land in timestamped dirs under `e2e/reports/<timestamp>/<device-id>/memory-profile.json`.

### Via the orchestration script
```bash
cd <project-root>
e2e/scripts/memory-profile.sh --platform ios --skip-build --model qwen3-1.7b --baseline e2e/baselines/iphone-13-pro-qwen3-1.7b.json
```

### Comparing results
```bash
npx tsx e2e/scripts/memory-compare.ts <baseline.json> <current.json>
```

## Typical Workflow

1. Check if physical devices are connected: `adb devices` and `xcrun xctrace list devices`
2. Ensure the correct model is loaded on LM Studio: `./tools/lmstudio.sh ensure "qwen/qwen3-1.7b"`
   (requires `REMOTE_SERVER_API_KEY` or `LMSTUDIO_API_KEY` env var — sourced from worktree's `e2e/.env`)
3. Build IPA and APK (in parallel if both platforms needed, skip if already built)
4. Run profiling on each device with `TEST_MODELS=qwen3-1.7b`
5. Compare each result against the matching baseline in `e2e/baselines/`
6. Present results side by side (baseline vs current, per checkpoint, deltas)

## Presenting Results

Show a table with both platforms:

| Checkpoint | iOS Baseline | iOS Current | iOS Delta | Android Baseline | Android Current | Android Delta |
|---|---|---|---|---|---|---|

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
