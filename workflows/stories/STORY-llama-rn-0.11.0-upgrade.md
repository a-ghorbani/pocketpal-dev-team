# Story: Upgrade llama.rn from 0.10.0 to 0.11.0-rc.0

## Metadata
- **Task ID**: TASK-20260120-1316
- **Issue**: N/A (Dependency upgrade)
- **Source**: prompt
- **Complexity**: standard
- **Native Changes**: YES
- **Created**: 2026-01-20
- **Status**: pending_approval

## Environment
- **Worktree**: `/Users/aghorbani/codes/pocketpal-dev-team/worktrees/TASK-20260120-1316`
- **Branch**: `feature/TASK-20260120-1316`
- **Base**: `main`

---

## Progress Tracking

### Current Phase
`[x] Planning → [ ] Approved → [ ] Implementing → [ ] Testing → [ ] Reviewing → [ ] PR Created`

### Checkpoints (Updated by Agents)

| Checkpoint | Status | Agent | Commit | Notes |
|------------|--------|-------|--------|-------|
| Worktree created | DONE | orchestrator | - | |
| Story approved | PENDING | human | - | |
| Package.json updated | PENDING | implementer | - | |
| Dependencies installed | PENDING | implementer | - | |
| Pod install | PENDING | implementer | - | |
| TypeScript check | PENDING | implementer | - | |
| iOS build (Release) | PENDING | implementer | - | |
| Android build (release) | PENDING | implementer | - | |
| Tests pass | PENDING | tester | - | |
| Review passed | PENDING | reviewer | - | |
| PR created | PENDING | reviewer | - | |

### Last Agent Handoff
```yaml
from_agent: planner
to_agent: human
timestamp: 2026-01-20T13:16:00Z
status: "Story created, awaiting approval"
completed:
  - Researched llama.rn usage across codebase
  - Identified 19 import points
  - Analyzed breaking changes from 0.10.0 to 0.11.0-rc.0
  - Verified native build configuration
  - Created comprehensive upgrade plan
next_steps:
  - Human review and approve story
  - Then route to implementer
blockers: []
context_for_next_agent: |
  This is a native dependency upgrade requiring full iOS/Android builds.
  NATIVE_CHANGES=YES - pod install + native builds REQUIRED.
  
  Breaking changes analysis:
  - 0.11.0-rc.0: Syncs llama.cpp to b7779 (underlying C++ library update)
  - 0.10.0-rc.2: fit_params disabled by default (NOT used by PocketPal)
  - 0.10.0-rc.3: snake_case for slot status (NOT used by PocketPal)
  
  PocketPal uses llama.rn exclusively for:
  1. Context initialization (initLlama, ContextParams)
  2. Inference (completion, stopCompletion)
  3. Multimodal support (initMultimodal, isMultimodalEnabled)
  4. Model metadata (loadLlamaModelInfo, TokenData, BuildInfo)
  5. Device selection (getBackendDevicesInfo, NativeBackendDeviceInfo)
  
  All these APIs appear stable across the upgrade.
```

---

## Context (For Recovery After Context Reset)

> **If you're an agent resuming work on this story:**
> 1. Read the "Progress Tracking" section above
> 2. Check `git log` in the worktree for commits
> 3. Read the "Last Agent Handoff" section
> 4. Continue from the next incomplete checkpoint

### Background

llama.rn is PocketPal's native bridge to llama.cpp, the underlying LLM inference engine. It's a critical dependency that provides:
- On-device model initialization and context management
- Streaming text completion
- Multimodal vision capabilities (image understanding)
- Device-specific GPU/CPU backend selection
- Model metadata and tokenization utilities

The library is actively developed and regularly syncs with upstream llama.cpp improvements. Version 0.11.0-rc.0 brings the latest llama.cpp sync (b7779) with performance improvements and bug fixes.

### Current State

**Current version**: llama.rn 0.10.0 (installed Jan 15, 2026)

**Usage points in PocketPal** (19 total imports):

1. **Core Store** (`src/store/ModelStore.ts`):
   - `ContextParams`, `LlamaContext`, `initLlama`
   - Handles model lifecycle, loading, inference

2. **Type Definitions**:
   - `src/utils/types.ts`: `ContextParams`, `TokenData`
   - `src/utils/completionTypes.ts`: `CompletionParams as LlamaRNCompletionParams`
   - `src/utils/contextInitParamsVersions.ts`: `ContextParams`

3. **Utilities**:
   - `src/utils/chat.ts`: `JinjaFormattedChatResult`, `LlamaContext`
   - `src/utils/memorySettings.ts`: `loadLlamaModelInfo`
   - `src/utils/deviceSelection.ts`: `getBackendDevicesInfo`, `NativeBackendDeviceInfo`
   - `src/utils/thinkingCapabilityDetection.ts`: `LlamaContext`

4. **Components**:
   - `src/components/ModelErrorReportSheet/ModelErrorReportSheet.tsx`: `ContextParams`
   - `src/screens/AboutScreen/AboutScreen.tsx`: `BuildInfo`
   - `src/screens/DevToolsScreen/screens/TestCompletionScreen/TestCompletionScreen.tsx`: `JinjaFormattedChatResult`

5. **Test Infrastructure**:
   - Multiple test files import `LlamaContext` for mocking
   - `__mocks__/external/llama.rn.ts`: Mock implementation
   - `jest/fixtures/models.ts`: `NativeLlamaContext`

**Native integration**:
- iOS: Podfile forces llama-rn to static_library build type (line 61-71)
- Android: NDK version 27.3.13750724, minSdk 24, targetSdk 36

### Target State

**Target version**: llama.rn 0.11.0-rc.0 (released Jan 20, 2026)

**Expected outcome**:
1. package.json updated to llama.rn 0.11.0-rc.0
2. All dependencies installed via yarn
3. iOS Podfile.lock updated via pod install
4. TypeScript compilation passes
5. iOS Release build succeeds
6. Android release build succeeds
7. All tests pass
8. Model loading and inference work as before

**Breaking changes analysis**:

From upstream changelog research:
- **0.11.0-rc.0**: Syncs llama.cpp to b7779 (performance improvements, bug fixes)
  - Impact: LOW - C++ library sync, no API changes detected
  
- **0.10.0-rc.3**: Changed to snake_case for slot management status
  - Impact: NONE - PocketPal doesn't use slot management APIs
  
- **0.10.0-rc.2**: fit_params disabled by default; default n_ctx set for vocab_only models
  - Impact: NONE - PocketPal explicitly sets all context params, doesn't use fit_params

**API compatibility**: All PocketPal usage points (ContextParams, LlamaContext, initLlama, completion, multimodal APIs, device selection) appear stable across the upgrade.

---

## Requirements

### Functional
1. [MUST] Update package.json to specify llama.rn version 0.11.0-rc.0
2. [MUST] Install dependencies successfully (yarn install)
3. [MUST] Update iOS dependencies (pod install in ios/)
4. [MUST] TypeScript compilation passes without errors
5. [MUST] iOS Release build completes successfully
6. [MUST] Android release build completes successfully
7. [MUST] All existing tests pass
8. [MUST] Model loading works (initContext succeeds)
9. [MUST] Text completion works (streaming inference)
10. [SHOULD] Multimodal inference works (vision models)
11. [SHOULD] Device backend selection works
12. [SHOULD] No regression in inference performance

### Non-Functional
- **Build time**: iOS build may take 5-10 minutes (llama.cpp is large)
- **Testing**: Must test on both iOS simulator and Android emulator
- **Rollback**: Must document rollback procedure if issues found
- **Documentation**: Update any affected documentation

### Platform Verification (NATIVE_CHANGES=YES)
- [x] NATIVE_CHANGES flag set to YES
- [ ] `pod install` succeeds
- [ ] iOS Release build succeeds
- [ ] Android Release build succeeds
- [ ] `ios/Podfile.lock` changes committed

---

## Acceptance Criteria

- [ ] package.json shows llama.rn: "0.11.0-rc.0"
- [ ] yarn install completes without errors
- [ ] pod install (ios/) completes without errors
- [ ] yarn typecheck passes
- [ ] yarn lint passes
- [ ] yarn test passes (all unit tests green)
- [ ] yarn ios --configuration Release builds successfully
- [ ] yarn android --variant=release builds successfully
- [ ] Manual testing: Model loads successfully in app
- [ ] Manual testing: Text completion generates responses
- [ ] Manual testing: Vision model with images works (if applicable)
- [ ] No new TypeScript errors introduced
- [ ] No new ESLint warnings introduced
- [ ] Podfile.lock changes committed to git

---

## Affected Files

| File | Action | Reason | Status |
|------|--------|--------|--------|
| `package.json` | MODIFY | Update llama.rn version to 0.11.0-rc.0 | PENDING |
| `yarn.lock` | MODIFY | Auto-updated by yarn install | PENDING |
| `ios/Podfile.lock` | MODIFY | Auto-updated by pod install | PENDING |
| `__mocks__/external/llama.rn.ts` | VERIFY | Ensure mock still compatible | PENDING |

**No source code changes expected** - This is a drop-in upgrade with no breaking API changes for PocketPal's usage.

---

## Implementation Plan

### Step 1: Update Package Dependencies
**Files**: `package.json`, `yarn.lock`
**Status**: `PENDING`
**Commit**: [hash when done]

**Change**:
- [ ] Update package.json line 50: `"llama.rn": "0.10.0"` → `"llama.rn": "0.11.0-rc.0"`
- [ ] Run `yarn install` to update yarn.lock
- [ ] Verify no peer dependency conflicts

**Verification**:
```bash
cd "${WORKTREE_PATH}"
grep '"llama.rn":' package.json
# Should show: "llama.rn": "0.11.0-rc.0"
yarn list --pattern llama.rn --depth=0
# Should confirm 0.11.0-rc.0 installed
```

### Step 2: Update iOS Native Dependencies
**Files**: `ios/Podfile.lock`
**Status**: `PENDING`
**Commit**: [hash when done]

**Change**:
- [ ] Navigate to ios/ directory
- [ ] Run `pod install` to update CocoaPods dependencies
- [ ] Verify llama-rn pod updated in Podfile.lock

**Verification**:
```bash
cd "${WORKTREE_PATH}/ios"
pod install
# Should complete without errors
grep -A 5 "llama-rn" Podfile.lock
# Should show new version reference
cd ..
```

### Step 3: Verify TypeScript Compatibility
**Files**: All TypeScript files importing from llama.rn (19 files)
**Status**: `PENDING`
**Commit**: [hash when done]

**Change**:
- [ ] Run TypeScript compiler check
- [ ] Verify all llama.rn type imports resolve correctly
- [ ] Check for any new type errors

**Pattern Reference**: Type imports should remain unchanged:
- `ContextParams` - used in 4 files
- `LlamaContext` - used in 10+ files  
- `TokenData`, `CompletionParams`, `BuildInfo`, etc.

**Verification**:
```bash
cd "${WORKTREE_PATH}"
yarn typecheck
# Should pass with no errors
```

### Step 4: Verify Mock Compatibility
**Files**: `__mocks__/external/llama.rn.ts`
**Status**: `PENDING`
**Commit**: [hash when done]

**Change**:
- [ ] Review mock implementation (lines 1-55)
- [ ] Verify MockLlamaContext includes all methods used in tests
- [ ] Check if any new llama.rn exports need mocking

**Current Mock Coverage**:
```typescript
// __mocks__/external/llama.rn.ts
class MockLlamaContext {
  loadSession, saveSession, completion, stopCompletion, bench
}
exports: LlamaContext, loadLlamaModelInfo, BuildInfo, initLlama, CompletionParams
```

**Verification**:
```bash
cd "${WORKTREE_PATH}"
yarn test --testPathPattern="ModelStore.test"
# Should pass if mock is compatible
```

### Step 5: Build Verification - iOS (Release)
**Status**: `PENDING`
**Commit**: [hash when done]

**Change**:
- [ ] Clean iOS build artifacts
- [ ] Build iOS in Release configuration
- [ ] Verify build completes without errors
- [ ] Check for new warnings (if any, document)

**Verification**:
```bash
cd "${WORKTREE_PATH}"
# Clean previous builds
yarn clean:ios
# Build iOS Release (this will take 5-10 minutes)
yarn ios:build:release
# Should complete with "** BUILD SUCCEEDED **"
```

**Expected build time**: 5-10 minutes (llama.cpp is a large C++ codebase)

### Step 6: Build Verification - Android (release)
**Status**: `PENDING`
**Commit**: [hash when done]

**Change**:
- [ ] Clean Android build artifacts
- [ ] Build Android in release variant
- [ ] Verify build completes without errors
- [ ] Check for new warnings (if any, document)

**Verification**:
```bash
cd "${WORKTREE_PATH}"
# Clean previous builds
yarn clean:android
# Build Android release (this will take 5-10 minutes)
yarn build:android:release
# Should complete with "BUILD SUCCESSFUL"
```

**Expected build time**: 5-10 minutes (first build with new native lib)

### Step 7: Run Test Suite
**Status**: `PENDING`
**Commit**: [hash when done]

**Change**:
- [ ] Run full Jest test suite
- [ ] Verify all tests pass
- [ ] Check for any test warnings

**Verification**:
```bash
cd "${WORKTREE_PATH}"
yarn test
# Should show: Tests: X passed, X total
# Coverage should be >= 60%
```

### Step 8: Manual Testing Checklist
**Status**: `PENDING`
**Commit**: N/A (manual verification)

**Change**:
- [ ] Launch app on iOS simulator
- [ ] Load a text model (e.g., Llama 3.2 1B)
- [ ] Generate a text completion (verify streaming works)
- [ ] Load a vision model (e.g., Llama 3.2 11B Vision)
- [ ] Send an image with prompt (verify multimodal works)
- [ ] Check device selection screen (verify backends listed)
- [ ] Launch app on Android emulator
- [ ] Repeat model loading and inference tests

**Expected behavior**: All functionality works as before the upgrade.

### Step 9: Commit Changes
**Status**: `PENDING`
**Commit**: [hash when done]

**Change**:
- [ ] Stage all modified files (package.json, yarn.lock, Podfile.lock)
- [ ] Create commit with descriptive message
- [ ] Verify commit includes only dependency changes

**Commit message**:
```
chore(deps): upgrade llama.rn from 0.10.0 to 0.11.0-rc.0

- Update package.json to llama.rn 0.11.0-rc.0
- Run yarn install (updates yarn.lock)
- Run pod install (updates ios/Podfile.lock)
- Verify TypeScript compilation passes
- Verify iOS and Android Release builds succeed
- Verify all tests pass

Breaking changes:
- None affecting PocketPal's usage
- 0.11.0-rc.0 syncs llama.cpp to b7779 (performance improvements)

Tested:
- iOS Release build: SUCCESS
- Android release build: SUCCESS
- Unit tests: PASS
- Manual model loading: PASS
- Manual inference: PASS

Story: TASK-20260120-1316
```

**Verification**:
```bash
cd "${WORKTREE_PATH}"
git add package.json yarn.lock ios/Podfile.lock
git status
# Should show only these 3 files staged
```

---

## Test Requirements

### Unit Tests
| Test Case | File | Priority | Status |
|-----------|------|----------|--------|
| ModelStore.initContext still works | `src/store/__tests__/ModelStore.test.ts` | MUST | PENDING |
| llama.rn mock compatibility | `__mocks__/external/llama.rn.ts` | MUST | PENDING |
| All existing tests pass | (all test files) | MUST | PENDING |

### Integration Tests
| Test Case | File | Priority | Status |
|-----------|------|----------|--------|
| E2E tests pass (if applicable) | `e2e/` | SHOULD | PENDING |

### Manual Testing
- [ ] **iOS Simulator** - Model loading
  - Open app on iOS simulator
  - Navigate to Models screen
  - Download/load a text model (e.g., Llama 3.2 1B)
  - Verify model loads without errors
  - Generate a text completion
  - Verify streaming works and response is coherent

- [ ] **iOS Simulator** - Vision model
  - Load a vision model (e.g., Llama 3.2 11B Vision)
  - Attach an image to chat
  - Send a prompt about the image
  - Verify vision inference works

- [ ] **Android Emulator** - Model loading
  - Repeat iOS model loading tests on Android emulator
  - Verify no Android-specific issues

- [ ] **Device Selection**
  - Navigate to Dev Tools > Device Selection
  - Verify backend devices are listed correctly
  - Verify getBackendDevicesInfo still works

- [ ] **Performance Check**
  - Compare inference speed before/after upgrade
  - Should be similar or improved (no regression)

---

## Rollback Plan

If critical issues are discovered after upgrade:

### Immediate Rollback (Revert Commit)
```bash
cd "${WORKTREE_PATH}"
git log --oneline | head -1  # Get commit hash
git revert <commit-hash>
yarn install
cd ios && pod install && cd ..
# Rebuild iOS and Android
yarn ios:build:release
yarn build:android:release
```

### Full Rollback (Manual)
```bash
cd "${WORKTREE_PATH}"
# 1. Revert package.json
# Change line 50 back to: "llama.rn": "0.10.0"

# 2. Reinstall dependencies
yarn install

# 3. Update iOS pods
cd ios && pod install && cd ..

# 4. Rebuild
yarn clean
yarn ios:build:release
yarn build:android:release

# 5. Test
yarn test
```

### Fallback Strategy

If 0.11.0-rc.0 has unforeseen issues:
1. **Option A**: Wait for 0.11.0 stable release
2. **Option B**: Upgrade to 0.10.1 instead (latest stable as of Jan 20, 2026)

---

## Coding Standards

### Testing Infrastructure (CRITICAL)
```
# No test code changes expected for this upgrade
# But verify these still work:
${WORKTREE_PATH}/jest/setup.ts      # Global mocks
${WORKTREE_PATH}/jest/test-utils.tsx # Custom render
${WORKTREE_PATH}/__mocks__/external/llama.rn.ts  # llama.rn mock

# If mock needs updates (unlikely), follow existing pattern:
# - MockLlamaContext class with jest.fn() methods
# - Export LlamaContext, initLlama, loadLlamaModelInfo, BuildInfo
```

### Commit Format
```
chore(deps): upgrade llama.rn from 0.10.0 to 0.11.0-rc.0

- Update package.json
- Run yarn install and pod install
- Verify builds and tests

Story: TASK-20260120-1316
```

---

## Dependencies

### Blocked By
- [ ] None

### Blocks
- [ ] Future llama.cpp feature utilization (post-b7779 improvements)

---

## Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| iOS build fails with new llama-rn version | Low | High | Test build immediately after pod install; Podfile forces static_library build type which should be compatible |
| Android build fails with NDK issues | Low | High | Verify NDK 27.3.13750724 compatibility; upgrade guide doesn't mention NDK changes |
| Runtime crash on model loading | Low | Critical | Test model loading immediately after build; llama.cpp b7779 sync is a mature release |
| Performance regression in inference | Low | Medium | Benchmark inference speed before/after; llama.cpp updates typically improve performance |
| New TypeScript type errors | Low | Medium | Run typecheck immediately after yarn install; API appears stable |
| Mock incompatibility breaking tests | Low | Medium | Run test suite immediately; mock is simple and unlikely to need changes |
| RC version instability | Medium | Medium | 0.11.0-rc.0 is a release candidate, not final; have rollback plan ready; consider upgrading to 0.10.1 (stable) instead if issues arise |

**Recommended mitigation order**:
1. Run typecheck immediately after yarn install
2. Run test suite to catch mock issues early
3. Build iOS first (faster feedback than Android)
4. Build Android to verify cross-platform compatibility
5. Test model loading before doing full manual testing

---

## Open Questions

### For Human
- [ ] Should we target 0.11.0-rc.0 (latest) or 0.10.1 (stable)?
  - **Recommendation**: Start with 0.11.0-rc.0 as requested, but be ready to fall back to 0.10.1 if RC has issues
- [ ] Are there specific models or inference scenarios that need extra testing?
  - **Recommendation**: Test at least one text model and one vision model

### Resolved
- Is this a drop-in upgrade? → **YES** - No breaking API changes detected
- Do we need source code changes? → **NO** - Only package.json and dependency lockfiles
- Are there breaking changes? → **NO** for PocketPal's usage patterns

---

## Agent Reports

### Planner Report
```
Research completed: 2026-01-20

Findings:
1. Identified 19 import points for llama.rn across codebase
2. Primary usage in ModelStore.ts (context init, inference, multimodal)
3. Breaking changes analyzed: No impact on PocketPal
4. Native build configuration verified (iOS Podfile, Android build.gradle)
5. Test infrastructure reviewed (mocks are simple, unlikely to break)

Risk assessment: LOW
- RC version is the main risk factor
- All APIs used by PocketPal appear stable
- Native builds may take time but should succeed
- Rollback is straightforward if needed

Recommended approach:
1. Update package.json to 0.11.0-rc.0
2. Install dependencies
3. Verify builds (iOS, Android)
4. Run tests
5. Manual verification
6. Commit changes
7. Monitor for issues; be ready to rollback or upgrade to 0.10.1

Estimated effort: 1-2 hours (mostly build time)
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
| 2026-01-20 13:16 | orchestrator | Created worktree and task |
| 2026-01-20 13:25 | planner | Initial story draft with research |

---

## References

### llama.rn Documentation
- GitHub: https://github.com/mybigday/llama.rn
- npm: https://www.npmjs.com/package/llama.rn
- Changelog: Review release notes for 0.11.0-rc.0

### PocketPal Context
- Context file: `/Users/aghorbani/codes/pocketpal-dev-team/context/pocketpal-overview.md`
- Patterns: `/Users/aghorbani/codes/pocketpal-dev-team/context/patterns.md`

### Related Files
- ModelStore: `src/store/ModelStore.ts` (2417 lines)
- Context params: `src/utils/contextInitParamsVersions.ts`
- Type definitions: `src/utils/types.ts`
- Mock: `__mocks__/external/llama.rn.ts`
