# Quick Story: Fix bootstrap.sh for llama-sampling -> llama-sampler rename

## Metadata
- **Task ID**: LLAMARN-20260210
- **Source**: github (CI failure in sync-llama-cpp workflow)
- **Complexity**: quick
- **Native Changes**: NO
- **Created**: 2026-02-10
- **Status**: complete
- **Target Repo**: llama.rn (https://github.com/mybigday/llama.rn)

## Environment
- **Local Clone**: `/Users/aghorbani/codes/llama.rn`
- **Fork**: `git@github.com:a-ghorbani/llama.rn.git`
- **Upstream**: `git@github.com:mybigday/llama.rn.git`
- **Branch**: `fix/rename-llama-sampling-to-sampler`
- **Base**: `main`

---

## Task Summary

**What**: Update `scripts/bootstrap.sh` to reference `llama-sampler.{h,cpp}` instead of `llama-sampling.{h,cpp}`.

**Why**: Upstream llama.cpp [PR #19363](https://github.com/ggml-org/llama.cpp/pull/19363) renamed `src/llama-sampling.{h,cpp}` to `src/llama-sampler.{h,cpp}`, breaking the [sync-llama-cpp CI workflow](https://github.com/mybigday/llama.rn/actions/runs/21850068134/job/63054448365).

**Where**: `scripts/bootstrap.sh`

---

## Root Cause Analysis

The `sync-llama-cpp.yml` workflow:
1. Updates `third_party/llama.cpp` submodule to latest
2. Runs `scripts/bootstrap.sh` to copy source files to `./cpp/`
3. Builds Android and iOS libraries
4. Creates a sync PR

Step 2 fails because `bootstrap.sh` tries to copy `llama-sampling.{h,cpp}` which no longer exists in the updated submodule.

**Upstream change**: llama.cpp commit `e696cfc` (merged Feb 6, 2026) by @danbev, approved by @ggerganov.

---

## Change Details

### File: `scripts/bootstrap.sh`

**Current** (lines 245-246):
```bash
cp ./$LLAMA_DIR/src/llama-sampling.h ./cpp/llama-sampling.h
cp ./$LLAMA_DIR/src/llama-sampling.cpp ./cpp/llama-sampling.cpp
```

**Change to**:
```bash
cp ./$LLAMA_DIR/src/llama-sampler.h ./cpp/llama-sampler.h
cp ./$LLAMA_DIR/src/llama-sampler.cpp ./cpp/llama-sampler.cpp
```

### Additional: Clean up old files

The old `cpp/llama-sampling.{h,cpp}` files are committed in the repo. Since bootstrap.sh won't overwrite them anymore (different filename), they'd become orphans. The build system uses glob patterns (`llama*.cpp`), so having both old and new files would cause duplicate symbol errors.

These files must be `git rm`'d in the same commit:
- `cpp/llama-sampling.h`
- `cpp/llama-sampling.cpp`

### Files NOT needing changes

| File | Reason |
|------|--------|
| `cpp/llama-grammar.cpp` | Copied from upstream by bootstrap.sh; new upstream already includes `llama-sampler.h` |
| `ios/CMakeLists.txt` | Uses glob pattern `file(GLOB LLAMA_FILES ${SOURCE_DIR}/llama*.cpp)` |
| `android/.../CMakeLists.txt` | Also uses glob patterns |
| `llama-rn.podspec` | Uses `s.source_files = "cpp/**/*.{h,cpp,hpp,c,m,mm}"` |
| `common/sampling.{h,cpp}` | Different file (higher-level sampler wrapper), not renamed |

---

## Verification

After the fix, the sync-llama-cpp CI workflow should:
1. Successfully update the submodule
2. Run bootstrap.sh without errors
3. Build Android and iOS libraries
4. Create a sync PR

---

## Acceptance Criteria

- [ ] `scripts/bootstrap.sh` references `llama-sampler` instead of `llama-sampling`
- [ ] Old `cpp/llama-sampling.{h,cpp}` files removed from repo
- [ ] PR opened against `mybigday/llama.rn` upstream

---

## Commit Message

```
fix(scripts): rename llama-sampling to llama-sampler in bootstrap.sh

Upstream llama.cpp PR #19363 renamed llama-sampling.{h,cpp} to
llama-sampler.{h,cpp}. Update the bootstrap copy commands and
remove the old files to fix the sync-llama-cpp CI workflow.
```

---

## Progress Tracking

| Step | Status | Notes |
|------|--------|-------|
| Story approved | DONE | |
| Change implemented | DONE | commit 48915c6 |
| PR created | DONE | https://github.com/mybigday/llama.rn/pull/290 |
