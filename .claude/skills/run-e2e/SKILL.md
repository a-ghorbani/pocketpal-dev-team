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

2. **Platform** (optional): `ios`, `android`, or `both` (default: `both`)

3. **Devices** (optional): `all`, `virtual-only`, `real-only`, or comma-separated device IDs (default: `all`)

4. **Spec** (optional): `quick-smoke`, `load-stress`, or `all` (default: `quick-smoke`)

5. **Skip build** (optional): If user says "skip build" or "no build" → `--skip-build`

## Step 1: Checkout the Source Code

Navigate to the PocketPal repo and checkout the requested source:

```bash
cd ./repos/pocketpal-ai
```

**For a PR:**
```bash
gh pr checkout [number]
```

**For a branch:**
```bash
git fetch origin
git checkout [branch-name]
git pull origin [branch-name]
```

**For main:**
```bash
git checkout main
git pull origin main
```

After checkout, confirm what was checked out:
```bash
git log --oneline -1
git branch --show-current
```

## Step 2: Install Dependencies

```bash
cd ./repos/pocketpal-ai
yarn install
cd e2e && yarn install
```

## Step 3: Run the Pipeline

From the `e2e/` directory, run the pipeline with the parsed flags:

```bash
cd ./repos/pocketpal-ai/e2e
npx ts-node scripts/run-e2e-pipeline.ts \
  --platform [ios|android|both] \
  --devices [all|virtual-only|real-only|device-ids] \
  --spec [quick-smoke|load-stress|all] \
  [--skip-build]
```

**IMPORTANT**: The pipeline will:
- Build the app (unless `--skip-build`)
- Run tests sequentially on each enabled device from `e2e/devices.json`
- Generate reports in a timestamped directory under `e2e/reports/`

This can take a long time (10-30+ minutes depending on builds and device count).

## Step 4: Report Results

After the pipeline completes, read the summary:

```bash
# Find the latest report directory
ls -td ./repos/pocketpal-ai/e2e/reports/*/ | head -1
```

Read the `summary.json` from that directory and present:
- Overall pass/fail status
- Per-device results (device name, platform, type, pass/fail, duration)
- Total duration
- If any failures: read the JUnit XML or screenshots for details

## Examples

```
/run-e2e PR #567
/run-e2e #567 ios only
/run-e2e main android virtual-only
/run-e2e feature/my-branch both skip build
/run-e2e 567 load-stress real-only
```

## Error Handling

- If `devices.json` is missing: Tell the user to copy `devices.template.json` to `devices.json` and configure it
- If build fails: Report the build error and suggest `--skip-build` if a previous build exists
- If a device test fails: Continue to next device (pipeline handles this), report all results at the end
- If checkout fails: Report the error (PR not found, branch doesn't exist, etc.)

## Notes

- The pipeline does NOT do git checkout — this skill handles checkout separately to avoid self-modification issues
- `devices.json` is machine-specific and gitignored — each test laptop has its own
- Use `--dry-run` on the pipeline to preview what would run without actually executing
