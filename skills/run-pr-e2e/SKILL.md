---
name: run-pr-e2e
description: Android E2E for a PR using the CI-built APK (no local build). Verifies the bit-identical artifact that would ship. Defers to /run-e2e for everything generic.
user-invocable: true
argument-hint: "<PR #number> [options]"
---

# Run PR E2E (CI APK)

This skill covers ONLY what's different from `/run-e2e`. For pre-flight (sim/emu booted, devices.json drift, port-4723 cleanup), reports, and failure-mode lookup — read `/run-e2e`. Do not duplicate.

## When to use this vs /run-e2e

| You want | Use |
|---|---|
| Test local changes you're iterating on | `/run-e2e` |
| Verify a PR with the EXACT artifact that would ship (no local build divergence) | `/run-pr-e2e` |
| Run iOS E2E for a PR | `/run-e2e` (iOS CI doesn't publish a reusable sim build — you have to build from source) |

This skill is **Android only**. iOS is out of scope at the CI-artifact level.

## What's different from /run-e2e

Four things. Everything else is the same and lives in `/run-e2e`.

### 1. Where the APK comes from

- **Default (prod APK from `ci.yml`).** `tools/run-pr-e2e.sh` calls `tools/fetch-pr-apk.sh`, which finds the newest completed `ci.yml` `pull_request` run for the PR, downloads `android-release-apk`, and drops it at `<worktree>/android/app/build/outputs/apk/release/app-release.apk`. This APK is **bridge-stripped** — specs that drive the `src/__automation__/` bridge (memory-snapshot, bench-runner) silently no-op.
- **`--e2e` flag (bridge-enabled APK from `e2e-tests.yml`).** Required for bridge-driven specs. `e2e-tests.yml` is `workflow_dispatch`-only and matched by head branch — **someone must have dispatched it for this PR's branch first**, otherwise fetch fails with "no completed workflow_dispatch run found for branch".

### 2. Worktree contract

Always a **fresh `./worktrees/PR-<N>-e2e`** on detached `origin/<head-branch>` — the exact commit CI built. Rules:

- Never reuse an in-flight `PR-<N>` fix worktree (APK-vs-specs drift — the fix worktree may have uncommitted changes the CI APK doesn't know about).
- If `PR-<N>-e2e` already exists from a prior run, fast-forward it to current `origin/<branch>`; don't create a parallel one.
- `./tools/create-worktree.sh PR-<N>-e2e --detach --ref origin/<branch>` already syncs `e2e/devices.json`, `.env`, keystores. For an existing worktree refresh via `./tools/sync-worktree-config.sh "$WORKTREE"`.

### 3. Spec selection

Default is **every `*.spec.ts` minus `visual-capture`, `diagnostic`, `memory-profile`**:

- `visual-capture` — screenshot generation driven by story files, not a regression.
- `diagnostic` — device-state inspector, not a regression.
- `memory-profile` — has its own pipeline (`/memory-profile`); needs device-specific baselines to be meaningful.

Enumerate dynamically so new specs on the PR are picked up:

```bash
EXCLUDE='^(visual-capture|diagnostic|memory-profile)$'
SPECS=$(find "$WORKTREE/e2e/specs" -type f -name '*.spec.ts' \
  | sed -E 's#.*/##; s#\.spec\.ts$##' | grep -vE "$EXCLUDE" \
  | sort -u | paste -sd, -)
```

### 4. The entry point is `tools/run-pr-e2e.sh`, not the runner directly

It's a thin wrapper around `scripts/run-e2e.ts --skip-build`. It handles APK fetch + placement, then loops `--specs` invocations against the runner. Don't replicate its work by calling the runner directly — you'll re-download the APK or fight the wrapper.

## Run

From the dev-team repo root:

```bash
PR=<number>
PR_BRANCH=$(gh pr view "$PR" --repo a-ghorbani/pocketpal-ai --json headRefName -q .headRefName)

# Create or fast-forward the e2e worktree
cd ./repos/pocketpal-ai && git fetch origin "$PR_BRANCH" && cd -
if [ -d "./worktrees/PR-${PR}-e2e" ]; then
  git -C "./worktrees/PR-${PR}-e2e" reset --hard "origin/$PR_BRANCH"
  ./tools/sync-worktree-config.sh "./worktrees/PR-${PR}-e2e"
else
  ./tools/create-worktree.sh "PR-${PR}-e2e" --detach --ref "origin/$PR_BRANCH"
fi

WORKTREE="./worktrees/PR-${PR}-e2e"
cd "$WORKTREE" && yarn install && (cd e2e && yarn install) && cd -

# Pre-flight: see /run-e2e Step 1 (sim/emu booted, port 4723, devices.json appPath).

SPECS=$(find "$WORKTREE/e2e/specs" -type f -name '*.spec.ts' \
  | sed -E 's#.*/##; s#\.spec\.ts$##' \
  | grep -vE '^(visual-capture|diagnostic|memory-profile)$' \
  | sort -u | paste -sd, -)

POCKETPAL_REPO="$(realpath "$WORKTREE")" \
  bash ./tools/run-pr-e2e.sh "$PR" [--e2e] --specs "$SPECS" -- --devices connected
```

Add `--e2e` if any spec in the list drives the automation bridge (memory-snapshot / bench-runner / `AUTOMATION_BRIDGE`).

## Inputs that ONLY exist here (not in /run-e2e)

| Flag | Purpose |
|---|---|
| `--e2e` | Fetch bridge-enabled APK from `e2e-tests.yml` (manual dispatch required) instead of prod APK from `ci.yml` |
| `--no-fetch` | Skip APK download; reuse an already-installed APK on the device |
| `--specs a,b,c` | Comma-separated list (one wrapper invocation per spec, sequentially) |

Everything after `--` is passed verbatim to `scripts/run-e2e.ts` (devices filter, dry-run, etc.).

## PR-specific failure modes (everything else: see /run-e2e)

| Symptom | Fix |
|---|---|
| `no completed CI runs found for PR #N` | PR's `ci.yml` is still running or failed. `gh run watch` or pick another run. |
| `artifact 'android-release-apk' not found` | The Android build job failed in that run. `gh run view <id>`. |
| `(--e2e) no completed e2e-tests.yml workflow_dispatch run found for branch` | `e2e-tests.yml` was never dispatched for this PR's branch. Dispatch it (select the PR's head branch as the workflow ref), wait, then rerun. |
| `(--e2e) artifact 'e2e-android-apk' not found` | E2E build job failed in that dispatch. `gh run view <id>`. |

## Required env

- `GITHUB_TOKEN` or `GH_TOKEN` (for artifact download)
- `ANDROID_HOME` or `ANDROID_SDK_ROOT`
