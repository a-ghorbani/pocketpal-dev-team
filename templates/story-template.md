# Story: [ISSUE_TITLE]

## Metadata
- **Task ID**: TASK-[YYYYMMDD]-[HHMM]
- **Issue**: #[ISSUE_ID] (if from GitHub)
- **Source**: github | linear | prompt
- **Complexity**: quick | standard | complex
- **Native Changes**: YES | NO
- **Created**: [TIMESTAMP]
- **Status**: draft | pending_approval | approved | in_progress | complete

## Environment
- **Worktree**: `/Users/aghorbani/codes/pocketpal-dev-team/worktrees/TASK-[id]`
- **Branch**: `feature/TASK-[id]`
- **Base**: `main`

---

## Progress Tracking

### Current Phase
`[ ] Planning → [ ] Approved → [ ] Implementing → [ ] Testing → [ ] Reviewing → [ ] PR Created`

### Checkpoints (Updated by Agents)

| Checkpoint | Status | Agent | Commit | Notes |
|------------|--------|-------|--------|-------|
| Worktree created | DONE | orchestrator | - | |
| Story approved | PENDING | human | - | |
| Step 1 complete | PENDING | implementer | - | |
| Step 2 complete | PENDING | implementer | - | |
| Tests written | PENDING | tester | - | |
| Review passed | PENDING | reviewer | - | |
| PR created | PENDING | reviewer | - | |

### Last Agent Handoff
```yaml
# Updated by each agent before passing to next
from_agent: orchestrator
to_agent: planner
timestamp: [ISO timestamp]
status: "Story created, awaiting approval"
completed:
  - Created worktree at worktrees/TASK-xxx
  - Analyzed requirements
  - Classified as standard complexity
next_steps:
  - Human review and approve story
  - Then route to implementer
blockers: []
context_for_next_agent: |
  This is a native change (llama.rn upgrade).
  NATIVE_CHANGES=YES - builds required.
  See package.json for current version.
```

---

## Context (For Recovery After Context Reset)

> **If you're an agent resuming work on this story:**
> 1. Read the "Progress Tracking" section above
> 2. Check `git log` in the worktree for commits
> 3. Read the "Last Agent Handoff" section
> 4. Continue from the next incomplete checkpoint

### Background
[Why this change is needed - business or user context]

### Current State
[How the relevant parts of the system work now]
- File: `src/path/to/file.tsx` - [current behavior]
- File: `src/path/to/other.ts` - [current behavior]

### Target State
[How it should work after this change]

---

## Requirements

### Functional
1. [MUST] [Requirement 1]
2. [MUST] [Requirement 2]
3. [SHOULD] [Nice-to-have requirement]

### Non-Functional
- Performance: [constraints if any]
- Compatibility: [platform considerations]
- Security: [security requirements if any]

### Platform Verification (if NATIVE_CHANGES=YES)
- [ ] `pod install` succeeds
- [ ] iOS Release build succeeds
- [ ] Android Release build succeeds
- [ ] `ios/Podfile.lock` changes committed

---

## Acceptance Criteria

- [ ] [Criterion 1 - testable statement]
- [ ] [Criterion 2 - testable statement]
- [ ] [Criterion 3 - testable statement]
- [ ] All tests pass
- [ ] Coverage >= 60%
- [ ] Platform builds succeed (if native)

---

## Affected Files

| File | Action | Reason | Status |
|------|--------|--------|--------|
| `src/components/Foo.tsx` | MODIFY | [why] | PENDING |
| `src/store/BarStore.ts` | MODIFY | [why] | PENDING |
| `src/components/Foo.test.tsx` | CREATE | Unit tests | PENDING |
| `src/types/foo.ts` | MODIFY | [why] | PENDING |

---

## Implementation Plan

### Step 1: [First Logical Change]
**Files**: `src/path/to/file.tsx`
**Status**: `PENDING | IN_PROGRESS | DONE`
**Commit**: [commit hash when done]

**Change**:
- [ ] [Specific sub-task]
- [ ] [Specific sub-task]

**Pattern Reference**: See `src/similar/Example.tsx:42-67`

**Code Guidance**:
```typescript
// Example of the pattern to follow
```

**Verification**:
```bash
cd "${WORKTREE_PATH}"
yarn lint
yarn typecheck
yarn test --findRelatedTests src/path/to/file.tsx
```

### Step 2: [Second Logical Change]
**Files**: `src/path/to/other.ts`
**Status**: `PENDING | IN_PROGRESS | DONE`
**Commit**: [commit hash when done]

**Change**:
- [ ] [Specific sub-task]

**Pattern Reference**: See `src/store/ExampleStore.ts`

### Step 3: [Update Tests]
**Files**: `src/components/Foo.test.tsx`
**Status**: `PENDING | IN_PROGRESS | DONE`
**Commit**: [commit hash when done]

**Change**:
- [ ] Add test for [scenario 1]
- [ ] Add test for [scenario 2]

### Step 4: Platform Verification (if NATIVE_CHANGES=YES)
**Status**: `PENDING | IN_PROGRESS | DONE`
**Commit**: [commit hash when done]

**Change**:
- [ ] Run `cd ios && pod install && cd ..`
- [ ] Commit Podfile.lock changes
- [ ] Run `yarn ios --configuration Release`
- [ ] Run `yarn android --variant=release`

---

## Test Requirements

### Unit Tests
| Test Case | File | Priority | Status |
|-----------|------|----------|--------|
| [Test description] | `Foo.test.tsx` | MUST | PENDING |
| [Test description] | `Foo.test.tsx` | MUST | PENDING |
| [Edge case test] | `Foo.test.tsx` | SHOULD | PENDING |

### Integration Tests
| Test Case | File | Priority | Status |
|-----------|------|----------|--------|
| [Integration scenario] | `e2e/spec.ts` | SHOULD | PENDING |

### Manual Testing
- [ ] [Manual test step 1]
- [ ] [Manual test step 2]

---

## Coding Standards

### Testing Infrastructure (CRITICAL)
```
# Read these BEFORE writing tests:
${WORKTREE_PATH}/jest/setup.ts      # Global mocks
${WORKTREE_PATH}/jest/test-utils.tsx # Custom render
${WORKTREE_PATH}/__mocks__/stores/  # Mock stores

# DO NOT mock stores inline - they're globally mocked
# Use runInAction() for MobX state changes
# Import render from jest/test-utils, NOT @testing-library/react-native
```

### Patterns to Follow
- **State**: Use MobX `@observable`, `@action`, `@computed`
- **Components**: Functional + `observer()` HOC
- **Hooks**: Follow existing hooks in `/src/hooks/`
- **Types**: Strict TypeScript, avoid `any`

### Commit Format
```
[type](scope): brief description

- Detail about change
- Another detail

Story: TASK-[ID]
```

### Naming Conventions
- Components: PascalCase (`MyComponent.tsx`)
- Hooks: camelCase with `use` prefix (`useMyHook.ts`)
- Stores: PascalCase with Store suffix (`MyStore.ts`)
- Utils: camelCase (`myUtil.ts`)

---

## Reference Code

### Pattern Example: [Pattern Name]
**File**: `src/path/to/example.tsx`
**Lines**: 42-67
```typescript
// Paste relevant code snippet that shows the pattern
```

### Pattern Example: [Another Pattern]
**File**: `src/store/ExampleStore.ts`
```typescript
// Paste relevant code snippet
```

---

## Dependencies

### Blocked By
- [ ] [Other issue/story if any]

### Blocks
- [ ] [Issues that depend on this]

---

## Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| [Risk description] | Low/Med/High | Low/Med/High | [How to mitigate] |

---

## Open Questions

### For Human
- [ ] [Question requiring human decision]

### Resolved
- [Question] -> [Answer/Decision]

---

## Agent Reports

### Planner Report
```
[Filled by planner after story creation]
```

### Implementation Report
```
[Filled by implementer after code complete]
```

### Test Report
```
[Filled by tester after tests written]
```

### Review Report
```
[Filled by reviewer after review]
```

---

## Changelog

| Date | Agent/Human | Change |
|------|-------------|--------|
| [DATE] | orchestrator | Created worktree and task |
| [DATE] | planner | Initial story draft |
| [DATE] | human | Approved with changes |
| [DATE] | implementer | Completed Step 1 |
| [DATE] | implementer | Completed Step 2 |
| [DATE] | tester | Tests written |
| [DATE] | reviewer | Approved, PR created |
