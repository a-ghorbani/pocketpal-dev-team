# WHAT Critique — Round 1

**Reviewer**: pocketpal-architect-critic
**Date**: 2026-05-05
**Verdict**: HAS_BLOCKERS

---

## Summary

The chosen rendering architecture is the right shape (per-step block iteration with one footer per turn, ChatView-owned caret, fallback chip for unknown talents). It cleanly solves all six user-visible problems from the intent brief. But the WHAT is missing the architecture-justification step, has multiple false `(C)` claims, leaves intent Q3 partially unanswered, and silently implies behaviour changes (D7, isThinking) that aren't called out as transitions — producing a real ping-pong risk for the planner.

## Findings

### BLOCKER 1: §5 deferred-cleanup #1 grounded in non-existent code

§5 names `appendToolCall *(today named `reconcileActiveStepToolCall`)*` as the single writer for `step.toolCalls`. **Neither function exists in the worktree.** The actual writer is `updateActiveStepStreaming` (called per-token from `useChatSession.applyEventToStore`, `useChatSession.ts:222–224`). The follow-up claim "fixed by removing toolCalls from the streaming partial" is also false; line 222–224 still does `partial.toolCalls = event.delta.toolCalls`.

Adjacent issue: today persisted `step.toolCalls[i].id` comes from `projectStreamChunk` (`tc.id ?? ''`), while `outcome.callId` comes from `normalizeToolCallIds` (synthetic `call_<seed>_<idx>`). If those diverge, TalentSurface's id-match (`outcome.callId === tc.id`) silently drops talent blocks. The WHAT promotes `step.toolCalls` to a renderer-driving field without addressing this.

**Fix**: Replace §5 row + paragraph with the actual writer (`updateActiveStepStreaming`). Decide explicitly: (a) keep streaming `toolCalls` and re-normalise ids at `step_finished`, or (b) remove toolCalls from streaming partial and only land via new `appendToolCall` after `step_finished`. Pick one and verify the writer it names exists.

### BLOCKER 2: "TextMessage renders timing/copy itself" diagnosis is wrong

§4d footnote names the wrong component. `TextMessage.tsx` does **not** render timings or copy. `Bubble.tsx:93–104` does. The duplicate-footer bug arises because `Message.renderAssistantTurn` (Message.tsx:288–303) wraps **each step's text fragment** in a fresh `Bubble` via `oneOf(renderBubble, ...)` — so once `run_finished` writes timings, every step re-renders the footer. N footers for an N-step turn.

**Fix**: Rewrite the §4d footnote naming Bubble (not TextMessage) as the current footer renderer. Then explicitly resolve: does Bubble keep rendering chrome for legacy `Text` rows, or does Message own chrome universally?

### BLOCKER 3: §9c states a non-existent "today" fallback

§9c: "Same fallback datetime/calculate use today. … No schema change required." But there is **no** fallback today — `TalentSurface.tsx:67` does `if (!ui) continue;` and renders nothing. The chip behaviour (I3) is the new design, not legacy.

**Fix**: Reword to acknowledge today renders nothing for unknown talents (which IS intent issue #3); per I3 the new design renders the tool-used chip / error block.

### BLOCKER 4: D3 doesn't answer intent Q3

Intent Q3 asked about reasoning **expand/collapse default state** ("collapsed or expanded?" — answer "match `main`"). D3 specifies render **order** ("BEFORE that step's content"), not the default state. ThinkingBubble has three states (COLLAPSED/PARTIAL/EXPANDED) and currently defaults to PARTIAL — the planner must know which one matches `main` to "revert" correctly.

**Fix**: Look at `main`, pin the answer in D3. Per critic prompt, unresolved `(?)` markers are automatic BLOCKERs.

## Concerns

### CONCERN 1: No alternatives considered for chosen architecture

The WHAT presents Option-B (N-blocks-in-one-row, Message-owned footer, ChatView-owned caret) without enumerating or rejecting alternatives. Three plausible ones:

1. Flatten storage to OpenAI shape (each step → its own chat row).
2. Make `Bubble` turn-aware (pass `isLastBlockInTurn`, render footer only on last).
3. Synthesise a "footer row" message after each finalized AssistantTurn.

Per critic prompt: "A WHAT that proposes an architecture without showing it considered and rejected alternatives is automatically `CONCERN`."

**Fix**: Add §4.0 "Architecture choice" with 2–3 alternatives + one-line trade-offs + reason chosen wins.

### CONCERN 2: D7 implies a `derivedText` change not flagged as (C) → (P)

D7 says "Copy semantics = combined turn content (all reasoning + content joined)." Today `derivedText` (`src/utils/chat.ts:32–40`) joins **content only**, not reasoning. The Bubble's copy button calls `derivedText`. Existing tests in `Bubble.test.tsx:195–280` assert content-only copy. D7 is a behaviour change but not flagged as (C) → (P) and `derivedText` isn't called out as a touch-point.

**Fix**: Add (C) entry; either make D7 explicit about updating `derivedText` + tests, or reduce D7 scope to "content only, all steps".

### CONCERN 3: Footer-ownership split between row types is implicit

§4d puts AssistantTurn footer in `Message.renderAssistantTurn` (new). For legacy `Text` rows, Bubble continues to render footer. This split between Text-row chrome (Bubble) and AssistantTurn-row chrome (Message) is never declared.

**Fix**: Either generalise the rule (Message owns chrome for all row types; Bubble is a pure shape) and remove Bubble's footer code in this PR, OR explicitly state the split in §4d and add an invariant or test guard.

### CONCERN 4: Dead-zone transitions not exercised in §6

Intent issue #2 ("dead zones") is load-bearing. §3 has the state→feedback table; §7's `isThinking` derivation flips the right behaviour. But §6 scenarios are end-states, not in-flight states. No scenario visualises the transition through dead zones.

**Fix**: Add Scenario I (or expand C): step-by-step storyboard showing what's visible at each phase (`prefill` → `streaming_text` → `generating_tool_call` → `executing_tool` → follow-up `prefill` → `streaming_text` → `done`).

## Suggestions

- **S1**: Q1's "dot-row indicator below the bubble" vs WHAT's "PulsingCaret" terminology — clarify or rename.
- **S2**: §3 state table missing `idle` row (post-abort state).
- **S3**: `metadata.copyable` has two writers in current code (run_finished and catch path); §5 row should acknowledge both event sources.

## Drift Spot-Checks (positive)

Verified against `feature/TASK-20260504-2320` @ f3b750e:

- ✓ `messages[0] = newest, FlatList inverted` — `ChatView.tsx:716, 903`; `ChatSessionStore.ts:386`.
- ✓ `AssistantTurn { steps: AgentStep[] }` shape — `src/utils/types.ts:43–54, 181–184`.
- ✓ `TalentResult` union — `src/services/talents/types.ts:10–14`.
- ✓ `pushAgentStep`, `appendToolOutcome`, `finalizeActiveStep`, `updateActiveStepStreaming` all exist — `src/store/ChatSessionStore.ts:571, 716, 754, 801`.
- ✓ State names in reducer (`preparing`, `streaming_text`, `streaming_followup`, `generating_tool_call`, `executing_tool`, `done`, `failed`, `idle`) match WHAT's pre-D5 baseline.
- ✓ `LoadingBubble` mounted as ListHeaderComponent driven by `isThinking` — `ChatView.tsx:868`.
- ✓ `derivedText` joins step content only (no reasoning) — `src/utils/chat.ts:32–40`.

## Routing

Per pipeline: HAS_BLOCKERS → back to architect (or de-facto architect) in revision mode.
Round 1 of max 2.
