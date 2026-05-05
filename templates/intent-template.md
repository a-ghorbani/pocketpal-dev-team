# Intent: <one-line summary>

**Purpose**: confirm with the human **what** they want built, before any design or implementation begins.

The brief is two things: the **request** (verbatim, not paraphrased) and any **clarifications** captured by asking the human. Nothing else. No invented acceptance criteria, no design rules, no coding conventions, no scope walls — those belong in WHAT and HOW, or already live in `context/patterns.md`.

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
- **Status**: draft | answered | approved

---

## Request

Paste the issue body or prompt **verbatim**. If the source is a link (issue, ticket), include enough of the body that the brief stands alone — a future reader shouldn't have to chase the link to know what was asked. Do not paraphrase, do not "improve", do not add framing.

If the request is a one-line prompt ("fix the typo in the welcome modal"), one line is fine.

---

## Clarifications

Only if the request was unclear. Capture the question you asked the human and their answer. Each Q must block the pipeline until answered.

If the request was already clear, omit this section or write "none".

- **Q1**: <question>?
  - **A1**: <human's answer, or "PENDING">

When all questions are answered, move `Status` to `answered`. When the human OKs the brief as a whole, move to `approved` and the next stage runs.

---

## What this brief is NOT

- not a design doc — the architect produces `what.md`
- not an implementation plan — the planner produces `how.md`
- not a place for invented acceptance criteria, performance budgets, coding conventions, or design constraints — those are downstream work or already covered by `context/patterns.md`
- not a paraphrase of the issue — paraphrasing creates a second source that drifts
