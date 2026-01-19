# Story: [ISSUE_TITLE]

## Metadata
- Issue: #[ISSUE_ID]
- Source: github | linear | prompt
- Complexity: quick | standard | complex
- Created: [TIMESTAMP]
- Status: draft | pending_approval | approved | in_progress | complete

---

## Context

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

---

## Acceptance Criteria

- [ ] [Criterion 1 - testable statement]
- [ ] [Criterion 2 - testable statement]
- [ ] [Criterion 3 - testable statement]

---

## Affected Files

| File | Action | Reason |
|------|--------|--------|
| `src/components/Foo.tsx` | MODIFY | [why] |
| `src/store/BarStore.ts` | MODIFY | [why] |
| `src/components/Foo.test.tsx` | CREATE | Unit tests |
| `src/types/foo.ts` | MODIFY | [why] |

---

## Implementation Plan

### Step 1: [First Logical Change]
**Files**: `src/path/to/file.tsx`
**Change**:
- [ ] [Specific sub-task]
- [ ] [Specific sub-task]

**Pattern Reference**: See `src/similar/Example.tsx:42-67`

**Code Guidance**:
```typescript
// Example of the pattern to follow
```

### Step 2: [Second Logical Change]
**Files**: `src/path/to/other.ts`
**Change**:
- [ ] [Specific sub-task]

**Pattern Reference**: See `src/store/ExampleStore.ts`

### Step 3: [Update Tests]
**Files**: `src/components/Foo.test.tsx`
**Change**:
- [ ] Add test for [scenario 1]
- [ ] Add test for [scenario 2]

---

## Test Requirements

### Unit Tests
| Test Case | File | Priority |
|-----------|------|----------|
| [Test description] | `Foo.test.tsx` | MUST |
| [Test description] | `Foo.test.tsx` | MUST |
| [Edge case test] | `Foo.test.tsx` | SHOULD |

### Integration Tests
| Test Case | File | Priority |
|-----------|------|----------|
| [Integration scenario] | `e2e/spec.ts` | SHOULD |

### Manual Testing
- [ ] [Manual test step 1]
- [ ] [Manual test step 2]

---

## Coding Standards

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

Story: ISSUE-[ID]
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

## Changelog

| Date | Author | Change |
|------|--------|--------|
| [DATE] | Planner | Initial draft |
| [DATE] | Human | Approved with changes |
| [DATE] | Implementer | Completed |
