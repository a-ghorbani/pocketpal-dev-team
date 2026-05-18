# Intent: <one-line summary>

**Purpose**: confirm **what** the requester wants built, before any design or implementation begins.

The brief is two things: the **request** (verbatim, not paraphrased) and any **clarifications**. Nothing else. No invented acceptance criteria, no design rules, no coding conventions, no scope walls — those belong in WHAT and HOW, or already live in `context/patterns.md`.

This file must stand on its own. Downstream agents may not have access to the source tracker or any surrounding control-plane context.

If the request is already unambiguous, save the brief with no Clarifications and move on.

---

## Metadata

- **Task ID**: TASK-YYYYMMDD-HHMM
- **Source**: <link to issue / ticket, or "prompt" if direct>
- **Worktree**: `./worktrees/TASK-YYYYMMDD-HHMM`
- **Branch**: `feature/TASK-YYYYMMDD-HHMM`
- **Complexity**: trivial | quick | standard | complex
- **Native Changes**: YES | NO
- **Visual Confirmation**: YES | NO
- **Created**: YYYY-MM-DD
- **Status**: draft | needs-input | answered | approved

---

## Request

Paste the issue body or prompt **verbatim**. If the source is a link (issue, ticket), include enough of the body that the brief stands alone — a future reader shouldn't have to chase the link to know what was asked. Do not paraphrase, do not "improve", do not add framing.

If the request is a one-line prompt ("fix the typo in the welcome modal"), one line is fine.

---

## Clarifications

Only if the request was unclear. Capture the unresolved question and the supplied answer when available. Each Q blocks the pipeline until answered.

If the request was already clear, omit this section or write "none".

- **Q1**: <question>?
  - **A1**: <answer, or "NEEDS_INPUT">

If answers are missing in a headless run, move `Status` to `needs-input`, return `NEEDS_INPUT`, and stop. When all questions are answered, move `Status` to `answered`. When the brief is confirmed as complete, move to `approved` and the next stage runs.

---

## What this brief is NOT

- not a design doc — the architect produces `what.md`
- not an implementation plan — the planner produces `how.md`
- not a place for invented acceptance criteria, performance budgets, coding conventions, or design constraints — those are downstream work or already covered by `context/patterns.md`
- not a paraphrase of the issue — paraphrasing creates a second source that drifts
