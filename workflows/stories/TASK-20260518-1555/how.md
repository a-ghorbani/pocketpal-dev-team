# Implementation Plan: Upgrade llama.rn to 0.12.1

**Purpose**: an executable worklist that lands the dependency bump described in `intent-brief.md`. This is a **quick** story — there is no `what.md`; the design source is `intent-brief.md` plus `context/architecture/chat-flow.md`. Steps reference the intent brief's acceptance criteria (AC1–AC5) and the established llama.rn upgrade pattern (reference commits `0614148`, `f91144d`, `d4130b4`).

This file lives at `workflows/stories/TASK-20260518-1555/how.md`.

---

## Metadata

- **Task ID**: TASK-20260518-1555
- **Worktree**: `./worktrees/TASK-20260518-1555`
- **Branch**: `feature/TASK-20260518-1555`
- **Native Changes**: YES
- **Visual Confirmation**: NO
- **Intent Brief**: `./workflows/stories/TASK-20260518-1555/intent-brief.md`
- **WHAT**: n/a (quick complexity — no what.md)
- **Architecture doc(s) being updated**: none expected — see "Architecture Doc Impact" below
- **Status**: done

---

## Baseline Reconciliation (read first)

- **Requested frame**: 0.12.0-rc.9 → 0.12.1.
- **Actual `origin/main` baseline**: llama.rn **`0.12.0` stable** — already merged via PR #722, commit `d4130b4`. Confirmed in the worktree: `package.json:53` is `"llama.rn": "0.12.0"`; `ios/Podfile.lock` shows `llama-rn (0.12.0)`; `yarn.lock:6518` resolves `llama.rn@0.12.0`.
- **Effective app-facing upgrade**: **0.12.0 (stable) → 0.12.1**. Plan the dependency edit on this basis.
- **Upstream-delta summary scope (AC4)**: still spans the full requested range **0.12.0-rc.9 → 0.12.1** (per the brief), but the deliverable must explicitly state PocketPal's app baseline is already 0.12.0 stable, so the *effective* app-facing delta is **0.12.0 → 0.12.1**.
- **Target published**: confirmed — `npm view llama.rn@0.12.1 version` → `0.12.1`, tarball `https://registry.npmjs.org/llama.rn/-/llama.rn-0.12.1.tgz`.
- This is a reconciliation note from the brief's Clarifications section, **not an open question**. No input required.

---

## Progress Tracking

| Step | Status | Commit | Notes |
| --- | --- | --- | --- |
| Step 1 — Bump dependency + lockfiles | done | - | `package.json` and `yarn.lock` updated to `llama.rn 0.12.1`. |
| Step 2 — Refresh iOS Podfile.lock | done | - | `ios/Podfile.lock` now resolves `llama-rn (0.12.1)` with a new checksum. |
| Step 3 — Verify native integration surface | done | - | No consumer-side app code changes were required beyond the expected dependency files. |
| Step 4 — Native verification (pod install + iOS + Android build) | done | - | `bundle exec pod install`, `yarn ios:build`, and `yarn build:android` all passed. |
| Step 5 — Targeted regression coverage | done | - | Existing llama.rn-facing Jest suites passed with the worktree env loaded and coverage disabled. |
| Step 6 — llama.cpp change summary deliverable | done | - | Captured in `reviewer-evidence.md`. |
| Architecture doc updated | n/a | - | none expected — conditional, see Step 3 / Architecture Doc Impact |
| Cleanup reminders applied | n/a | - | none (no diagnostic code introduced) |

---

## Affected Files

| Path | Change kind | Reference |
| --- | --- | --- |
| `package.json` | edit (line 53: `"llama.rn": "0.12.0"` → `"0.12.1"`) | AC1, pattern: `d4130b4` |
| `yarn.lock` | edit (regenerated `llama.rn@0.12.1` block: version, resolved, integrity) | AC1, pattern: `d4130b4` |
| `ios/Podfile.lock` | edit (`llama-rn (0.12.0)` → `(0.12.1)`, dependency line, checksum) | AC2, pattern: `d4130b4` |
Expected diff footprint (per reference commits `0614148`, `f91144d`, `d4130b4`): `package.json` (~1 line), `yarn.lock` (~4–8 lines), `ios/Podfile.lock` (~3–4 lines). Step 3 confirmed no additional consumer-side files were required by `0.12.1`.

---

## Testable-Contract Coverage

This is a **quick** story (no WHAT). User-visible outcomes implied by `intent-brief.md`:

| Contract item (from intent brief) | Verified by |
| --- | --- |
| AC1 — `package.json` + lockfiles cleanly at llama.rn 0.12.1 | Step 1 + Step 2; `git diff` review; `yarn install --frozen-lockfile` clean |
| AC2 — required iOS/Android native integration applied | Step 2 (`ios/Podfile.lock`) + Step 3 (jniLibs/JSI surface check) |
| AC3 — pod install + iOS build + Android build + smallest sensible regression | Step 4 (native builds, in worktree) + Step 5 (targeted existing llama.rn-facing Jest suites) |
| AC4 — itemized llama.cpp change summary (0.12.0-rc.9 → 0.12.1) | Step 6 → `reviewer-evidence.md` |
| AC5 — STOP & report if upstream needs broader app changes / blockers | Step 3 STOP condition; Step 4/5 failure handling |

App-behavior regression surface for this llama.rn patch bump is covered by existing tests that exercise the dependency-facing model init, completion-setting / chat-format defaults, and automation / init-log wiring. No new app tests were added because the PR changes no PocketPal source files.

---

## Implementation Steps

### Step 1: Bump llama.rn to 0.12.1 in package.json and regenerate yarn.lock

**Implements**: intent brief AC1. Pattern: reference commits `0614148`, `f91144d`, `d4130b4` (each touches only `package.json` + `yarn.lock` + `ios/Podfile.lock`).

**Files**:

- `package.json` — line 53: `"llama.rn": "0.12.0"` → `"llama.rn": "0.12.1"` (exact pin, no caret — on-pattern with current entry).
- `yarn.lock` — regenerate the `llama.rn@0.12.1:` block (`version`, `resolved` tarball URL, `integrity` sha512) via the package manager, not by hand.

**Approach**: Edit the single version string in `package.json`. Run `yarn install` in the worktree to resolve `llama.rn@0.12.1` and rewrite the lockfile entry. Inspect `git diff yarn.lock` — it must be confined to the `llama.rn` block (version/resolved/integrity); any wider lockfile churn means an unintended transitive change and must be reviewed before proceeding.

**Verification**:

- `git diff package.json` shows exactly the one-line version change.
- `git diff yarn.lock` is confined to the `llama.rn@0.12.1` block.
- `yarn install --frozen-lockfile` succeeds (lockfile internally consistent).
- `yarn typecheck` and `yarn lint` pass (no app source changed; sanity gate only).

### Step 2: Refresh iOS Podfile.lock for llama-rn 0.12.1

**Implements**: intent brief AC1, AC2 (iOS native integration). Pattern: `d4130b4` (`ios/Podfile.lock` +/- the `llama-rn` version, dependency line, and SPEC CHECKSUM).

**Files**:

- `ios/Podfile.lock` — `llama-rn (0.12.0)` → `llama-rn (0.12.1)`, the `llama-rn (from ...)` dependency entry, and the `llama-rn:` SPEC CHECKSUM line (line ~3723).

**Approach**: After Step 1's `yarn install`, run `pod install` from `worktrees/TASK-20260518-1555/ios` (CocoaPods reads the pod from `../node_modules/llama.rn`). Let CocoaPods rewrite `Podfile.lock`. Confirm the diff is limited to `llama-rn` version, dependency, and checksum lines (and any mechanical re-pin of the Pods checksum) — consistent with `d4130b4`.

**Verification**:

- `git diff ios/Podfile.lock` is confined to `llama-rn` version/dependency/checksum lines.
- `pod install` completes without error (captured in Step 4 evidence).

### Step 3: Verify the 0.12.1 native-integration surface (no hidden extra changes)

**Implements**: intent brief AC2 + AC5 (don't assume; verify). Brief explicitly says to verify against the actual 0.12.1 release (prebuilt jniLibs, JSI binding changes) rather than assuming the 3-file pattern blindly.

**Files**: none edited in this step — it is a verification gate. (If it finds required changes, those land here and the diff footprint section above is amended.)

**Approach**: After `yarn install`, confirm Android uses prebuilt binaries shipped in the npm package — `android/gradle.properties` keeps `rnllamaBuildFromSource` commented out (verified: lines 41–42 in the worktree), so no manual jniLibs vendoring or version pin is needed; `yarn install` pulls the correct prebuilt `.so`/`.aar` from `node_modules/llama.rn`. Diff the JS-facing API surface between the installed 0.12.0 and 0.12.1 packages (`node_modules/llama.rn` `lib/`/`src/` typings and any podspec/`build.gradle` inside the package) for breaking signature or build-config changes. Cross-check the upstream llama.rn 0.12.1 release notes / changelog for native-integration-affecting items.

**STOP condition (AC5)**: If 0.12.1 requires consumer-side changes beyond the documented 3 files (e.g. changed JSI method signatures PocketPal calls, new required Podfile/Gradle config, removed/renamed exports used by `src/`), STOP and report explicitly with the specific upstream change and the PocketPal call sites affected. Do not invent app-side fixes — this is a quick dependency bump; a broader surface means re-scoping.

**Verification**:

- Documented finding: "0.12.1 native surface vs 0.12.0 — no consumer changes required beyond package.json/yarn.lock/Podfile.lock" OR an explicit STOP report.
- `android/gradle.properties` `rnllamaBuildFromSource` remains commented (prebuilt path unchanged).

### Step 4: Native verification — pod install + iOS build + Android build (in worktree)

**Implements**: intent brief AC3, constraint `NATIVE_CHANGES=YES`. All builds run **inside `worktrees/TASK-20260518-1555`** — never `repos/pocketpal-ai` (read-only submodule).

**Files**: none — verification only. May regenerate build caches inside the worktree only.

**Approach**: From the worktree root, run the native verification block (see "Native Verification" section). Capture pass/fail and key log lines (especially first-token / model-load success on at least one model) as durable evidence for the pipeline reviewer.

**Verification**: see "Native Verification" section. Skipping this is a blocking review issue. Any build failure traceable to 0.12.1 → STOP and report (AC5).

### Step 5: Run targeted regression coverage for llama.rn-facing surfaces

**Implements**: intent brief AC3 ("smallest sensible regression coverage for llama.rn initialization / chat formatting / structured-output behavior").

**Files**: none — verification only.

**Approach**: Run the narrowest existing test files that touch the changed dependency surface. Because this repo's default Jest config forces broad coverage collection even for file-scoped runs, load the worktree `.env` and disable coverage for these targeted commands so the signal reflects the actual dependency-facing assertions rather than unrelated coverage-threshold failures.

**Verification**:

- `src/store/__tests__/ModelStore.test.ts` passes.
- `src/utils/__tests__/completionSettingsVersions.test.ts` passes.
- `src/__automation__/screens/__tests__/BenchmarkRunnerScreen.test.tsx` passes.
- Reported results are real and reproducible (commands + summary captured).
- A genuine regression here → STOP and report (AC5).

### Step 6: Produce the itemized llama.cpp change summary deliverable

**Implements**: intent brief AC4. This is a separately-callable step and a **named deliverable**.

**Named deliverable**: `workflows/stories/TASK-20260518-1555/reviewer-evidence.md`

**Files**:

- `workflows/stories/TASK-20260518-1555/reviewer-evidence.md` — add.

**Approach**: Use upstream primary sources to enumerate the requested range **0.12.0-rc.9 → 0.12.1**. Itemize: (a) llama.rn-level release notes in that span; (b) the effective PocketPal app-facing movement (`0.12.0 -> 0.12.1`); and (c) the broader requested `llama.cpp` movement (`b8827 -> b9204`) inferred from the tagged release notes.

**Verification**:

- File exists at the named path, itemized, with the baseline-vs-effective-delta note.
- Upstream source links are captured directly in the deliverable.

---

## Native Verification (NATIVE_CHANGES=YES)

All commands run inside the worktree. Never build/install in `repos/pocketpal-ai`.

```bash
cd "/Users/aghorbani/codes/pocketpal-dev-team/worktrees/TASK-20260518-1555"

# Dependency + iOS pods (Steps 1–2)
yarn add llama.rn@0.12.1
bundle install
cd ios && bundle exec pod install && cd ..

# Native builds (Step 4)
yarn ios:build
yarn build:android

# Targeted regression coverage (Step 5)
zsh -lc 'set -a; source .env; set +a; yarn test --coverage=false --runInBand src/store/__tests__/ModelStore.test.ts'
zsh -lc 'set -a; source .env; set +a; yarn test --coverage=false --runInBand src/utils/__tests__/completionSettingsVersions.test.ts'
zsh -lc 'set -a; source .env; set +a; yarn test --coverage=false --runInBand src/__automation__/screens/__tests__/BenchmarkRunnerScreen.test.tsx'
```

Note: skipping native verification is a blocking review issue. Builds/tests must run in the worktree; the submodule is read-only.

---

## Visual Confirmation

Not applicable — Visual Confirmation=NO (dependency bump, no UI change).

---

## Architecture Doc Impact

**No architecture-doc update expected.** Reasoning:

- This is a patch-level dependency bump (0.12.0 → 0.12.1) with zero planned PocketPal source changes.
- `context/architecture/chat-flow.md` references llama.rn only at the abstract message-shape / wire-boundary level (e.g. §1b "Ours vs OpenAI / llama.rn shape", Jinja-template tool-call contract). It contains **no version pins** and describes no behavior a patch release is expected to alter.
- The other architecture docs (`agent-runner.md`, `benchmark-matrix.md`, `pals-and-talents.md`, `tts.md`) do not describe llama.rn version-specific behavior relevant to this bump.

**Conditional (per repo non-negotiable — drift is forbidden):** if Step 3 or Step 6 surfaces an upstream 0.12.1 change that alters behavior documented in any `context/architecture/*.md` (chat formatting, tool-call/structured-output contract, init semantics), the relevant doc MUST be updated **in the same PR**. In that case add the doc-update as a step and flag it in Progress Tracking. Quick stories do not silently land architecture changes — surface it; if it implies a contract change, route back to the orchestrator for re-classification.

---

## Deferred Items

None. The intent brief scopes this to a minimal dependency bump; nothing is deferred.

---

## What this plan is NOT

- not a design doc — this is quick; design source is `intent-brief.md` + `context/architecture/chat-flow.md`.
- not a justification — the request lives in `intent-brief.md`.
- not exhaustive — only the steps the implementer needs to land the bump on-pattern and verify it.
