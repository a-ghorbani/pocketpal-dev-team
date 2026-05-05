# AssistantTurn — Architecture & Flow Board

**Purpose**: a shared design board to align on the rendering architecture before
any further code changes. Verbose investigation notes were intentionally
stripped on 2026-05-04. This doc is meant to fit in your head.

Convention used in this doc:

- **(C)** = current behaviour, documented from code
- **(P)** = proposal, open for challenge
- **(?)** = open question, decision needed
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
  `call_<seed>_<idx>` so our outcome match by id works
- `reasoning_content` is a llama.cpp extension, mirrored by `step.reasoningContent`
- `step.partial` is ours only — needed for streaming UI

---

## 2. Event flow (runner → hook → store)

```
run_started
  step_started turn=0 isFollowUp=false        → push empty step
    token+                                    → write content / reasoning / toolCalls
    [marker_seen]                             → sentinel matched in raw text
  step_finished turn=0
  [tool_call_started + tool_call_finished]+   → one pair per tool call
  [step_started turn=1 isFollowUp=true        → push empty step
     token+
   step_finished turn=1]
run_finished | run_failed
```

Per-token deltas carry **per-turn cumulative** values. `accumulated_text` is the
raw model output; `content` is the same text with tool-call sentinels and JSON
stripped by llama.rn.

---

## 3. State machine (agentStateReducer)

`streaming_followup` is collapsed per **D5**. `streaming_text` means "tokens
are flowing right now," independent of which turn. After a tool call finishes,
the follow-up step transitions back to `prefill` (waiting for the first
token), and the first content/reasoning token flips it to `streaming_text` —
the same path as the initial step. The `isFollowUp` flag remains on the
`step_started` event for any per-step UI that wants it.

The state name `prefill` is new; today the reducer uses `preparing`. The rename
matches the conceptual model (waiting for the first token) and is part of the
proposal — see (P) in §4d's component table.

**(P)** the follow-up's path *through* `prefill` is also a behaviour change,
not just a rename. Today (`agentStateReducer.ts:33–38`) the reducer transitions
`executing_tool → streaming_followup` directly on `step_started(isFollowUp)`,
with no `prefill` intermediate. The proposal routes the follow-up through
`prefill` so the indicator (D4) covers the dead zone between the tool finishing
and the first follow-up token — see Scenario I phase 7.

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

## 4. Rendering contract (the missing piece)

For **one** AssistantTurn:

### 4.0 Architecture choice

The chosen architecture: keep PR #709's rolled-up `AssistantTurn { steps[] }`
storage shape; render N visual blocks within ONE FlatList row from
`Message.renderAssistantTurn`; move chrome (footer, pending indicator) ownership
out of `Bubble` to turn-level (Message) and screen-level (ChatView).

Three plausible alternatives were considered:

1. **Flatten storage to OpenAI shape** — each step persisted as its own chat
   row. Pros: matches wire format; FlatList cell-per-message reuse simpler.
   Cons: turn-level chrome (one footer per turn, sender name on first row)
   becomes harder to coordinate across rows; multi-row updates during streaming
   hurt perf; conflicts with PR #709's just-landed storage choice.
2. **Make `Bubble` turn-aware** — pass `isLastBlockInTurn`, render footer only
   when true. Pros: minimal API surface change. Cons: couples `Bubble` to turn
   structure; bubble is meant to be a pure shape primitive, and this entrenches
   the chrome-in-bubble pattern that produced the duplicate-footer bug.
3. **Synthesise a "footer row" message** — push a virtual chat row after each
   finalized AssistantTurn just to hold the footer. Pros: cleanest separation
   between content and chrome. Cons: invariant "one footer per turn" becomes
   "one synthetic row per turn"; FlatList key drift on streaming finalisation;
   more state plumbing for negligible visual benefit.

Chosen path wins because (a) it preserves PR #709's storage choice, (b) chrome
ownership moves to the turn level cleanly without introducing a new row type,
and (c) the pending indicator lifts to ChatView, so the dead-zone problem
(intent issue #2) is solved at the right layer rather than worked around inside
each bubble.

### 4a. Per-step blocks (in declaration order)

For each step, emit blocks in this order:

1. **reasoning block** — iff `step.reasoningContent?.length > 0`
2. **content block** — iff `step.content?.length > 0`
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

If a step has no `toolCalls` array yet but is the active step and
`pendingTalentNames` lists a registered talent (early streaming, before
the runner emits `tool_call_started`), no per-call block is emitted. The
pending indicator already covers feedback during the lead-up.

**(P)** Today's TalentSurface inline pending paths (`renderPending` per call
at lines 71–77, the `pendingTalentNames` skeleton at lines 83–87, and the
generic `isGeneratingToolCall` fallback at lines 102–130) become unreachable
under this rule once the indicator lifts to ChatView. They should be removed
in this PR; leaving them in produces two competing pending UIs (dot-row
below the turn AND inline skeletons inside it) during in-flight phases.

If a step contributes zero blocks total, skip it entirely (no phantom layout).

### 4b. Turn footer (rendered ONCE per turn)

After the last step block, ONE footer carrying turn-level chrome:

- timing (`metadata.timings`)
- copy button → copies combined turn content (D7)
- sender name (only if `showName` and turn is first in group)

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
  LoadingBubble is replaced.

### 4d. What each component renders

| Component                         | Renders                                                         | Does NOT render            |
|-----------------------------------|-----------------------------------------------------------------|----------------------------|
| `Message.renderAssistantTurn`     | ordered step blocks + ONE footer                                | bubble chrome              |
| `Message` (Text rows, legacy)     | TextMessage wrapped in Bubble + ONE footer (same component)     | duplicate per-step chrome  |
| `TextMessage` **(P)**             | text/markdown + reasoning for ONE step                          | timing, copy, name         |
| `Bubble` **(P)**                  | bubble shape (border, bg) around any child                      | timing, copy, name         |
| `TalentSurface`                   | dispatcher → talent UI / tool-used chip / error block, per call | text content               |
| `AssistantTurnFooter` **(P)**     | timing, copy, sender name                                       | text, talent               |
| `PendingIndicator` **(P)**        | subtle dot-row indicator below the latest turn                  | text, chrome               |
| `ChatView`                        | message list + pending indicator                                | per-turn structure         |

The **(P)** rows are proposed changes. Today the duplicate-footer bug has a
specific cause: `Bubble` (`Bubble.tsx:93–104`) renders the footer (timing +
copy) whenever `metadata.timings` is set, and `Message.renderAssistantTurn`
wraps **each step's text fragment** in a fresh `Bubble` via
`oneOf(renderBubble, ...)` (`Message.tsx:288–303`) — so an N-step turn renders
N footers.

**Footer-ownership decision (D9)**: Message owns chrome **universally** for
all assistant rows in this PR, not only for `assistant_turn` rows. `Bubble`
loses its timing/copy/name rendering and becomes a pure shape primitive. The
legacy Text-row path also routes through `Message` for chrome (one footer per
message, same as today's user-visible behaviour, just now sourced from
`AssistantTurnFooter`/Message rather than from inside Bubble). Rationale: the
chrome-in-Bubble pattern was the proximate cause of the duplicate-footer bug;
keeping it for Text rows would leave a drift trap. The story is already
"complex"; we pay the cost once.

The pending indicator's visual is a subtle dot-row (matches the LoadingBubble
shape but at lower prominence), positioned below the latest turn — see D4.
Component name `PendingIndicator` is neutral; the previous draft's
`PulsingCaret` implied a single text-marker character, which mismatched the
dot-row visual the intent specified.

---

## 5. Layer ownership (single-writer rule)

| Field                                    | Single writer (current) **(C)** / proposed **(P)**  |
|------------------------------------------|------------------------------------------------------|
| `step.content`, `step.reasoningContent`  | **(C)** throttled streaming via `updateActiveStepStreaming` (`useChatSession.ts:217–233`) |
| `step.toolCalls`                         | **(C)** `updateActiveStepStreaming` writes `partial.toolCalls = event.delta.toolCalls` per token (`useChatSession.ts:222–224`). **(P)** new `appendToolCall` writes once after `step_finished`; streaming partial no longer carries `toolCalls`. See cleanup #1. |
| `step.toolOutcomes`                      | **(C)** `appendToolOutcome` (`ChatSessionStore.ts:754`) |
| `step.partial`                           | **(C)** `pushAgentStep` (true), `finalizeActiveStep` (false; `ChatSessionStore.ts:801`) |
| New step                                 | **(C)** `pushAgentStep` (`ChatSessionStore.ts:716`) |
| `metadata.timings`, `metadata.completionResult` | **(C)** `updateMessage` at `run_finished` (`useChatSession.ts:256–266`) |
| `metadata.copyable`                      | **(C)** `updateMessage` from EITHER `run_finished` (`useChatSession.ts:262`) OR the catch path on abort (`useChatSession.ts:498`). Sequential events; not a race, just two write sites both routing through `updateMessage`. |
| `metadata.interrupted`, `hitMaxTurns`    | **(C)** `updateMessage` from the catch path / max-turns guard |
| `agentUiState`                           | **(C)** `agentStateReducer` only (canonical state source) |
| `modelStore.inferencing` / `isStreaming` | **(C)** `useChatSession` at run boundaries (legacy; see cleanup #2) |

Reading is unrestricted.

**Deferred cleanup #1 — split `step.toolCalls` writer from the streaming
partial** (do during the refactor):

- *Today* (`useChatSession.ts:217–233`): every `token` event hits
  `updateActiveStepStreaming(...)` with a partial that includes
  `toolCalls: event.delta.toolCalls` — so `step.toolCalls` is rewritten on
  every token. The accumulator-side ids come from `projectStreamChunk`
  (`tc.id ?? ''`) and may be empty strings.
- *Separately*, after each `tool_call_started` the runner emits its
  *normalized* call ids (synthetic `call_<seed>_<idx>` from
  `normalizeToolCallIds`) into `step.toolOutcomes[i].callId`. These are NOT
  the same string as the per-token ids that landed via the streaming partial.
- Consequence: TalentSurface's id-match (`outcome.callId === tc.id`) silently
  drops talent blocks whenever the streaming-side id is empty or mismatched.
  This is a real, latent bug in PR #709, exposed by the new design's promotion
  of `step.toolCalls` to a renderer-driving field.
- *Proposal*: stop streaming `toolCalls` into the partial. Introduce a single
  `appendToolCall` writer that fires *after* `step_finished` with the
  runner's normalized ids — so `step.toolCalls[i].id === outcome.callId` by
  construction. Mirrors `appendToolOutcome`. Until step_finished, the renderer
  shows the pending indicator (D4); per-call blocks appear only once the call
  is settled, which matches the user's mental model anyway.
- The existing `reconcileActiveStepToolCall` function is *not* part of the
  current code path; it's a name that appeared in earlier drafts of this WHAT.
  The new writer is named `appendToolCall` and added in this PR.

**Deferred cleanup #2 — consolidate state signals**: today there are six
overlapping signals (`agentUiState.status`, `inferencing`, `isStreaming`,
`isGenerating`, `isGeneratingToolCall`, `isThinking`). Make
`agentUiState.status` the single canonical value; everything else becomes a
**computed read** derived from it. `modelStore.inferencing` / `isStreaming` may
need to remain global (other screens read them — model loading, settings) but
should be derived from agent status, not separately written. Eliminates a
class of "did this signal flip?" bugs and shrinks `DebugStatusBar`. See §7
for the proposed derivation table.

---

## 6. Canonical scenarios

What the design must produce. Each scenario should be testable manually.

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

This scenario is the visual proof for intent issue #2 ("dead zones with no
indicator while the model is working between steps"). All other scenarios
show end states; this one shows what's visible at each phase of a tool-call
turn. The pending indicator (D4, owned by ChatView) appears in every state
EXCEPT `streaming_text` and `done`.

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
                                |   (cleanup #1)
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

The two dead zones are phases 5 and 7. Both must show the indicator. The
acceptance-test version of this scenario is "fire a render_html call, observe
the indicator below the bubble through phases 2, 4, 5, 7, never see a moment
where the chat is silent."

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

## 7. State signals — proposed derivation

After **Deferred cleanup #2**: `agentUiState.status` is canonical. Other
signals become computed reads.

| Signal                               | Where it comes from                     | Read by                       |
|--------------------------------------|------------------------------------------|-------------------------------|
| `agentUiState.status` **(C)**        | reducer (canonical)                      | everywhere                    |
| `agentUiState.pendingTalentNames`    | reducer                                  | TalentSurface, Message        |
| `inferencing` **(P: derived)**       | `status ∉ { idle, done, failed }`        | ChatScreen, model load screens |
| `isStreaming` **(P: derived)**       | `status === streaming_text`              | ChatScreen                    |
| `isGenerating` **(P: derived)**      | `status ∉ { idle, done, failed }` (= `inferencing`) | ChatScreen           |
| `isGeneratingToolCall` **(P: drop)** | (was: `status === generating_tool_call`) | nothing (legacy)              |
| `isThinking` **(P: derived)**        | `status ∈ { prefill, generating_tool_call, executing_tool }` | ChatView (PendingIndicator) |

Note: `isGenerating` and `inferencing` collapse to the same predicate; one of
them should win the rename.

---

## 8. Decisions (was: open questions)

- **D1** (was Q1): Footer renders whatever footer-eligible fields are present
  in `metadata`. Each field is independent — no all-or-nothing gating:
  - `metadata.timings` present → render the timing line.
  - `metadata.copyable` true → render the copy button.
  - (sender name handled separately, gated by `showName`.)

  The rule is "show what we have." The outcome of the run (done, interrupted,
  failed) does not gate the footer; only field presence does. If llama.rn
  returns partial timings on a mid-stream stop, write them to `metadata.timings`
  and the footer will render them. If a turn is mid-stream and not yet
  copyable, neither field is set, so nothing renders.

  Implementation note: today the hook writes `timings` only on `run_finished`
  and `copyable` only in the catch path. Preserving partial timings on
  interruption is a future enhancement at the writer side; the renderer
  contract above already supports it.
- **D2** (was Q2): Failed tool → subtle inline error block. Default copy
  "Tool call failed" when no errorMessage. Must NOT visually compete with
  the rest of the turn.
- **D3** (was Q3): Reasoning content is rendered, per step, BEFORE that step's
  content (matches model emission order). Visual: `ThinkingBubble` with
  `BubbleState.PARTIAL` initial state — same default as `main` and as
  `f3b750e` (PR #709 didn't change the bubble's expand/collapse default; what
  it changed was where reasoning lives in the data shape, which the new
  per-step render path absorbs cleanly). User can still toggle to COLLAPSED or
  EXPANDED; the default initial state matches `main`.
- **D4** (was Q4): Replace LoadingBubble with a subtle **dot-row indicator**
  (`PendingIndicator` component) positioned **below the latest turn**, owned by
  ChatView (I4). Visual is a low-prominence dot row (similar shape to today's
  LoadingBubble at reduced visual weight); minimal vertical space; signals
  "more is coming." Note on terminology: earlier drafts called this a "pulsing
  caret" — that was misleading because "caret" connotes a single text-marker
  character. Intent Q1 specifies dot-row.
- **D5** (was Q5): Collapse `streaming_followup` into `streaming_text`.
  `step_started.isFollowUp` flag remains on the event for any per-step UI that
  wants it.
- **D6** (was Q6): Multi-tool turns render N per-call blocks in
  `step.toolCalls` array order. Made an explicit invariant (I2).
- **D7** (was Q7): Copy semantics = **all step content joined per turn** (no
  reasoning, no tool-call JSON). Not per-step. This matches today's
  `derivedText` behaviour (`src/utils/chat.ts:32–40` joins `step.content` only)
  — so D7 is a *scope* change ("once per turn" rather than "once per step"),
  not a *content* change. The Bubble copy tests (`Bubble.test.tsx:195–280`)
  remain valid; the new per-turn copy uses the same `derivedText`-equivalent
  string.
- **D8** (was Q8): Persistence — if a TalentUI isn't registered at load time,
  fall back to the tool-used chip (or error block for failed outcomes). No
  schema change required.
- **D9** (was Concern 3 from round-1 critique): Footer ownership is moved
  out of `Bubble` for **all** assistant rows in this PR — not only for
  `assistant_turn` rows. Bubble becomes a pure shape primitive (border, bg,
  no chrome). Message owns timing/copy/sender-name rendering universally
  via the new `AssistantTurnFooter`. Rationale: chrome-in-Bubble was the
  proximate cause of the duplicate-footer bug; keeping it for legacy Text
  rows would leave a drift trap.

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
  caret indicator stops.
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
- *Today* (`TalentSurface.tsx:67`) the renderer does `if (!ui) continue;` and
  emits nothing — this is exactly intent issue #3 ("no feedback for tool
  calls that have no registered UI"). Per I3 the new design renders the chip
  / error block, so a turn loaded from disk whose talent was deleted from the
  build still surfaces what was attempted.
- No schema change required (D8). The chip shows the tool's name from the
  persisted call data; the user knows what was attempted even if the rich
  UI is gone.

### 9d. Race between state flip and step push (follow-up)

The reducer flips `executing_tool → prefill` on `step_started(isFollowUp)`.
The hook also calls `pushAgentStep` to create the new step. If a render
happens between the state flip and the step push (or vice versa), the
renderer sees `prefill` status with `lastStep` still being step 0. The
caret renders correctly because §7's `isThinking` derivation reads only
`status`, not step content. Single-frame artifact at most; no functional
issue.

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
- not an implementation plan
- not a record of recent fixes (those live in commits)

When this doc and a commit disagree, the commit wins — but then this doc must
be updated in the same change. Drift is the failure mode that will bring back
the ping-pong.

**Cleanup reminder**: the `DebugStatusBar` overlay (currently mounted
unconditionally in `ChatScreen` for diagnostics) is a temporary tool. Remove
it once the refactor lands and the §6 scenarios + §10 edge cases verify
cleanly.

---

## Review History

### Round 1 (2026-05-05)

`pocketpal-architect-critic` returned **HAS_BLOCKERS** against `f3b750e`
(PR #709's tip). Full critique at `architect-critic-round-1.md`. The critic
verified every `(C)` claim against the worktree and caught that the prior
draft mixed committed code with the human's local uncommitted WIP. Resolutions:

| Finding | Resolution | Where applied |
|---|---|---|
| BLOCKER 1: §5 names non-existent `appendToolCall`/`reconcileActiveStepToolCall`; "fixed by removing toolCalls" claim is false | **FIXED**. §5 now describes the actual `(C)` writer (`updateActiveStepStreaming` writing `partial.toolCalls` per token); cleanup #1 spells out the real id-reconciliation gap (`projectStreamChunk` ids vs `normalizeToolCallIds` synthetic ids) and the proposal to land `step.toolCalls` only after `step_finished` via a new `appendToolCall` writer. | §5 table + cleanup #1 |
| BLOCKER 2: §4d footnote names TextMessage as the duplicate-footer source; actual source is `Bubble.tsx:93–104` invoked by `Message.renderAssistantTurn:288–303` | **FIXED**. Footnote rewritten with correct file:line citations. | §4d footnote |
| BLOCKER 3: §9c claims today's renderer falls back for unknown talents; actually `TalentSurface.tsx:67` does `if (!ui) continue;` | **FIXED**. §9c rewritten to acknowledge today renders nothing (intent issue #3) and the chip is the new design. | §9c |
| BLOCKER 4: D3 specifies render order but doesn't pin reasoning expand/collapse default | **FIXED**. Verified against `origin/main` and `f3b750e`: both initialise `ThinkingBubble` to `BubbleState.PARTIAL`. PR #709 didn't change the bubble's default; what it changed was where reasoning lives in the data shape. D3 now pins PARTIAL. | D3 |
| CONCERN 1: chosen architecture has no enumerated alternatives | **FIXED**. New §4.0 lists three plausible alternatives (flatten storage, turn-aware Bubble, synthetic footer-row) with one-line trade-offs and the reason the chosen path wins. | §4.0 |
| CONCERN 2: D7 implies `derivedText` change unmarked as (C) → (P) | **FIXED**. D7 narrowed to "all step content joined per turn (no reasoning)" — matches today's `derivedText` behaviour, so D7 is a *scope* change (per-turn vs per-step) not a *content* change. No test churn. | D7 |
| CONCERN 3: footer-ownership split between Bubble (text rows) and Message (assistant_turn rows) was implicit | **FIXED**. New D9 commits to the universal path: Message owns chrome for all assistant rows; Bubble loses chrome rendering and becomes a pure shape primitive. | D9 + §4d footnote |
| CONCERN 4: §6 scenarios all show end-states, no dead-zone storyboard | **FIXED**. New Scenario I (phase-by-phase) shows the indicator's appearance/disappearance through `prefill → streaming_text → generating_tool_call → executing_tool → prefill (follow-up) → streaming_text → done`. | §6.I |
| SUGGESTION 1: caret/dot-row terminology mismatch with intent Q1 | **FIXED**. Component renamed `PulsingCaret → PendingIndicator`. D4 explicitly states the visual is a dot-row positioned below the latest turn. References updated throughout. | §3, §4a, §4d, §7, D4, I4 |
| SUGGESTION 2: §3 state table missing `idle` row | **FIXED**. Added. | §3 table |
| SUGGESTION 3: `metadata.copyable` written by both run_finished and catch path; §5 didn't acknowledge | **FIXED**. §5 row spells out both event sources (sequential, not racing). | §5 table |

Note for round 2 reviewer: the prior draft was written from the human's local
uncommitted WIP in `worktrees/TASK-20260502-2115`, which contained
`reconcileActiveStepToolCall`, `DebugStatusBar`, and other rendering
experiments not yet on PR #709. Round 1's critic correctly flagged the
mismatch. This revision is grounded in the committed PR #709 tree at
`f3b750e`; the human's WIP is treated as informative (Implementation may
cherry-pick), not as a constraint on the design.

### Round 2 (2026-05-05)

`pocketpal-architect-critic` returned **LGTM** with three SUGGESTIONs (full
critique at `architect-critic-round-2.md`). All three were applied:

| Finding | Resolution | Where applied |
|---|---|---|
| SUGGESTION 1: tag prefill-on-followup transition as (P), not just the rename | Added a `(P)` paragraph in §3 prose noting today's reducer (`agentStateReducer.ts:33–38`) goes `executing_tool → streaming_followup` directly; the proposal routes through `prefill` for the indicator. | §3 prose |
| SUGGESTION 2: refresh §5 line numbers (`pushAgentStep` is at 716, `appendToolOutcome` at 754, not 571 / 716) | Citations corrected; added `finalizeActiveStep:801`. | §5 table |
| SUGGESTION 3: TalentSurface's inline pending paths become dead under §4a's skip-rule | Added `(P)` note in §4a calling out lines 71–77, 83–87, 102–130 should be removed in this PR to avoid two competing pending UIs. | §4a |

**Verdict**: WHAT advances to planner.
