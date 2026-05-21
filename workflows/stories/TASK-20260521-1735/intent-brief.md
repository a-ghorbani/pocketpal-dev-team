# Intent: Non-touch trigger to start the bench E2E matrix run

**Purpose**: confirm **what** the requester wants built, before any design or implementation begins.

---

## Metadata

- **Task ID**: TASK-20260521-1735
- **Source**: prompt
- **Worktree**: `./worktrees/TASK-20260521-1735`
- **Branch**: `feature/TASK-20260521-1735`
- **Complexity**: standard
- **Native Changes**: NO
- **Visual Confirmation**: NO
- **Created**: 2026-05-21
- **Status**: approved

---

## Request

Add a non-touch way to start the bench E2E run that invokes the same handler as the on-screen "RUN BENCHMARK MATRIX" button.

CONTEXT: The bench pipeline drives the E2E APK entirely over adb except one step: starting the run. Starting requires a UI tap on "RUN BENCHMARK MATRIX", and that tap goes through Android's synthetic-input layer (adb shell input tap). On HyperOS (POCO F7 Ultra) and MediaTek (POCO X7 Pro), the OS silently drops the injected tap — the button's onPress never fires, the matrix never starts. Confirmed NOT an app bug: a real finger tap works fine, so screen/button wiring is correct; the OS rejects injected touches. Fallback chain (swipe → monkey → long-hold → off-center taps) didn't reliably break through. Result: every config on every device needs a manual human tap (~10-15 per PR validation), so runs can't be unattended.

ASK: add a non-touch trigger that calls the same handler as the button.
- Preferred: honor a deep-link param like pocketpal://e2e/benchmark?autostart=1 that immediately starts using the already-pushed bench-config.json.
- Alternatives: a broadcast-intent trigger (am broadcast -a …START_BENCH), or make the button respond to KEYCODE_ENTER so `input keyevent 66` works.

Any one makes the bench fully scriptable. This is automation-ergonomics only and does NOT change what's measured.

ACCEPTANCE CRITERIA:
- An automation script can start the benchmark matrix run on HyperOS and MediaTek devices without any human touch.
- The trigger invokes the exact same start handler the button does (same code path, same use of the already-pushed bench-config.json).
- No change to what is measured or how results are produced.

CONSTRAINTS:
- This is an E2E/benchmark harness feature. It should not affect production user-facing behavior. Confirm whether the bench screen is gated to E2E/debug builds and keep the trigger consistent with that gating.

NOTE FROM USER: Run the pipeline but do NOT create the PR. After implementation, I want to test on the locally connected devices to confirm the trigger works; only then create the PR. So produce code + commits in the worktree, but pipeline-reviewer should stop short of opening the PR.

Repository: ./repos/pocketpal-ai

---

## Clarifications

none — request was clear and self-contained, including acceptance criteria and constraints.
