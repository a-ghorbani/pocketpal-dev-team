---
name: run-e2e
description: Run E2E tests for a PR, branch, or main across multiple devices on the test laptop.
user-invocable: true
argument-hint: "[PR #number | branch-name | main] [options]"
---

# Run E2E Tests

You are running E2E tests for PocketPal AI on the local test machine.

## Input

Request: $ARGUMENTS

## Parse Input

Extract the following from the user's request:

1. **Source** (required): What code to test
   - `PR #567` or `#567` or `567` → PR number
   - `feature/xyz` or any branch name → branch
   - `main` → main branch (default if not specified)

2. **Platform** (optional): `ios`, `android`, or `both` (default: `ios`)

3. **Devices** (optional): `all`, `virtual-only`, `real-only`, `connected`, or comma-separated device IDs (default: `virtual-only`)

4. **Spec** (optional): `quick-smoke`, `load-stress`, `diagnostic`, `language`, or `all` (default: `quick-smoke`)

5. **Skip build** (optional): If user says "skip build" or "no build" → `--skip-build`

6. **Other flags** (optional): Parse any additional flags the user mentions:
   - "each model" or "per model" → `--each-model`
   - "each device" or "per device" → `--each-device`
   - "all models" → `--all-models`
   - "dry run" → `--dry-run`
   - specific models → `--models model1,model2`

## Step 1: Kill Stale Appium Processes

Appium processes from previous runs can hold port 4723. Always clean up first:

```bash
lsof -ti:4723 | xargs kill -9 2>/dev/null || true
```

## Step 2: Determine the Test Directory

The E2E tests can run from two locations depending on context:

### Option A: Active Worktree (preferred when working on a task)

If there is an active worktree for the current task (e.g., `worktrees/TASK-xxx`), AND the requested source matches the worktree's branch, run tests directly from the worktree. This avoids touching the shared `repos/pocketpal-ai` submodule.

**How to detect**: Check if a worktree exists for the current task:

```bash
# Look for active worktrees
ls ./worktrees/TASK-*/package.json 2>/dev/null
```

**When to use the worktree**:

- The user invokes `/run-e2e` without specifying a source (implicit: test current work)
- The user specifies a branch that matches the worktree's branch (e.g., `feature/TASK-xxx`)
- The user is in the middle of a task workflow (orchestrator → planner → implementer → **E2E**)

If using the worktree:

```bash
TEST_DIR=./worktrees/TASK-xxx
cd "${TEST_DIR}"
git log --oneline -1
git branch --show-current
```

Skip to Step 3 (no checkout needed — the code is already there).

### Option B: Dedicated E2E Worktree (for independent/standalone runs)

Create a dedicated E2E worktree when testing code that is not already in an active task worktree:

- `main` branch
- A PR number
- A branch with no corresponding worktree

Never checkout, build, or test directly inside `repos/pocketpal-ai/`.

**For a PR:**

```bash
PR=[number]
cd ./repos/pocketpal-ai
PR_BRANCH=$(gh pr view "$PR" --json headRefName --jq '.headRefName')
git fetch origin "$PR_BRANCH"
cd - >/dev/null
./tools/create-worktree.sh "PR-${PR}-e2e" --detach --ref "origin/$PR_BRANCH"
TEST_DIR="./worktrees/PR-${PR}-e2e"
```

**For a branch:**

```bash
BRANCH=[branch-name]
SAFE_NAME=$(printf '%s' "$BRANCH" | tr '/ ' '--')
cd ./repos/pocketpal-ai
git fetch origin "$BRANCH"
cd - >/dev/null
./tools/create-worktree.sh "E2E-${SAFE_NAME}" --detach --ref "origin/$BRANCH"
TEST_DIR="./worktrees/E2E-${SAFE_NAME}"
```

If a matching worktree already exists, reuse it:

```bash
WORKTREE=$(git -C ./repos/pocketpal-ai worktree list | grep "[branch-name]" | awk '{print $1}')
TEST_DIR="${WORKTREE}"
cd "${TEST_DIR}"
```

**For main:**

```bash
./tools/create-worktree.sh E2E-main --detach --ref origin/main
TEST_DIR="./worktrees/E2E-main"
```

After creating or selecting the worktree, sync allowlisted config and confirm:

```bash
./tools/sync-worktree-config.sh "${TEST_DIR}"
cd "${TEST_DIR}"
git log --oneline -1
git branch --show-current || echo "(detached HEAD)"
```

## Step 3: Install Dependencies

```bash
cd "${TEST_DIR}"
yarn install
cd e2e && yarn install
```

## Step 4: Run the E2E Test Runner

From the `e2e/` directory, run with the parsed flags:

```bash
cd "${TEST_DIR}/e2e"
npx ts-node scripts/run-e2e.ts \
  --platform [ios|android|both] \
  --spec [quick-smoke|load-stress|diagnostic|language|all] \
  [--devices all|virtual-only|real-only|connected|device-ids] \
  [--each-device] \
  [--each-model] \
  [--models model1,model2] \
  [--all-models] \
  [--skip-build] \
  [--dry-run]
```

### Available Flags

| Flag | Values | Default | Description |
| --- | --- | --- | --- |
| `--platform` | `ios`, `android`, `both` | _(required)_ | Which platform(s) to test |
| `--spec` | `quick-smoke`, `load-stress`, `diagnostic`, `language`, `all` | `quick-smoke` | Which test spec to run |
| `--models` | comma-separated model IDs | _(all)_ | Specific model(s) to test |
| `--each-model` | _(flag)_ | off | Iterate spec once per model (isolated process) |
| `--all-models` | _(flag)_ | off | Include crash-repro models in the pool |
| `--devices` | `all`, `virtual-only`, `real-only`, `connected`, or IDs | `all` | Device filter (implies `--each-device`) |
| `--each-device` | _(flag)_ | off | Iterate across devices from `devices.json` |
| `--mode` | `local`, `device-farm` | `local` | Execution mode |
| `--skip-build` | _(flag)_ | builds by default | Skip app builds, reuse existing |
| `--dry-run` | _(flag)_ | off | Print what would run without executing |
| `--report-dir` | path | auto-timestamped | Override report output directory |
| `--list-models` | _(flag)_ | off | List all available models and exit |

**IMPORTANT**: The runner will:

- Build the app (unless `--skip-build`)
- Run tests on each matched device/model combination
- Generate reports in a timestamped directory under `e2e/reports/`

This can take a long time (10-30+ minutes depending on builds and device count).

## Step 5: Report Results

After the runner completes, read the summary:

```bash
# Find the latest report directory
ls -td "${TEST_DIR}/e2e/reports"/*/ | head -1
```

Read the `summary.json` from that directory and present:

- Overall pass/fail status
- Per-device/model results (device name, platform, pass/fail, duration)
- Total duration
- If any failures: read the JUnit XML or screenshots for details

## Examples

```
/run-e2e                              # test current worktree, smoke, virtual-only
/run-e2e language                     # test current worktree, language spec
/run-e2e PR #567
/run-e2e #567 ios
/run-e2e main android virtual-only
/run-e2e feature/my-branch skip build
/run-e2e 567 language
/run-e2e main ios each model
/run-e2e main ios each device virtual-only
/run-e2e main dry run
```

## Error Handling

- **Stale Appium on port 4723**: Kill it before running (Step 1 handles this)
- **Branch in worktree**: Use the worktree directly instead of detached HEAD in the submodule (Step 2 handles this)
- **`devices.json` missing**: Tell user to `cp devices.template.json devices.json` and configure it
- **App binary not found**: Need to build first — remove `--skip-build` or run `yarn ios:build:e2e` / `yarn android:build:e2e` manually
- **Build fails**: Report the build error and suggest `--skip-build` if a previous build exists
- **Device test fails**: Runner continues to next device, report all results at the end
- **Checkout fails**: Report the error (PR not found, branch doesn't exist, etc.)

## Notes

- **Prefer worktrees** when testing task branches — avoids touching the shared submodule
- The runner script is `scripts/run-e2e.ts` (NOT `run-e2e-pipeline.ts`)
- `devices.json` is machine-specific and gitignored — each test laptop has its own
- Use `--dry-run` to preview what would run without actually executing
- iOS simulator builds: `yarn ios:build:e2e` (outputs to `ios/build/Build/Products/Release-iphonesimulator/`)
- iOS real device builds: `yarn ios:build:ipa`
- Android builds: `cd android && ./gradlew assembleRelease`
