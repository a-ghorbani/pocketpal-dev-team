---
name: run-pr-e2e
description: Run Android E2E tests for a PR using the CI-built APK, inside a dedicated worktree under the dev-team repo.
user-invocable: true
argument-hint: "<PR #number> [options]"
---

# Run PR E2E (CI APK)

Run Android E2E tests against the **CI-built APK** for a PocketPal AI PR, inside a dedicated worktree of the dev-team repo. iOS is out of scope (iOS CI doesn't publish a reusable simulator build — use `/run-e2e` for iOS).

## Input

Request: $ARGUMENTS

## Hard Rules

1. **Stay inside the dev-team repo.** All work happens under the current dev-team checkout (the repo containing this skill). Never use another standalone pocketpal-ai clone on the machine.
2. **Never modify `./repos/pocketpal-ai/` directly.** It's the shared read-only submodule. It's only used as the source for creating worktrees and for copying gitignored config (`e2e/devices.json`, `e2e/.env`, keystore, etc.).
3. **Always use a fresh `./worktrees/PR-<N>-e2e` worktree** on `origin/<branch>` — not an in-flight `PR-<N>` fix worktree. The CI APK was built from `origin/<branch>`, so the specs must match that commit to avoid APK-vs-specs drift.
4. If any pre-flight fails, STOP and report. Do not fall back silently to another checkout.

## Parse Input

From the user's request extract:

1. **PR number** (required): `#688`, `PR 688`, or `688`.
2. **Specs** (optional): **default = every `*.spec.ts` found in the worktree's `e2e/specs/**/`minus`visual-capture`, `diagnostic`, and `memory-profile`** (see enumeration below). This is "all E2E except visual-capture and diagnostic" — `memory-profile` is also dropped because it has its own pipeline (`/memory-profile`) and needs a device-specific model + baseline comparison to be meaningful.
   - User can override with an explicit list (e.g. "just quick-smoke") or add excluded specs back explicitly (e.g. "include memory-profile").
3. **Devices** (optional): `connected` (default), `virtual-only`, `real-only`, `all`, or comma-separated IDs from `devices.json`.
4. **Skip fetch** (optional): `--no-fetch` if user wants to reuse an already-installed APK.
5. **E2E APK** (optional): `--e2e` to fetch the bridge-**enabled** E2E build (`com.pocketpalai.e2e`) from the manual `e2e-tests.yml` workflow instead of the default bridge-**stripped** prod APK from `ci.yml`. Use this when the requested specs drive the automation bridge (memory-snapshot / bench-runner / `AUTOMATION_BRIDGE`). Prerequisite: someone must have already dispatched `e2e-tests.yml` with the PR's head branch — it is a manual workflow, not auto-built per PR.
6. **MIUI watcher** (optional): if a connected Xiaomi device is detected AND will be used, offer to run `tools/miui-install-watcher.sh` in background.

## Step 1 — Pre-flight

Run all commands from the dev-team repo root (the directory containing `./repos/pocketpal-ai/` and `./tools/run-pr-e2e.sh`). Use relative paths so this skill works on any machine.

```bash
# Confirm we're in the dev-team root — look for its fingerprints.
test -d ./repos/pocketpal-ai && test -x ./tools/run-pr-e2e.sh || {
  echo "Not in the dev-team repo root (no ./repos/pocketpal-ai or ./tools/run-pr-e2e.sh)"
  exit 1
}

# Token for CI artifact
test -n "${GITHUB_TOKEN:-${GH_TOKEN:-}}" || { echo "Need GITHUB_TOKEN / GH_TOKEN"; exit 1; }

# Android SDK must be configured by the user/machine
test -n "${ANDROID_HOME:-${ANDROID_SDK_ROOT:-}}" || {
  echo "Set ANDROID_HOME (or ANDROID_SDK_ROOT) to the Android SDK location for this machine"
  exit 1
}
export ANDROID_HOME="${ANDROID_HOME:-$ANDROID_SDK_ROOT}"

# Source devices.json exists in the submodule (auto-copied to worktree by hook)
test -f ./repos/pocketpal-ai/e2e/devices.json || {
  echo "Missing ./repos/pocketpal-ai/e2e/devices.json — configure it first for this machine"
  exit 1
}

# Free stale Appium
lsof -ti:4723 | xargs kill -9 2>/dev/null || true
```

### Device sanity check

Report what's plugged in vs what's enabled in `devices.json`:

```bash
adb start-server >/dev/null 2>&1
echo "--- connected ---"; adb devices | tail -n +2
echo "--- configured (enabled Android) ---"
jq -r '.devices[] | select(.platform=="android" and .enabled) | "\(.id)\t\(.udid)\t\(.name)"' \
  ./repos/pocketpal-ai/e2e/devices.json
```

If a connected serial has no matching `udid` in `devices.json`, tell the user and ask whether to:

- proceed with only the matching devices, or
- stop so they can add the new device to `repos/pocketpal-ai/e2e/devices.json` (they must edit it themselves — the submodule is guarded against Edit/Write from agents).

## Step 2 — Resolve PR branch

```bash
PR=<number>
PR_BRANCH=$(gh pr view "$PR" --repo a-ghorbani/pocketpal-ai --json headRefName -q .headRefName)
test -n "$PR_BRANCH" || { echo "PR #$PR not found"; exit 1; }
echo "PR #$PR → branch: $PR_BRANCH"
```

## Step 3 — Create/reuse the E2E worktree

Always use a dedicated `PR-<N>-e2e` worktree to avoid colliding with any in-flight `PR-<N>` fix worktree, and always check out `origin/<branch>` (the exact commit CI built).

```bash
WORKTREE="./worktrees/PR-${PR}-e2e"

if [ -d "$WORKTREE" ]; then
  # Fast-forward the existing e2e worktree to the current PR head
  cd "$WORKTREE"
  git fetch origin "$PR_BRANCH"
  git reset --hard "origin/$PR_BRANCH"
  cd - >/dev/null
else
  cd ./repos/pocketpal-ai
  git fetch origin "$PR_BRANCH"
  cd - >/dev/null
  # Detached HEAD on origin/<branch> — we never commit from the e2e worktree
  ./tools/create-worktree.sh "PR-${PR}-e2e" --detach --ref "origin/$PR_BRANCH"
fi
```

**Important:** `./tools/create-worktree.sh` already syncs the allowlisted `.env`, `e2e/.env`, `e2e/devices.json`, keystores, and related config from `repos/pocketpal-ai/` into the new worktree. If you reuse an existing worktree, refresh that allowlisted sync explicitly:

```bash
./tools/sync-worktree-config.sh "$WORKTREE"
```

Verify critical config is present:

```bash
test -f "$WORKTREE/e2e/devices.json" || {
  echo "devices.json not copied to worktree — hook may have failed"; exit 1
}
```

## Step 4 — Install worktree deps

```bash
cd "$WORKTREE"
test -d node_modules   || yarn install
test -d e2e/node_modules || (cd e2e && yarn install)
cd -
```

(The hook `block-commit-to-main.sh` is fine here — we're on a detached HEAD, not main.)

## Step 5 — (Optional) MIUI watcher

Only if a Xiaomi/MIUI device is going to be used:

```bash
bash ./tools/miui-install-watcher.sh <serial> &
WATCHER_PID=$!
trap 'kill $WATCHER_PID 2>/dev/null || true' EXIT
```

## Step 6 — Enumerate specs and run

Compute the default spec list dynamically from the worktree (so newly-added specs on the PR are picked up automatically):

```bash
EXCLUDE='^(visual-capture|diagnostic|memory-profile)$'
SPECS=$(
  find "$WORKTREE/e2e/specs" -type f -name '*.spec.ts' \
    | sed -E 's#.*/##; s#\.spec\.ts$##' \
    | grep -vE "$EXCLUDE" \
    | sort -u \
    | paste -sd, -
)
echo "Running specs: $SPECS"
```

The runner's `resolveSpecPath()` accepts bare basenames and checks both `e2e/specs/<name>.spec.ts` and `e2e/specs/features/<name>.spec.ts`, so the list doesn't need to encode directory structure.

Then invoke:

```bash
POCKETPAL_REPO="$(realpath "$WORKTREE")" \
  bash ./tools/run-pr-e2e.sh "$PR" \
  --specs "$SPECS" \
  -- \
  --devices connected
```

If the user requested `--e2e`, add it before `--specs`:

```bash
POCKETPAL_REPO="$(realpath "$WORKTREE")" \
  bash ./tools/run-pr-e2e.sh "$PR" \
  --e2e \
  --specs "$SPECS" \
  -- \
  --devices connected
```

If the user passed an explicit spec list or override, use that instead of the enumerated default.

What the script does:

1. `fetch-pr-apk.sh` — **default (prod)**: locates the newest completed `ci.yml` pull_request run for the PR, downloads `android-release-apk`, drops it at `$WORKTREE/android/app/build/outputs/apk/release/app-release.apk` (bridge-stripped). **`--e2e`**: resolves the PR's head branch, locates the newest completed `e2e-tests.yml` `workflow_dispatch` run for that branch, downloads `e2e-android-apk`, drops it at `$WORKTREE/android/app/build/outputs/apk/e2e/releaseE2e/app-e2e-releaseE2e.apk` (bridge-enabled, `com.pocketpalai.e2e`).
2. For each spec in `--specs`, runs `yarn e2e:android --skip-build --spec <name> <pass-through>`.
3. Continues through spec failures so you get full coverage; exits non-zero if any spec failed.

## Step 7 — Report

Reports are in `$WORKTREE/e2e/reports/<timestamp>/`:

```bash
ls -td "$WORKTREE/e2e/reports"/*/ | head -1
cat "<latest>/summary.json"  # if present
```

Summarize per-spec × per-device: pass/fail, duration, links to JUnit XML or screenshots for failures.

## Step 8 — Cleanup (don't by default)

Leave the worktree in place after the run so the user can inspect reports, screenshots, and app logs. Only remove it if the user explicitly asks:

```bash
./tools/remove-worktree.sh "PR-${PR}-e2e" --yes
```

## Error Handling

| Symptom | Fix |
| --- | --- |
| "no completed CI runs found for PR #N" | PR's CI still running/failed. `gh run watch` or pick another run. |
| "artifact 'android-release-apk' not found" | Android build job failed in that run. `gh run view <id>`. |
| (`--e2e`) "no completed e2e-tests.yml workflow_dispatch run found for branch" | `e2e-tests.yml` was never dispatched for this PR's branch (it is manual). Dispatch it with the PR branch selected as the workflow ref, wait for completion, then rerun. |
| (`--e2e`) "artifact 'e2e-android-apk' not found" | The E2E build job failed in that dispatch run. `gh run view <id>`. |
| `devices.json` not copied | Run `./tools/sync-worktree-config.sh "$WORKTREE"` and re-check. |
| Connected device isn't in `devices.json` | User updates `repos/pocketpal-ai/e2e/devices.json` themselves, then rerun `./tools/sync-worktree-config.sh "$WORKTREE"` or recreate the worktree. |
| MIUI device refuses install | Start `miui-install-watcher.sh` for that serial. |
| Port 4723 in use | Pre-flight kills it; if it came back, some other Appium is running. |

## Quick Example

```
User: /run-pr-e2e 688
```

Resolves to (run from the dev-team repo root):

```bash
PR=688
PR_BRANCH=$(gh pr view "$PR" --repo a-ghorbani/pocketpal-ai --json headRefName -q .headRefName)

cd ./repos/pocketpal-ai && git fetch origin "$PR_BRANCH" && cd -
./tools/create-worktree.sh "PR-${PR}-e2e" --detach --ref "origin/$PR_BRANCH"

# Helper script auto-syncs e2e/devices.json + allowlisted secrets into the worktree

cd "./worktrees/PR-${PR}-e2e" && yarn install && (cd e2e && yarn install) && cd -

WORKTREE="./worktrees/PR-${PR}-e2e"
SPECS=$(find "$WORKTREE/e2e/specs" -type f -name '*.spec.ts' \
  | sed -E 's#.*/##; s#\.spec\.ts$##' \
  | grep -vE '^(visual-capture|diagnostic|memory-profile)$' \
  | sort -u | paste -sd, -)

POCKETPAL_REPO="$(realpath "$WORKTREE")" \
  bash ./tools/run-pr-e2e.sh "$PR" --specs "$SPECS" -- --devices connected
```

## Notes

- `visual-capture` is screenshot generation driven by the story file — not a regression test. See `docs/workflows/visual-capture.md`.
- `diagnostic` is for device-state inspection, not regressions.
- `memory-profile` has its own pipeline (`/memory-profile`).
- `--e2e` fetches a **different app** (`com.pocketpalai.e2e`, bridge-enabled) from the manual `e2e-tests.yml` workflow — the prod `ci.yml` APK has the automation bridge DCE-stripped, so bridge-driven specs only work with `--e2e`. Because `e2e-tests.yml` is `workflow_dispatch`-only and matched by head branch, dispatch it for the PR branch *before* running this skill with `--e2e`.
- `devices.json` is machine-specific and gitignored inside pocketpal-ai. It lives in `repos/pocketpal-ai/e2e/devices.json` on this machine as the source of truth, and the post-worktree hook copies it into every new worktree.
