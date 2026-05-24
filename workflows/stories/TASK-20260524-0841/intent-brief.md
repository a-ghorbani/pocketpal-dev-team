# Intent: Fix iOS Release CI archive failing on fmt consteval errors after GitHub Xcode bump

## Metadata

- **Task ID**: TASK-20260524-0841
- **Source**: prompt
- **Worktree**: `./worktrees/TASK-20260524-0841`
- **Branch**: `feature/TASK-20260524-0841`
- **Complexity**: quick
- **Native Changes**: YES
- **Visual Confirmation**: NO
- **Created**: 2026-05-24
- **Status**: approved

---

## Request

Fix iOS Release CI build failure: fmt consteval errors after GitHub Actions Xcode bump (26.2 → 26.4.1 / clang 21).

### Symptom
`build_ios` / `build-ios` job fails during archive (and sometimes simulator build) with:

```
ios/Pods/fmt/include/fmt/format-inl.h:59:24
error: call to consteval function
  'fmt::basic_format_string<char, ...>::basic_format_string<FMT_COMPILE_STRING, 0>'
  is not a constant expression
  59 |     fmt::format_to(it, FMT_STRING("{}{}"), message, SEP);
```

Same in `ios/Pods/fmt/src/format.cc:60`. Ends with `** ARCHIVE FAILED ** (2 failures)`.

### Cause
GitHub bumped the `macos-26-arm64` runner image between 2026-05-22 and 2026-05-23:
- Last green: `macos-26-arm64/20260427.0026` — Xcode 26.2
- Now: `macos-26-arm64/20260520.0098` — Xcode 26.4.1

Xcode 26.4.1 ships Apple clang 21, which tightens `consteval` constant-expression rules. The fmt library vendored by React Native uses `FMT_STRING(...)` macros that worked under clang in 26.2 but no longer satisfy the stricter rules. Not a code regression on our side — environmental change in GitHub's runner image. PR #709 / #737 builds passed on the old image; subsequent runs on main fail on the new image with the same source.

### Fix (proposed, but planner should verify against current Podfile structure)
Add inside the existing `post_install do |installer|` block in `ios/Podfile`:

```ruby
installer.pods_project.targets.each do |target|
  if target.name == 'fmt'
    target.build_configurations.each do |config|
      config.build_settings['CLANG_CXX_LANGUAGE_STANDARD'] = 'c++17'
    end
  end
end
```

`consteval` only exists in C++20, so dropping fmt to C++17 skips the broken code path; fmt falls back to runtime format-string validation. Only affects the fmt pod, not the rest of the app.

Alternative (equivalent): keep fmt at C++20 but add `FMT_USE_CONSTEVAL=0` to `GCC_PREPROCESSOR_DEFINITIONS` on the fmt target.

### Why this approach
- Community-converged workaround referenced in RN, Expo, and fmt upstream issues
- Repo-local — works for every contributor and every CI run regardless of which Xcode is on the runner
- Scoped to fmt pod only
- Reversible — when RN ships a fmt bump that handles clang 21, the hook can be deleted

### Upstream tracking
- facebook/react-native#55601 — canonical RN tracking; subscribe for "when can I remove the workaround"
- expo/expo#44229 — Expo's tracking
- fmtlib/fmt#4740 — fmt upstream; the real fix will be RN vendoring a newer fmt

### Acceptance criteria
- iOS Release archive succeeds on current `macos-26-arm64` runner
- iOS Debug / simulator builds still succeed
- No change to non-fmt pods' C++ standard
- Open a follow-up GitHub issue in pocketpal-ai repo titled "Remove fmt C++17 downgrade in ios/Podfile when RN ships clang-21-compatible fmt" linking to RN#55601

### Constraints
- `NATIVE_CHANGES=YES` (Podfile change) — must run `pod install`, iOS build, Android build before ready
- Estimated ~10 minutes of work; likely **quick** complexity (1–3 files: `ios/Podfile`, possibly `ios/Podfile.lock` if pod install regenerates)
- No new contract; existing flow doc coverage is N/A — this is build config

---

## Clarifications

none — request was clear; diagnosis, proposed fix, and acceptance criteria are concrete.
