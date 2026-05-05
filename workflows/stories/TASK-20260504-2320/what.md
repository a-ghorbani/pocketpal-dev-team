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
| `prefill`              | pulsing caret (D4) — waiting for first token             |
| `streaming_text`       | text appearing in bubble — no caret                      |
| `generating_tool_call` | pulsing caret — sentinel detected, JSON streaming        |
| `executing_tool`       | pulsing caret — tool running                             |
| `done`                 | turn footer (timing, copy)                               |
| `failed`               | inline error indicator                                   |

---

## 4. Rendering contract (the missing piece)

For **one** AssistantTurn:

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
     `tool_call_started` and `tool_call_finished`). The pulsing caret on
     the turn covers feedback during this window; no placeholder block.

If a step has no `toolCalls` array yet but is the active step and
`pendingTalentNames` lists a registered talent (early streaming, before
the runner emits `tool_call_started`), no per-call block is emitted. The
pulsing caret already covers feedback during the lead-up.

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
- **I4**: pulsing caret indicator (D4) is owned by ChatView, NOT by Message —
  it lives on/below the latest turn during dead zones, never inside one.
  LoadingBubble is replaced.

### 4d. What each component renders

| Component                     | Renders                                                         | Does NOT render            |
|-------------------------------|-----------------------------------------------------------------|----------------------------|
| `Message.renderAssistantTurn` | ordered step blocks + ONE footer                                | timing, copy               |
| `TextMessage` **(P)**         | text/markdown + reasoning for ONE step                          | timing, copy, name         |
| `Bubble`                      | bubble shape (border, bg) around any child                      | content, chrome            |
| `TalentSurface`               | dispatcher → talent UI / tool-used chip / error block, per call | text content               |
| `AssistantTurnFooter` **(P)** | timing, copy, name                                              | text, talent               |
| `PulsingCaret` **(P)**        | subtle caret/dot indicator                                      | -                          |
| `ChatView`                    | message list + caret indicator                                  | per-turn structure         |

The **(P)** rows are proposed changes. Today, `TextMessage` renders timing/copy
itself (root cause of duplicate-footer bug); LoadingBubble is the heavier
indicator we're replacing.

---

## 5. Layer ownership (single-writer rule)

| Field                                    | Single writer                                      |
|------------------------------------------|----------------------------------------------------|
| `step.content`, `step.reasoningContent`  | throttled streaming via `updateActiveStepStreaming`|
| `step.toolCalls`                         | `appendToolCall` **(P)** *(today named `reconcileActiveStepToolCall`)* |
| `step.toolOutcomes`                      | `appendToolOutcome`                                |
| `step.partial`                           | `pushAgentStep` (true), `finalizeActiveStep` (false)|
| New step                                 | `pushAgentStep`                                    |
| `metadata.timings`, `completionResult`   | `updateMessage` at run_finished                    |
| `agentUiState`                           | `agentStateReducer` only (canonical state source)  |
| `modelStore.inferencing` / `isStreaming` | `useChatSession` at run boundaries (legacy; see deferred) |

Reading is unrestricted. Recent bugs: multiple writers to `step.toolCalls`
(streaming partial vs reconcile) — fixed by removing toolCalls from the
streaming partial.

**Deferred cleanup #1 — rename `reconcileActiveStepToolCall`** (do during the
refactor): legacy name from when the function had to merge a streaming-time
placeholder with the runner's normalized call. After removing
`partial.toolCalls` from the streaming write, the matching logic is dead code
— `step.toolCalls` is always empty when this function fires, so it always falls
through to the append branch. Rename to `appendToolCall` (mirrors
`appendToolOutcome`) and delete the match-and-replace branch. By the codebase
rule, dead "just in case" code is not kept; if streaming-time toolCalls writes
are ever re-introduced, the matching logic comes back with that change.

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
| `isThinking` **(P: derived)**        | `status ∈ { prefill, generating_tool_call, executing_tool }` | ChatView (caret) |

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
  content (matches model emission order). Restore the pre-PR rendering.
- **D4** (was Q4): Replace LoadingBubble with a pulsing caret on the last
  visible block (or below it, ChatView's call). Subtle, takes minimal vertical
  space, signals "more is coming."
- **D5** (was Q5): Collapse `streaming_followup` into `streaming_text`.
  `step_started.isFollowUp` flag remains on the event for any per-step UI that
  wants it.
- **D6** (was Q6): Multi-tool turns render N per-call blocks in
  `step.toolCalls` array order. Made an explicit invariant (I2).
- **D7** (was Q7): Copy semantics = combined turn content (all reasoning +
  content joined). Not per-step.
- **D8** (was Q8): Persistence — if a TalentUI isn't registered at load time,
  fall back to the tool-used chip (or error block for failed outcomes). No
  schema change required.

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
  outcome was an error). Same fallback datetime/calculate use today.
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
