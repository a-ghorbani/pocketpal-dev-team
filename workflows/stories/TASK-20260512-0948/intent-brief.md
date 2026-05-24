# Intent: Upgrade llama.rn from 0.12.0-rc.9 to 0.12.0 stable

## Metadata

- **Task ID**: TASK-20260512-0948
- **Source**: prompt (routine native dependency bump)
- **Worktree**: `./worktrees/TASK-20260512-0948`
- **Branch**: `feature/TASK-20260512-0948`
- **Complexity**: quick
- **Native Changes**: YES
- **Visual Confirmation**: NO
- **Created**: 2026-05-12
- **Status**: approved

---

## Request

Upgrade llama.rn from 0.12.0-rc.9 to 0.12.0 (latest stable release).

This is a routine native dependency bump — same shape as prior llama.rn upgrades:
- PR #689 (TASK-20260414-llama-rc8): rc.5 → rc.8
- PR #664 (TASK-20260404-1551): rc.2 → rc.3
- PR #608 (TASK-20260304-0808): 0.11.0 → 0.11.3

Expected file changes (only 3):
- `package.json` (version bump)
- `yarn.lock`
- `ios/Podfile.lock`

NATIVE_CHANGES=YES — requires pod install + iOS build + Android build verification before ready.

Recommend E2E smoke spec (`e2e/specs/quick-smoke.spec.ts`) verification after build per established pattern for llama.rn upgrades.

---

## Clarifications

none — request matches an established, repeatable pattern (rc → rc and rc → stable bumps for the same dependency). No ambiguity.
