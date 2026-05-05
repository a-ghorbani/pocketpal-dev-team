# Intent: Apply chat-flow architecture to AssistantTurn rendering

## Metadata

- **Task ID**: TASK-20260504-2320
- **Source**: prompt — follow-up to PR #709 (TASK-20260502-2115 AssistantTurn refactor)
- **Worktree**: `./worktrees/TASK-20260504-2320` *(not yet created)*
- **Branch**: `feature/TASK-20260504-2320`
- **Complexity**: complex
- **Native Changes**: NO
- **Visual Confirmation**: YES
- **Created**: 2026-05-04
- **Status**: approved

---

## Request

Follow-up to PR #709 (the AssistantTurn refactor). The foundational data shape and agent loop landed in #709, but the chat-rendering layer still has the user-visible problems the design exposes:

- duplicate timing footers (one per step instead of one per turn)
- dead zones with no indicator while the model is working between steps
- no feedback for tool calls that have no registered UI (datetime, calculate just disappear)
- hidden reasoning content
- the LoadingBubble is too loud; we want a subtle indicator
- the `streaming_followup` state contributes to the dead zone after a tool call

The full architecture (data model, invariants, scenarios, decisions D1–D8) is already drafted in `what.md`. Make the running app match that design contract.

---

## Clarifications

- **Q1**: Pulsing-indicator visual — small text caret at the end of the last bubble, or a separate dot-row indicator below the bubble?
  - **A1**: separate dot-row indicator below the bubble.
- **Q2**: Tool-used chip placement — inside the same bubble as the step's content, or as its own block between steps?
  - **A2**: no strong preference; pick whatever a good UI/UX expert would call simplest and neatest, and easy to maintain.
- **Q3**: Reasoning block expand/collapse default behaviour — collapsed or expanded?
  - **A3**: match what `main` does today. PR #709 changed that behaviour; revert it (refit onto the new data shape).
- **Q4**: Should this ship as one PR for everything in `what.md`, or split into smaller follow-up PRs?
  - **A4**: single PR.
