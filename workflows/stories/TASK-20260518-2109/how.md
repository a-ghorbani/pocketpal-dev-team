# Implementation Plan: Rework e2e-tests.yml into a ref-targeted, Android-only, build-only artifact workflow

**Purpose**: an executable worklist that lands the request specified in `intent-brief.md`. This is a **quick** task — there is no `what.md`; the intent brief is the design source of truth. The hard safety property (no `secrets.*` / `vars.*` / AWS references; preserve `com.pocketpalai.e2e` client + dummy keystore + `E2E_BUILD=true ./gradlew assembleE2eReleaseE2e` exactly) is non-negotiable and is enumerated in intent-brief §"Required behavior" 3–4 and §"Context / safety rationale".

This file lives at `workflows/stories/TASK-20260518-2109/how.md`.

---

## Metadata

- **Task ID**: TASK-20260518-2109
- **Worktree**: `./worktrees/TASK-20260518-2109`
- **Branch**: `feature/TASK-20260518-2109`
- **Native Changes**: NO
- **Visual Confirmation**: NO
- **Intent Brief**: `./workflows/stories/TASK-20260518-2109/intent-brief.md`
- **WHAT**: none (quick task)
- **Architecture doc(s) being updated**: none — no `context/architecture/*.md` doc covers GitHub Actions CI; the library covers app-runtime flows only. No architecture-doc update step required for this quick task.
- **Status**: Merged in #729 (`65100d0`, squash) on 2026-05-19. Follow-up ref-input removal merged in #731 (`d1f492a`) on 2026-05-19.

---

## Progress Tracking

| Step | Status | Commit | Notes |
| --- | --- | --- | --- |
| Step 1 | DONE | 946cbef | Rename workflow + replace dispatch input |
| Step 2 | DONE | 946cbef | Delete build-ios, test-android, test-ios jobs |
| Step 3 | DONE | 946cbef | Wire build-android to ref input + tidy artifact upload |
| Step 4 | DONE | 946cbef | Validate YAML + safety grep — all checks PASS |

---

## Affected Files

| Path | Change kind | Intent ref |
| --- | --- | --- |
| `.github/workflows/e2e-tests.yml` | edit (rename, input swap, job deletions, checkout ref, artifact tidy) | §Required behavior 1–6 |

Only this one file is touched. No app source, no native, no `package.json` (intent §Constraints).

---

## Implementation Steps

> All paths are relative to the worktree root `./worktrees/TASK-20260518-2109`. The target file is `.github/workflows/e2e-tests.yml`. Note `repos/pocketpal-ai/` is read-only — never edit the submodule.

### Step 1: Rename workflow and replace the `platform` choice input with a required `ref` input

**Implements**: intent §Required behavior 1 and 6.

**Files**:

- `.github/workflows/e2e-tests.yml` — lines 1–19 (header + `on:` block)

**Approach**:

- Change `name:` (line 1) from `E2E Tests (AWS Device Farm)` to a name with no AWS/Device-Farm reference, e.g. `E2E Android Build (manual)`. Exact wording is free choice as long as it does not say "AWS" or "Device Farm" (intent §Required behavior 6).
- Replace the entire `workflow_dispatch.inputs.platform` choice block (lines 6–15) with a single required free-form input named `ref`: `description` naming it a branch name or commit SHA, `required: true`, `type: string`, no `default`. Keep `workflow_dispatch:` as the only trigger; leave the commented-out `push:` block (lines 17–19) as-is or remove it — both acceptable; prefer removing the now-misleading "platform selection" comment on line 4.

**Verification**:

- After Step 4, `inputs.ref` exists and `inputs.platform` is gone (grep below).

### Step 2: Delete the `build-ios`, `test-android`, and `test-ios` jobs entirely

**Implements**: intent §Required behavior 2 and 3.

**Files**:

- `.github/workflows/e2e-tests.yml` — delete `build-ios` (current lines 127–235), `test-android` (current lines 237–291), `test-ios` (current lines 293–348)

**Approach**:

- Remove all three job blocks in full. This deletes every AWS step (`aws-actions/configure-aws-credentials@v4`), every `secrets.AWS_*` / `vars.AWS_*` reference, every `dorny/test-reporter@v1` publish step, the iOS build/IPA steps, and the `download-artifact` test jobs.
- After deletion, `jobs:` contains exactly one job: `build-android`.
- Do NOT delete or alter any step inside `build-android` in this step.

**Verification**:

- After Step 4, the file contains no `aws`, `AWS_`, `secrets.`, `vars.`, `dorny`, `build-ios`, `test-android`, `test-ios`, `xcodebuild`, or `pod install` tokens (grep below).

### Step 3: Wire `build-android` to the `ref` input and tidy the artifact upload

**Implements**: intent §Required behavior 1, 4, 5.

**Files**:

- `.github/workflows/e2e-tests.yml` — `build-android` job: the `if:` line (current line 27), the Checkout step (current lines 30–31), the Upload step (current lines 121–125)

**Approach**:

- Remove the `if:` condition on `build-android` (current line 27 — it referenced the deleted `platform` input). The job must run unconditionally on dispatch.
- In the Checkout step, add `with: { ref: ${{ inputs.ref }} }` to `actions/checkout@v4` so it checks out the dispatched ref (intent §Required behavior 1). Use `inputs.ref` (or `github.event.inputs.ref`, consistent with repo style — `ci.yml`/`release.yml` use `inputs.*` for dispatch inputs; prefer `inputs.ref`).
- In the Upload APK step, give the artifact a clear name (e.g. `e2e-android-apk`; must not collide with `ci.yml`'s `android-release-apk`) and add a bounded `retention-days` in the 14–30 range (recommend `30`, matching the retention already used elsewhere in this file's deleted blocks). Keep `path:` exactly `android/app/build/outputs/apk/e2e/releaseE2e/app-e2e-releaseE2e.apk` (unchanged).
- Do NOT touch the dummy `google-services.json` step (incl. the `com.pocketpalai.e2e` client entry, current lines 69–79), the dummy `.env` step, the dummy keystore step, or the `E2E_BUILD=true ./gradlew assembleE2eReleaseE2e` invocation. These are preserved byte-for-byte per the safety property (intent §Required behavior 4, §Context/safety rationale). The `APP_RELEASE_STORE_PASSWORD`/`APP_RELEASE_KEY_PASSWORD: dummy-ci-password` env stays as literal dummy strings — not secrets.

**Verification**:

- After Step 4, `build-android` has no `if:`, checkout uses `ref: ${{ inputs.ref }}`, the upload step has a bounded `retention-days`, and the `com.pocketpalai.e2e` + `E2E_BUILD=true ./gradlew assembleE2eReleaseE2e` text is unchanged (grep below).

### Step 4: Validate YAML and run the safety grep

**Implements**: intent §Acceptance criteria (YAML valid; no AWS/real-secret references) and §Context/safety rationale.

**Files**: none (verification only)

**Approach** — run from the worktree root:

```bash
cd "./worktrees/TASK-20260518-2109"
F=.github/workflows/e2e-tests.yml

# 1. YAML is valid
python3 -c "import yaml,sys; yaml.safe_load(open('$F')); print('YAML OK')"

# 2. No AWS / real-secret / removed-job references anywhere (must print nothing)
grep -nEi 'secrets\.|vars\.|aws|device.?farm|dorny|build-ios|test-android|test-ios|xcodebuild|pod install|platform' "$F" && echo "SAFETY FAIL" || echo "SAFETY OK"

# 3. Required structure present (each must print a line)
grep -n 'inputs:' "$F"
grep -nE '^\s+ref:' "$F"          # the new dispatch input
grep -n 'ref: \${{ inputs.ref }}' "$F"   # checkout uses it
grep -n 'com.pocketpalai.e2e' "$F"       # safety: e2e client entry preserved
grep -n 'E2E_BUILD=true ./gradlew assembleE2eReleaseE2e' "$F"  # safety: build invocation preserved
grep -n 'retention-days:' "$F"           # bounded retention
grep -nc 'jobs:' "$F"; grep -nE '^\s{2}build-android:' "$F"  # exactly one job, build-android

# 4. Old input gone
grep -n 'platform' "$F" && echo "platform STILL PRESENT (FAIL)" || echo "platform removed OK"
```

**Verification**:

- Check 1 prints `YAML OK`.
- Check 2 prints `SAFETY OK` (no matches for AWS / secrets / vars / removed jobs / `platform`).
- Check 3: all five `grep -n` lines return a match (input, checkout-ref, e2e client, build invocation, retention).
- The file defines exactly one job, `build-android`.

This is a single logical change; Steps 1–3 may be committed as one commit. Step 4 is the pre-commit gate.

---

## Testable-Contract Coverage

This is a quick task (no WHAT). The user-visible outcomes implied by `intent-brief.md` §Acceptance criteria, mapped to verification:

| Contract item (intent §Acceptance criteria) | Verified by |
| --- | --- |
| `workflow_dispatch`-only with a required `ref` input | Step 4 check 3 (`inputs:` + `ref:` input present); manual read confirms `required: true`, no other trigger |
| Checkout uses that ref | Step 4 check 3 (`ref: ${{ inputs.ref }}` on checkout) |
| Only an Android E2E APK build job remains | Step 4 check 3 (exactly one `build-android` job) + check 2 (no `build-ios`/`test-android`/`test-ios`) |
| No AWS or real-secret references anywhere | Step 4 check 2 (`SAFETY OK`: no `secrets.`/`vars.`/`aws`/`dorny`) |
| Safety: `com.pocketpalai.e2e` + dummy keystore + `E2E_BUILD=true` gradle invocation preserved | Step 4 check 3 (`com.pocketpalai.e2e`, `E2E_BUILD=true ./gradlew assembleE2eReleaseE2e` still present); diff review confirms keystore step unchanged |
| APK uploaded as artifact with bounded retention | Step 4 check 3 (`retention-days:` present, value in 14–30) |
| Workflow name no longer references AWS Device Farm | Step 4 check 2 (no `aws`/`device.?farm` match, which includes line 1 `name:`) |
| YAML valid | Step 4 check 1 (`YAML OK`) |

No unit/integration tests apply (CI workflow file, not app code). Verification is the static YAML parse + safety grep above. A live `workflow_dispatch` run is out of scope for this task (it requires the change to be on a branch GitHub can dispatch from); the gradle invocation itself is unchanged from the working baseline per intent §Constraints, so build behavior is preserved by construction.

---

## Native Verification

N/A — NATIVE_CHANGES=NO. No `package.json`, `ios/`, `android/` source, Podfile, or build.gradle changes (only a CI YAML file).

---

## Visual Confirmation

N/A — Visual Confirmation=NO.

---

## Deferred Items

Explicitly out of scope per intent §Out of scope — these do NOT land in this PR:

- Wiring `tools/fetch-pr-apk.sh` / the `/run-pr-e2e` skill to consume the new E2E artifact (separate, deliberate follow-up — the new artifact is bridge-enabled, distinct from `ci.yml`'s bridge-stripped `android-release-apk`).
- Any change to `ci.yml`, `release.yml`, or iOS E2E builds.

---

## What this plan is NOT

- not a design doc — the design/decisions live in `intent-brief.md` (all settled by the requester)
- not a justification — `intent-brief.md` is where the request lives
- not exhaustive — only the steps the implementer needs to restructure one CI file safely

---

## Post-merge notes

Landed across two pocketpal-ai PRs plus dev-team consumer wiring:

1. **PR #729 (`65100d0`, squash) — the planned rework.** Shipped Steps 1–4 as designed. Two non-blocking Copilot review items were adopted before merge in a follow-up commit on the PR branch: workflow-level `permissions: contents: read` (matches `ci.yml` precedent) and `fetch-depth: 0` on checkout.
2. **PR #731 (`d1f492a`) — follow-up: drop the redundant `workflow_dispatch` `ref` input.** Post-merge it was found the custom `ref` input duplicated GitHub's built-in "Use workflow from" selector for the normal flow and was inconsistent with the consumer (which matches dispatch runs by `head_branch`, the dispatched ref; `workflow_dispatch` input values are not exposed by the GitHub API). The input + `ref:` checkout line were removed; checkout now defaults to the dispatched ref. Bare-SHA targeting dropped; branch/tag selection still covers the merge-ready-PR and release-tag cases. (PR #730 was an earlier attempt at this same change, accidentally built on an orphaned base because #729 was squash-merged; closed and replaced by the clean #731.)
3. **Deferred item now done (dev-team repo, not pocketpal-ai).** The "wire `fetch-pr-apk.sh` / `run-pr-e2e`" follow-up listed under §Deferred Items was implemented as an opt-in `--e2e` mode: `tools/fetch-pr-apk.sh` (dev-team `c5765cc`), `tools/run-pr-e2e.sh` + `skills/run-pr-e2e/SKILL.md` passthrough (`bbab652`), stale-comment fix (`5296e92`). Prod `ci.yml` path remains the default; `--e2e` resolves the PR head branch and pulls the bridge-enabled `e2e-android-apk` from the newest `e2e-tests.yml` dispatch run for that branch. The `e2e-tests.yml` workflow must be manually dispatched for the PR branch first (it is `workflow_dispatch`-only).
