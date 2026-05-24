# Intent: Upgrade llama.rn to 0.12.1

**Purpose**: confirm **what** the requester wants built, before any design or implementation begins.

---

## Metadata

- **Task ID**: TASK-20260518-1555
- **Source**: prompt (direct)
- **Worktree**: `./worktrees/TASK-20260518-1555`
- **Branch**: `feature/TASK-20260518-1555`
- **Complexity**: quick
- **Native Changes**: YES
- **Visual Confirmation**: NO
- **Created**: 2026-05-18
- **Status**: approved

---

## Request

Upgrade llama.rn in PocketPal AI from 0.12.0-rc.9 to 0.12.1. Treat 0.12.1 as the latest published version as of 2026-05-18.

This is a native dependency change. Keep the implementation limited to the dependency bump plus any required lockfile, pod, or native-integration refresh needed to make the app build and run correctly. Do not introduce unrelated app changes.

### Acceptance criteria

1. `package.json` and lockfiles / worktree state are updated cleanly to llama.rn 0.12.1.
2. Any required iOS/Android native integration changes for the new llama.rn release are applied (e.g. Podfile.lock, prebuilt jniLibs, JSI binding changes).
3. Verification includes the required pipeline artefacts for the chosen complexity level, PLUS: `pod install`, an iOS build, an Android build, and the smallest sensible regression coverage for llama.rn initialization / chat formatting / structured-output behavior affected by the upstream delta.
4. Final output includes an itemized summary of llama.cpp changes between PocketPal's current baseline and the target version, derived from upstream llama.rn changes across 0.12.0-rc.9 → 0.12.1 (include the llama.cpp build/commit range if determinable).
5. If upstream 0.12.1 requires broader app changes or introduces blockers, STOP and report them explicitly instead of guessing.

### Constraints

- All work goes through the pocketpal-dev-team workflow in a dedicated worktree created from `repos/pocketpal-ai`.
- Never edit, build, commit, or switch branches inside `repos/pocketpal-ai/` directly.
- `NATIVE_CHANGES=YES` — native verification (pod install + iOS build + Android build) is mandatory before the work can be called ready.
- Do not assume any internal tracker / story context beyond this brief. Treat the current baseline as 0.12.0-rc.9 as stated here.
- If any required information is missing, stop with `NEEDS_INPUT:` and list the exact unanswered questions; do not guess or classify until answered.

### Baseline / version context

- Current llama.rn version in the brief's frame of reference: 0.12.0-rc.9
- Target: 0.12.1 (treat as latest published as of 2026-05-18)
- Prior llama.rn upgrade reference commits in this codebase: `0614148` (rc.4), `f91144d` (rc.3). Upgrades historically touch only `package.json`, `yarn.lock`, `ios/Podfile.lock`.
- E2E smoke test `e2e/specs/quick-smoke.spec.ts` is the established way to verify native dependency upgrades; E2E requires a separate build (`yarn ios:build:e2e`) and `cd e2e && yarn install`.

---

## Clarifications

The request frames the baseline as `0.12.0-rc.9`. The actual `origin/main` codebase baseline is already llama.rn **`0.12.0` stable** (PR #722, commit `d4130b4` — the rc.9 → 0.12.0 upgrade already merged). The brief explicitly anticipates this in its "Baseline / version context" (it cites prior merged upgrade commits and asks for the delta "across 0.12.0-rc.9 → 0.12.1"). The target — `0.12.1` — is unambiguous and confirmed published (2026-05-18). The effective upgrade is therefore `0.12.0 → 0.12.1`; the upstream-delta summary in acceptance criterion 4 still spans the full requested range (0.12.0-rc.9 → 0.12.1). This is a reconciliation note, not an open question — no input required.

- none
