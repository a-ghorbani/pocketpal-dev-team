# WHAT Critique — Round 2

**Reviewer**: pocketpal-architect-critic
**Date**: 2026-05-05
**Verdict**: LGTM

---

## Summary

The architecture is the right shape and is now properly defended against alternatives. All four round-1 BLOCKERs are resolved with code-grounded evidence: the id-reconciliation gap (projectStreamChunk vs normalizeToolCallIds) is named with a concrete proposal, the duplicate-footer root cause is correctly traced to `Bubble.tsx:93–104` × `Message.tsx:288–303`, the missing-talent-UI fallback is acknowledged as new behaviour rather than legacy, and D3 pins `BubbleState.PARTIAL` to match `main`. Two minor annotation gaps and one stale-line-number cluster remain; neither blocks the planner.

## Drift spot-checks (positive)

Verified against `feature/TASK-20260504-2320` @ f3b750e:

| Claim | Verification |
|---|---|
| `updateActiveStepStreaming` writes `partial.toolCalls` per token at `useChatSession.ts:222–224` | VERIFIED |
| `projectStreamChunk` sets `id: tc.id ?? ''` (possibly empty) | VERIFIED at AgentRunner.ts:88 |
| `normalizeToolCallIds` sets `id: tc.id || \`call_${seed}_${i}\`` | VERIFIED at AgentRunner.ts:110 |
| `tool_call_started.call` carries normalised id | VERIFIED at AgentRunner.ts:369–373 |
| TalentSurface matches outcome-to-call by id strict equality | VERIFIED at TalentSurface.tsx:70 |
| `if (!ui) continue;` for unknown talents | VERIFIED at TalentSurface.tsx:67 |
| Bubble renders timings/copy footer at lines 93–104 | VERIFIED |
| Message wraps each step in fresh Bubble at 288–303 | VERIFIED |
| `derivedText` joins `step.content` only | VERIFIED at chat.ts:32–40 |
| ThinkingBubble defaults to PARTIAL on `main` and `f3b750e` | VERIFIED on both |

The id-reconciliation gap is **substantively correct**: in-flight call writes `step.toolCalls[i].id = ''` via streaming partial, while `appendToolOutcome` writes `step.toolOutcomes[j].callId = 'call_<seed>_<idx>'`. TalentSurface line 70's strict-equality find returns undefined; for a turn loaded from disk after the run is done (`isActiveRun=false`), nothing renders for the registered talent. Real latent bug, correctly named, correctly attributed to cleanup-#1's design.

## Findings

### SUGGESTION 1: Tag the prefill-on-followup transition as (P) in §3 prose

§3 tags the `prefill ← preparing` rename as (P) in the §4d component table, but the semantic shift "after a tool call finishes, the follow-up step transitions back to `prefill` (waiting for the first token)" is also a (P) — today's reducer (`agentStateReducer.ts:33–38`) sends `step_started.isFollowUp` directly to `streaming_followup` (collapsed by D5 to `streaming_text`), with no `prefill` intermediate.

**Where**: §3 (state machine prose, second paragraph)
**Suggestion**: Add one sentence: "(P) The follow-up's path through `prefill` is also a behaviour change; today the reducer transitions `executing_tool → streaming_followup` directly on `step_started(isFollowUp)`."

### SUGGESTION 2: Refresh §5 line numbers

`appendToolOutcome` is at `ChatSessionStore.ts:754` (cited as 716). `pushAgentStep` is at line 716 (cited as 571 — line 571 is `updateActiveStepStreaming`). Function names and behaviours are correctly described; only the line numbers are stale.

**Where**: §5 single-writer table rows for `step.toolOutcomes` and "New step"
**Suggestion**: Update to `ChatSessionStore.ts:754` and `ChatSessionStore.ts:716`.

### SUGGESTION 3: Note the fate of TalentSurface's `renderPending` path

§4a's "no per-call block during in-flight" rule (combined with I4's ChatView-owned indicator) makes today's TalentSurface inline pending paths (`renderPending`, `pendingTalentNames` skeleton, `isGeneratingToolCall` generic fallback at lines 83–87, 102–118, 122–130) effectively dead. The WHAT doesn't explicitly say "deprecate these branches"; it's implied. Without the note, the planner could leave the inline pending paths in place, producing two competing pending UIs.

**Where**: §4a (per-step blocks, after the "(none)" bullet) or §4d (TalentSurface row)
**Suggestion**: One sentence: "TalentSurface's inline pending branches (`renderPending` per call, `pendingTalentNames` skeleton, generic `isGeneratingToolCall` fallback) become unreachable under this rule and should be removed when the indicator lifts to ChatView."

## Routing

LGTM → producer advances. Architect/de-facto-architect applies the 3 SUGGESTIONs (or acknowledges in Review History), then hands off to planner for HOW.
