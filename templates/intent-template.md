# Intent Brief: <one-line summary>

**Purpose**: capture **what** the user is trying to accomplish and **why**, before any design or implementation begins. This brief is the contract between the requester and the team.

If anything below is unclear from the issue / request, the orchestrator **asks the human** before passing the brief downstream. Open questions block the pipeline until answered.

---

## Metadata

- **Task ID**: TASK-YYYYMMDD-HHMM
- **Issue / Source**: <link or "prompt">
- **Worktree**: `./worktrees/TASK-YYYYMMDD-HHMM`
- **Branch**: `feature/TASK-YYYYMMDD-HHMM`
- **Complexity**: trivial | quick | standard | complex
- **Native Changes**: YES | NO
- **Visual Confirmation**: YES | NO
- **Created**: YYYY-MM-DD
- **Status**: draft | answered | approved

---

## Goal

One paragraph. What is the user trying to accomplish? Why does it matter? Avoid jargon; a future contributor reading this in six months should understand the motivation.

---

## Acceptance Criteria

Testable bullets. Each should be a concrete observable outcome — something a test or a manual check can verify.

- [ ] **AC-1**: When <input>, the user sees <output>.
- [ ] **AC-2**: When <input>, the system produces <state change>.
- [ ] **AC-3**: <other testable claim>.

Bad acceptance criteria look like "the code is clean" or "performance is good." Good acceptance criteria look like "user types `/help` and a tooltip listing 5 commands appears within 200 ms."

---

## Constraints

What must be true. The implementation cannot violate these.

- **Performance**: <budget — "no extra re-renders per token", "TTFT under 300 ms", etc.>
- **Native targets**: <"iOS 16+ / Android 9+", or "no native changes">
- **Compatibility**: <"backward-compatible with chats persisted before v1.13", or N/A>
- **Localisation**: <"all new strings go through l10n", or N/A>
- **Other**: <code freeze windows, security gates, etc.>

---

## Non-Goals

What the team will explicitly NOT do as part of this work. Scope guard.

- <"This story does not introduce voice input">
- <"This story does not refactor the model loading screen">
- <"This story does not change the DB schema">

---

## Open Questions (block until answered)

Anything ambiguous from the issue / request. The orchestrator pauses here until the human answers each one.

- **Q1**: <question>?
  - **Answer**: <human's answer, or "PENDING">
- **Q2**: <question>?
  - **Answer**: <human's answer, or "PENDING">

When all questions are answered, the brief moves to `Status: answered`. When the human gives an explicit OK on the brief as a whole, it moves to `Status: approved` and the next pipeline stage runs (architect for standard/complex, planner for quick, implementer for trivial).

---

## What this brief is NOT

- not a design doc — the architect produces `what.md`
- not an implementation plan — the planner produces `how.md`
- not a record of conversation — keep ambiguity in Open Questions, not in narrative prose
