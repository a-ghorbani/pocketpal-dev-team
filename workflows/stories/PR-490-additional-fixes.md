# Story: Fix Additional Issues in PR #490

## Metadata
- **Task ID**: PR-490-additional-fixes
- **Parent Issue**: PR-490-fix
- **Source**: manual_testing
- **Complexity**: standard
- **Native Changes**: NO
- **Created**: 2026-01-21
- **Status**: updated

## Environment
- **Worktree**: `/Users/aghorbani/codes/pocketpal-dev-team/worktrees/PR-490`
- **Branch**: `pr-490`
- **Base**: `main`

---

## Progress Tracking

### Current Phase
`[X] Planning → [X] Approved → [X] Implementing → [X] Testing → [X] Reviewing → [X] PR Updated`

### Checkpoints (Updated by Agents)

| Checkpoint | Status | Agent | Commit | Notes |
|------------|--------|-------|--------|-------|
| Worktree exists | DONE | orchestrator | - | Using same worktree as PR-490-fix |
| Story approved | DONE | human | - | Approved |
| Step 1 complete | DONE | implementer | d6e407b | Removed disabled prop and divider |
| Step 2 complete | DONE | implementer | 180e595 | Added test for model name editability |
| Step 3 complete | DONE | implementer | c88162a | Removed preset check in ModelStore |
| Step 4 complete | DONE | implementer | b6c9e1c | Removed preset check and unused import |
| Step 5 complete | DONE | implementer | 86fced1 | Updated test to expect preset renames |
| Tests written | DONE | implementer | - | All tests pass (107 ModelStore, 9 ModelSettingsSheet, 9 ModelSettings) |
| Review passed | PENDING | reviewer | - | |

### Last Agent Handoff
```yaml
from_agent: implementer
to_agent: reviewer
timestamp: 2026-01-21T21:30:00Z
status: "Implementation complete - all steps finished and tests passing"
completed:
  - Step 1: Removed disabled prop and divider (commit d6e407b) ✅
  - Step 2: Added test for model name editability (commit 180e595) ✅
  - Step 3: Removed preset check in ModelStore.updateModelName (commit c88162a) ✅
  - Step 4: Removed preset check in ModelSettingsSheet.handleSaveSettings (commit b6c9e1c) ✅
  - Step 5: Updated ModelStore test to expect preset renames (commit 86fced1) ✅
  - Verified all related tests pass: ModelStore (107), ModelSettingsSheet (9), ModelSettings (9)
next_steps:
  - Manual testing to verify preset models can be renamed and saved
  - Verify reset button still works for preset models
  - Ready for merge into PR #490
blockers:
  - None
context_for_next_agent: |
  All code changes complete and tested:
  1. ✅ UI now allows editing preset model names (Step 1-2)
  2. ✅ ModelStore.updateModelName now accepts preset models (Step 3)
  3. ✅ ModelSettingsSheet calls updateModelName for all models (Step 4)
  4. ✅ Tests updated to verify preset renames work (Step 5)

  Key changes:
  - Removed `model.origin !== ModelOrigin.PRESET` check from ModelStore.ts line 1476
  - Removed preset conditional from ModelSettingsSheet.tsx lines 55-58
  - Cleaned up unused ModelOrigin import in ModelSettingsSheet.tsx
  - Updated test "should update model name for preset model" in ModelStore.test.ts

  Manual testing needed to confirm:
  - Open preset model settings (e.g., Gemma)
  - Change name and save → should persist
  - Reset button → should restore original name
  - Reopen settings → custom name should still be there
```

---

## Context (For Recovery After Context Reset)

### Background
During manual testing of PR #490 (model rename feature), THREE issues were discovered:

1. **[FIXED] Preset model name input disabled**: Users could not change the name of preset models because the input was disabled. (Fixed in commit d6e407b)

2. **[FIXED] Visual issue - horizontal line**: Unwanted Divider under model name input. (Fixed in commit d6e407b)

3. **[NEW] Preset model names not saving**: Users CAN now edit preset model names in the UI, but when they click Save, nothing happens - the old name remains. This is the CRITICAL issue that must be fixed.

### Current State

**Issue 3 - ModelStore.ts line 1476** (CRITICAL):
```typescript
updateModelName = (modelId: string, newName: string) => {
  const model = this.models.find(m => m.id === modelId);
  if (model && model.origin !== ModelOrigin.PRESET) {  // ← BLOCKS preset saves
    runInAction(() => {
      model.name = newName;
    });
  }
};
```

**Issue 3 - ModelSettingsSheet.tsx line 56** (CRITICAL):
```typescript
const handleSaveSettings = () => {
  if (model) {
    // Only update model name if it's not a preset model
    if (model.origin !== ModelOrigin.PRESET) {  // ← BLOCKS preset saves
      modelStore.updateModelName(model.id, tempModelName);
    }
    modelStore.updateModelChatTemplate(model.id, tempChatTemplate);
    modelStore.updateModelStopWords(model.id, tempStopWords);
    onClose();
  }
};
```

**Test - ModelStore.test.ts line 197-212**:
```typescript
it('should not update model name for preset model', () => {
  // This test EXPECTS presets to NOT be renamed
  // Must be updated to expect presets CAN be renamed
});
```

### Target State

After all fixes:
1. ✅ Input is NOT disabled for preset models - users can type/edit the name (DONE)
2. ✅ Divider removed for cleaner UI (DONE)
3. **Preset model names CAN be saved** (NEW - must be implemented)
4. Reset button restores original preset name (already working via getOriginalModelName)

---

## Requirements

### Functional
1. [MUST] ✅ Remove `disabled={isPresetModel}` from model name TextInput (DONE)
2. [MUST] ✅ Remove unwanted Divider after model name section (DONE)
3. [MUST] **Remove `model.origin !== ModelOrigin.PRESET` check from ModelStore.updateModelName**
4. [MUST] **Remove preset conditional from ModelSettingsSheet.handleSaveSettings**
5. [MUST] **Update test to verify preset model names CAN be saved**
6. [MUST] Verify reset button still restores original name for presets

### Non-Functional
- UX: Preset models are fully renamable like local models
- Testing: Test coverage for preset model rename functionality
- Persistence: Changed preset names persist across app restarts

---

## Acceptance Criteria

- [X] Model name input is NOT disabled for preset models
- [X] Users can type in preset model name field
- [X] Divider after model name input is removed
- [ ] **Preset model names CAN be saved (save logic updated)**
- [ ] **ModelStore.updateModelName accepts preset models**
- [ ] **ModelSettingsSheet calls updateModelName for all models**
- [ ] **Test updated to verify preset names can be saved**
- [ ] Reset button still works for preset models
- [ ] All existing tests pass
- [ ] No regressions in model name functionality

---

## Affected Files

| File | Action | Reason | Status |
|------|--------|--------|--------|
| `src/screens/ModelsScreen/ModelSettings/ModelSettings.tsx` | MODIFY | Remove disabled prop and divider | ✅ DONE |
| `src/screens/ModelsScreen/ModelSettings/__tests__/ModelSettings.test.tsx` | MODIFY | Add test for preset model input | ✅ DONE |
| `src/store/ModelStore.ts` | MODIFY | Remove preset check in updateModelName | PENDING |
| `src/components/ModelSettingsSheet/ModelSettingsSheet.tsx` | MODIFY | Remove preset check in save handler | PENDING |
| `src/store/__tests__/ModelStore.test.ts` | MODIFY | Update test to verify preset renames work | PENDING |

---

## Implementation Plan

### Step 1: Fix Disabled Input and Remove Divider ✅
**Status**: `DONE` (commit d6e407b)

### Step 2: Add Test for Preset Model Input ✅
**Status**: `DONE` (commit 180e595)

### Step 3: Remove Preset Check in ModelStore
**Files**: `src/store/ModelStore.ts`
**Status**: `PENDING`
**Commit**: [commit hash when done]

**Change**:
- [ ] Line 1476: Remove `&& model.origin !== ModelOrigin.PRESET` from updateModelName

**Code Guidance**:
```typescript
// BEFORE (line 1474-1481):
updateModelName = (modelId: string, newName: string) => {
  const model = this.models.find(m => m.id === modelId);
  if (model && model.origin !== ModelOrigin.PRESET) {  // ← REMOVE THIS CHECK
    runInAction(() => {
      model.name = newName;
    });
  }
};

// AFTER:
updateModelName = (modelId: string, newName: string) => {
  const model = this.models.find(m => m.id === modelId);
  if (model) {  // ← Allow all models (preset and local)
    runInAction(() => {
      model.name = newName;
    });
  }
};
```

**Why**: The preset check prevents users from saving name changes to preset models. Since the reset button (via getOriginalModelName utility) allows users to restore the original name, there's no reason to block renaming presets.

**Pattern Reference**: See resetModelName method at line 1483-1499 which already supports both preset and local models.

**Verification**:
```bash
cd /Users/aghorbani/codes/pocketpal-dev-team/worktrees/PR-490
yarn typecheck
yarn lint
yarn test src/store/__tests__/ModelStore.test.ts
```

---

### Step 4: Remove Preset Check in ModelSettingsSheet
**Files**: `src/components/ModelSettingsSheet/ModelSettingsSheet.tsx`
**Status**: `PENDING`
**Commit**: [commit hash when done]

**Change**:
- [ ] Lines 55-58: Remove conditional that skips updateModelName for presets

**Code Guidance**:
```typescript
// BEFORE (lines 53-63):
const handleSaveSettings = () => {
  if (model) {
    // Only update model name if it's not a preset model
    if (model.origin !== ModelOrigin.PRESET) {  // ← REMOVE THIS CONDITIONAL
      modelStore.updateModelName(model.id, tempModelName);
    }
    modelStore.updateModelChatTemplate(model.id, tempChatTemplate);
    modelStore.updateModelStopWords(model.id, tempStopWords);
    onClose();
  }
};

// AFTER:
const handleSaveSettings = () => {
  if (model) {
    modelStore.updateModelName(model.id, tempModelName);  // ← Call for all models
    modelStore.updateModelChatTemplate(model.id, tempChatTemplate);
    modelStore.updateModelStopWords(model.id, tempStopWords);
    onClose();
  }
};
```

**Why**: The check in ModelStore.updateModelName already handled this (before we removed it in Step 3). Now that we want presets to be renamable, this conditional is no longer needed.

**Pattern Reference**: See lines 59-60 where updateModelChatTemplate and updateModelStopWords are called unconditionally for all models.

**Verification**:
```bash
cd /Users/aghorbani/codes/pocketpal-dev-team/worktrees/PR-490
yarn typecheck
yarn lint
yarn test src/components/ModelSettingsSheet/__tests__/ModelSettingsSheet.test.tsx
```

---

### Step 5: Update ModelStore Tests
**Files**: `src/store/__tests__/ModelStore.test.ts`
**Status**: `PENDING`
**Commit**: [commit hash when done]

**Change**:
- [ ] Line 197-212: Update test to verify preset names CAN be updated
- [ ] Update test name from "should not update" to "should update"

**Code Guidance**:
```typescript
// BEFORE (lines 197-212):
it('should not update model name for preset model', () => {
  const presetModel = {
    ...basicModel,
    id: 'preset-test-id',
    name: 'Gemma-2-2b-it (Q6_K)',
    origin: ModelOrigin.PRESET,
  };
  runInAction(() => {
    modelStore.models = [presetModel];
  });

  modelStore.updateModelName('preset-test-id', 'New Name');

  // Name should remain unchanged
  expect(modelStore.models[0].name).toBe('Gemma-2-2b-it (Q6_K)');
});

// AFTER:
it('should update model name for preset model', () => {
  const presetModel = {
    ...basicModel,
    id: 'preset-test-id',
    name: 'Gemma-2-2b-it (Q6_K)',
    origin: ModelOrigin.PRESET,
  };
  runInAction(() => {
    modelStore.models = [presetModel];
  });

  modelStore.updateModelName('preset-test-id', 'New Name');

  // Name should be updated
  expect(modelStore.models[0].name).toBe('New Name');
});
```

**Pattern Reference**: See test at lines 182-195 for local model rename test (same pattern).

**Verification**:
```bash
cd /Users/aghorbani/codes/pocketpal-dev-team/worktrees/PR-490
yarn test src/store/__tests__/ModelStore.test.ts
```

---

## Test Requirements

### Unit Tests
| Test Case | File | Priority | Status |
|-----------|------|----------|--------|
| Preset model input is not disabled | `ModelSettings.test.tsx` | MUST | ✅ DONE |
| Local model input is not disabled | `ModelSettings.test.tsx` | MUST | ✅ DONE |
| **Preset model name can be updated** | `ModelStore.test.ts` | MUST | PENDING |
| Local model name can be updated | `ModelStore.test.ts` | MUST | ✅ EXISTS |
| Reset button restores original preset name | `ModelStore.test.ts` | MUST | ✅ EXISTS |

### Integration Tests
No integration tests needed - covered by existing ModelSettingsSheet tests.

### Manual Testing
- [ ] Open model settings for a preset model (e.g., Gemma)
- [ ] Verify you CAN type in the model name field ✅
- [ ] Change the name to "My Custom Gemma"
- [ ] Click Save
- [ ] **Verify name DOES change to "My Custom Gemma"** (CRITICAL)
- [ ] Click Reset
- [ ] Verify name resets to original "Gemma-2-2b-it (Q6_K)"
- [ ] Close and reopen model settings
- [ ] Verify custom name persists
- [ ] Open model settings for a local model
- [ ] Verify renaming still works as before

---

## Coding Standards

### Patterns to Follow
- **MobX State**: Use runInAction for state mutations
- **Testing**: Follow existing ModelStore test patterns
- **Consistency**: Treat preset models same as local models for renaming

### Commit Format (enforced by commitlint)
```
fix(model): allow renaming preset models
```

---

## Reference Code

### Pattern Example: Reset Method (Already Supports Both Types)
**File**: `src/store/ModelStore.ts`
**Lines**: 1483-1499
```typescript
resetModelName = (modelId: string) => {
  const model = this.models.find(m => m.id === modelId);
  if (model) {
    runInAction(() => {
      model.name = getOriginalModelName(model);  // ← Works for both preset and local
    });
  }
};
```

### Pattern Example: Existing Test for Local Model Rename
**File**: `src/store/__tests__/ModelStore.test.ts`
**Lines**: 182-195
```typescript
it('should update model name for local model', () => {
  const localModel = {
    ...basicModel,
    id: 'local-test-id',
    name: 'old-name',
    origin: ModelOrigin.LOCAL,
  };
  runInAction(() => {
    modelStore.models = [localModel];
  });

  modelStore.updateModelName('local-test-id', 'New Name');

  expect(modelStore.models[0].name).toBe('New Name');
});
```

---

## Dependencies

### Blocked By
- PR-490-fix story (completed and approved)

### Blocks
- PR #490 final merge

---

## Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Breaking existing preset functionality | Low | Medium | Reset button still works via getOriginalModelName |
| Users confused by custom preset names | Low | Low | Reset button clearly restores original name |
| Persistence issues | Very Low | Low | MobX persistence handles all model changes uniformly |
| Test failures after changes | Medium | Low | Update test expectations to match new behavior |

---

## Open Questions

### For Human
- None - user explicitly requested preset models be renamable

### Resolved
- Should preset models be renamable? → YES (per user request)
- Should reset work differently for presets? → NO (already works via getOriginalModelName)

---

## Agent Reports

### Planner Report
```
Research completed on 2026-01-21 (updated):

CRITICAL DISCOVERY during manual testing:
Steps 1 & 2 were completed (UI fixes), but preset model names STILL cannot be saved.

Root cause analysis:
- ModelStore.ts line 1476: updateModelName has origin check that blocks presets
- ModelSettingsSheet.tsx line 56: Conditional skips calling updateModelName for presets
- ModelStore.test.ts line 197-212: Test EXPECTS presets NOT to be renamed

Both checks must be removed to allow preset renaming.
Reset functionality already works correctly (getOriginalModelName utility).

Impact assessment:
- STANDARD complexity (was quick, now standard due to store changes)
- NO breaking changes - reset button preserves ability to restore original names
- Tests must be updated to reflect new behavior

Files affected: 5 files total
- ModelSettings.tsx (✅ DONE - UI fixes)
- ModelSettings.test.tsx (✅ DONE - UI tests)
- ModelStore.ts (PENDING - remove origin check)
- ModelSettingsSheet.tsx (PENDING - remove conditional)
- ModelStore.test.ts (PENDING - update test expectations)

Recommendation: Continue with Steps 3-5 to complete preset rename functionality.

Story updated and ready for implementer.
```

---

## Implementation Report

### Environment
- **Task ID**: PR-490-additional-fixes
- **Worktree**: /Users/aghorbani/codes/pocketpal-dev-team/worktrees/PR-490
- **Branch**: pr-490

### Story
PR-490-additional-fixes: Fix Additional Issues in PR #490 (Allow preset model renaming)

### Status
complete

### Changes Made

| File | Change | Commit |
|------|--------|--------|
| `src/screens/ModelsScreen/ModelSettings/ModelSettings.tsx` | Removed disabled prop and divider | d6e407b |
| `src/screens/ModelsScreen/ModelSettings/__tests__/ModelSettings.test.tsx` | Added test for preset model input editability | 180e595 |
| `src/store/ModelStore.ts` | Removed preset check from updateModelName | c88162a |
| `src/components/ModelSettingsSheet/ModelSettingsSheet.tsx` | Removed preset check from save handler | b6c9e1c |
| `src/store/__tests__/ModelStore.test.ts` | Updated test to expect preset renames | 86fced1 |

### Deviations from Plan
None - all steps implemented exactly as specified in the story.

### Verification Results
- Lint: PASS
- TypeCheck: PASS
- Related Tests:
  - ModelStore.test.ts: PASS (107/107 tests)
  - ModelSettingsSheet.test.tsx: PASS (9/9 tests)
  - ModelSettings.test.tsx: PASS (9/9 tests)
- Pod Install: N/A (NATIVE_CHANGES=NO)
- iOS Build: N/A (NATIVE_CHANGES=NO)
- Android Build: N/A (NATIVE_CHANGES=NO)

### Notes for Tester
Manual testing needed to verify:
1. Open model settings for a preset model (e.g., Gemma-2-2b-it)
2. Edit the model name field and change it to "My Custom Gemma"
3. Click Save button
4. **VERIFY**: Name should change to "My Custom Gemma" (previously stayed unchanged)
5. Click Reset button
6. **VERIFY**: Name should restore to original "Gemma-2-2b-it (Q6_K)"
7. Close and reopen model settings
8. **VERIFY**: Custom name persists across reopening
9. Test with a local model to ensure renaming still works as before

### Blockers
None - all steps complete and tests passing.

---

### Previous Implementation (Steps 1-2)
See commits d6e407b and 180e595 - UI fixes complete.

### Current Implementation (Steps 3-5) - COMPLETE
All three remaining steps implemented successfully:

**Step 3 (commit c88162a)**: Removed the preset origin check in ModelStore.updateModelName
- Changed `if (model && model.origin !== ModelOrigin.PRESET)` to `if (model)`
- This allows preset models to have their names updated in the store

**Step 4 (commit b6c9e1c)**: Removed the preset conditional in ModelSettingsSheet.handleSaveSettings
- Removed the `if (model.origin !== ModelOrigin.PRESET)` wrapper around updateModelName call
- Cleaned up unused ModelOrigin import
- Now all models (preset and local) are handled uniformly

**Step 5 (commit 86fced1)**: Updated ModelStore test expectations
- Changed test name from "should not update" to "should update model name for preset model"
- Updated assertion to expect preset model names DO change (not remain unchanged)
- Test now verifies the new behavior is correct

---

## Changelog

| Date | Agent/Human | Change |
|------|-------------|--------|
| 2026-01-21 | planner | Created story for additional fixes found in manual testing |
| 2026-01-21 | implementer | Steps 1-2 complete - UI fixes and tests |
| 2026-01-21 | planner | Updated story with Steps 3-5 after discovering preset save issue |
