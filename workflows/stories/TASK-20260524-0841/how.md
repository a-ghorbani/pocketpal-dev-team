# Implementation Plan: Pin fmt pod to C++17 in ios/Podfile to fix clang-21 consteval errors

**Purpose**: land the Podfile workaround that unblocks the iOS Release build on the new `macos-26-arm64` runner image (Xcode 26.4.1 / Apple clang 21), and open the upstream-tracking follow-up issue so the workaround can be removed when RN ships a clang-21-compatible fmt.

This is a **quick** task. There is no `what.md`; the design source is the intent brief itself.

---

## Metadata

- **Task ID**: TASK-20260524-0841
- **Worktree**: `/Users/aghorbani/codes/pocketpal-dev-team/worktrees/TASK-20260524-0841`
- **Branch**: `feature/TASK-20260524-0841`
- **Native Changes**: YES (Podfile)
- **Visual Confirmation**: NO (build-config only; no UI surface)
- **Intent Brief**: `./workflows/stories/TASK-20260524-0841/intent-brief.md`
- **WHAT**: n/a (quick)
- **Architecture doc(s) being updated**: n/a (this is CI/build config, not a product flow; no doc in `context/architecture/` covers iOS pod build settings)
- **Status**: draft

---

## Progress Tracking

| Step | Status | Commit | Notes |
| --- | --- | --- | --- |
| Step 1 (Podfile patch) | DONE | cd63e36 | fmt-target loop added inside existing `post_install` block; `ruby -c` passed |
| Step 2 (pod install) | DONE | cd63e36 | Podfile.lock diff was the predicted single-line PODFILE CHECKSUM update; fmt target's Debug/Release/Profiling configs all show `CLANG_CXX_LANGUAGE_STANDARD = "c++17"` in `Pods.xcodeproj/project.pbxproj` |
| Step 3 (iOS sim Release build) | DONE | n/a | local `yarn ios:build:e2e` PASS in 291s, "Build Succeeded", zero consteval / fmt errors. Local Xcode is 26.0.1 / clang < 21, so this build does NOT reproduce the original failure pre-fix; the canonical pass for AC #1 is the CI `build-ios` run on the pushed branch against `macos-26-arm64/Xcode 26.4.1+`. |
| Step 4 (iOS Debug build) | DONE | n/a | local `yarn ios:build` PASS in 131s, "Build Succeeded", zero errors, no fmt warnings |
| Step 5 (Android Release build) | DONE | n/a | `yarn build:android:release` "BUILD SUCCESSFUL" in 4m 23s; AAB produced at `android/app/build/outputs/bundle/prodRelease/app-prod-release.aab` |
| Step 6 (open follow-up issue) | DONE | n/a | https://github.com/a-ghorbani/pocketpal-ai/issues/738 — title and body match Step 6 spec verbatim |

---

## Affected Files

| Path | Change kind | Source reference |
| --- | --- | --- |
| `ios/Podfile` | edit (insert 7 lines inside existing `post_install`) | intent-brief "Fix" |
| `ios/Podfile.lock` | possible regeneration by `pod install` | intent-brief "Constraints" |

No other files are touched. App code, Android config, scripts, and tests are out of scope.

---

## Design decisions (locked here so the implementer makes none)

### D1. C++17 standard downgrade, not the preprocessor define

The intent brief lists two equivalent fixes:

- **Primary**: `CLANG_CXX_LANGUAGE_STANDARD = c++17` on the fmt target.
- **Alternative**: `FMT_USE_CONSTEVAL=0` in `GCC_PREPROCESSOR_DEFINITIONS` on the fmt target.

**Decision: take the primary (C++17 downgrade).** Rationale: it's the community-converged form in facebook/react-native#55601 / expo/expo#44229 and is what other RN apps land — the implementer can lift the snippet verbatim, search engines surface the same snippet during future debugging, and the failure mode if mis-applied is loud (compile error) rather than a quiet runtime behaviour change. The preprocessor define touches fmt's compile-time validation semantics, which is more invasive to reason about for an equivalent outcome.

### D2. Exact patch placement

The current `post_install do |installer|` block in `ios/Podfile` spans **lines 74-82** and contains a single statement: a call to `react_native_post_install(...)`. The fmt loop is added immediately **after** that call, inside the same block (so it runs once `react_native_post_install` has finished mutating the project). Verified in this worktree (`ios/Podfile` lines 74-82).

Exact diff the implementer applies:

```diff
   post_install do |installer|
     # https://github.com/facebook/react-native/blob/main/packages/react-native/scripts/react_native_pods.rb#L197-L202
     react_native_post_install(
       installer,
       config[:reactNativePath],
       :mac_catalyst_enabled => false,
       # :ccache_enabled => true
     )
+
+    # Workaround: pin the fmt pod to C++17 so it skips the consteval code path
+    # that Apple clang 21 (Xcode 26.4.1) rejects. Tracking facebook/react-native#55601.
+    # Remove once RN vendors a fmt release that is clang-21-compatible.
+    installer.pods_project.targets.each do |target|
+      if target.name == 'fmt'
+        target.build_configurations.each do |config|
+          config.build_settings['CLANG_CXX_LANGUAGE_STANDARD'] = 'c++17'
+        end
+      end
+    end
   end
```

### D3. Podfile.lock handling

`pod install` may or may not produce a `Podfile.lock` diff:

- **Most likely**: no diff. Build settings overrides do not change the resolved pod graph or checksums — `Podfile.lock` is a function of the Podfile's pod declarations and resolved versions, neither of which we touch. The current `Podfile.lock` already pins `fmt (11.0.2)` (verified: `Podfile.lock` line 36).
- **Possible**: the trailing `PODFILE CHECKSUM` line changes because the Podfile bytes changed. CocoaPods recomputes this whenever the source Podfile differs.

**Handling**: commit any `ios/Podfile.lock` changes alongside the Podfile change in the same commit. Do **not** revert lock-file changes; do **not** create a separate commit for them. If pod install produces unexpected churn beyond `PODFILE CHECKSUM` (e.g. version bumps, new dependencies), stop and report — that signals an environment problem, not normal behaviour.

---

## Implementation Steps

### Step 1: Add fmt-target C++17 override to `ios/Podfile`'s `post_install`

**Implements**: intent-brief "Fix" + decision D1 + decision D2.

**Files**:

- `ios/Podfile` — insert the fmt-target loop inside the existing `post_install do |installer|` block, immediately after the `react_native_post_install(...)` call, separated by one blank line. Apply the diff in D2 exactly.

**Approach**: open `ios/Podfile`, locate the `post_install` block at lines 74-82, insert the 12-line block (blank line + 3-line comment + 7-line loop) after the closing `)` of `react_native_post_install`. Preserve existing indentation (4 spaces inside the block, matching the surrounding code). Include the inline comment exactly as written — it cites the upstream tracking issue so future maintainers know where to check for removability.

**Verification**:

- `git diff ios/Podfile` shows the additions in D2 verbatim and no other changes.
- `ruby -c ios/Podfile` (syntax check) prints `Syntax OK`.

**Commit**: `fix(ios): pin fmt pod to C++17 to fix clang-21 consteval errors`

---

### Step 2: Run `pod install` to regenerate Pods project with the new build setting

**Implements**: intent-brief "Constraints" + decision D3.

**Files**:

- `ios/Podfile.lock` — may regenerate (see D3); commit any resulting diff alongside the Podfile change.
- `ios/Pods/` — regenerated; gitignored, not committed.

**Approach**: from the worktree root, `cd ios && pod install && cd ..`. Inspect `git status` — if `ios/Podfile.lock` changed, `git add ios/Podfile.lock` and amend it into the Step-1 commit (or include both files in a single commit if Step 1 hasn't been committed yet). If no Podfile.lock diff appears, that's expected and fine.

**Verification**:

- `pod install` exits 0 and prints `Pod installation complete!`.
- The fmt target now has `CLANG_CXX_LANGUAGE_STANDARD = c++17`: confirm with
  ```bash
  /usr/libexec/PlistBuddy -c "Print" ios/Pods/Pods.xcodeproj/project.pbxproj 2>/dev/null | grep -A 2 -B 2 "fmt" | head -40
  ```
  or open `ios/Pods/Pods.xcodeproj` in Xcode → fmt target → Build Settings → "C++ Language Dialect" reads "C++17 [-std=c++17]" for both Debug and Release.
- `git status` shows only `ios/Podfile` and (optionally) `ios/Podfile.lock` modified. No Pods/ churn (Pods/ is gitignored).

---

### Step 3: Native verification — iOS Release simulator build (originally failing path)

**Implements**: AC "iOS Release archive succeeds on current `macos-26-arm64` runner". Note that locally on the implementer's machine, the failing path is reproduced by the **CI Release-on-simulator build** (`.github/workflows/ci.yml` lines 360-378) — `yarn ios:build:e2e` runs the same `xcodebuild` invocation. If the implementer's local Xcode is 26.4.1+/clang 21, this build will reproduce the failure pre-fix and must succeed post-fix. If their local Xcode is older, the local pass is necessary but not sufficient — the **real verification is the GitHub Actions `build-ios` job** once the branch is pushed.

**Files**: none (build-only).

**Approach**:

```bash
cd "${WORKTREE_PATH}"
yarn ios:build:e2e
```

This invokes `xcodebuild -configuration Release -sdk iphonesimulator` — the same configuration CI uses. Capture stdout to a log (`yarn ios:build:e2e 2>&1 | tee /tmp/ios-build-e2e.log`) so any failure can be greped for `error:`.

**Verification**:

- Exit code 0; the log ends with `** BUILD SUCCEEDED **` (xcpretty may format this as a green checkmark).
- `grep -i "consteval" /tmp/ios-build-e2e.log` returns nothing (no fmt consteval errors).
- `grep -i "fmt/include/fmt/format-inl.h:.*error" /tmp/ios-build-e2e.log` returns nothing.
- **Push the branch** so CI runs `build-ios` against the actual `macos-26-arm64/Xcode 26.4.1` image; the green CI run is the canonical pass for this AC.

---

### Step 4: Native verification — iOS Debug build (no-regression on the dev path)

**Implements**: AC "iOS Debug / simulator builds still succeed".

**Files**: none (build-only).

**Approach**:

```bash
cd "${WORKTREE_PATH}"
yarn ios:build
```

This invokes `xcodebuild -configuration Debug -sdk iphonesimulator -arch $(uname -m)` (see `package.json` `ios:build` script). It exercises the path a contributor would hit when running `yarn ios` locally.

**Verification**:

- Exit code 0; build succeeds.
- No new fmt-related warnings or errors in the log compared with the pre-change baseline (the Step-1 change is scoped to the fmt target's C++ standard; other pods are untouched).
- `grep -i "warning.*fmt" build log` is unchanged or empty.

---

### Step 5: Native verification — Android Release build (no-regression, cross-platform requirement)

**Implements**: AGENTS.md non-negotiable: "`NATIVE_CHANGES=YES` requires `pod install` + iOS build + Android build before the work can be called ready." The change is iOS-only; the Android build is purely a no-regression sanity check.

**Files**: none (build-only).

**Approach**:

```bash
cd "${WORKTREE_PATH}"
yarn build:android:release
```

This invokes `cd android && ./gradlew bundleRelease`. Since the Podfile change does not touch any Android-relevant file, this should pass without surprises.

**Verification**:

- Exit code 0; Gradle prints `BUILD SUCCESSFUL`.
- AAB produced at `android/app/build/outputs/bundle/prodRelease/app-prod-release.aab` (or the equivalent default output for the project).
- If this fails, the failure is **not** caused by this change — investigate as a separate concern and surface to the orchestrator rather than reverting Step 1.

---

### Step 6: Open upstream-tracking follow-up issue in pocketpal-ai

**Implements**: AC #4 "Open a follow-up GitHub issue in pocketpal-ai repo titled 'Remove fmt C++17 downgrade in ios/Podfile when RN ships clang-21-compatible fmt' linking to RN#55601".

**Files**: none (GitHub issue creation, off-repo).

**Approach**: from the worktree directory, run `gh issue create` against the `a-ghorbani/pocketpal-ai` repo (the worktree's `origin`, verified). Capture the issue URL into the PR body when the implementer/reviewer pipeline opens the PR for this branch.

```bash
gh issue create \
  --repo a-ghorbani/pocketpal-ai \
  --title "Remove fmt C++17 downgrade in ios/Podfile when RN ships clang-21-compatible fmt" \
  --body "$(cat <<'BODY'
The `ios/Podfile` `post_install` block currently pins the `fmt` pod to `CLANG_CXX_LANGUAGE_STANDARD = c++17` to work around clang-21 (Xcode 26.4.1) rejecting fmt's `consteval` code path. This was landed in TASK-20260524-0841 to unblock the iOS Release CI build after the GitHub `macos-26-arm64` runner image bumped from Xcode 26.2 to 26.4.1.

The workaround should be removed once React Native vendors a `fmt` release that compiles cleanly under Apple clang 21.

**Upstream tracking**:
- React Native: https://github.com/facebook/react-native/issues/55601 (canonical)
- Expo: https://github.com/expo/expo/issues/44229
- fmt: https://github.com/fmtlib/fmt/issues/4740

**Removal criteria**: after a React Native upgrade where the vendored `fmt` is known to be clang-21-compatible (watch RN#55601 for the resolution commit), delete the fmt-target loop in `ios/Podfile`'s `post_install` block and verify the iOS Release build still passes.

Generated by [PocketPal Dev Team](https://github.com/a-ghorbani/pocketpal-dev-team)
BODY
)"
```

**Verification**:

- Command prints a URL of the form `https://github.com/a-ghorbani/pocketpal-ai/issues/<n>`.
- `gh issue view <n> --repo a-ghorbani/pocketpal-ai` shows the title and body as written.
- Record the issue URL in the implementer's hand-off so the pipeline-reviewer can reference it in the PR description.

This step does **not** add a label; it inherits whatever default applies. If the repo's convention requires `[Bug]` / `[Feat]` style title prefixes (per AGENTS.md GitHub conventions), the title remains untagged because this is a tracking/cleanup issue, not a bug or feature request — title clarity outweighs prefix consistency here.

---

## Testable-Contract Coverage

Since this is a **quick** task with no WHAT, the testable contract is the acceptance criteria from `intent-brief.md`:

| Contract item (intent-brief AC) | Verified by |
| --- | --- |
| iOS Release archive succeeds on current `macos-26-arm64` runner | Step 3 (local `yarn ios:build:e2e`) + CI `build-ios` green on the pushed branch |
| iOS Debug / simulator builds still succeed | Step 4 (`yarn ios:build`) |
| No change to non-fmt pods' C++ standard | Step 2 manual inspection (only the `fmt` target build configs are mutated; the loop's `if target.name == 'fmt'` guard scopes the change) |
| Follow-up GitHub issue opened in pocketpal-ai | Step 6 (`gh issue create` → URL recorded) |

There are no unit tests added or modified — this is a build-config change with no JS/TS surface area. The Jest suite is unaffected; running `yarn test` is optional and only useful as a sanity check that the working tree wasn't accidentally disturbed.

---

## Native Verification (NATIVE_CHANGES=YES)

```bash
cd "${WORKTREE_PATH}"
cd ios && pod install && cd ..        # Step 2
yarn ios:build:e2e                     # Step 3 — Release simulator (originally failing path)
yarn ios:build                         # Step 4 — Debug simulator (no-regression)
yarn build:android:release             # Step 5 — Android Release (cross-platform requirement)
```

All four commands must exit 0 before the work is considered "ready". Skipping any of them is a blocking review issue per AGENTS.md.

The CI `build-ios` job on the pushed branch is the canonical pass for the AC; the local Release build is the implementer's smoke test (and reproduces the failure pre-fix iff their local Xcode is 26.4.1+).

---

## Visual Confirmation

Not applicable. Visual Confirmation = NO. This change has no UI surface; no screenshots are produced.

---

## Deferred Items

The intent brief defers nothing explicitly. The fmt C++17 downgrade itself is **intentionally temporary** — its removal is tracked by the follow-up issue opened in Step 6, not deferred to this story. Once RN ships a clang-21-compatible fmt, a separate story will remove the Podfile block.

---

## What this plan is NOT

- not a design doc — this is a one-line Podfile workaround; the "design" is the community-converged fix cited in the intent brief.
- not a justification — `intent-brief.md` holds the diagnosis and rationale.
- not a CI workflow change — `.github/workflows/ci.yml` and `release.yml` are unchanged; only the Podfile is patched.
- not an Android change — the Step-5 Android build is a no-regression check mandated by the NATIVE_CHANGES policy, not a code change.
- not a test addition — there is no JS/TS surface to test; verification is via builds.

---

## Review History

| Round | Critic verdict | Notes |
| --- | --- | --- |
| 1 | LGTM | plan-critic approved with no required changes |

---

## Outcome

- **PR**: [a-ghorbani/pocketpal-ai#739](https://github.com/a-ghorbani/pocketpal-ai/pull/739) — Merged 2026-05-24 (commit `4a04609`)
- **Follow-up tracking issue**: [a-ghorbani/pocketpal-ai#738](https://github.com/a-ghorbani/pocketpal-ai/issues/738) — remove the C++17 downgrade when RN ships clang-21-compatible fmt (subscribe to facebook/react-native#55601)
- **Canonical AC #1 verification**: CI `build-ios` green on `macos-26-arm64/20260520.0098.1` with Xcode 26.4.1 — the originally failing toolchain

---

## Implementation Notes

- **Local Xcode version**: 26.0.1 (build 17A400). This is older than the broken runner image (Xcode 26.4.1 / clang 21), so the local Release build (Step 3) does **not** reproduce the original consteval failure pre-fix. The local pass confirms the patch does not introduce regressions on Xcode 26.0; the canonical pass for AC #1 ("iOS Release archive succeeds on current `macos-26-arm64` runner") is the CI `build-ios` job once this branch is pushed.
- **Podfile.lock churn**: exactly one line changed (`PODFILE CHECKSUM`), as decision D3 predicted. Committed alongside the Podfile change in the same commit.
- **fmt-target verification**: `Pods.xcodeproj/project.pbxproj` shows `CLANG_CXX_LANGUAGE_STANDARD = "c++17"` on all three fmt build configurations (Debug, Release, Profiling); the per-target setting takes precedence over the unchanged xcconfig defaults.
- **PocketPalTests CocoaPods warnings**: pre-existing, unrelated to this change — they reference the PocketPalTests target's own C++ standard override, not the fmt pod.
- **Branch state**: implementer leaves the branch **un-pushed** per the implementer brief; the pipeline-reviewer will push and open the draft PR.
