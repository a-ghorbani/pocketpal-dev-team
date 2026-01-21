# Story: Fix Model Name Reset and Test Coverage for PR #490

## Metadata
- **Task ID**: PR-490-fix
- **Issue**: PR #490 by @ArkaneFans (feat: support rename models)
- **Source**: pr_review
- **Complexity**: standard
- **Native Changes**: NO
- **Created**: 2026-01-21
- **Status**: draft

## Environment
- **Worktree**: `/Users/aghorbani/codes/pocketpal-dev-team/worktrees/PR-490`
- **Branch**: `pr-490`
- **Base**: `main`

---

## Progress Tracking

### Current Phase
`[X] Planning → [ ] Approved → [ ] Implementing → [ ] Testing → [ ] Reviewing → [ ] PR Created`

### Checkpoints (Updated by Agents)

| Checkpoint | Status | Agent | Commit | Notes |
|------------|--------|-------|--------|-------|
| Worktree created | DONE | orchestrator | - | |
| Story approved | PENDING | human | - | |
| Step 1 complete | PENDING | implementer | - | Add model name utilities |
| Step 2 complete | PENDING | implementer | - | Update PalStore to use utility |
| Step 3 complete | PENDING | implementer | - | Remove inline mocks |
| Step 4 complete | PENDING | implementer | - | Add component tests |
| Step 5 complete | PENDING | implementer | - | Fix resetModelName |
| Step 6 complete | PENDING | implementer | - | Add store unit tests (optional) |
| Tests written | PENDING | tester | - | |
| Review passed | PENDING | reviewer | - | |
| PR updated | PENDING | reviewer | - | |

### Last Agent Handoff
```yaml
from_agent: planner
to_agent: human
timestamp: 2026-01-21T10:00:00Z
status: "Story created, awaiting approval"
completed:
  - Researched codebase in worktree
  - Analyzed global mock patterns in jest/setup.ts
  - Studied existing test patterns in ModelStore
  - Identified how PalStore strips .gguf extensions
  - Found defaultModels structure for preset names
next_steps:
  - Human review and approve story
  - Route to implementer for fixes
blockers: []
context_for_next_agent: |
  This is a PR review fix for #490 which adds model rename functionality.
  
  Key issues identified:
  1. Test uses inline store mock (violates global mock pattern)
  2. Missing component test coverage for new methods
  3. resetModelName needs to strip .gguf extension like PalStore does
  4. Preset models should reset to original nice name from defaultModels
  5. Optional: Add ModelStore unit tests
  
  Pattern references:
  - PalStore.ts:383 - shows .replace(/\.gguf$/i, '') pattern
  - jest/setup.ts:88-101 - global store mocking
  - ModelStore.ts:1522-1538 - reset methods pattern
  - defaultModels.ts - contains original "name" field for presets
```

---

## Context (For Recovery After Context Reset)

### Background
PR #490 by @ArkaneFans adds the ability to rename models with reset functionality. The PR implements:
- `updateModelName(modelId, newName)` - Updates model name (disabled for preset models)
- `resetModelName(modelId)` - Resets model name to default

The feature works correctly but has several issues that need fixing:
1. Test violates PocketPal's global mock pattern
2. Incomplete test coverage
3. Reset logic doesn't match PalStore's .gguf stripping behavior
4. Preset models should reset to original display name, not filename

### Current State

**ModelStore.ts:1473-1547** - Model name methods:
```typescript
updateModelName = (modelId: string, newName: string) => {
  const model = this.models.find(m => m.id === modelId);
  if (model && model.origin !== ModelOrigin.PRESET) {
    runInAction(() => {
      model.name = newName;
    });
  }
};

resetModelName = (modelId: string) => {
  const model = this.models.find(m => m.id === modelId);
  if (model) {
    runInAction(() => {
      model.name = model.filename || '';  // ISSUE: Doesn't strip .gguf
    });
  }
};
```

**ModelSettingsSheet.test.tsx:55-65** - Inline mock (WRONG pattern):
```typescript
// ISSUE: Inline store mock violates global mock pattern
jest.mock('../../../store', () => ({
  modelStore: {
    updateModelChatTemplate: jest.fn(),
    updateModelStopWords: jest.fn(),
    resetModelChatTemplate: jest.fn(),
    resetModelStopWords: jest.fn(),
    updateModelName: jest.fn(),
    resetModelName: jest.fn(),
  },
}));
```

**PalStore.ts:383** - Correct .gguf stripping pattern:
```typescript
const modelName = modelRef.filename.replace(/\.gguf$/i, '');
```

**defaultModels.ts:15-29** - Preset models have nice display names:
```typescript
{
  id: 'bartowski/gemma-2-2b-it-GGUF/gemma-2-2b-it-Q6_K.gguf',
  author: 'bartowski',
  name: 'Gemma-2-2b-it (Q6_K)',  // This is the nice name to restore
  filename: 'gemma-2-2b-it-Q6_K.gguf',
  origin: ModelOrigin.PRESET,
  ...
}
```

### Target State

After fixes:
1. Test imports global mock from `jest/setup.ts` instead of inline mock
2. Component tests verify both `updateModelName` and `resetModelName` are called
3. `resetModelName` strips .gguf extension like PalStore does
4. For preset models, `resetModelName` restores original `name` from defaultModels
5. Optional: ModelStore unit tests verify the reset logic

---

## Requirements

### Functional
1. [MUST] Create utility functions for model name handling (`getDisplayNameFromFilename`, `getOriginalModelName`)
2. [MUST] Update PalStore to use new utility (consolidate .gguf stripping)
3. [MUST] Replace inline store mock with global mock import
4. [MUST] Add component tests for resetModelName and updateModelName
5. [MUST] Fix resetModelName to use new utility (strips .gguf for local, restores nice name for preset)
6. [SHOULD] Add ModelStore unit tests for new methods

### Non-Functional
- Testing: Follow PocketPal's centralized mock pattern
- Consistency: Match existing reset method patterns (resetModelChatTemplate, resetModelStopWords)
- Performance: No impact (same operations)

---

## Acceptance Criteria

- [ ] ModelSettingsSheet.test.tsx uses global mock, not inline mock
- [ ] Tests verify resetModelName and updateModelName are called
- [ ] resetModelName strips .gguf extension for all models
- [ ] resetModelName restores original name for preset models
- [ ] Local/HF models reset to filename without .gguf
- [ ] All tests pass with global mock
- [ ] Optional: ModelStore unit tests added
- [ ] Coverage >= 60%
- [ ] No regressions in existing tests

---

## Affected Files

| File | Action | Reason | Status |
|------|--------|--------|--------|
| `src/utils/formatters.ts` | MODIFY | Add model name utility functions | PENDING |
| `src/utils/__tests__/formatters.test.ts` | MODIFY | Add tests for new utilities | PENDING |
| `src/store/ModelStore.ts` | MODIFY | Fix resetModelName using new utilities | PENDING |
| `src/store/PalStore.ts` | MODIFY | Use new utility instead of inline regex | PENDING |
| `src/components/ModelSettingsSheet/__tests__/ModelSettingsSheet.test.tsx` | MODIFY | Remove inline mock, add tests | PENDING |
| `src/store/__tests__/ModelStore.test.ts` | MODIFY | Add unit tests (optional) | PENDING |

---

## Implementation Plan

### Step 1: Add Model Name Utility Functions
**Files**: `src/utils/formatters.ts`, `src/utils/__tests__/formatters.test.ts`
**Status**: `PENDING`
**Commit**: [commit hash when done]

**Change**:
- [ ] Add `getDisplayNameFromFilename(filename: string): string` - strips .gguf extension
- [ ] Add `getOriginalModelName(model: Model): string` - returns original name for preset or stripped filename for local/HF
- [ ] Add unit tests for both utilities

**Why**: Consolidate the .gguf stripping logic into a single utility for consistency across the codebase (currently duplicated in PalStore.ts:383 and needed in ModelStore.ts).

**Code Guidance**:
```typescript
// src/utils/formatters.ts - Add at end of file

import {defaultModels} from '../store/defaultModels';
import {Model, ModelOrigin} from './types';

/**
 * Strips the .gguf extension from a model filename for display purposes.
 * @param filename - The model filename (e.g., "llama-3.1-8b-q4_0.gguf")
 * @returns Clean display name without .gguf extension (e.g., "llama-3.1-8b-q4_0")
 */
export const getDisplayNameFromFilename = (filename: string): string => {
  return (filename || '').replace(/\.gguf$/i, '');
};

/**
 * Returns the original/default display name for a model.
 * - For preset models: Returns the curated display name from defaultModels
 * - For local/HF models: Returns the filename without .gguf extension
 * @param model - The model object
 * @returns The original display name
 */
export const getOriginalModelName = (model: Model): string => {
  // For preset models, look up the original name from defaultModels
  if (model.origin === ModelOrigin.PRESET) {
    const defaultModel = defaultModels.find(dm => dm.id === model.id);
    if (defaultModel) {
      return defaultModel.name;
    }
  }

  // For local/HF models (or preset not found), strip .gguf from filename
  return getDisplayNameFromFilename(model.filename);
};
```

```typescript
// src/utils/__tests__/formatters.test.ts - Add tests

describe('getDisplayNameFromFilename', () => {
  it('should strip .gguf extension', () => {
    expect(getDisplayNameFromFilename('model-q4_0.gguf')).toBe('model-q4_0');
  });

  it('should strip .GGUF extension (case-insensitive)', () => {
    expect(getDisplayNameFromFilename('model-q4_0.GGUF')).toBe('model-q4_0');
  });

  it('should return empty string for empty input', () => {
    expect(getDisplayNameFromFilename('')).toBe('');
  });

  it('should return filename unchanged if no .gguf extension', () => {
    expect(getDisplayNameFromFilename('model-q4_0')).toBe('model-q4_0');
  });
});

describe('getOriginalModelName', () => {
  it('should return original name for preset models', () => {
    const presetModel = {
      id: defaultModels[0].id,
      name: 'User Modified Name',
      filename: defaultModels[0].filename,
      origin: ModelOrigin.PRESET,
    } as Model;

    expect(getOriginalModelName(presetModel)).toBe(defaultModels[0].name);
  });

  it('should strip .gguf for local models', () => {
    const localModel = {
      id: 'local-id',
      name: 'Some Name',
      filename: 'my-model.gguf',
      origin: ModelOrigin.LOCAL,
    } as Model;

    expect(getOriginalModelName(localModel)).toBe('my-model');
  });

  it('should fallback to stripped filename if preset not found in defaultModels', () => {
    const orphanPreset = {
      id: 'unknown-preset-id',
      name: 'Some Name',
      filename: 'orphan.gguf',
      origin: ModelOrigin.PRESET,
    } as Model;

    expect(getOriginalModelName(orphanPreset)).toBe('orphan');
  });
});
```

**Verification**:
```bash
cd "${WORKTREE_PATH}"
yarn typecheck
yarn test src/utils/__tests__/formatters.test.ts
```

---

### Step 2: Update PalStore to Use New Utility
**Files**: `src/store/PalStore.ts`
**Status**: `PENDING`
**Commit**: [commit hash when done]

**Change**:
- [ ] Import `getDisplayNameFromFilename` from utils/formatters
- [ ] Replace inline `.replace(/\.gguf$/i, '')` at line 383 with utility call

**Code Guidance**:
```typescript
// At top of file, add import:
import {getDisplayNameFromFilename} from '../utils/formatters';

// Line 383 - Replace:
const modelName = modelRef.filename.replace(/\.gguf$/i, '');
// With:
const modelName = getDisplayNameFromFilename(modelRef.filename);
```

**Verification**:
```bash
cd "${WORKTREE_PATH}"
yarn typecheck
yarn test src/store/__tests__/PalStore.test.ts
```

---

### Step 3: Remove Inline Store Mock in Component Test
**Files**: `src/components/ModelSettingsSheet/__tests__/ModelSettingsSheet.test.tsx`
**Status**: `PENDING`
**Commit**: [commit hash when done]

**Change**:
- [ ] Delete inline jest.mock for store (lines 55-65)
- [ ] Import modelStore from '../../../store' (already exists at line 4)
- [ ] Verify global mock is used (defined in jest/setup.ts:88-101)
- [ ] Keep all other mocks (ModelSettings component, Sheet component)

**Pattern Reference**: See `jest/setup.ts:88-101`
```typescript
// jest/setup.ts - Global store mock
jest.mock('../src/store', () => {
  const {UIStore} = require('../__mocks__/stores/uiStore');
  return {
    modelStore: mockModelStore,  // Already mocked globally
    UIStore,
    uiStore: mockUiStore,
    // ... other stores
  };
});
```

**Code Guidance**:
```typescript
// DELETE lines 55-65 (inline mock)

// KEEP this import (already exists):
import {modelStore} from '../../../store';

// The global mock will be used automatically
```

**Verification**:
```bash
cd "${WORKTREE_PATH}"
yarn test src/components/ModelSettingsSheet/__tests__/ModelSettingsSheet.test.tsx
```

---

### Step 4: Add Component Test Coverage for New Methods
**Files**: `src/components/ModelSettingsSheet/__tests__/ModelSettingsSheet.test.tsx`
**Status**: `PENDING`
**Commit**: [commit hash when done]

**Change**:
- [ ] Add test: "handles reset model name correctly"
- [ ] Add test: "handles model name change correctly"
- [ ] Verify resetModelName is called with correct modelId
- [ ] Verify updateModelName is called with correct modelId and name

**Pattern Reference**: See existing reset test at line 162-173

**Code Guidance**:
```typescript
// Add after existing "handles reset correctly" test (line 173)

it('handles reset model name correctly', async () => {
  const {getByText} = render(<ModelSettingsSheet {...defaultProps} />);

  await act(async () => {
    fireEvent.press(getByText('Reset'));
  });

  expect(modelStore.resetModelName).toHaveBeenCalledWith(mockModel.id);
});

it('handles model name change correctly', async () => {
  const {getByTestId} = render(<ModelSettingsSheet {...defaultProps} />);
  
  // Trigger the mock model name update
  await act(async () => {
    fireEvent.press(getByTestId('mock-model-name-update'));
  });

  // Then save
  await act(async () => {
    fireEvent.press(getByText('Save Changes'));
  });

  expect(modelStore.updateModelName).toHaveBeenCalledWith(
    mockModel.id,
    'new model name'
  );
});
```

**Verification**:
```bash
cd "${WORKTREE_PATH}"
yarn test src/components/ModelSettingsSheet/__tests__/ModelSettingsSheet.test.tsx
```

---

### Step 5: Fix resetModelName to Use New Utility
**Files**: `src/store/ModelStore.ts`
**Status**: `PENDING`
**Commit**: [commit hash when done]

**Change**:
- [ ] Import `getOriginalModelName` from utils/formatters
- [ ] Replace resetModelName implementation to use the utility function
- [ ] Follow same pattern as resetModelChatTemplate and resetModelStopWords

**Pattern Reference**:
- See `resetModelChatTemplate` at line 1522-1529
- See new utility in `src/utils/formatters.ts`

**Code Guidance**:
```typescript
// At top of file, add import:
import {getOriginalModelName} from '../utils/formatters';

// Replace resetModelName (line 1540-1547) with:
resetModelName = (modelId: string) => {
  const model = this.models.find(m => m.id === modelId);
  if (model) {
    runInAction(() => {
      model.name = getOriginalModelName(model);
    });
  }
};
```

**Note**: The `getOriginalModelName` utility handles both cases:
- Preset models: Returns original display name from defaultModels
- Local/HF models: Returns filename without .gguf extension

**Verification**:
```bash
cd "${WORKTREE_PATH}"
yarn typecheck
yarn lint
yarn test src/store/__tests__/ModelStore.test.ts
```

---

### Step 6: Add ModelStore Unit Tests (Optional but Recommended)
**Files**: `src/store/__tests__/ModelStore.test.ts`
**Status**: `PENDING`
**Commit**: [commit hash when done]

**Change**:
- [ ] Add test suite: "model name management"
- [ ] Test: updateModelName for local model
- [ ] Test: updateModelName does nothing for preset model
- [ ] Test: resetModelName strips .gguf for local model
- [ ] Test: resetModelName restores original name for preset model

**Pattern Reference**: See existing test structure at lines 151-178

**Code Guidance**:
```typescript
// Add after "model management" describe block (around line 178)

describe('model name management', () => {
  it('should update model name for local model', () => {
    const localModel = {
      ...basicModel,
      id: 'local-test-id',
      name: 'Original Name',
      origin: ModelOrigin.LOCAL,
    };
    modelStore.models = [localModel];

    modelStore.updateModelName('local-test-id', 'New Name');

    expect(modelStore.models[0].name).toBe('New Name');
  });

  it('should not update model name for preset model', () => {
    const presetModel = {
      ...basicModel,
      id: 'preset-test-id',
      name: 'Gemma-2-2b-it (Q6_K)',
      origin: ModelOrigin.PRESET,
    };
    modelStore.models = [presetModel];

    modelStore.updateModelName('preset-test-id', 'New Name');

    // Name should remain unchanged
    expect(modelStore.models[0].name).toBe('Gemma-2-2b-it (Q6_K)');
  });

  it('should reset local model name by stripping .gguf extension', () => {
    const localModel = {
      ...basicModel,
      id: 'local-test-id',
      name: 'Modified Name',
      filename: 'my-model-file.gguf',
      origin: ModelOrigin.LOCAL,
    };
    modelStore.models = [localModel];

    modelStore.resetModelName('local-test-id');

    expect(modelStore.models[0].name).toBe('my-model-file');
  });

  it('should reset preset model name to original display name', () => {
    // Use a real preset model from defaultModels
    const presetModel = {
      ...defaultModels[0],
      name: 'User Modified Name', // User changed it
    };
    modelStore.models = [presetModel];

    modelStore.resetModelName(presetModel.id);

    // Should restore to original name from defaultModels
    expect(modelStore.models[0].name).toBe(defaultModels[0].name);
  });

  it('should handle reset when preset model not found in defaultModels', () => {
    const orphanPresetModel = {
      ...basicModel,
      id: 'orphan-preset-id',
      name: 'Modified Name',
      filename: 'orphan-model.gguf',
      origin: ModelOrigin.PRESET,
    };
    modelStore.models = [orphanPresetModel];

    modelStore.resetModelName('orphan-preset-id');

    // Should fall back to stripping .gguf from filename
    expect(modelStore.models[0].name).toBe('orphan-model');
  });
});
```

**Verification**:
```bash
cd "${WORKTREE_PATH}"
yarn test src/store/__tests__/ModelStore.test.ts
```

---

## Test Requirements

### Unit Tests
| Test Case | File | Priority | Status |
|-----------|------|----------|--------|
| Remove inline mock, use global | `ModelSettingsSheet.test.tsx` | MUST | PENDING |
| Test resetModelName called on reset | `ModelSettingsSheet.test.tsx` | MUST | PENDING |
| Test updateModelName called on save | `ModelSettingsSheet.test.tsx` | MUST | PENDING |
| Update local model name | `ModelStore.test.ts` | SHOULD | PENDING |
| Block preset model name update | `ModelStore.test.ts` | SHOULD | PENDING |
| Reset local strips .gguf | `ModelStore.test.ts` | SHOULD | PENDING |
| Reset preset restores original | `ModelStore.test.ts` | SHOULD | PENDING |
| Handle orphan preset fallback | `ModelStore.test.ts` | SHOULD | PENDING |

### Integration Tests
No integration tests needed - unit tests cover the functionality.

### Manual Testing
- [ ] Open model settings for a local model
- [ ] Rename it and save - verify name updates
- [ ] Press reset - verify name resets to filename without .gguf
- [ ] Open model settings for a preset model (e.g., Gemma)
- [ ] Try to rename - verify name field is disabled
- [ ] If user somehow modified preset name, press reset - verify it restores to original nice name

---

## Coding Standards

### Testing Infrastructure (CRITICAL)
```
# Read these BEFORE writing tests:
${WORKTREE_PATH}/jest/setup.ts      # Global mocks (line 88-101 for stores)
${WORKTREE_PATH}/jest/test-utils.tsx # Custom render
${WORKTREE_PATH}/__mocks__/stores/  # Mock stores

# DO NOT mock stores inline - they're globally mocked
# Use runInAction() for MobX state changes in store tests
# Import render from jest/test-utils, NOT @testing-library/react-native
```

### Patterns to Follow
- **Store Methods**: Use `runInAction()` for state changes
- **Reset Methods**: Follow pattern from resetModelChatTemplate (line 1522)
- **Tests**: Use `jest.unmock('../../store')` for store unit tests
- **Fixtures**: Use existing fixtures from `jest/fixtures/models`

### Commit Format (enforced by commitlint)
```
fix(model): correct reset name behavior and test patterns
```

---

## Reference Code

### Pattern Example: Global Store Mock (jest/setup.ts)
**File**: `jest/setup.ts`
**Lines**: 88-101
```typescript
jest.mock('../src/store', () => {
  const {UIStore} = require('../__mocks__/stores/uiStore');
  return {
    modelStore: mockModelStore,
    UIStore,
    uiStore: mockUiStore,
    chatSessionStore: mockChatSessionStore,
    hfStore: mockHFStore,
    benchmarkStore: mockBenchmarkStore,
    palStore: mockPalStore,
    deepLinkStore: mockDeepLinkStore,
    defaultCompletionSettings: mockDefaultCompletionSettings,
  };
});
```

### Pattern Example: Reset Method (ModelStore.ts)
**File**: `src/store/ModelStore.ts`
**Lines**: 1522-1538
```typescript
resetModelChatTemplate = (modelId: string) => {
  const model = this.models.find(m => m.id === modelId);
  if (model) {
    runInAction(() => {
      model.chatTemplate = {...model.defaultChatTemplate};
    });
  }
};

resetModelStopWords = (modelId: string) => {
  const model = this.models.find(m => m.id === modelId);
  if (model) {
    runInAction(() => {
      model.stopWords = [...(model.defaultStopWords || [])];
    });
  }
};
```

### Pattern Example: .gguf Stripping (PalStore.ts)
**File**: `src/store/PalStore.ts`
**Lines**: 382-383
```typescript
// Extract model name from filename (remove .gguf extension)
const modelName = modelRef.filename.replace(/\.gguf$/i, '');
```

### Pattern Example: Store Unit Test (ModelStore.test.ts)
**File**: `src/store/__tests__/ModelStore.test.ts`
**Lines**: 1-18
```typescript
jest.unmock('../../store');
import {runInAction} from 'mobx';
import {LlamaContext} from '@pocketpalai/llama.rn';
import {Alert} from 'react-native';

import {defaultModels} from '../defaultModels';
import {downloadManager} from '../../services/downloads';
import {ModelOrigin, ModelType} from '../../utils/types';
import {
  basicModel,
  mockContextModel,
  mockHFModel1,
} from '../../../jest/fixtures/models';

import {modelStore, uiStore} from '..';
```

---

## Dependencies

### Blocked By
- None

### Blocks
- PR #490 merge and release

---

## Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Breaking existing tests | Low | High | Run full test suite after changes |
| Preset name lookup failure | Low | Medium | Add fallback to strip .gguf if not found in defaultModels |
| Global mock not working | Low | High | Verify jest/setup.ts loads correctly, clear jest cache if needed |

---

## Open Questions

### For Human
- [ ] Should we add the optional ModelStore unit tests? (Recommended: YES for better coverage)

### Resolved
- None yet

---

## Agent Reports

### Planner Report
```
Research completed:
- Analyzed global mock pattern in jest/setup.ts (lines 88-101)
- Found inline mock violation in ModelSettingsSheet.test.tsx (lines 55-65)
- Identified .gguf stripping pattern in PalStore.ts (line 383)
- Studied reset methods pattern (resetModelChatTemplate, resetModelStopWords)
- Located defaultModels structure with original preset names
- Examined existing ModelStore test patterns

Key findings:
1. Inline store mock violates PocketPal's centralized mocking system
2. Component tests missing coverage for new methods
3. resetModelName doesn't strip .gguf extension (inconsistent with PalStore)
4. Preset models should restore original display name from defaultModels
5. Optional: ModelStore unit tests would improve coverage

All affected files identified and implementation steps are detailed.
Story is ready for human approval.
```

---

## Changelog

| Date | Agent/Human | Change |
|------|-------------|--------|
| 2026-01-21 | orchestrator | Created worktree and task for PR-490 review |
| 2026-01-21 | planner | Initial story draft created |
