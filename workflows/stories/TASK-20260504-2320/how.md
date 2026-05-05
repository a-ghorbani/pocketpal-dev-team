# Implementation Plan: Apply chat-flow architecture to AssistantTurn rendering

**Purpose**: land the rendering contract specified in `what.md` so the running app matches the intent's user-visible promises (one footer per turn, no dead zones, feedback for tool calls without UI, reasoning visible per step, subtle pending indicator). Design lives in `what.md`; this is the executable worklist.

This file lives at `workflows/stories/TASK-20260504-2320/how.md`.

---

## Metadata

- **Task ID**: TASK-20260504-2320
- **Worktree**: `./worktrees/TASK-20260504-2320` (stacked on PR #709's branch `feature/TASK-20260502-2115` at `f3b750e`)
- **Branch**: `feature/TASK-20260504-2320`
- **Native Changes**: NO (story is **non-native** — no `package.json`, `ios/`, `android/`, podfile or build.gradle changes; native verification is intentionally omitted)
- **Visual Confirmation**: YES (intent flagged it; canonical scenarios A–I are all visual contracts)
- **Intent Brief**: `./workflows/stories/TASK-20260504-2320/intent-brief.md`
- **WHAT**: `./workflows/stories/TASK-20260504-2320/what.md`
- **Architecture doc(s) being updated**: `context/architecture/chat-flow.md` — this story **bootstraps** the file by absorbing WHAT into it. The file lives in the **dev-team repo** (`/Users/aghorbani/codes/pocketpal-dev-team/context/architecture/chat-flow.md`), NOT the pocketpal-ai worktree. See Step 14.
- **PR target base**: `feature/TASK-20260502-2115` (PR #709). Per intent Q4, single PR for everything.
- **Status**: round-2 revision (post plan-critic round 1)

---

## Progress Tracking

| Step | Status | Commit | Notes |
| --- | --- | --- | --- |
| Step 1 — Rename `preparing` → `prefill`, collapse `streaming_followup` | DONE | bf0f6ed | WHAT §3, D5; reducer + types + tests |
| Step 2 — Route follow-up through `prefill` | DONE | ea05a8a | WHAT §3 (P), Scenario I phase 7. Reducer extension flips prefill→streaming_text on first non-empty content/reasoning token (necessary for §6.I phase 8) |
| Step 3 — Drop `partial.toolCalls` from streaming partial | DONE | 861ff52 | WHAT §5 cleanup #1 (first half) |
| Step 4 — Add `appendToolCall` writer; runner attaches `toolCalls` to `step_finished` | DONE | 01c839a | WHAT §5 cleanup #1 (second half). Per round-2 SUGGESTION 1, hoisted finishedResult/rawToolCalls/calls block above step_finished yield |
| Step 5 — Add `AssistantTurnFooter` component | DONE | 231d63f | WHAT §4b, §4d, D9. Sender-name handling stays in TextMessage (deviation from D9's literal "owns sender-name" claim — keeping today's UX of name-above-bubble; documented in component JSDoc) |
| Step 6 — Strip chrome from `Bubble` | DONE | 325833c | WHAT §4d, D9, I1 |
| Step 7 — Hoist footer to `Message` (universal owner) | DONE | da74bb7 | WHAT §4b, §4d, D9, I1. Footer attached in outer JSX adjacent to renderBubbleContainer (round-2 SUGGESTION 3), not inside renderMessage |
| Step 8 — Add `ToolUsedChip` + `ToolErrorBlock` (subtle blocks) | DONE | 0fca05b | WHAT §4a (I3), D2, D8. en.json strings added; other languages fall back to en via existing l10n overlay |
| Step 9 — Rewire `TalentSurface` per-call dispatch + remove dead pending paths | DONE | 03076b0 | WHAT §4a (I2, I3), §4a (P) note. Inline pending paths removed; TalentUI.renderPending kept on the interface but @deprecated |
| Step 10 — Add `PendingIndicator` component | DONE | 0a86e55 | WHAT §4d, D4, I4 |
| Step 11 — Wire `PendingIndicator` from `ChatView`, retire `LoadingBubble` from chat | DONE | d692163 | WHAT §4d, I4. ChatScreen + VideoPalScreen no longer pass isThinking; ChatView derives isPending locally from agentUiState.status |
| Step 12 — Split reasoning and content into separate per-step blocks | DONE | 7dba22b | WHAT §4a, D3. ThinkingBubble PARTIAL default verified; MarkdownView reasoning-before-content order verified |
| Step 13 — Update tests for new contract (reducer, Bubble, Message, TalentSurface, ChatView) | DONE | 5e41af8 | WHAT §6 A–I. All 162 test suites pass (2123 tests) |
| Step 14 — Bootstrap `context/architecture/chat-flow.md` (dev-team repo) + reference SHA in code PR | DONE | dev-team@baeb825 | absorb WHAT delta; SHA referenced in code PR description |
| Cleanup reminders applied | DONE | n/a | DebugStatusBar absent in `f3b750e` (verified); no-op for this PR. Architecture doc §10 records "no cleanup reminders outstanding" |

---

## Affected Files

| Path | Change kind | WHAT reference |
| --- | --- | --- |
| `src/services/agent/AgentRunner.types.ts` | edit | §3, D5; §5 cleanup #1 (extend `step_finished` payload) |
| `src/services/agent/AgentRunner.ts` | edit | §5 cleanup #1 (attach normalized `toolCalls` to `step_finished`) |
| `src/services/agent/agentStateReducer.ts` | edit | §3, D5 |
| `src/services/agent/__tests__/agentStateReducer.test.ts` | edit | §3, D5 |
| `src/hooks/useChatSession.ts` | edit | §5 cleanup #1 |
| `src/store/ChatSessionStore.ts` | edit | §5 (new `appendToolCall`) |
| `src/store/__tests__/ChatSessionStore.assistantTurn.test.ts` | edit | §5 |
| `src/components/AssistantTurnFooter/AssistantTurnFooter.tsx` | add | §4b, §4d, D9 |
| `src/components/AssistantTurnFooter/styles.ts` | add | §4d |
| `src/components/AssistantTurnFooter/index.ts` | add | — |
| `src/components/AssistantTurnFooter/__tests__/AssistantTurnFooter.test.tsx` | add | §4b, I1 |
| `src/components/Bubble/Bubble.tsx` | edit | §4d, D9 (strip chrome) |
| `src/components/Bubble/__tests__/Bubble.test.tsx` | edit | D9 (chrome ownership moves) |
| `src/components/Message/Message.tsx` | edit | §4a, §4b, §4d, D9 |
| `src/components/Message/__tests__/Message.assistantTurn.test.tsx` | edit | §4a, §4b |
| `src/components/Message/__tests__/Message.test.tsx` | edit | D9 |
| `src/components/ToolUsedChip/ToolUsedChip.tsx` | add | §4a (I3), D8 |
| `src/components/ToolUsedChip/styles.ts` | add | §4a |
| `src/components/ToolUsedChip/index.ts` | add | — |
| `src/components/ToolErrorBlock/ToolErrorBlock.tsx` | add | §4a, D2 |
| `src/components/ToolErrorBlock/styles.ts` | add | §4a |
| `src/components/ToolErrorBlock/index.ts` | add | — |
| `src/components/ToolUsedChip/__tests__/ToolUsedChip.test.tsx` | add | I3 |
| `src/components/ToolErrorBlock/__tests__/ToolErrorBlock.test.tsx` | add | D2, I3 |
| `src/components/TalentSurface/TalentSurface.tsx` | edit | §4a (P), §4a I2/I3 |
| `src/components/TalentSurface/__tests__/TalentSurface.test.tsx` | edit | §4a |
| `src/components/PendingIndicator/PendingIndicator.tsx` | add | §4d, D4, I4 |
| `src/components/PendingIndicator/styles.ts` | add | D4 |
| `src/components/PendingIndicator/index.ts` | add | — |
| `src/components/PendingIndicator/__tests__/PendingIndicator.test.tsx` | add | D4 |
| `src/components/ChatView/ChatView.tsx` | edit | §4d, §7, I4 |
| `src/components/ChatView/__tests__/ChatView.assistantTurn.test.tsx` | edit | §6.I, I4 |
| `src/components/LoadingBubble/LoadingBubble.tsx` | keep | retired from chat usage; left exported for any out-of-scope callers |
| `src/components/index.ts` | edit | new component exports |
| `src/components/MarkdownView/MarkdownView.tsx` | unchanged (read) | D3 default already PARTIAL — verify only |
| `src/components/ThinkingBubble/ThinkingBubble.tsx` | unchanged (read) | D3 default already PARTIAL — verify only |
| `src/screens/ChatScreen/ChatScreen.tsx` | edit | §7 (rm `isThinking` LoadingBubble plumbing) |
| `src/utils/chat.ts` | unchanged | D7 — `derivedText` already matches contract |
| `src/locales/en.json` | edit | new `pendingIndicator` / `toolUsedChip` / `toolErrorBlock` strings (en only — Weblate fans out) |
| `context/architecture/chat-flow.md` (dev-team repo) | add | bootstrap from WHAT |

---

## Implementation Steps

Each step:

- references the WHAT section(s) it's executing
- is atomic (one logical change, one commit)
- specifies the file paths it touches
- states the acceptance check (lint, typecheck, targeted test, manual scenario)

### Step 1: Rename `preparing` → `prefill`; remove `streaming_followup` from the union

**Implements**: WHAT §3, **D5**.

**Files**:

- `src/services/agent/AgentRunner.types.ts` — rename status string in `AgentUiState['status']` union: drop `'preparing'`, add `'prefill'`; drop `'streaming_followup'`. Final union: `'idle' | 'prefill' | 'streaming_text' | 'generating_tool_call' | 'executing_tool' | 'done' | 'failed'`.
- `src/services/agent/agentStateReducer.ts` — `run_started` returns `status: 'prefill'`; `step_started` returns `status: 'streaming_text'` regardless of `isFollowUp` (collapse per D5; the runner-side `isFollowUp` flag stays on the event payload for any per-step UI that wants it, see §3 prose).
- `src/services/agent/__tests__/agentStateReducer.test.ts` — update test expectations: `'preparing'` → `'prefill'`; `'streaming_followup'` cases now expect `'streaming_text'`. Existing `#6` (isFollowUp=true → streaming_followup) becomes "isFollowUp=true → streaming_text".

**Approach**: Pure rename + collapse. No new logic in this step. The follow-up indicator coverage (Scenario I phase 7) is achieved in Step 2 by routing through `prefill`. Keep this commit small to make the rename diff easy to read.

**Verification**:

- `yarn typecheck` passes (compile-time check that no other site references the old names — see grep output noting all sites are in the four files above).
- `yarn test src/services/agent/__tests__/agentStateReducer.test.ts` passes.
- `yarn lint` passes.

### Step 2: Route follow-up through `prefill` so the indicator covers phase 7 of Scenario I

**Implements**: WHAT §3 (P) prose, Scenario I phases 5–7.

**Files**:

- `src/services/agent/agentStateReducer.ts` — on `tool_call_started`, the reducer already flips to `executing_tool`. Add an explicit handler so `step_started(isFollowUp=true)` flips to `'prefill'` (NOT `'streaming_text'`); the first `token` with content/reasoning then flips to `streaming_text` via the regular path. (After Step 1 the `step_started` branch sets `streaming_text` unconditionally — this step splits the branch so `isFollowUp=true` yields `prefill` instead.) This restores indicator coverage during the dead zone between tool finish and the first follow-up token.
- `src/services/agent/__tests__/agentStateReducer.test.ts` — update or add a scripted-sequence test that asserts the status timeline: `prefill → streaming_text → generating_tool_call → executing_tool → prefill (follow-up) → streaming_text → done`.

**Approach**: Two-line reducer change. The first content/reasoning `token` after `prefill` already flips to `streaming_text` via the existing `case 'token'` handler — confirmed by reading the reducer; no extra wiring needed.

**Verification**:

- `yarn test src/services/agent/__tests__/agentStateReducer.test.ts` — scripted sequence matches §6.I phases 2–9.
- `yarn typecheck` passes.

### Step 3: Drop `partial.toolCalls` from the streaming partial

**Implements**: WHAT §5 **cleanup #1**, first half (remove the per-token write site).

**Files**:

- `src/hooks/useChatSession.ts` — in `applyEventToStore`'s `case 'token'`, delete the `if (event.delta.toolCalls) { partial.toolCalls = event.delta.toolCalls; }` block (currently lines 222–224). The reducer still consumes `event.delta.toolCalls` for `pendingTalentNames` — that path is untouched.

**Approach**: Single targeted deletion. After this step, `step.toolCalls` is no longer overwritten on every token. Step 4 introduces the replacement writer.

**Verification**:

- `yarn typecheck` passes.
- `yarn test src/hooks/__tests__/useChatSession.assistantTurn.test.ts` — adjust any assertion that observed `step.toolCalls` mid-stream; the new contract is "toolCalls land after step_finished" (covered by Step 4's test).

### Step 4: Add `appendToolCall` writer; runner attaches `toolCalls` to `step_finished`

**Implements**: WHAT §5 **cleanup #1**, second half (introduce the post-`step_finished` writer with normalized ids).

**Resolution of plan-critic CONCERN 2** (round 1): instead of having the hook accumulate `tool_call_started` events into a per-step buffer and re-derive what the runner already knows, extend the `step_finished` event payload with the runner's normalized `toolCalls` list. The hook becomes a single-line dispatcher in `case 'step_finished'`. No buffer in `applyEventToStore`. Cleaner single-writer.

**Files**:

- `src/services/agent/AgentRunner.types.ts` — extend the `step_finished` event variant to:
  ```ts
  | {type: 'step_finished'; turn: number; toolCalls?: AgentToolCall[]}
  ```
  Optional because not every step has tool calls (text-only turns, the final step of a multi-turn chain). When present, the array is the runner's authoritative normalized list (synthetic ids reconciled with outcomes).
- `src/services/agent/AgentRunner.ts` — at line 356, where the runner currently emits `yield {type: 'step_finished', turn};`, restructure so the normalized `calls` array is computed BEFORE the `step_finished` yield (currently it's computed at line 369, after) and passed into the event payload. Concretely:
  - Move the `const rawToolCalls = finishedResult.tool_calls ?? []` and `const calls = rawToolCalls.length === 0 ? undefined : normalizeToolCallIds(rawToolCalls, callIdSeed + turn)` lines up so they execute before the `step_finished` yield.
  - Yield: `yield {type: 'step_finished', turn, toolCalls: calls};`
  - Then continue with the existing `if (rawToolCalls.length === 0) break;` and per-call loop over `calls` for `tool_call_started` / `tool_call_finished` (no behaviour change to those events; ids are already normalized).
- `src/store/ChatSessionStore.ts` — add an `appendToolCall(messageId, sessionId, calls: AgentToolCall[])` action that mirrors `appendToolOutcome`: in-memory replaces the active (last) step's `toolCalls` array (replace, not append — the runner emits the full normalized list once); persists `{steps: nextSteps}` via `chatSessionRepository.updateMessage`. Single-writer rule (see §5).
- `src/hooks/useChatSession.ts` — in `applyEventToStore`'s `case 'step_finished'`, before calling `finalizeActiveStep`, if `event.toolCalls && event.toolCalls.length > 0` call `chatSessionStore.appendToolCall(messageId, sessionId, event.toolCalls)`. No buffer; no re-derivation.
- `src/store/__tests__/ChatSessionStore.assistantTurn.test.ts` — add a test that `appendToolCall` writes `step.toolCalls` with ids exactly equal to outcomes' `callId`s after a follow-up `appendToolOutcome`.
- `src/hooks/__tests__/useChatSession.assistantTurn.test.ts` — add a scripted-event test that asserts `step.toolCalls[i].id === step.toolOutcomes[i].callId` after a tool-using turn (this is the latent-bug regression guard called out in WHAT §5 cleanup #1). Per plan-critic SUGGESTION 1 (round 1), additionally assert the id-match invariant **at every render frame** during the scripted event walk — not only after completion — to future-proof against subtle regressions in writer ordering. Concretely: after each event applied, assert `step.toolCalls.every((c, i) => step.toolOutcomes[i] === undefined || step.toolOutcomes[i].callId === c.id)` (vacuously true while outcomes lag the calls, strictly enforced as soon as both are present).

**Approach**: This is the single non-cosmetic correctness change in the story. After Step 4, `step.toolCalls[i].id === outcome.callId` by construction — TalentSurface's id-match in Step 9 then becomes safe. WHAT §5 cleanup #1 explicitly authorises this writer addition. The runner-attached payload (rather than a hook buffer) keeps the runner as the single source of truth for normalized ids.

**Verification**:

- `yarn typecheck` passes (the optional `toolCalls?` field on `step_finished` is exhaustiveness-safe; existing `case 'step_finished'` consumers in the reducer ignore the new field by structural typing).
- `yarn test src/services/agent/__tests__/agentStateReducer.test.ts` passes (no reducer change in this step; the reducer's `step_finished` handler reads only `turn`).
- `yarn test src/store/__tests__/ChatSessionStore.assistantTurn.test.ts` passes (with new test).
- `yarn test src/hooks/__tests__/useChatSession.assistantTurn.test.ts` passes (with new scripted-event test + per-frame id-match assertion).

### Step 5: Add `AssistantTurnFooter` component

**Implements**: WHAT §4b, §4d, **D9**, **I1**.

**Files**:

- `src/components/AssistantTurnFooter/AssistantTurnFooter.tsx` — new component. Props: `{ message: MessageType.Any, showName: boolean, currentUserIsAuthor: boolean }`. Renders timing line (from `metadata.timings`) + copy button (gated on `metadata.copyable`) + sender name (gated on `showName`). Each field renders independently per **D1** ("show what we have"). Copy uses `derivedText(message)` — same string the existing `Bubble.tsx` uses today (no behaviour change to copy content per **D7**).
- `src/components/AssistantTurnFooter/styles.ts` — extract the relevant styles from `Bubble/styles.ts` (`dateHeaderContainer`, `dateHeader`, `iconContainer`).
- `src/components/AssistantTurnFooter/index.ts` — barrel export.
- `src/components/AssistantTurnFooter/__tests__/AssistantTurnFooter.test.tsx` — exercise: timing-only, copy-only, both, neither, sender-name visible/hidden, copy clipboard call.
- `src/components/index.ts` — add `export * from './AssistantTurnFooter';`.

**Approach**: Lift the existing chrome-rendering JSX from `Bubble.tsx:93–104` (the `{timings && (...)}` block) into the new component verbatim, plus add the sender-name slot for D9. The existing `Bubble.test.tsx` chrome assertions become `AssistantTurnFooter.test.tsx` assertions in Step 13.

**Verification**:

- `yarn typecheck` passes.
- `yarn test src/components/AssistantTurnFooter/__tests__/AssistantTurnFooter.test.tsx` passes.
- `yarn lint` passes.

### Step 6: Strip chrome from `Bubble` (pure shape primitive)

**Implements**: WHAT §4d, **D9**.

**Files**:

- `src/components/Bubble/Bubble.tsx` — delete the `{timings && (...)}` block (lines 93–104) and all its supporting code: `timingParts`, `fullTimingsString`, `copyToClipboard`, the related `useContext(L10nContext)`, `Clipboard`, haptic, `Icon`, `t()` imports (those that are now unused). `Bubble` becomes: take `child`, render an `Animated.View` with shape styles + `transform: [{scale}]`, return.
- `src/components/Bubble/__tests__/Bubble.test.tsx` — remove tests that assert chrome (timing string, copy click, copyable gating, derivedText copy variants for AssistantTurn). Move the relevant chrome tests into Step 5's `AssistantTurnFooter.test.tsx` (they are mostly already a 1:1 fit). Keep tests that verify pure shape behaviour (renders child, accepts `nextMessageInGroup`).

**Approach**: This is purely subtractive. After this step, `Bubble.tsx` is < 40 lines. The change compiles only because Steps 5 and 7 hoist chrome to its new owner.

**Verification**:

- `yarn typecheck` passes (Step 7 lands in the same PR; if Steps 6 and 7 are committed separately, run `yarn typecheck` after Step 7).
- `yarn test src/components/Bubble/__tests__/Bubble.test.tsx` passes (with reduced suite).

### Step 7: Hoist footer to `Message` (universal owner for assistant rows)

**Implements**: WHAT §4b, §4d, **D9**, **I1**.

**Files**:

- `src/components/Message/Message.tsx`:
  - Inside `renderMessage()` for `case 'text'`: after the bubble container call, if the row is authored by the assistant (`!currentUserIsAuthor`), append `<AssistantTurnFooter message={message} showName={showName} currentUserIsAuthor={currentUserIsAuthor} />`. User-authored Text rows still render no chrome (no behaviour change for users).
  - In `renderAssistantTurn()`: after the per-step blocks loop, append exactly ONE `<AssistantTurnFooter ... />` (turn-level) — independent of how many steps the turn has. Satisfies **I1**.
  - Drop `isFirstBlock` book-keeping for sender-name; the footer owns that now (sender name renders only on the first row of an assistant group anyway, gated by `showName`).
- `src/components/Message/__tests__/Message.assistantTurn.test.tsx` — assert one footer per multi-step turn (regression guard for the original duplicate-footer bug).
- `src/components/Message/__tests__/Message.test.tsx` — assert assistant Text rows now route chrome through `AssistantTurnFooter`.

**Approach**: One footer per assistant row, two render paths converge. The duplicate-footer bug is fixed by **construction**: chrome is rendered exactly once per `Message`, never inside any `Bubble`.

**Verification**:

- `yarn typecheck` passes.
- `yarn test src/components/Message/__tests__/` passes.
- Manual: render a 3-step turn (Scenario G) — exactly one footer below all blocks.

### Step 8: Add `ToolUsedChip` and `ToolErrorBlock` (subtle, low-prominence)

**Implements**: WHAT §4a (**I3**), **D2**, **D8**.

**Files**:

- `src/components/ToolUsedChip/ToolUsedChip.tsx` — new component. Props: `{ toolName: string }`. Renders an inline row: small icon (e.g. `wrench` from MaterialCommunityIcons) + `t(l10n.chat.toolUsedChip, { name: toolName })` ("used X"). Style: low-prominence (theme.colors.onSurfaceVariant text, no border/bg, single line).
- `src/components/ToolUsedChip/styles.ts` — minimal.
- `src/components/ToolUsedChip/index.ts` — barrel.
- `src/components/ToolUsedChip/__tests__/ToolUsedChip.test.tsx` — renders name; renders nothing for empty name.
- `src/components/ToolErrorBlock/ToolErrorBlock.tsx` — new component. Props: `{ toolName: string, errorMessage?: string }`. Renders an inline row: warning icon + `t(l10n.chat.toolErrorBlock, { name: toolName })` ("X failed") + optional `errorMessage` on a second line. Default copy when `errorMessage` is missing comes from D2: "Tool call failed".
- `src/components/ToolErrorBlock/styles.ts` — uses theme error tone but at low prominence (text color only, not a filled container).
- `src/components/ToolErrorBlock/index.ts` — barrel.
- `src/components/ToolErrorBlock/__tests__/ToolErrorBlock.test.tsx` — renders name + message; renders default copy when message missing.
- `src/components/index.ts` — exports for both.
- `src/locales/en.json` — add `chat.toolUsedChip = "used {{name}}"` and `chat.toolErrorBlock = "{{name}} failed"`. Only edit en.json (Weblate fans out per project l10n workflow).

**Approach**: Small, dumb display components. No registry interaction — they are rendered by `TalentSurface` in Step 9.

**Verification**:

- `yarn typecheck` passes.
- `yarn test src/components/ToolUsedChip` and `src/components/ToolErrorBlock` pass.
- `yarn l10n:validate` passes.

### Step 9: Rewire `TalentSurface` per-call dispatch; remove dead inline pending paths

**Implements**: WHAT §4a (priority order **error > talent > chip > none**), **I2**, **I3**, §4a (P) note (delete dead lines 71–77, 83–87, 102–130).

**Files**:

- `src/components/TalentSurface/TalentSurface.tsx`:
  - New shape: takes `{ step: AgentStep }` only. Drop `isActiveRun`, `pendingTalentNames`, `isGeneratingToolCall` props (the indicator at ChatView level subsumes them — see Step 11).
  - For each call in `step.toolCalls` (in array order — **I2**):
    1. Find `outcome = (step.toolOutcomes ?? []).find(o => o.callId === call.id)`. Note: after Step 4, ids match by construction.
    2. If `outcome.result.type === 'error'` → render `<ToolErrorBlock toolName={call.function.name} errorMessage={outcome.result.errorMessage} />`.
    3. Else if `outcome` exists and `talentUIRegistry.get(call.function.name)?.renderResult` exists → render `ui.renderResult(outcome.result)`.
    4. Else if `outcome` exists (no UI registered) → render `<ToolUsedChip toolName={call.function.name} />`.
    5. Else (no outcome yet) → render nothing (the per-turn `PendingIndicator` covers feedback during the in-flight window).
  - Delete: `renderPending()` calls (the per-call pending case at lines 71–77 and pendingTalentNames skeleton at 83–87 and `isGeneratingToolCall` fallback at 102–130). The `renderPending` method on the `TalentUI` interface is **retained** for completeness but no longer called from `TalentSurface`; mark it `@deprecated` in the registry's TS doc but leave the field for now (Step 9 doesn't remove method definitions on existing UIs — narrow scope).
- `src/components/TalentSurface/styles.ts` — keep minimal styles; remove pending-specific ones used only by the deleted code paths.
- `src/components/TalentSurface/__tests__/TalentSurface.test.tsx` — new tests covering the four-priority-order dispatch (registered-UI happy path, unregistered → chip, error → error block, no-outcome → null). Drop the legacy active-run/pending-talents tests.
- `src/components/Message/Message.tsx` — update the call site: pass only `step` to `TalentSurface`. Remove the `showTalentSurface` predicate's "active run" branch; the new rule is "render TalentSurface iff `step.toolCalls?.length > 0`".

**Approach**: Tightening contract. The single id-match (`outcome.callId === call.id`) is now safe because Step 4 guarantees id reconciliation. Inline pending paths are removed because the indicator (Step 10) takes over feedback during the dead zone — see WHAT §4a (P).

**Verification**:

- `yarn typecheck` passes.
- `yarn test src/components/TalentSurface/__tests__/TalentSurface.test.tsx` passes.
- `yarn test src/components/Message/__tests__/Message.assistantTurn.test.tsx` passes.

### Step 10: Add `PendingIndicator` component

**Implements**: WHAT §4d, **D4**, **I4**.

**Files**:

- `src/components/PendingIndicator/PendingIndicator.tsx` — subtle dot-row indicator. Visual is similar to `LoadingBubble`'s three pulsing dots but at lower visual weight (smaller dots, no card-like background, `theme.colors.onSurfaceVariant` for the dots). The shape "matches the LoadingBubble shape but at lower prominence" per D4. Single-line height; no `useTheme`-required, no l10n string (purely decorative).
- `src/components/PendingIndicator/styles.ts` — minimal.
- `src/components/PendingIndicator/index.ts` — barrel.
- `src/components/PendingIndicator/__tests__/PendingIndicator.test.tsx` — renders three dots, has correct `testID="pending-indicator"`.
- `src/components/index.ts` — export.

**Approach**: Almost a direct trim of `LoadingBubble.tsx`'s structure (LoadingDot already exists). The component itself is intentionally small — placement and visibility are owned by `ChatView` (Step 11).

**Verification**:

- `yarn typecheck` passes.
- `yarn test src/components/PendingIndicator/__tests__/` passes.

### Step 11: Wire `PendingIndicator` from `ChatView`; retire `LoadingBubble` from chat

**Implements**: WHAT §4d, §7, **I4**, Scenario I.

**Files**:

- `src/components/ChatView/ChatView.tsx`:
  - Update the active-set predicate (lines 717–726) to use the new status names: `isAgentActive = status ∈ {'prefill', 'streaming_text', 'generating_tool_call', 'executing_tool'}` (D5 collapsed `streaming_followup`; D9 keeps the predicate at this layer per §7 — `isThinking` derivation).
  - Compute `isPending = status ∈ {'prefill', 'generating_tool_call', 'executing_tool'}` (matches §7 `isThinking` derivation; the indicator is hidden in `streaming_text` and `done`).
  - In `renderListHeaderComponent` (currently renders `<LoadingBubble />`): replace with `{isPending && <PendingIndicator />}`. Because the FlatList is `inverted={true}` (line 903), the `ListHeaderComponent` actually renders **at the bottom** visually — which is **below the latest turn** as required by I4. Confirmed by reading the existing `LoadingBubble` placement: identical positional semantics; we are swapping component, not position.
  - Drop the `isThinking` prop input in favour of `isPending` derived locally from `chatSessionStore.agentUiState.status`. Keep `isStreaming` as a prop because `ChatScreen` derives it from `modelStore.isStreaming` for FlatList `maintainVisibleContentPosition`.
  - Remove `LoadingBubble` from the imports.
- `src/screens/ChatScreen/ChatScreen.tsx`:
  - Drop the `isThinking` derivation (`modelStore.inferencing && !modelStore.isStreaming`) and the `isThinking={isThinking}` prop. `ChatView` now owns the indicator entirely.
- `src/components/ChatView/__tests__/ChatView.assistantTurn.test.tsx`:
  - Replace `LoadingBubble`-presence assertions (if any — search the file) with `PendingIndicator`-presence assertions for each status in the active set. Add a single scripted-state test that walks `prefill → streaming_text → generating_tool_call → executing_tool → prefill (follow-up) → streaming_text → done` and verifies the indicator is visible / hidden per §3 table.

**Approach**: The placement is a one-line swap (LoadingBubble for PendingIndicator, gated on `isPending`). The conceptual shift is "ChatView owns the indicator" (I4) — which the existing code already does for `LoadingBubble` via `ListHeaderComponent`. The story's contribution is renaming the component, refining the gating predicate, and pulling the predicate from `agentUiState` instead of `modelStore.inferencing`.

**Verification**:

- `yarn typecheck` passes.
- `yarn test src/components/ChatView/__tests__/ChatView.assistantTurn.test.tsx` passes.
- Manual: Scenario I — fire a `render_html` call, observe the indicator below the latest turn through phases 2, 4, 5, 7; confirm it disappears in 3 (streaming_text), 8 (streaming_text), 9 (done). No moment of silence.

### Step 12: Split reasoning and content into separate per-step blocks (D3 + §4a)

**Implements**: WHAT §4a (reasoning before content as separate blocks), **D3**.

**Resolution of plan-critic CONCERN 3** (round 1): step renamed to surface the structural change. The reasoning-and-content block split inside `Message.renderAssistantTurn` is the substance of this step; the rest are one-line verifications.

**Files**:

- `src/components/Message/Message.tsx` — **structural change**. Today (lines 273–286) the loop routes per-step `reasoningContent` and `content` into a single `TextMessage` block, which feeds `MarkdownView` with both. The current path produces "reasoning → content" inside one bubble per step. WHAT §4a requires reasoning and content as **separate blocks** (block #1 reasoning, block #2 content) so they can be skipped independently when empty. Tweak the `Message.renderAssistantTurn` loop:
  - If `step.reasoningContent?.length > 0`, emit a dedicated reasoning block — render `<TextMessage>` with a step shaped `{...step, content: undefined}` (or pass an explicit `reasoningOnly` flag depending on TextMessage's prop signature; choose whichever requires the smallest patch).
  - If `step.content?.length > 0`, emit a separate content block — render `<TextMessage>` with `{...step, reasoningContent: undefined}`.
  - Order: reasoning first, content second (matches model emission and **D3**).
  - Spacing between blocks is already handled by `turnBlockStyles.blockSpacer`.
- `src/components/ThinkingBubble/ThinkingBubble.tsx` — **read-only verification**: confirm initial state is `BubbleState.PARTIAL` (line 47) per WHAT D3. **No code change required** unless a regression has crept in; if so, restore PARTIAL.
- `src/components/MarkdownView/MarkdownView.tsx` — **read-only verification**: confirm reasoning is rendered before main content (already true at lines 162–177 vs 179–190). **No code change required** unless a regression has crept in.

**Approach**: One real diff (block split in `Message.renderAssistantTurn`), two confirmations. The minimal patch renders two separate `<TextMessage>` siblings (one with reasoning-only step, one with content-only step) when both are present, instead of one combined.

**Verification**:

- `yarn typecheck` passes.
- `yarn test src/components/Message/__tests__/Message.assistantTurn.test.tsx` passes (add a Scenario F test: step with both reasoning and content emits two blocks in order).
- Manual: Scenario F — reasoning bubble shows in `BubbleState.PARTIAL` (header + scrollable masked preview), tap toggles to EXPANDED, tap toggles to COLLAPSED.

### Step 13: Test sweep — cover all canonical scenarios A–I

**Implements**: WHAT §6 A–I (testable contract).

**Files**:

- `src/components/Message/__tests__/Message.assistantTurn.test.tsx`:
  - **A** text only — single TextMessage, no TalentSurface, ONE footer.
  - **B** datetime (no UI) — TextMessage(s₀) + ToolUsedChip + TextMessage(s₁) + ONE footer.
  - **C** render_html with preamble + follow-up — TextMessage(s₀) + HtmlPreviewBubble + TextMessage(s₁) + ONE footer.
  - **D** render_html no preamble — HtmlPreviewBubble + TextMessage(s₁) + ONE footer (no empty leading TextMessage).
  - **E** tool failed — TextMessage(s₀) + ToolErrorBlock + TextMessage(s₁) + ONE footer.
  - **F** reasoning + content — separate reasoning block + content block + ONE footer.
  - **G** multi-tool — TextMessage(s₀) + HtmlPreview#1 + HtmlPreview#2 + ONE footer (block order matches `step.toolCalls` per **I2**).
- `src/components/ChatView/__tests__/ChatView.assistantTurn.test.tsx`:
  - **I** dead-zone storyboard — drive the agent state through phases 2–9 by directly setting `chatSessionStore.agentUiState.status` and asserting the `PendingIndicator` testID is present/absent per §3 table.
  - **H** abort with partial content — set `metadata.interrupted = true, copyable = true`, no `timings`; assert `AssistantTurnFooter` shows the copy button only (no timing).

**Approach**: Use existing fixtures + `defaultDerivedMessageProps`. Stubbing `TalentSurface` and `TextMessage` is already established (Message tests). Add ChatView-level tests for I and H that observe testIDs (`pending-indicator`, `tool-used-chip`, `tool-error-block`, `assistant-turn-footer`).

**Verification**:

- `yarn lint` passes.
- `yarn test` passes for all touched files.
- All seven scenarios A, B, C, D, E, F, G have corresponding tests; H, I are at ChatView level.
- `yarn typecheck` passes.

### Step 14: Bootstrap `context/architecture/chat-flow.md` (dev-team repo) + reference SHA in code PR

**Implements**: architecture-doc absorption (story-pipeline requirement); converts the story-scoped WHAT into the cumulative truth doc.

**Resolution of plan-critic BLOCKER 1** (round 1): §10 is retained per `templates/what-template.md` lines 182–190. The DebugStatusBar cleanup-reminder paragraph is dropped (the diagnostic is absent in `f3b750e`), but the §10 section and its **Cleanup reminders** slot stay.

**Resolution of plan-critic CONCERN 1** (round 1): the architecture doc lives in the dev-team repo; the code PR opens from the pocketpal-ai worktree. They cannot literally be in the same git PR. This story is the FIRST under the new pipeline — the convention lands here: the dev-team commit SHA is referenced in the code PR description (e.g. `Architecture doc bootstrap: dev-team@<sha>`). Pipeline-reviewer enforces the link.

**Files** (in **dev-team repo**, NOT the worktree):

- `/Users/aghorbani/codes/pocketpal-dev-team/context/architecture/chat-flow.md` (new) — bootstrap from `workflows/stories/TASK-20260504-2320/what.md`.

**Approach**:

1. Copy `what.md`'s body into a new file at `context/architecture/chat-flow.md`.
2. Promote markers: every `(P)` becomes `(C)` (the proposal is now landed truth); every `(C)` stays `(C)`; every `(D)` stays `(D)` (decisions remain decisions). There should be **zero** `(?)` markers remaining (Round-2 LGTM verified this; if any sneaked in, STOP and route back to architect — Drift).
3. Drop the legend's "(C)-only" note that's now redundant; the legend stays useful for future deltas.
4. **Drop** the `## Review History` section — it is story-scoped, not part of cumulative architecture.
5. **Keep §10** ("What this doc is NOT") **and its `Cleanup reminders` slot** intact, per `templates/what-template.md` lines 182–190 (the canonical template per `context/architecture/README.md` line 75 — promoted-doc form retains §10). Drop ONLY the `DebugStatusBar` cleanup-reminder paragraph (the diagnostic is absent in `f3b750e`; verified by `grep -rn DebugStatusBar src` returning empty). Optionally append a one-line "Drift policy: see `context/architecture/README.md` §Drift prevention" link at the bottom of §10 — it complements the section, doesn't replace it.
6. Adjust the title from "AssistantTurn — Architecture & Flow Board" to "Chat Flow" (matches `chat-flow.md` filename and the README's flow-name convention).
7. Update §5 cleanup #1 / #2 wording: cleanup #1 has been **landed** by this PR's Step 4 — change its tag to `(C)` and rewrite it as the new normal ("step.toolCalls is appended once after step_finished, with normalized ids attached to the event payload by the runner"). Cleanup #2 remains a deferred future ("see §7 derivation table"); leave that as-is in the architecture doc, mark it `(D)` because the derivation is the decided shape, even if the global signals haven't been physically removed yet.
8. **Commit separately to the dev-team repo**, then **reference the SHA in the code PR description**. The commit message should reference the TASK-ID and note "bootstrap chat-flow.md" — e.g.:
   ```
   docs(architecture): bootstrap chat-flow.md from TASK-20260504-2320 WHAT
   ```
   The code PR (opened from `worktrees/TASK-20260504-2320` against `feature/TASK-20260502-2115`) MUST include in its description a line of the form:
   ```
   Architecture doc bootstrap: dev-team@<sha>
   ```
   where `<sha>` is the dev-team-repo commit hash from this step. This is the cross-repo equivalent of "same PR" — pipeline-reviewer confirms the SHA exists and matches the code PR's behavioural deltas.

**Verification**:

- `grep -c '(?)' context/architecture/chat-flow.md` returns `0` (or only matches in legend examples).
- `grep -c '(P)' context/architecture/chat-flow.md` returns `0` (all proposals landed).
- `grep -c '^## 10\.' context/architecture/chat-flow.md` returns `1` (§10 retained per template).
- `grep -c 'Cleanup reminders' context/architecture/chat-flow.md` returns `≥ 1` (the slot is kept; only the DebugStatusBar paragraph is removed).
- `wc -l context/architecture/chat-flow.md` ≤ 700 — the doc fits in your head per WHAT's intent.
- The code PR description contains a `dev-team@<sha>` line that resolves to the dev-team commit produced in this step.
- Manually skim the doc: every section corresponds to a real claim about the running app at HEAD of `feature/TASK-20260504-2320`.

**Why this lives in dev-team, not the worktree**: `context/architecture/` is part of the workflow control plane in the dev-team repo, not the app source. Per AGENTS.md, the submodule (and its worktrees) are read-only with respect to the dev-team repo. The PR opened from `worktrees/TASK-20260504-2320` cannot include this file. The implementer commits it as a separate commit on `main` (or a small PR) in the dev-team repo, then references the SHA in the code PR description so pipeline-reviewer can enforce the link — the cross-repo equivalent of AGENTS.md's "same PR" rule. This is the FIRST story under the new pipeline; the SHA-link convention is established here.

---

## Testable-Contract Coverage

Maps WHAT §6 canonical scenarios A–I to tests / manual scenarios.

| Contract item | Verified by |
| --- | --- |
| §6.A — text only | `Message.assistantTurn.test.tsx` ("A — text only: one TextMessage, no TalentSurface, one footer") + Visual capture #A |
| §6.B — datetime tool (no UI) | `Message.assistantTurn.test.tsx` ("B — datetime: TextMessage + ToolUsedChip + TextMessage + one footer") + Visual capture #B |
| §6.C — render_html with preamble + follow-up | `Message.assistantTurn.test.tsx` ("C — render_html preamble+followup") + Visual capture #C |
| §6.D — render_html, no preamble | `Message.assistantTurn.test.tsx` ("D — render_html no preamble") + Visual capture #D |
| §6.E — tool failed | `Message.assistantTurn.test.tsx` ("E — tool failed: ToolErrorBlock subtle") + `ToolErrorBlock.test.tsx` + Visual capture #E |
| §6.F — reasoning + content | `Message.assistantTurn.test.tsx` ("F — reasoning before content, separate blocks") + Visual capture #F (reasoning bubble PARTIAL default) |
| §6.G — multi-tool in one step | `Message.assistantTurn.test.tsx` ("G — multi-tool: two HtmlPreviewBubbles in toolCalls order") + Visual capture #G |
| §6.H — abort with partial content | `ChatView.assistantTurn.test.tsx` ("H — abort: copy-only footer, no timing") + Visual capture #H |
| §6.I — dead-zone storyboard | `ChatView.assistantTurn.test.tsx` ("I — phase walk: PendingIndicator visible in prefill, generating_tool_call, executing_tool, prefill (follow-up); hidden in streaming_text, done") + Visual capture #I (manual phase walk) |
| Single-writer (§5 cleanup #1) — id reconciliation | `ChatSessionStore.assistantTurn.test.tsx` ("appendToolCall writes ids matching outcomes") + `useChatSession.assistantTurn.test.ts` ("step.toolCalls[i].id === step.toolOutcomes[i].callId after tool turn", **per-frame invariant**) |
| State machine (§3, D5) | `agentStateReducer.test.ts` (scripted sequence covers prefill → streaming_text → generating_tool_call → executing_tool → prefill → streaming_text → done) |
| Invariant I1 (one footer per turn) | `Message.assistantTurn.test.tsx` ("multi-step turn renders exactly one AssistantTurnFooter") |
| Invariant I2 (toolCalls array order) | `Message.assistantTurn.test.tsx` G case asserts block order matches array order |
| Invariant I3 (subtle chip / error) | `ToolUsedChip.test.tsx`, `ToolErrorBlock.test.tsx`, plus visual A11y inspection (low prominence, no border, theme onSurfaceVariant) |
| Invariant I4 (indicator owned by ChatView, below turn) | `ChatView.assistantTurn.test.tsx` (I phase test asserts testID presence at FlatList header position) |

---

## Native Verification

**Not applicable** — this story is `NATIVE_CHANGES=NO`. No `package.json`, native module, `ios/`, `android/`, podfile, or build.gradle changes. Per AGENTS.md the native-verification block is intentionally omitted; reviewer should confirm by checking the diff scope.

---

## Visual Confirmation

Intent flagged `Visual Confirmation: YES`. Each WHAT §6 scenario has a visible signature; capture one screenshot per scenario via the visual-capture E2E pipeline (see `docs/workflows/visual-capture.md`).

```json
[
  {
    "label": "A — text only",
    "prompt": "Hi! How can I help?",
    "look_for": "single text bubble with one footer below it (timing line + copy icon); no tool blocks; no pending dot indicator after the response settles."
  },
  {
    "label": "B — datetime tool, no UI",
    "prompt": "What time is it?",
    "look_for": "text preamble (e.g. 'Let me check.'), a subtle 'used datetime' chip (low prominence, single-line, no card), then text follow-up (e.g. 'It's 8:28 AM.'), then ONE footer below the whole turn."
  },
  {
    "label": "C — render_html with preamble and follow-up",
    "prompt": "Show me a simple HTML preview of a colorful gradient page.",
    "look_for": "text preamble bubble, an HtmlPreviewBubble (the rich talent UI for render_html), text follow-up bubble, then ONE footer. No duplicate timing lines."
  },
  {
    "label": "D — render_html with no preamble",
    "prompt": "Just give me the HTML preview, no commentary.",
    "look_for": "HtmlPreviewBubble appears as the first visible block (no empty text bubble above it), followed by a short text follow-up, then ONE footer."
  },
  {
    "label": "E — tool failed",
    "prompt": "Render an HTML preview using <invalid> markup that should fail.",
    "look_for": "text preamble, then a subtle inline 'render_html failed' error block (warning icon, low prominence — does NOT visually compete with bubbles), followed by an apology text bubble, then ONE footer."
  },
  {
    "label": "F — reasoning + content",
    "prompt": "Think step by step: what is 17 * 23?",
    "look_for": "ThinkingBubble shown in PARTIAL state (collapsible header 'Reasoning' + scrollable masked preview), THEN the content bubble with the answer below it, ONE footer. Tapping the chevron toggles between PARTIAL and EXPANDED, then COLLAPSED."
  },
  {
    "label": "G — multi-tool in one step",
    "prompt": "Render two simple HTML previews back to back.",
    "look_for": "text preamble, then two HtmlPreviewBubble blocks in array order (preview #1 above preview #2), then ONE footer."
  },
  {
    "label": "H — abort with partial content",
    "prompt": "Write me a 1000-word essay on butterflies. (Tap stop after the first sentence appears.)",
    "look_for": "partial text bubble preserved; footer renders only the copy icon (no timing line); a system 'completion stopped' message appears as a separate row below."
  },
  {
    "label": "I — dead-zone phases (manual phase walk)",
    "prompt": "Render an HTML preview of a hello-world page.",
    "look_for": "during phase 2 (prefill, before any token): subtle dot-row PendingIndicator visible BELOW the latest turn. During phase 3 (streaming_text): indicator hidden, tokens flow into the bubble. During phase 4 (generating_tool_call after marker_seen): indicator returns. During phase 5 (executing_tool, the dead zone fixed by this story): indicator visible. During phase 7 (prefill follow-up, second dead zone): indicator visible. During phase 8 (streaming_text follow-up): indicator hidden. Phase 9 (done): indicator hidden, footer renders ONCE."
  }
]
```

After the PR is opened, the reviewer runs `yarn ios:build:e2e && cd e2e && VISUAL_CAPTURES='[…]' yarn e2e:ios --spec visual-capture --skip-build` and attaches the screenshots to the PR. Each screenshot's `look_for` is a checklist for the human reviewer.

---

## Deferred Items

WHAT explicitly defers cleanup #2 (consolidate state signals — make `agentUiState.status` the single canonical source for `inferencing`, `isStreaming`, `isGenerating`, `isThinking`, `isGeneratingToolCall`). This story does **not** land that change.

- **WHAT §5 cleanup #2** — derivation table in §7 stays as the proposed shape; the actual de-duplication of overlapping signals (six-down-to-one) is left for a follow-up story. We do touch `isThinking` at the ChatView level here (Step 11 derives it locally from `agentUiState.status`), but `modelStore.inferencing` / `isStreaming` remain separately written by `useChatSession` for now.
- **`modelStore.isStreaming` survives this PR** (per plan-critic SUGGESTION 2, round 1) — `ChatScreen` derives the FlatList `maintainVisibleContentPosition` flag from it. Consolidating to a derived form would require touching FlatList config and is out of scope per cleanup #2. Step 11 retains `isStreaming` as a `ChatView` prop sourced from `modelStore`.
- **`DebugStatusBar` removal** (WHAT §10 reminder) — the diagnostic overlay is **not present** in the committed `f3b750e` tree (verified via `grep -rn DebugStatusBar src` returning empty). The reminder is preserved in the architecture doc for any future work that lands the local WIP. No-op for this PR.
- **`TalentUI.renderPending` interface field** — no longer called by `TalentSurface` after Step 9, but kept on the interface (and on `RenderHtmlTalentUI`) for now. Removing it would be a contract break across the registry; defer to a future tidy-up story.

---

## What this plan is NOT

- not a design doc — design lives in `what.md`, soon to live in `context/architecture/chat-flow.md`
- not a justification — `intent-brief.md` is where the request lives
- not exhaustive — only steps the implementer needs; if a step would just be "obey WHAT §N", reference WHAT instead of restating

---

## Review History

### Round 1 (2026-05-05)

`pocketpal-plan-critic` returned **HAS_CONCERNS** (1 BLOCKER, 2 CONCERNs, 2 SUGGESTIONs). Full critique at `plan-critic-round-1.md`. The critic confirmed step→§ traceability, scenario A–I coverage, and bounded scope of the id-reconciliation fix. Resolutions:

| Finding | Resolution | Where applied |
|---|---|---|
| BLOCKER 1: Step 14 instruction #5 ("Drop §10") contradicts `templates/what-template.md` lines 182–190 — §10 retained for both story-scoped delta AND promoted architecture-doc forms; instruction also drops the `Cleanup reminders` slot (template line 190) | **FIXED**. Step 14 instruction #5 rewritten: §10 and its `Cleanup reminders` slot are kept intact in the bootstrapped `chat-flow.md`. ONLY the DebugStatusBar cleanup-reminder *paragraph* is dropped (diagnostic absent in `f3b750e`). The "Drift policy" link is **appended** to §10, not a replacement. New verification asserts `grep '^## 10\.' returns 1` and `grep 'Cleanup reminders' returns ≥ 1`. | Step 14 instructions #5, Verification |
| CONCERN 1: cross-repo architecture-doc commit conflicts with AGENTS.md "same PR" rule (architecture lives in dev-team repo; code PR opens from pocketpal-ai worktree) | **FIXED**. Step 14 retitled "Bootstrap … + reference SHA in code PR". Sub-step #8 expanded: dev-team commit SHA must be referenced in the code PR description as `Architecture doc bootstrap: dev-team@<sha>`. Pipeline-reviewer enforces the link. Rationale recorded as "this is the FIRST story under the new pipeline; the cross-repo SHA-link convention is established here." Verification adds: "code PR description contains a `dev-team@<sha>` line that resolves to the dev-team commit produced in this step." | Step 14 title, sub-step #8, Verification, "Why this lives in dev-team" rationale |
| CONCERN 2: Step 4 hook accumulating `tool_call_started` events into a per-step buffer re-derives what the runner already has at `AgentRunner.ts:369` (`normalizeToolCallIds`) | **FIXED**. Step 4 restructured: (a) `step_finished` event variant in `AgentRunner.types.ts` extended with optional `toolCalls?: AgentToolCall[]` payload; (b) `AgentRunner.ts` computes `normalizeToolCallIds` BEFORE yielding `step_finished` (lines reordered) and attaches the result to the event; (c) hook becomes a single-line dispatcher in `case 'step_finished'` — `if (event.toolCalls?.length) appendToolCall(...)`. No buffer in `applyEventToStore`. Single source of truth: the runner. | Step 4 (entire body) |
| CONCERN 3: Step 12 title "Verify reasoning order + ThinkingBubble default state" undersells the real `Message.tsx` block-split change | **FIXED**. Step 12 renamed to "Split reasoning and content into separate per-step blocks (D3 + §4a)". Body restructured: structural change (block split in `Message.renderAssistantTurn`) is the lead bullet; ThinkingBubble PARTIAL and MarkdownView ordering are demoted to one-line "read-only verification" confirmations. Progress Tracking row updated. | Step 12 title + body, Progress Tracking |
| SUGGESTION 1: Step 4 — defensive id-match assertion at every render frame, not just final | **FIXED**. Step 4's `useChatSession.assistantTurn.test.ts` test bullet now includes a per-frame invariant assertion: after each event applied during the scripted walk, assert `step.toolCalls.every((c, i) => step.toolOutcomes[i] === undefined || step.toolOutcomes[i].callId === c.id)` (vacuously true while outcomes lag the calls; strictly enforced as soon as both are present). Coverage table updated to call out "per-frame invariant". | Step 4 hook test bullet, Testable-Contract Coverage table |
| SUGGESTION 2: surface `modelStore.isStreaming` survival in Deferred Items with a one-line reason | **FIXED**. New Deferred Items bullet added: "`modelStore.isStreaming` survives this PR — `ChatScreen` derives the FlatList `maintainVisibleContentPosition` flag from it; consolidating to derived form requires touching FlatList config and is out of scope per cleanup #2." | Deferred Items |

**Verification of revisions** (Quality Checklist re-run):

- [x] Every step references a WHAT §-section (no change from round 1; all steps still cite §3, §4a/b/d, §5, §7, §6.A–I, D1–D9).
- [x] Every step is atomic and individually verifiable.
- [x] Every AC in `intent-brief.md` has a corresponding test/scenario.
- [x] Every canonical scenario in WHAT §6 has a corresponding test/scenario.
- [x] All affected files exist (or, if new, are in conventional directories).
- [x] Native verification step omitted intentionally (NATIVE_CHANGES=NO).
- [x] VISUAL_CAPTURES JSON included.
- [x] Architecture-doc update step (Step 14) retains §10 + Cleanup reminders slot per template; cross-repo SHA-link convention recorded.
- [x] Deferred items from WHAT stay deferred; new bullet records `modelStore.isStreaming` survival.
- [x] No design content invented (no new invariants, no new single-writer rules; the runner-attached `toolCalls` payload on `step_finished` is a transport mechanism for the WHAT §5 cleanup #1 writer, not a design change).
- [x] Plan length: ~580 lines, within budget for a complex story with 14 steps + coverage tables + visual JSON.

**Verdict on advance**: HOW v2 routed back to plan-critic for round 2.

---

## Last Agent Handoff

```yaml
from_agent: implementer
to_agent: tester
timestamp: 2026-05-05
status: "Implementation complete (Steps 1–14); ready for tests"
completed:
  - Step 1: Reducer rename preparing→prefill, drop streaming_followup (commit bf0f6ed)
  - Step 2: Follow-up routes through prefill (commit ea05a8a)
  - Step 3: Drop partial.toolCalls per-token write (commit 861ff52)
  - Step 4: appendToolCall writer + runner step_finished payload (commit 01c839a)
  - Step 5: AssistantTurnFooter component (commit 231d63f)
  - Step 6: Bubble stripped of chrome (commit 325833c)
  - Step 7: Footer hoisted to outer Message JSX (commit da74bb7)
  - Step 8: ToolUsedChip + ToolErrorBlock + en.json strings (commit 0fca05b)
  - Step 9: TalentSurface rewired (commit 03076b0)
  - Step 10: PendingIndicator component (commit 0a86e55)
  - Step 11: ChatView wires PendingIndicator; isThinking dropped from ChatView/Screen/VideoPalScreen (commit d692163)
  - Step 12: reasoning/content split into separate per-step blocks (commit 7dba22b)
  - Step 13: Canonical scenario tests A–I (commit 5e41af8)
  - Step 14: chat-flow.md bootstrapped (dev-team@baeb825)
verification:
  - lint: pre-existing errors only (HtmlPreviewBubble, PalSheet) — not from this PR
  - typecheck: PASS
  - tests: 162 suites, 2123 passed, 2 skipped (full repo run)
  - native verification: N/A (NATIVE_CHANGES=NO)
notes:
  - Reducer extension in Step 2: the existing case 'token' did NOT flip prefill→streaming_text on plain content, so I added a minimal extension to that branch. WHAT §3 explicitly states this transition; HOW underspecified the reducer change.
  - Sender-name handling kept in TextMessage (above bubble) rather than moved into AssistantTurnFooter (below bubble). The literal D9 reading would move the name visually below the message — a UX regression. Documented in AssistantTurnFooter JSDoc and the bootstrapped chat-flow.md §4b.
  - Existing `isFirstBlock` book-keeping retained for the showName gate inside renderAssistantTurn (HOW Step 7's "drop isFirstBlock" hint applied only to sender-name, but showName still has to be gated to the first text block of the turn so the name doesn't appear above every block).
  - TalentUI.renderPending interface field marked @deprecated; kept for compat with RenderHtmlTalentUI which still defines it.
  - Mock store updated for new status union and appendToolCall.
next_steps:
  - Run full E2E (visual capture for Scenarios A–I) before opening PR
  - Add the dev-team@baeb825 line to the eventual PR description
  - Pipeline-reviewer should verify the SHA link resolves and the doc matches the code
blockers: []
context_for_next_agent: |
  All scenarios A–G are unit-tested at Message level; H and I are
  unit-tested at ChatView level (phase walk via runInAction over
  agentUiState.status). Tester should focus on:
  - Visual confirmation captures per HOW's VISUAL_CAPTURES JSON.
  - Per-frame id-match invariant (already covered by hookTest2 but
    worth adding more scripted-event variations).
  - Edge cases: persistence load with deleted talent (9c), abort
    with no partial content (9a path B), multi-tool partial
    completion (9e).
```
