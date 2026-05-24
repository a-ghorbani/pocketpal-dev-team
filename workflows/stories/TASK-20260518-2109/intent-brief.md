# Intent: Rework manual E2E workflow into a ref-targeted, Android-only, build-only artifact workflow

**Purpose**: confirm **what** the requester wants built, before any design or implementation begins.

---

## Metadata

- **Task ID**: TASK-20260518-2109
- **Source**: prompt
- **Worktree**: `./worktrees/TASK-20260518-2109`
- **Branch**: `feature/TASK-20260518-2109`
- **Complexity**: quick
- **Native Changes**: NO
- **Visual Confirmation**: NO
- **Created**: 2026-05-18
- **Status**: approved

---

## Request

Rework the manual E2E workflow into a ref-targeted, Android-only, build-only artifact workflow.

### Request
Convert `.github/workflows/e2e-tests.yml` in pocketpal-ai from its current AWS-Device-Farm-driven shape into a deliberately-triggered E2E APK build. E2E builds are only needed when a PR is merge-ready (or for a release), not on every push, so this stays manual.

### Required behavior
1. Trigger: `workflow_dispatch` only (it already is). Replace the existing `platform` choice input (android/ios/both) with a single required free-form input `ref` — a branch name or commit SHA. The checkout step must check out that `ref` (e.g. `actions/checkout` with `ref: ${{ inputs.ref }}`). This same input is how a release is targeted (pass a release tag/branch), so no `release.yml` change is needed.
2. Android only: delete the `build-ios` job.
3. Build only: delete the `test-android` and `test-ios` jobs entirely, including all AWS Device Farm steps, `aws-actions/configure-aws-credentials`, and every reference to AWS secrets/vars (`AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_REGION`, `AWS_DEVICE_FARM_PROJECT_ARN`, `AWS_DEVICE_POOL_ARN_*`) and the `dorny/test-reporter` publish steps. The resulting file must reference no AWS or real secrets at all.
4. Keep the existing Android E2E build steps exactly as the safety property requires: dummy `android/app/google-services.json` (including the `com.pocketpalai.e2e` client entry), dummy `.env`, dummy release keystore, and `E2E_BUILD=true ./gradlew assembleE2eReleaseE2e`. Do NOT introduce any real `secrets.*` / `vars.*` into this workflow — the no-real-secrets-in-binary property and the separate `com.pocketpalai.e2e` app id + dummy keystore must be preserved.
5. Upload `android/app/build/outputs/apk/e2e/releaseE2e/app-e2e-releaseE2e.apk` as a workflow artifact. Give it a clear name and a bounded `retention-days` (recommend 14–30) since this is a public repo and the artifact is world-readable.
6. Update the workflow `name:` so it no longer says "AWS Device Farm".

### Constraints
- App-repo CI change only: the only file touched is `.github/workflows/e2e-tests.yml`. No app source, no native, no package.json. NATIVE_CHANGES=NO.
- Must be done in a worktree off `repos/pocketpal-ai` `origin/main`; never edit the submodule.
- The E2E build must remain functionally the same gradle invocation that works today (`assembleE2eReleaseE2e` with `E2E_BUILD=true`); this task only restructures triggering/targeting and removes iOS + AWS, it does not change how the APK is built.

### Out of scope
- Wiring `tools/fetch-pr-apk.sh` / the `/run-pr-e2e` skill to consume this new workflow's E2E artifact. (Today fetch-pr-apk.sh pulls `android-release-apk` from `ci.yml` pull_request runs — the prod, bridge-stripped APK. Reconciling that with this new bridge-enabled E2E artifact is a deliberate, separate follow-up task.)
- Any change to `ci.yml`, `release.yml`, or iOS E2E builds.

### Acceptance criteria
- `e2e-tests.yml` is `workflow_dispatch`-only, has a required `ref` input, and checks out that ref.
- Only an Android E2E APK build job remains; no iOS job, no AWS/test jobs, no AWS or real-secret references anywhere in the file.
- The E2E APK is uploaded as a workflow artifact with a bounded retention period.
- Workflow name no longer references AWS Device Farm.
- YAML is valid.

### Context / safety rationale (already analyzed by the requester — these are settled, not open questions)
- CI/E2E builds use dummy config only; real secrets live only in `release.yml`. Verified.
- `ci.yml` already publicly uploads `android-release-apk`, so public workflow artifacts are an existing, accepted precedent.
- The E2E flavor (`applicationId com.pocketpalai.e2e`, buildType `releaseE2e`, `E2E_BUILD=true`) intentionally ships the automation bridge; that is correct for a test artifact and is why it must stay a workflow artifact (not a public GitHub Release asset) and must never be built with real secrets.
- Decisions already made with the human (do not re-ask): manual trigger only (not per-PR auto); target via free-form ref input; Android only; build-only with AWS dropped entirely; PR-and-release both covered by the ref input (no release.yml change); consumer wiring of fetch-pr-apk.sh is explicitly out of scope.

---

## Clarifications

none — request was unambiguous and self-contained; all decisions explicitly settled by the requester.
