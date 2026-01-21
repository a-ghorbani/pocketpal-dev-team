# Quick Story: [TITLE]

## Metadata
- **Task ID**: [TASK_ID from orchestrator]
- **Source**: github | linear | prompt
- **Complexity**: quick
- **Native Changes**: YES | NO
- **Created**: [TIMESTAMP]
- **Status**: draft | pending_approval | approved | in_progress | complete

## Environment
- **Worktree**: `/Users/aghorbani/codes/pocketpal-dev-team/worktrees/[TASK_ID]`
- **Branch**: `feature/[TASK_ID]`
- **Base**: `main`

---

## Task Summary

**What**: [One sentence describing the change]

**Why**: [One sentence explaining the reason]

**Where**: [File path(s) affected]

---

## Change Details

### File: `[path/to/file.tsx]`

**Current** (line ~XX):
```typescript
// Current code
```

**Change to**:
```typescript
// New code
```

---

## Verification

```bash
cd "${WORKTREE_PATH}"
yarn lint
yarn typecheck
yarn test --findRelatedTests [path/to/file]
```

### Platform Verification (if NATIVE_CHANGES=YES)
- [ ] `pod install` succeeds
- [ ] iOS Release build succeeds
- [ ] Android Release build succeeds

---

## Acceptance Criteria

- [ ] [Primary criterion]
- [ ] All tests pass
- [ ] Lint/typecheck pass

---

## Commit Message

```
[type](scope): [description]
```

Example: `fix(l10n): correct typo in Japanese translation`

---

## Progress Tracking

| Step | Status | Notes |
|------|--------|-------|
| Story approved | PENDING | |
| Change implemented | PENDING | |
| Verified | PENDING | |
| PR created | PENDING | |

### Last Agent Handoff
```yaml
from_agent: planner
to_agent: implementer
timestamp: [ISO timestamp]
status: "Quick story created, awaiting approval"
completed:
  - Identified change location
  - Documented required change
next_steps:
  - Human approval
  - Implementer makes change
  - Verify and create PR
blockers: []
```

---

## Notes

[Any additional context for the implementer]
