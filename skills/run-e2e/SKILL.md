---
name: run-e2e
description: Build PocketPal AI from source in a worktree and run E2E specs against the local build. For testing the CI-built APK of a PR instead, use /run-pr-e2e.
user-invocable: true
argument-hint: "[branch-name | main] [options]"
---

# Run E2E Tests (local build)

You are building PocketPal AI from source in a worktree and running E2E specs against the local build. If the user wants to verify a PR matches the bit-identical artifact CI produced — without a local build — use `/run-pr-e2e` instead; that skill covers the CI-artifact path and defers to this one for everything generic.

## Project facts (not exposed by `--help`)

1. **No CI gate on E2E.** `.github/workflows/e2e-tests.yml` is a manual `workflow_dispatch` that only uploads the Android APK as an artifact; no specs are executed. Treat "E2E green" claims outside this skill as unverified until reproduced locally.
2. **Android uses a separate `e2e` flavor**, package `com.pocketpalai.e2e`, output at `android/app/build/outputs/apk/e2e/releaseE2e/app-e2e-releaseE2e.apk`. The prod APK (`outputs/apk/release/app-release.apk`) is non-debuggable and has the `src/__automation__/` bridge DCE-stripped — specs against it silently no-op. Always build via `yarn android:build:e2e`, never `assembleRelease`.
3. **iOS has no separate flavor.** Same bundleId as prod (`ai.pocketpal`), differentiated only by the `__E2E__` define from `babel.config.js: transform-define` driven by `E2E_BUILD=true`. `yarn ios:build:e2e` is the only correct build command for sim tests; `yarn ios:build:ipa` for iOS devices.
4. **Reset behaviour differs across platforms.** iOS uses `noReset:false, fullReset:false` — install state (including downloaded models) is preserved across runs. Android uses `fullReset:true` — the app is reinstalled every run and any downloaded model is lost. Plan timing accordingly.
5. **`e2e/devices.json` is gitignored and per-worktree.** Verify the Android `appPath` matches the e2e-flavor output (`../android/app/build/outputs/apk/e2e/releaseE2e/app-e2e-releaseE2e.apk`). A wrong path surfaces as `WebDriverError: The application at '...' does not exist`, even when the build itself succeeded.
6. **`TIMEOUTS.appReady = 60s`** in `e2e/fixtures/models.ts`. Most specs block on the `chat-input` testID for 60s before doing anything else. A broken first-paint manifests as `no such element 'chat-input'` after roughly the appReady timeout.

## Available specs

Pick the smallest spec that exercises what changed. Defaults to `quick-smoke`.

### Core (`e2e/specs/*.spec.ts`)

| Spec | Tests | Use when |
|---|---|---|
| `quick-smoke` | Full user journey on the smallest model (SmolLM2-135M): drawer → Models → HF search → download → load → chat → assert tokens/sec timing. | Default sanity gate. First thing to run before anything more targeted. |
| `load-stress` | Multiple load/unload cycles with inference between each. Per-model via `TEST_MODELS`. | Reproducing or guarding against crashes on model reload. |
| `benchmark-matrix` | Drives the in-app `BenchmarkRunnerScreen` across `{models} × {quants} × {backends}`; writes canonical JSON via the automation bridge. Android-only, requires the `e2e` flavor APK. | Perf regression sweeps; producing a report for `scripts/benchmark-compare.ts`. |
| `memory-profile` | Captures memory at 7 lifecycle checkpoints (app_launch → models_screen → chat_screen → model_loaded → chat_active → post_chat_idle → model_unloaded); writes canonical JSON for the `/memory-profile` pipeline. | Memory regression sweeps; producing a report for `scripts/memory-compare.ts`. |
| `visual-capture` | Parametrised screenshot generator driven by the `VISUAL_CAPTURES` env var. Skips silently if the var is unset — it is not a regression test. | Producing PR screenshots from a story file (`docs/workflows/visual-capture.md`). |
| `diagnostic` | Dumps Appium page-source XML to `e2e/debug-output/` at each navigation step. Not a regression test. | Debugging "no such element" failures by inspecting what Appium actually sees. |

### Feature (`e2e/specs/features/*.spec.ts`)

| Spec | Tests | Use when |
|---|---|---|
| `quick-smoke` already covers the core chat path. Run a feature spec instead when the change is localised to that feature. ||
| `thinking` | Loads qwen3-0.6b, toggles thinking, asserts the "Reasoning" bubble appears and disappears. | Touching the thinking toggle, reasoning bubble, or thinking-capable inference path. |
| `language` | Cycles every supported language, asserts the UI updates. No model load required. | l10n changes, language switcher, `src/locales/` work. |
| `draft-autosave` | Asserts unsent input text persists across session switches and clears on send. | Changes to chat input draft persistence or session-switch behaviour. |
| `remote-server` | Adds a remote OpenAI-compatible model from the Models FAB, chats with it, deletes the server. Requires a reachable OpenAI-compatible server. | Remote-model / remote-server changes. |
| `talent-tool-use` | Creates a Pal with `render_html` enabled, sends a prompt, asserts the HTML preview bubble appears. Uses Qwen3-1.7B with temperature=0/seed=1 for determinism. | Talent registry, tool-use plumbing, HTML preview surface. |

`benchmark-matrix`, `memory-profile`, and `visual-capture` are deliberately excluded from the `/run-pr-e2e` default-spec list because they are measurement infrastructure, not regression gates.

## Parse input

Extract from `$ARGUMENTS`:

- **Worktree** (optional): if a branch name is given, check it out in a dedicated `./worktrees/E2E-<safe-name>` via `./tools/create-worktree.sh ... --detach --ref origin/<branch>`. If `main`, use `./worktrees/E2E-main`. If omitted, use the current task worktree if there is one; otherwise stop and ask the user which worktree. (For the PR-CI-artifact path, redirect to `/run-pr-e2e`.)
- **Platform**: `ios`, `android`, `both` (default: `both`).
- **Devices**: `all` / `virtual-only` / `real-only` / `connected` / comma-separated IDs (runner default: `all`).
- **Spec**: any basename from the catalogs above (the runner resolves both `specs/` and `specs/features/`); default `quick-smoke`.
- **Flags**: pass through `--each-model`, `--each-device`, `--all-models`, `--skip-build`, `--dry-run`, `--models a,b`. Anything else: consult `npx ts-node scripts/run-e2e.ts --help`.

## Step 1 — Pre-flight

Verify before starting a run:

- **Worktree**: reuse an existing one for the branch when present; otherwise create with `./tools/create-worktree.sh` (`--detach --ref origin/<branch>`, or `--ref origin/main` for main). Never test inside `repos/pocketpal-ai/` — it's a read-only submodule.
- **Local branch is in sync with origin**. Stale checkouts produce results that don't reflect the code being shipped.
- **iOS simulator is booted** (the runner does not boot it).
- **Android emulator or device is attached and showing as `device`** in `adb devices`.
- **Appium ports 4723 and 4724 are free** — the WDIO config spawns Appium on these (see `wdio.{ios,android}.local.conf.ts`); a leftover daemon from a previous run causes session creation to hang.

## Step 2 — One-time worktree setup

Each fresh worktree needs three project-specific things beyond root `yarn install`:

- **`e2e/` has its own `package.json`** (WDIO + Appium client deps). Run `yarn install` separately in that subdirectory.
- **`ios/` has a `Gemfile`** that pins `xcpretty` and the cocoapods version. Install via Bundler before `pod install`, otherwise `yarn ios:build:e2e` fails opaquely — xcpretty swallows the real xcodebuild error.
- **`pod install`** after any `Podfile.lock` change (llama.rn upgrades, new native deps).

Then verify `e2e/devices.json` (gitignored, per-worktree, copied from `devices.template.json` on creation). The Android `appPath` must be `../android/app/build/outputs/apk/e2e/releaseE2e/app-e2e-releaseE2e.apk`. Anything else — most often the prod-release path — fails Android session creation with `APK does not exist`.

## Step 3 — Run the pipeline

Entry point: `npx ts-node scripts/run-e2e.ts` from inside `e2e/`. Required flags: `--platform <ios|android|both>` and `--spec <name>`. Everything else is documented in `--help`.

Non-obvious flag semantics:

- **`--dry-run`** first whenever changing platform/devices/spec — it prints the matched targets and per-device WDIO invocations without spending the build budget.
- **`--each-device` is required** to iterate over more than one device from `devices.json`. Passing `--devices a,b` alone does *not* imply `--each-device`; without it the runner picks the default device only.
- **Builds are sequential** (iOS first, then Android). Cold builds typically run ~10-15 min iOS + ~3-5 min Android per worktree.

## Step 4 — Report

Reports land in `e2e/reports/<timestamp>/`:

- `summary.json` — overall pass/fail + per-device breakdown.
- `junit-results.xml` — merged JUnit across devices.
- `<device-id>/[<model-id>/]` subdirectories — per-run JUnit + `screenshots/failure-*.png`.

For each failure, open the per-device subdirectory and look at the failure screenshot and the per-device JUnit before drilling into the spec.

## Failure-mode lookup

| Symptom | Likely cause |
|---|---|
| `WebDriverError: The application at '...app-release.apk' does not exist` | `e2e/devices.json` Android `appPath` points at the prod build instead of the e2e flavor. Fix the path; the build itself is fine. |
| iOS red box `No script URL provided. unsanitizedScriptURLString = (null)` | The installed app on the sim is a Debug build expecting Metro, not the Release `.app` from the build. Uninstall and reinstall from the new `.app`. |
| `no such element 'chat-input'` ~appReady seconds after session start (iOS) | First-paint is broken, or the install on the sim is from a different build than the `.app` on disk. Confirm install matches build before deeper investigation. |
| iOS `BUILD FAILED` with no error text above it | Bundler gems (specifically `xcpretty`) are missing in `ios/`. Install Bundler gems, then retry. |
| iOS build succeeds but the `.app` won't launch after a `Podfile.lock` change | Pods are stale. Re-run `pod install`. |
| Android Appium connects but session creation hangs >60s | A stale Appium daemon is holding port 4723/4724. Free the ports and retry. |
| Run times shorter than the spec's workload would imply | iOS preserves install state, so a previously downloaded model short-circuits the download step. Compare timings only with a clean install. |

## Notes

- `devices.json` is per-worktree and gitignored — every fresh worktree starts from `devices.template.json`; re-verify the Android `appPath` after copying.
- The runner script is `scripts/run-e2e.ts`. There is no `run-e2e-pipeline.ts`.
- For real iOS devices use `yarn ios:build:ipa`, not `:e2e`.
