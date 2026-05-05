# HOW Critique — Round 1

**Reviewer**: pocketpal-plan-critic
**Date**: 2026-05-05
**Verdict**: HAS_CONCERNS (1 BLOCKER, 2 CONCERNs, 2 SUGGESTIONs)

---

## Summary

The plan executes the WHAT cleanly and traces every step to a §-section. The id-reconciliation fix (Steps 3–4) is in scope and bounded. Coverage of canonical scenarios A–I and invariants I1–I4 is complete. A small set of concerns: Step 14 deviates from the template's promoted-doc shape (drops §10) and contains some loose copy, and the cross-repo architecture-doc commit is a structural concession that deserves explicit pipeline-reviewer awareness. Step 12's title undersells what it does.

## Findings

### BLOCKER 1: Step 14 instruction "Drop §10" contradicts the WHAT template

**What**: HOW Step 14 instruction #5 says drop §10 ("What this doc is NOT") in the promoted architecture doc and replace with a "Drift policy" link.

**Where**: HOW Step 14, item 5.

**Why**: `templates/what-template.md` retains §10 for both story-scoped delta AND promoted architecture doc forms. The template is canonical per `context/architecture/README.md` line 75. Dropping §10 makes the bootstrapped doc template-noncompliant; also drops the `Cleanup reminders` slot the template formalises (line 190).

**Fix**: Keep §10 intact. Optionally append a one-line link to `context/architecture/README.md`. The `DebugStatusBar` cleanup reminder paragraph is fine to drop (diagnostic absent in committed tree); `Cleanup reminders` as a section/slot stays.

### CONCERN 1: cross-repo architecture-doc commit conflicts with AGENTS.md "same PR" rule

**What**: AGENTS.md says architecture doc updates must land "in the same PR." Step 14 lands the doc in a separate commit on the dev-team repo while the code PR opens from the pocketpal-ai worktree — different repos.

**Where**: HOW Step 14.

**Why**: This is the FIRST story under the pipeline; the convention lands here. "Single PR" guarantee from intent Q4 implicitly applies to the code PR; the architecture-doc commit cannot be in that PR by construction.

**Fix**: Add a sub-step under Step 14: "Before invoking pipeline-reviewer, verify the dev-team commit at `<sha>` is referenced in the code PR description (e.g. 'Architecture doc bootstrap: dev-team@<sha>')." Pipeline-reviewer can then enforce the link.

### CONCERN 2: Step 4's hook-side accumulation duplicates work the runner has

**What**: Step 4 has the hook accumulate `tool_call_started` events into a per-step buffer and flush on `step_finished`. The runner already has the full normalized list at `AgentRunner.ts:369` (`const calls = normalizeToolCallIds(...)`).

**Where**: Step 4, AgentRunner bullet.

**Why**: Hook re-derives what the runner already produced; adds stateful buffer to `applyEventToStore`. Single-writer is cleaner if the runner attaches `calls` to the next `step_finished` event payload.

**Fix**: Extend `step_finished` event type to `{type: 'step_finished'; turn: number; toolCalls?: AgentToolCall[]}`; hook calls `appendToolCall` from `case 'step_finished'`. SHOULD, not MUST.

### CONCERN 3: Step 12's title undersells the change

**What**: Step 12 titled "Verify reasoning order + ThinkingBubble default state" but contains a real behaviour change in `Message.tsx` — split single `<TextMessage>` into two siblings (reasoning-only step + content-only step) when both present.

**Where**: Step 12 third bullet.

**Why**: A reviewer scanning step titles will see "verify" and skip. The actual diff is structural.

**Fix**: Rename Step 12 to "Split reasoning and content into separate per-step blocks (D3 + §4a)". Demote the "verify" notes (ThinkingBubble.tsx PARTIAL, MarkdownView ordering) to one-line confirmations.

### SUGGESTION 1: Step 9 — defensive test for id-match invariant

Add an assertion that `step.toolCalls[i].id === step.toolOutcomes[i].callId` holds at every render frame, not just the final. Future-proofs against subtle regressions in Step 4's writer ordering.

### SUGGESTION 2: Step 11 — surface `modelStore.isStreaming` survival in Deferred Items

`modelStore.isStreaming` continues to be separately-written for FlatList `maintainVisibleContentPosition`. Add a third Deferred bullet naming this with a one-line reason.

## Routing

HAS_CONCERNS with 1 BLOCKER → back to the planner for revision. WHAT does not need re-litigating; the design is settled.
