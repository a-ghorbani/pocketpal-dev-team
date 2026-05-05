# Chat Flow

**Purpose**: cumulative architecture truth for the chat rendering, streaming,
tool-calling, and agent-loop behaviour. Bootstrapped from the AssistantTurn
rendering refactor (TASK-20260504-2320, building on TASK-20260502-2115). Meant
to fit in your head.

Convention used in this doc:

- **(C)** = current behaviour, documented from code
- **(D)** = decision (was an open question, now resolved)

---

## 1. Data model

```
Session
  messages: Message[]                      // [0] = newest (unshift)
    UserText           { id, text, ... }
    AssistantTurn      { id, createdAt, metadata, steps: AgentStep[] }
        metadata                            // turn-level chrome + run flags
            timings?         : { tokensPerSecond, msPerToken, timeToFirstTokenMs, ... }
            completionResult?: raw final result from llama.rn
            copyable?        : boolean      // turn has user-visible content worth copying
            interrupted?     : boolean      // run failed/aborted with partial content
            hitMaxTurns?     : boolean      // agent loop hit the max-turns guard
        AgentStep
            content?         : string      // assistant-visible text for this step
            reasoningContent?: string      // <think>...</think>, rendered (D3)
            toolCalls?       : AgentToolCall[]
            toolOutcomes?    : AgentToolOutcome[]
            partial?         : boolean     // true while streaming, false on step_finished
        AgentToolCall                      // OpenAI function-call shape
            { id, type: 'function', function: { name, arguments } }
        AgentToolOutcome
            callId, toolName, result: TalentResult, responseContent
        TalentResult
            { type: 'html', html, title, summary }
            { type: 'text', summary }
            { type: 'audio', audioUri, summary }
            { type: 'error', summary, errorMessage }
```

Stored on disk: everything inside `AssistantTurn` (via `ChatSessionRepository`).
Computed at render time only: visible block list, "is this the active run", "is
the indicator on".

A turn always has at least one step. Steps are appended; existing steps are
updated in place during streaming.

**Glossary** — terms used elsewhere in this doc:

- **TalentUIRegistry** — `Map<toolName, TalentUI>` populated at startup. Each
  entry provides a `renderResult(result)` method. A lookup miss means the tool
  has no registered UI and falls back to the subtle tool-used chip (I3).
- **TalentUI** — interface implemented by per-tool render adapters (e.g.
  `RenderHtmlTalentUI`).
- **TalentEngine** — the executor side: `execute(args) → Promise<TalentResult>`.
  Engines and UIs live in separate registries; a tool can have an engine
  without a UI (datetime, calculate) but not the other way around.

---

## 1b. Ours vs OpenAI / llama.rn shape

Storage and in-memory: **rolled-up** (`AssistantTurn` with `steps[]`,
tool outcomes nested in their step).
Wire (sent to llama.rn) and visual display: **flat OpenAI shape**.

Conversion happens at the wire boundary — `toApiCompletionParams` /
`convertToChatMessages` flatten our turn into the OpenAI message array before
each call:

```
AssistantTurn { steps: [s₀, s₁] }
   ─ flatten ─►
[ assistant(s₀.content, s₀.toolCalls),
  tool(callId, s₀.toolOutcomes[i].responseContent),     // one per outcome
  assistant(s₁.content) ]
```

OpenAI / llama.rn message-array shape (what we send back to the model and what
llama.rn emits):

```js
[
  { role: 'user',      content: 'show me ...' },
  { role: 'assistant', content: "Sure, here's a preview.",
                       tool_calls: [
                         { id: 'call_xxx', type: 'function',
                           function: { name: 'render_html', arguments: '{...}' } }
                       ] },
  { role: 'tool',      tool_call_id: 'call_xxx', content: '<summary string>' },
  { role: 'assistant', content: 'Hope this looks right.' }
]
```

Three flat messages for the assistant side: assistant(preamble+toolcall) → tool(result) → assistant(followup).

Our AssistantTurn shape (one row per turn):

```js
AssistantTurn {
  steps: [
    step₀ { content: "Sure, here's a preview.",
            toolCalls:    [{ id: 'call_xxx', function: {name, arguments} }],
            toolOutcomes: [{ callId: 'call_xxx',
                             result: { type:'html', html, title, summary },
                             responseContent: '<summary string>' }] },
    step₁ { content: "Hope this looks right." }
  ]
}
```

The renderer mirrors the same flat shape on screen — one block per implicit
message — which is why §4's per-step interleave matches what the user expects.

Same scenario, two views:

| OpenAI / llama.rn flat                           | Ours (one row)                                  |
|--------------------------------------------------|-------------------------------------------------|
| `assistant{ content, tool_calls[] }`             | `step₀ { content, toolCalls[] }`                |
| `tool{ tool_call_id, content: string }`          | `step₀.toolOutcomes[{ callId, result, responseContent }]` |
| `assistant{ content }` (follow-up)               | `step₁ { content }`                             |

Differences worth remembering:

- their `tool.content: string` ↔ our `result: TalentResult` (rich union) +
  `responseContent: string` (the string we send back)
- their `id` is often `null` / `""` from llama.rn → we reconcile to a synthetic
  `call_<seed>_<idx>` so our outcomes match by id
- `reasoning_content` is a llama.cpp extension, mirrored by `step.reasoningContent`
- `step.partial` is ours only — needed for streaming UI

---

## 2. Event flow (runner → hook → store)

```
run_started
  step_started turn=0 isFollowUp=false        → push empty step
    token+                                    → write content / reasoning
    [marker_seen]                             → sentinel matched in raw text
  step_finished turn=0 (toolCalls?)           → if toolCalls present, appendToolCall
  [tool_call_started + tool_call_finished]+   → one pair per tool call
  [step_started turn=1 isFollowUp=true        → push empty step
     token+
   step_finished turn=1]
run_finished | run_failed
```

Per-token deltas carry **per-turn cumulative** values. `accumulated_text` is the
raw model output; `content` is the same text with tool-call sentinels and JSON
stripped by llama.rn. The `step_finished` event carries an optional
`toolCalls?: AgentToolCall[]` payload — the runner's authoritative
normalized list (synthetic ids reconciled with outcomes); the hook calls
`appendToolCall` with that list once per step.

---

## 3. State machine (agentStateReducer)

`streaming_followup` was collapsed per **D5**. `streaming_text` means "tokens
are flowing right now," independent of which turn. After a tool call finishes,
the follow-up step transitions back to `prefill` (waiting for the first
token), and the first content/reasoning token flips it to `streaming_text` —
the same path as the initial step. The `isFollowUp` flag remains on the
`step_started` event for any per-step UI that wants it.

```
idle
  ─run_started→ prefill
                  ─first content/reasoning token→ streaming_text
                                          ─marker_seen→ generating_tool_call
                                                          ─tool_call_started→ executing_tool
                                                                              ─step_started(isFollowUp)→ prefill
                                                                              ─run_finished→ done
                                          ─step_finished w/o tool_calls→ done
  ─run_failed→ failed
```

What the user should see in each state (single rule, no sub-cases):

| State                  | User-visible feedback                                    |
|------------------------|----------------------------------------------------------|
| `idle`                 | nothing (no active turn; persisted blocks only)          |
| `prefill`              | pending indicator (D4) — waiting for first token         |
| `streaming_text`       | text appearing in bubble — no indicator                  |
| `generating_tool_call` | pending indicator — sentinel detected, JSON streaming    |
| `executing_tool`       | pending indicator — tool running                         |
| `done`                 | turn footer (timing, copy)                               |
| `failed`               | inline error indicator                                   |

---

## 4. Rendering contract

For **one** AssistantTurn:

### 4.0 Architecture choice

Chosen architecture: rolled-up `AssistantTurn { steps[] }` storage shape; render
N visual blocks within ONE FlatList row from `Message.renderAssistantTurn`;
chrome (footer, pending indicator) ownership lives at turn-level (Message) and
screen-level (ChatView).

Three plausible alternatives were considered and rejected:

1. **Flatten storage to OpenAI shape** — each step persisted as its own chat
   row. Rejected: turn-level chrome (one footer per turn, sender name on first
   row) becomes harder to coordinate across rows; multi-row updates during
   streaming hurt perf.
2. **Make `Bubble` turn-aware** — pass `isLastBlockInTurn`, render footer only
   when true. Rejected: couples `Bubble` to turn structure; bubble is meant to
   be a pure shape primitive, and this entrenches the chrome-in-bubble pattern
   that produced the duplicate-footer bug.
3. **Synthesise a "footer row" message** — push a virtual chat row after each
   finalized AssistantTurn just to hold the footer. Rejected: invariant "one
   footer per turn" becomes "one synthetic row per turn"; FlatList key drift
   on streaming finalisation; more state plumbing for negligible visual
   benefit.

Chosen path wins because (a) it preserves the rolled-up storage choice, (b)
chrome ownership moves to the turn level cleanly without introducing a new row
type, and (c) the pending indicator lives at ChatView, so the dead-zone
problem is solved at the right layer rather than worked around inside each
bubble.

### 4a. Per-step blocks (in declaration order)

For each step, emit blocks in this order:

1. **reasoning block** — iff `step.reasoningContent?.length > 0` (rendered as
   a separate `TextMessage` block, fed only `reasoningContent`)
2. **content block** — iff `step.content?.length > 0` (rendered as a separate
   `TextMessage` block, fed only `content`)
3. **per-call blocks** — for each call in `step.toolCalls` (in array order),
   emit ONE of (in priority order):
   - **error block (subtle)** — outcome exists and `result.type === 'error'`.
     Low-prominence inline marker (icon + "Tool X failed" + optional
     errorMessage). Must not visually compete with bubbles.
   - **talent block** — outcome exists, non-error, AND a TalentUI is
     registered for the call's name → `ui.renderResult(outcome.result)`.
   - **tool-used chip (subtle)** — outcome exists, non-error, and no
     TalentUI is registered → slim "used X" chip. Same prominence as the
     error block.
   - **(none)** — outcome doesn't exist yet (call is in-flight, between
     `tool_call_started` and `tool_call_finished`). The pending indicator
     on the turn covers feedback during this window; no placeholder block.

If a step has no `toolCalls` array yet, no per-call block is emitted. The
pending indicator already covers feedback during the lead-up.

If a step contributes zero blocks total, it is skipped entirely (no phantom
layout).

### 4b. Turn footer (rendered ONCE per turn)

After the last step block, ONE footer carrying turn-level chrome:

- timing (`metadata.timings`)
- copy button → copies combined turn content (D7)

The footer is rendered by `AssistantTurnFooter` adjacent to the bubble
container in `Message`'s outer JSX (not inside `renderAssistantTurn` /
`renderMessage`), so it's exactly one per assistant row regardless of step
count. Sender-name handling stays in `TextMessage` via the `showName` prop —
sender name appears above the first text block of an assistant group, which
matches today's user-visible behaviour and avoids moving the name below the
bubble (a UX regression we don't want).

### 4c. Hard invariants

- **I1**: exactly one footer per turn, rendered when at least one
  footer-eligible field is present in `metadata` (`timings` or `copyable`).
  Independent of `status`. See D1.
- **I2**: within a step, blocks are ordered reasoning → content → per-call
  blocks in `step.toolCalls` array order. Multi-tool turns render N per-call
  blocks (D6).
- **I3**: tools with no registered UI render as a subtle tool-used chip;
  failed tools render as a subtle error block. Both are low-prominence and
  must not dominate the layout.
- **I4**: pending indicator (D4) is owned by ChatView, NOT by Message — it
  lives below the latest turn during dead zones, never inside one.
  LoadingBubble has been retired from the chat surface.

### 4d. What each component renders

| Component                         | Renders                                                         | Does NOT render            |
|-----------------------------------|-----------------------------------------------------------------|----------------------------|
| `Message.renderAssistantTurn`     | ordered step blocks + ONE footer                                | bubble chrome              |
| `Message` (Text rows, legacy)     | TextMessage wrapped in Bubble + ONE footer (same component)     | duplicate per-step chrome  |
| `TextMessage`                     | text/markdown for ONE block (content-only OR reasoning-only)    | timing, copy               |
| `Bubble`                          | bubble shape (border, bg) around any child                      | timing, copy, name         |
| `TalentSurface`                   | dispatcher → talent UI / tool-used chip / error block, per call | text content               |
| `AssistantTurnFooter`             | timing, copy                                                    | text, talent, sender name  |
| `PendingIndicator`                | subtle dot-row indicator below the latest turn                  | text, chrome               |
| `ChatView`                        | message list + pending indicator                                | per-turn structure         |

**Footer-ownership decision (D9)**: Message owns chrome **universally** for all
assistant rows, not only for `assistant_turn` rows. `Bubble` is a pure shape
primitive (border, bg, no chrome). The legacy Text-row path also routes
through `Message` for chrome (one footer per message, same as today's
user-visible behaviour, just sourced from `AssistantTurnFooter`/Message
rather than from inside Bubble). Rationale: chrome-in-Bubble was the proximate
cause of the duplicate-footer bug; keeping it for Text rows would leave a
drift trap.

The pending indicator's visual is a subtle dot-row (smaller dots than
LoadingBubble, no card background, theme `onSurfaceVariant`), positioned below
the latest turn — see D4.

---

## 5. Layer ownership (single-writer rule)

| Field                                    | Single writer                                       |
|------------------------------------------|------------------------------------------------------|
| `step.content`, `step.reasoningContent`  | throttled streaming via `updateActiveStepStreaming` (`useChatSession.ts` token handler) |
| `step.toolCalls`                         | `appendToolCall` (`ChatSessionStore.ts`), invoked once per step on `step_finished` with the runner's normalized list (no per-token writes; see Cleanup-LANDED below) |
| `step.toolOutcomes`                      | `appendToolOutcome` (`ChatSessionStore.ts`), one per `tool_call_finished` |
| `step.partial`                           | `pushAgentStep` (true), `finalizeActiveStep` (false; `ChatSessionStore.ts`) |
| New step                                 | `pushAgentStep` (`ChatSessionStore.ts`)             |
| `metadata.timings`, `metadata.completionResult` | `updateMessage` at `run_finished` (`useChatSession.ts`) |
| `metadata.copyable`                      | `updateMessage` from EITHER `run_finished` OR the catch path on abort (`useChatSession.ts`). Sequential, not racing. |
| `metadata.interrupted`, `hitMaxTurns`    | `updateMessage` from the catch path / max-turns guard |
| `agentUiState`                           | `agentStateReducer` only (canonical state source)   |
| `modelStore.inferencing` / `isStreaming` | `useChatSession` at run boundaries (legacy; see Cleanup-DEFERRED below) |

Reading is unrestricted.

**Cleanup-LANDED (id reconciliation, was cleanup #1)**: `step.toolCalls` is
appended **once** after `step_finished` via `appendToolCall`, with normalized
ids attached to the event payload by the runner — so
`step.toolCalls[i].id === outcome.callId` holds by construction the moment
outcomes start landing. This replaced the previous per-token write site that
could ship empty / mismatched ids.

**Cleanup-DEFERRED (consolidate state signals, was cleanup #2)**: today there
are several overlapping signals (`agentUiState.status`, `inferencing`,
`isStreaming`, `isGenerating`, `isGeneratingToolCall`, `isThinking`). The
canonical value is `agentUiState.status`; everything else should become a
**computed read** derived from it (see §7). `modelStore.inferencing` /
`isStreaming` may need to remain global (other screens read them — model
loading, settings) but should be derived from agent status rather than
separately written. ChatView already reads `agentUiState.status` directly to
gate the `PendingIndicator` (no `isThinking` prop), so the reducer is the
single source of truth for that signal. Full de-duplication of the other
flags is left for a follow-up story.

---

## 6. Canonical scenarios

What the design must produce. Each scenario should be testable manually and is
covered by tests in `Message.assistantTurn.test.tsx` (A–G), or in
`ChatView.assistantTurn.test.tsx` (H, I).

### A. Text only (no tool)

```
steps = [ { content: "Hi! How can I help?" } ]
─────────────────────────────────────────
  Hi! How can I help?
  ┌──────────────────────────────────┐
  │  32ms/tok | 30 tok/s | 251ms TTFT │   ← footer (×1)
  └──────────────────────────────────┘
```

### B. Tool with NO UI (datetime)

```
steps = [
  { content: "Let me check.", toolCalls: [datetime] },
  { content: "It's 8:28 AM." },
]
─────────────────────────────────────────
  Let me check.
   · used datetime          ← subtle tool-used chip (no UI registered)
  It's 8:28 AM.
  ──── footer ────
```

### C. Tool with UI + preamble + follow-up (render_html)

```
steps = [
  { content: "Sure, here's a preview.",
    toolCalls: [render_html],
    toolOutcomes: [{result: html-ok}] },
  { content: "Hope this looks right." },
]
─────────────────────────────────────────
  Sure, here's a preview.

  ┌──────────────────────┐
  │ [HtmlPreviewBubble]  │
  └──────────────────────┘

  Hope this looks right.
  ──── footer ────
```

### D. Tool with UI, NO preamble

```
steps = [
  { content: "",
    toolCalls: [render_html],
    toolOutcomes: [{result: html-ok}] },
  { content: "There you go." },
]
─────────────────────────────────────────
  ┌──────────────────────┐
  │ [HtmlPreviewBubble]  │
  └──────────────────────┘

  There you go.
  ──── footer ────
```

### E. Tool failed

```
steps = [
  { content: "Trying...",
    toolCalls: [X],
    toolOutcomes: [{result: error, errorMessage: "..."}] },
  { content: "Sorry, couldn't do that." },
]
─────────────────────────────────────────
  Trying...
   ⚠ X failed              ← subtle error block (low prominence)
  Sorry, couldn't do that.
  ──── footer ────
```

### F. Reasoning + content

```
steps = [
  { reasoningContent: "Let me think about this...",
    content: "The answer is 42." },
]
─────────────────────────────────────────
  ┌─ thought ────────────┐
  │ Let me think about… │   ← reasoning block (collapsible, italicized)
  └──────────────────────┘
  The answer is 42.
  ──── footer ────
```

### G. Multi-tool in one step

```
steps = [
  { content: "Here are two:",
    toolCalls: [render_html#1, render_html#2],
    toolOutcomes: [{result: html-ok#1}, {result: html-ok#2}] },
]
─────────────────────────────────────────
  Here are two:
  ┌──────────────────┐
  │ [Preview #1]     │
  └──────────────────┘
  ┌──────────────────┐
  │ [Preview #2]     │
  └──────────────────┘
  ──── footer ────
```

### I. Dead-zone transitions (phase-by-phase storyboard)

This scenario is the visual proof that "no dead zones with no indicator while
the model is working between steps." All other scenarios show end states; this
one shows what's visible at each phase of a tool-call turn. The pending
indicator (D4, owned by ChatView) appears in every state EXCEPT
`streaming_text` and `done`.

```
phase                           | visible state
--------------------------------|----------------------------------------
1. user submits prompt          | (no AssistantTurn yet)
2. status → prefill             | empty turn row + pending indicator below
3. first token                  | ' ↳ status → streaming_text;
                                |   indicator hidden; tokens appear in step₀
4. marker_seen                  | status → generating_tool_call;
                                |   indicator visible; tool-call JSON streams
                                |   (sentinel detected, not yet finalized)
5. step_finished + tool_started | status → executing_tool;
                                |   indicator visible (was the dead zone);
                                |   per-call block not yet present because
                                |   step.toolCalls is finalized after step_finished
                                |   (Cleanup-LANDED)
6. tool_call_finished           | step.toolOutcomes appended; talent block
                                |   (or chip / error block) renders inline
7. step_started(isFollowUp)     | status → prefill (D5);
                                |   indicator visible (this is the second dead
                                |   zone); step₁ row appended (empty content)
8. first follow-up token        | status → streaming_text;
                                |   indicator hidden; tokens appear in step₁
9. step_finished + run_finished | status → done;
                                |   indicator hidden; footer renders ONCE for
                                |   the whole turn (timing + copy)
```

The two dead zones are phases 5 and 7. Both must show the indicator.

### H. Run aborted mid-stream (with partial content)

User tapped stop while step₀ was streaming. The hook's catch path preserves
the turn by writing `metadata: { interrupted: true, copyable: true }` and
appends a system message about the abort below it.

```
steps = [
  { content: "I was about to say...", partial: true },
]
metadata = { interrupted: true, copyable: true }
─────────────────────────────────────────
  I was about to say...
  ──── footer (copy only) ────         ← copy renders, no timing
  ⓘ completion stopped                 ← system message (separate row)
```

If the run was aborted with NO partial content, the hook deletes the empty
turn entirely. No row, no footer — only the system message. See §9a.

---

## 7. State signals — derivation

`agentUiState.status` is canonical. Other signals are computed reads (or
should be — see Cleanup-DEFERRED).

| Signal                               | Where it comes from                     | Read by                       |
|--------------------------------------|------------------------------------------|-------------------------------|
| `agentUiState.status`                | reducer (canonical)                      | everywhere                    |
| `agentUiState.pendingTalentNames`    | reducer                                  | (no UI consumer today; was used by old TalentSurface inline pending paths, now retired) |
| `inferencing` (deferred derivation)  | `status ∉ { idle, done, failed }`        | ChatScreen, model load screens |
| `isStreaming` (deferred derivation)  | `status === streaming_text`              | ChatScreen, ChatView (FlatList) |
| `isGenerating` (deferred derivation) | `status ∉ { idle, done, failed }` (= `inferencing`) | ChatScreen           |
| `isGeneratingToolCall` (deprecate)   | `status === generating_tool_call`        | nothing (legacy, removable)   |
| `isPending` (LANDED, ChatView-local) | `status ∈ { prefill, generating_tool_call, executing_tool }` | ChatView (PendingIndicator) |

Note: `isGenerating` and `inferencing` collapse to the same predicate; one of
them should win the rename when Cleanup-DEFERRED lands.

---

## 8. Decisions

- **D1**: Footer renders whatever footer-eligible fields are present in
  `metadata`. Each field is independent — no all-or-nothing gating:
  - `metadata.timings` present → render the timing line.
  - `metadata.copyable` true → render the copy button.

  The rule is "show what we have." The outcome of the run (done, interrupted,
  failed) does not gate the footer; only field presence does. If llama.rn
  returns partial timings on a mid-stream stop, write them to `metadata.timings`
  and the footer will render them. If a turn is mid-stream and not yet
  copyable, neither field is set, so nothing renders.

  Implementation note: today the hook writes `timings` only on `run_finished`
  and `copyable` only in the catch path. Preserving partial timings on
  interruption is a future enhancement at the writer side; the renderer
  contract above already supports it.
- **D2**: Failed tool → subtle inline error block. Default copy
  "Tool call failed" when no errorMessage. Must NOT visually compete with
  the rest of the turn.
- **D3**: Reasoning content is rendered, per step, BEFORE that step's content
  (matches model emission order). Visual: `ThinkingBubble` with
  `BubbleState.PARTIAL` initial state. User can still toggle to COLLAPSED or
  EXPANDED; the default initial state is PARTIAL.
- **D4**: Replace LoadingBubble with a subtle **dot-row indicator**
  (`PendingIndicator` component) positioned **below the latest turn**, owned
  by ChatView (I4). Visual is a low-prominence dot row (4px dots, no
  card-style background, `onSurfaceVariant` colour); minimal vertical space;
  signals "more is coming."
- **D5**: `streaming_followup` was collapsed into `streaming_text`. The
  `step_started.isFollowUp` flag remains on the event for any per-step UI
  that wants it. Follow-up steps route through `prefill` so the indicator
  covers the dead zone between tool finish and the first follow-up token.
- **D6**: Multi-tool turns render N per-call blocks in `step.toolCalls` array
  order. Made an explicit invariant (I2).
- **D7**: Copy semantics = **all step content joined per turn** (no
  reasoning, no tool-call JSON). Not per-step.
- **D8**: Persistence — if a TalentUI isn't registered at load time, fall
  back to the tool-used chip (or error block for failed outcomes). No
  schema change required.
- **D9**: Footer ownership is moved out of `Bubble` for **all** assistant
  rows — not only for `assistant_turn` rows. Bubble is a pure shape primitive
  (border, bg, no chrome). Message owns timing/copy rendering universally
  via `AssistantTurnFooter`. Rationale: chrome-in-Bubble was the proximate
  cause of the duplicate-footer bug; keeping it for legacy Text rows would
  leave a drift trap.

---

## 9. Edge cases

The decisions in §8 imply behaviours the §6 scenarios don't show explicitly.
Captured here so they don't surface as "but what about…" later.

### 9a. Cancel / abort mid-stream

User taps stop while the run is in flight.

- The runner's abort signal fires; the in-flight `engine.completion(...)`
  returns whatever it has.
- The hook catches the resulting throw. **If** the partial turn has any
  visible content (text or tool calls), it writes
  `metadata: { interrupted: true, copyable: true }` and the turn is preserved
  (Scenario H). Otherwise the empty turn is deleted — no row, only a system
  message about the abort.
- `step.partial` may remain `true` (no `step_finished` fired). The renderer
  treats partial steps the same as finalized ones for display.
- Reducer transitions to `idle` (the catch path resets `agentUiState`); the
  pending indicator stops.
- D1 / I1 already handle the footer correctly: copy renders because
  `metadata.copyable` is set; timing does not render because
  `metadata.timings` is not set.

### 9b. Empty turn (zero visible blocks)

Theoretically possible if a model emits only whitespace, no reasoning, no
content, and a tool call with no registered UI and no follow-up. The §4a skip
rule produces zero blocks. The chat row would render an empty container.
Treat as a model bug — log and accept the empty row. Not worth designing
extra UI for.

### 9c. Persistence load — missing TalentUI

App reloads a chat from disk. A turn references a tool whose
`TalentUIRegistry` entry was removed (talent deleted from the build, or
registry not initialised yet at first paint).

- `talentUIRegistry.get(name)` returns `undefined`.
- Per §4a, falls through to the **tool-used chip** (or **error block** if the
  outcome was an error).
- No schema change required (D8). The chip shows the tool's name from the
  persisted call data; the user knows what was attempted even if the rich
  UI is gone.

### 9d. Race between state flip and step push (follow-up)

The reducer flips `executing_tool → prefill` on `step_started(isFollowUp)`.
The hook also calls `pushAgentStep` to create the new step. If a render
happens between the state flip and the step push (or vice versa), the
renderer sees `prefill` status with `lastStep` still being step 0. The
pending indicator renders correctly because §7's `isPending` derivation reads
only `status`, not step content. Single-frame artifact at most; no
functional issue.

### 9e. Multi-tool partial completion

Step₀ has two tool calls. The first succeeds, the second fails.

- `step.toolCalls = [A, B]`, `step.toolOutcomes = [{ok}, {error}]`
- §4a iteration emits one talent block (A) followed by one error block (B),
  in array order (I2).
- The follow-up step proceeds normally; the model can apologise for B,
  proceed without it, or both.

---

## 10. What this doc is NOT

- not a TODO list
- not an implementation plan (those live in `how.md`)
- not a record of recent fixes (those live in commits)

When this doc and a commit disagree, the commit wins — but then this doc must
be updated in the same change. Drift is the failure mode that will bring back
the ping-pong.

**Cleanup reminders**: none currently outstanding. Future stories that touch
this flow should add their cleanup reminders here and remove them as they
land. Drift policy: see `context/architecture/README.md` § Drift prevention.
