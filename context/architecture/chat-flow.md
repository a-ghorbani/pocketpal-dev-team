# Chat Flow

**Purpose**: cumulative architecture truth for the chat rendering, streaming,
tool-calling, and agent-loop behaviour. Bootstrapped from the AssistantTurn
rendering refactor (TASK-20260504-2320, building on TASK-20260502-2115). Meant
to fit in your head.

Convention used in this doc:

- **(C)** = current behaviour, documented from code
- **(D)** = decision (was an open question, now resolved)

---

## Invariants

Load-bearing rules. If a change breaks one of these, the reviewer should
ask "is this an architecture change?" before approving.

- **Single global n_ctx, two named views.** The banner resolver and the
  pal-load hint read `modelStore.activeContextSettings?.n_ctx` — the
  n_ctx the running `LlamaContext` was actually initialised with.
  `modelStore.contextInitParams.n_ctx` is the *next-init intent*
  (writable from the Settings n_ctx input via `setNContext` and from the
  banner "Increase context" CTA, which also calls `setNContext`). Both
  views read from the same global — there is no per-session or pending
  override layer. If a future field exposes "the n_ctx for X", it must
  say which copy of state it represents.
- **Snapshot truth.** The `lastCompletionResult` on `ChatSessionStore`
  and the matching `metadata.completionResult` persisted on the newest
  assistant message are normalised at the moment of writing
  (`deriveSnapshotFromResult` in `useChatSession`). Readers
  (`resolveBannerVariant`) do not redo the arithmetic; the resolver's
  freshness gate mirrors the same `used >= effectiveNCtx -
  AUTOCLEAR_RUNWAY` boundary.
- **One advisory surface at a time.** `ChatView` renders at most one
  snackbar per frame. When the increase-context confirm raises the
  reload snackbar it synchronously dismisses the pal-load hint in the
  same handler (React 18 auto-batched setState commits the pair
  atomically); the pal-load snackbar is also gated on `!reloadSnackbar`.
- **One banner variant per render.** `resolveBannerVariant` is pure and
  returns exactly one of context-full / context-warning /
  context-remote-hedged / html-soft-cap / none. The context-* variants
  are suppressed when no `LlamaContext` is loaded
  (`activeModelId === undefined`). The nCtx-reading variants (context-full,
  context-warning) additionally require a known runtime n_ctx
  (`activeContextSettings.n_ctx`); context-remote-hedged does not read
  n_ctx (remote models never set `activeContextSettings.n_ctx`) and gates
  on a loaded model only. html-soft-cap is independent of model state.
- **Loaded n_ctx is the user's only runtime signal.** Every reload path
  (Settings, the banner CTA, Models screen, auto-load) honors
  `contextInitParams.n_ctx` by construction; there is no hidden state
  shadowing it.

---

## 1. Data model

```
Session
  messages: Message[]                      // [0] = newest (unshift)
    UserText           { id, text, ... }
    AssistantTurn      { id, createdAt, metadata, steps: AgentStep[] }
        metadata                            // turn-level chrome + run flags
            timings?         : { predicted_per_second, predicted_per_token_ms,
                                 time_to_first_token_ms, ... }   // llama.rn shape
            completionResult?: CompletionResultSnapshot           // turn snapshot
                                            //   { content?, reasoning_content?,
                                            //     used, contextFull, tokensPredicted?,
                                            //     finishReason?, isRemote }
                                            //   used = tokens_evaluated + tokens_predicted
                                            //   (tokens_cached unavailable at the boundary)
            copyable?        : boolean      // turn has user-visible content worth copying
            interrupted?     : boolean      // run failed/aborted with partial content
            truncationLikely?: true         // set ONLY when the tool-args JSON
                                            //   parse error fires on abort
                                            //   (n_ctx-exhaustion smoking gun)
            hitMaxTurns?     : true         // set ONLY when the loop hit the guard
                                            //   (absent otherwise — not `false`)
        AgentStep
            content?         : string      // assistant-visible text for this step
            reasoningContent?: string      // <think>...</think>, rendered (D3)
            toolCalls?       : AgentToolCall[]
            toolOutcomes?    : AgentToolOutcome[]
            partial?         : boolean     // true while streaming, false on step_finished
        AgentToolCall                      // OpenAI function-call shape
            { id, type: 'function', function: { name, arguments },
              metrics?: { tokens, durationMs } }   // generation cost, post-hoc
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
Wire (sent to the active `CompletionEngine`) and visual display: **flat
OpenAI shape**. Two engines today: llama.rn (local) and an
OpenAI-compatible remote engine (`api/openai.ts`). Both consume / emit the
same flat shape — the remote engine reassembles streaming `tool_calls`
deltas (which arrive index-by-index across SSE chunks) back into the
single-shot shape the runner expects.

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

**Orphan-pair guard at the wire boundary** (`utils/chat.ts`
`stepToApiMessages`). The Jinja templates we hand to llama.rn enforce
"every `tool_call_id` must have a matching `role:'tool'` response." A
persisted step with `toolCalls` but no matching outcomes (user abort
fired between `step_finished` and `tool_call_finished`, or a crash) would
otherwise emit malformed prompts on reload. The conversion synthesises an
`"aborted"` sentinel response for every unmatched call:

```
persisted step (post-abort)             flattened wire shape
─────────────────────────────           ──────────────────────────────────────
step {                                  assistant { content, tool_calls: [c0] }
  content: "Let me look that up",       ── (no outcome for c0)
  toolCalls: [ {id:'c0', …} ],           tool { tool_call_id:'c0',
  toolOutcomes: [],   ← orphan                  content: 'aborted' }   ← synthesised
}
```

The §9a abort path is the most common producer of this shape; mid-step
process crash on reload is the other.

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

`agentUiState` shape (reducer-owned; the canonical UI status source):

```
AgentUiState
  status              : 'idle' | 'prefill' | 'streaming_text' |
                        'generating_tool_call' | 'executing_tool' |
                        'done' | 'failed'
  pendingTalentNames  : string[]   // names from the first delta.toolCalls
                                   //   we see; carried so the label doesn't
                                   //   flicker if later deltas drop the name
  pendingToolTokens   : number     // token-event count during the current
                                   //   `generating_tool_call` phase; reset on
                                   //   tool_call_started / run_finished
  hitMaxTurns         : boolean    // mirrored from the final run_finished
                                   //   payload (also persisted in metadata)
```

`chatSessionStore.isStopping` (separate from `agentUiState`) is set by
`handleStopPress` and cleared once the runner exits — it gates the
"Stopping…" overlay on the indicator (D4) without touching `status`.

What the user should see in each state (single rule, no sub-cases):

| State                  | User-visible feedback                                                 |
|------------------------|------------------------------------------------------------------------|
| `idle`                 | nothing (no active turn; persisted blocks only)                        |
| `prefill`              | pending indicator (D4) — plain dot-row                                 |
| `streaming_text`       | text appearing in bubble — no indicator                                |
| `generating_tool_call` | pending indicator — dots + "Building page · N tokens · Ks" (see D4)   |
| `executing_tool`       | pending indicator — dots + tool label                                  |
| `done`                 | turn footer (timing, copy)                                             |
| `failed`               | inline error indicator                                                 |
| (overlay) `isStopping` | indicator stays visible, suffix overridden by "Stopping…" (any status) |

Indicator content per state (single component, three modes):

```
prefill / executing_tool      generating_tool_call         isStopping=true
─────────────────────────     ─────────────────────────    ─────────────────
 · · ·                         · · · Building page          · · · Stopping…
                               · · · Building page · 87 tokens
                               · · · Building page · 87 tokens · 4s

      (plain)                   token count appears once     overrides any
                                pendingToolTokens ≥ 10;      tool-call suffix;
                                elapsed seconds once ≥ 1s    keeps visible even
                                                             if status had been
                                                             `streaming_text`
```

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

1. **reasoning block** — iff `step.reasoningContent?.length > 0`. Rendered by
   `ReasoningBlock` (which internally wraps `ThinkingBubble`). **Skips the
   chat-bubble shell entirely** — it sits directly on the chat surface with no
   bubble background, no contentContainer, no sender-name slot. Reasoning is
   metadata, not a chat post.
2. **content block** — iff `step.content?.length > 0` (rendered as a
   `TextMessage` wrapped in the same `contentContainer` / `renderBubble`
   shell as a normal Text message)
3. **per-call blocks** — for each call in `step.toolCalls` (in array order),
   emit ONE of (in priority order, all dispatched by `TalentSurface`):
   - **error block (subtle)** — outcome exists and `result.type === 'error'`
     → `<ToolErrorBlock>`. Low-prominence inline marker (icon + "Tool X
     failed" + optional errorMessage). Must not visually compete with bubbles.
   - **talent block** — outcome exists, non-error, AND a TalentUI is
     registered for the call's name → `ui.renderResult(outcome.result)`. When
     `call.metrics` is present, a sibling `<ToolMetricsFooter>` renders just
     below the result.
   - **tool-used chip (subtle)** — outcome exists, non-error, and no
     TalentUI is registered → `<ToolUsedChip>` (slim "used X" chip, with
     inline metrics suffix when `call.metrics` is present).
   - **(none)** — outcome doesn't exist yet (call is in-flight, between
     `tool_call_started` and `tool_call_finished`). The pending indicator
     on the turn covers feedback during this window; no placeholder block.

If a step has no `toolCalls` array yet, no per-call block is emitted. The
pending indicator already covers feedback during the lead-up.

If a step contributes zero blocks total, it is skipped entirely (no phantom
layout).

**Reasoning auto-collapse rule** (per step, single source: `Message.tsx`):

```
                  reasoning streaming alone   content begins   step.partial=false
                  ─────────────────────────   ──────────────   ──────────────────
ThinkingBubble    PARTIAL (expanded)          → collapsed       → collapsed
state             (live thought)              text-only row     text-only row

condition         !hasContent && partial      hasContent ||     partial === false
                                              partial === false
```

Once collapsed, the user's manual toggle (tap to expand) wins for the
bubble's lifetime — see `ThinkingBubble.userToggledRef`.

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

| Component                         | Renders                                                                              | Does NOT render            |
|-----------------------------------|---------------------------------------------------------------------------------------|----------------------------|
| `Message.renderAssistantTurn`     | ordered step blocks + ONE footer                                                      | bubble chrome              |
| `Message` (Text rows, legacy)     | TextMessage wrapped in Bubble + ONE footer (same component)                           | duplicate per-step chrome  |
| `TextMessage`                     | text/markdown for ONE content block (consumes `step` prop, reads `content`)           | timing, copy               |
| `ReasoningBlock`                  | reasoning markdown for ONE step — directly on chat surface, NO bubble shell           | timing, copy, sender name  |
| `ThinkingBubble`                  | the PARTIAL / COLLAPSED / EXPANDED shape used inside `ReasoningBlock`                 | markdown rendering         |
| `Bubble`                          | bubble shape (border, bg) around any child                                            | timing, copy, name         |
| `TalentSurface`                   | dispatcher → `ToolErrorBlock` / talent UI / `ToolUsedChip`, plus `ToolMetricsFooter`  | text content               |
| `AssistantTurnFooter`             | timing, copy                                                                          | text, talent, sender name  |
| `PendingIndicator`                | subtle dot-row indicator + optional label / token-count / "Stopping…" overlay         | text, chrome               |
| `ChatView`                        | message list + pending indicator (visibility-gated by `status` + `isStopping`)        | per-turn structure         |
| `BannerRow` (`ChatView/BannerRow.tsx`, in the input slot) | ONE of five variants from `resolveBannerVariant` (`context-full` / `context-warning` / `context-remote-hedged` / `html-soft-cap` / none) | per-variant logic (lives in the resolver) |
| `IncreaseContextSheet`            | owns target selection (slider over `CONTEXT_LADDER`, filtered to stops above current n_ctx and capped at `model.ggufMetadata.context_length`, 3-zone fit classifier); reloads the model + reports result to `ChatView`'s reload snackbar | the banner variant; the resolver's `ratio` |
| `resolveBannerVariant` (pure, `utils/bannerVariantResolver.ts`) | resolved variant + payload (`ratio` = `used / effectiveNCtx` on the warning/full branches, heavy-talent name) | JSX, MobX writes, async, the increase target |
| `usePalLoadHint` (pure hook)      | one-shot snackbar trigger when a heavy-talent pal loads below its recommended n_ctx  | banner state (I8 — snackbar layer is separate) |

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
| `metadata.timings`                       | `updateMessage` at `run_finished` (`useChatSession.ts`) |
| `metadata.completionResult` (`CompletionResultSnapshot`) | `updateMessage` at `run_finished` AND the catch path on abort with partial content (`useChatSession.ts`, via `deriveSnapshotFromResult`). The same site then calls `chatSessionStore.recordCompletionSnapshot`, which seeds `lastCompletionResult` and `consecutiveFullFailures` in one action. |
| `metadata.copyable`                      | `updateMessage` from EITHER `run_finished` OR the catch path on abort (`useChatSession.ts`). Sequential, not racing. |
| `metadata.interrupted`                   | `updateMessage` from the catch path (abort with partial content) |
| `metadata.truncationLikely`              | `updateMessage` from the catch path, only when the tool-args JSON parse error fires |
| `metadata.hitMaxTurns`                   | `updateMessage` from `run_finished`, only when `result.hitMaxTurns === true` (absent otherwise) |
| `chatSessionStore.lastCompletionResult`  | `recordCompletionSnapshot`, called by `useChatSession` at `run_finished` AND abort-with-partial-content (same site that writes `metadata.completionResult`); `setActiveSession` hydrates from the newest turn on disk; cleared on `resetActiveSession` and on `removeMessagesFromId` (edit/regenerate invalidates the frozen snapshot) |
| `chatSessionStore.dismissedBannerVariants` | `BannerRow` on user dismiss (`setBannerDismissed`, incl. the per-draft `context-full` dismiss); cleared per-draft by `recordCompletionSnapshot`, on `deleteSession(id)`, as a whole-op clear in `bulkDeleteSessions()`, on `removeMessagesFromId` (edit/regenerate), and on `resetActiveSession` / `setActiveSession` |
| `chatSessionStore.consecutiveFullFailures` | `recordCompletionSnapshot` (called from `useChatSession` at `run_finished` / abort-with-partial-content): increment on `snapshot.contextFull`, reset otherwise; cleared on `resetActiveSession` / `setActiveSession` / `removeMessagesFromId` |
| `modelStore.contextInitParams.n_ctx` | Settings n_ctx input (`ModelStore.setNContext`) AND `IncreaseContextSheet` confirm (calls `setNContext(target)` then `releaseContext` + `initContext`; on failure restores the prior value with a second `setNContext`). Single global — no per-session or pending override. |
| `chatSessionStore.palLoadHintSeen` | `usePalLoadHint` at emit time (`markPalLoadHintSeen`); cleared on `resetActiveSession` |
| `modelStore.activeContextSettings` | `ModelStore.initContext` on success; cleared on release. Set only by those two writers. |
| `agentUiState` (full bag)                | `agentStateReducer` only (canonical state source)   |
| `chatSessionStore.isStopping`            | `useChatSession.handleStopPress` (set), `handleSendPress` cleanup paths (clear) |
| `modelStore.inferencing` / `isStreaming` | `useChatSession` at run boundaries (legacy; see Cleanup-DEFERRED below) |
| TTS streaming handle (out-of-band)       | `useChatSession.applyEventToStore` token branch — opens on first content/reasoning token, forwards diffed substrings to `ttsStore.onAssistantMessageChunk`, closes at `run_finished` / abort. Persistence side is unaffected; see `tts.md`. |
| `session.completionSettings` (sessions[].metadata) | `createNewSession` at birth (`ChatSessionStore.ts`) — baked from the resolver's no-session output; updated thereafter only by `ChatGenerationSettingsSheet` save flow via `updateSessionCompletionSettings`. (C) |
| `session.settingsSource` (sessions[].metadata) | `createNewSession` at birth (`ChatSessionStore.ts`); updated thereafter only by `ChatGenerationSettingsSheet` save flow. Birth-rule: `'custom'` if `newChatThinkingOverride !== undefined`, else `newChatSettingsSource`. (C) |
| `chatSessionStore.newChatThinkingOverride` | `ChatScreen.handleThinkingToggle` (set, no-session branch only); `createNewSession`, `resetActiveSession`, `setActiveSession` (clear). Read by `resolveCompletionSettings` no-session branch only. (C) |

Reading is unrestricted.

**n_ctx resolution.** There is no override layer. Banner-side readers
(`BannerRow` / `resolveBannerVariant`, `usePalLoadHint`) read
`modelStore.activeContextSettings?.n_ctx` for "what is actually loaded"
and `modelStore.contextInitParams.n_ctx` for "what the next reload would
use". `ChatSessionStore` does NOT read `ModelStore` — `BannerRow` and
`usePalLoadHint` perform the cross-store reads, so there is no cycle.

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

### 6.0 The full picture (illustrative composite)

**Not a real model output.** A synthetic turn that crams every block kind
onto one canvas so the component layout, ownership boundaries, and
invariants are visible at a glance. Do **not** write tests against this —
the testable scenarios are A–I below. This panel exists so an agent or a
human can grep the labels back to source.

```
┌─ [ChatView] ─────────────────────────────────────────────────────────────┐
│   owns the message list and the PendingIndicator (I4)                    │
│                                                                          │
│   ▼ user row — owned by [Message] (via renderMessage, right-aligned)     │
│                                   ┌──────────────────────────────────┐   │
│                                   │ show me a colour wheel           │   │
│                                   └──────────────────────────────────┘   │
│                                     [TextMessage] inside [Bubble]        │
│                                                                          │
│   ▼ assistant row — owned by [Message] (via renderAssistantTurn)         │
│                                                                          │
│       Assistant                  ← sender name via [TextMessage]         │
│                                    showName (first block only)           │
│                                                                          │
│       ┌─ reasoning block (step₀) ────────┐                               │
│       │ Let me think about colours…      │   [ReasoningBlock] —          │
│       └──────────────────────────────────┘   no bubble shell.            │
│                                              Inner shape: [ThinkingBubble] │
│                                              D3 · PARTIAL → auto-collapses │
│                                              when content begins or       │
│                                              step.partial === false       │
│                                                                          │
│       ┌─ content block (step₀) ──────────┐                               │
│       │ Sure, here's a preview.          │   [TextMessage] inside        │
│       └──────────────────────────────────┘   [Bubble]                    │
│                                                                          │
│       ┌─ per-call block (step₀) ─────────┐                               │
│       │ [HtmlPreviewBubble]              │   [TalentSurface] →           │
│       │ ─── 87 tokens · 4s ───           │   ui.renderResult() then      │
│       └──────────────────────────────────┘   [ToolMetricsFooter] sibling │
│                                              when call.metrics is set    │
│                                                                          │
│       ┌─ content block (step₁ follow-up) ┐                               │
│       │ Hope this looks right.           │   [TextMessage] inside        │
│       └──────────────────────────────────┘   [Bubble]                    │
│                                                                          │
│       ── 32ms/tok · 30 tok/s · 251ms TTFT · [copy] ──                    │
│                      [AssistantTurnFooter]  (I1 · exactly one per turn)  │
│                                                                          │
│   ▼ below the latest turn (during dead zones only)                       │
│       · · ·         [PendingIndicator]  (D4)                             │
│                     visible when status ∈ { prefill,                     │
│                       generating_tool_call, executing_tool }             │
│                     OR chatSessionStore.isStopping === true (overlay     │
│                     keeps it visible across `streaming_text` too).       │
│                     Suffix builds from pendingTalentNames →              │
│                       label · `pendingToolTokens` tokens · elapsed s     │
│                     (when isStopping: suffix is forced to "Stopping…")   │
└──────────────────────────────────────────────────────────────────────────┘
```

The same picture, with three subtle/error variants overlaid so the
low-prominence shapes are recognisable:

```
   ┌─ per-call block (no UI registered) ─────────┐
   │  · used datetime                            │   subtle tool-used chip
   └─────────────────────────────────────────────┘   (I3, via [TalentSurface])

   ┌─ per-call block (tool errored) ─────────────┐
   │  ⚠ render_html failed                       │   subtle error block
   └─────────────────────────────────────────────┘   (D2 / I3, via [TalentSurface])

   ── [copy] ──                                       interrupted-run footer
       [AssistantTurnFooter]                          (I1 · timing absent
                                                       because metadata.timings
                                                       is not written on abort;
                                                       see §9a)
```

**Component → source map.** Click-through paths for grep / IDE:

| Label in diagram | Source | Role | Refs |
| --- | --- | --- | --- |
| `[ChatView]` | `src/components/ChatView/ChatView.tsx` | Message list + PendingIndicator gating | I4, D4 |
| `[Message]` | `src/components/Message/Message.tsx` | Per-row dispatcher; routes by `message.type`; owns Avatar, the row-level `<Pressable>` (long-press routing), and the single `<AssistantTurnFooter>`. Assistant turns go through `renderAssistantTurn()` which emits the ordered step blocks. | I1, I2, D9 |
| `[TextMessage]` | `src/components/TextMessage/TextMessage.tsx` | One content block (markdown body); carries `showName`. NOT used for reasoning. | §4a |
| `[ReasoningBlock]` | `src/components/ReasoningBlock/ReasoningBlock.tsx` | Per-step reasoning markdown; **renders outside the bubble shell** | §4a, D3 |
| `[Bubble]` | `src/components/Bubble/Bubble.tsx` | Pure shape primitive (border, bg) — **no chrome** | D9 |
| `[ThinkingBubble]` | `src/components/ThinkingBubble/ThinkingBubble.tsx` | PARTIAL/COLLAPSED/EXPANDED shape used inside `ReasoningBlock` | D3 |
| `[TalentSurface]` | `src/components/TalentSurface/TalentSurface.tsx` | Per-call dispatcher → talent UI / tool-used chip / error block + metrics | I3, D8 |
| `[ToolErrorBlock]` | `src/components/ToolErrorBlock/` | Subtle inline error marker; rendered by TalentSurface for `result.type === 'error'` | I3, D2 |
| `[ToolUsedChip]` | `src/components/ToolUsedChip/` | Subtle "used X" chip; TalentSurface fallback when no TalentUI is registered (carries inline metrics suffix) | I3, D8 |
| `[ToolMetricsFooter]` | `src/components/ToolMetricsFooter/` | Sibling of talent UI: "N tokens · Ks" line for the per-call generation cost | §4a |
| `[AssistantTurnFooter]` | `src/components/AssistantTurnFooter/AssistantTurnFooter.tsx` | Turn-level chrome: timings + copy (×1 per turn) | I1, D1, D7, D9 |
| `[PendingIndicator]` | `src/components/PendingIndicator/PendingIndicator.tsx` | Subtle dot-row + optional label / count / "Stopping…" — owned by ChatView | I4, D4 |

Tests anchoring the layout: `Message.assistantTurn.test.tsx` (per-turn
block ordering, I1/I2/I3, D9 footer ownership), `ChatView.assistantTurn.test.tsx`
(I4, D4 — pending indicator gating + dead-zone storyboard in scenario I).

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
                                |   (plain dots)
3. first token                  | ' ↳ status → streaming_text;
                                |   indicator hidden; tokens appear in step₀
4. marker_seen OR first         | status → generating_tool_call;
   token w/ delta.toolCalls     |   indicator visible — suffix builds:
                                |   plain dots → "Building page" once a
                                |   pendingTalentName lands → "Building page
                                |   · 87 tokens" once ≥ MIN_TOKENS → adds
                                |   "· 4s" once elapsed ≥ 1s.
                                |   (If triggerMarkers is [], `marker_seen`
                                |   never fires and the indicator turns
                                |   labeled one beat later on the first
                                |   delta with toolCalls.)
5. step_finished + tool_started | status → executing_tool;
                                |   indicator visible (was the dead zone);
                                |   per-call block not yet present because
                                |   step.toolCalls is finalized after step_finished
                                |   (Cleanup-LANDED). pendingToolTokens reset.
6. tool_call_finished           | step.toolOutcomes appended; talent block
                                |   (or chip / error block) renders inline;
                                |   per-call ToolMetricsFooter renders if
                                |   call.metrics was attached by the runner.
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

**Orthogonal: user-initiated stop overlay.** If the user taps Stop at any
point between phases 2 and 8, `isStopping` flips true, the indicator stays
visible across `streaming_text` (where it would normally hide), and its
suffix is forced to "Stopping…" until the runner exits — see §9a.

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

| Signal                               | Where it comes from                                                                | Read by                       |
|--------------------------------------|--------------------------------------------------------------------------------------|-------------------------------|
| `agentUiState.status`                | reducer (canonical)                                                                  | everywhere                    |
| `agentUiState.pendingTalentNames`    | reducer — set from the first delta with `toolCalls`, cleared on `tool_call_started` | `PendingIndicator` (label)    |
| `agentUiState.pendingToolTokens`     | reducer — `+1` per `token` event that carries `toolCalls`; reset out of phase        | `PendingIndicator` (count suffix, gated on ≥ `MIN_TOKENS`) |
| `agentUiState.hitMaxTurns`           | reducer — copied from `run_finished` payload                                         | (mirrored into `metadata.hitMaxTurns`; no direct UI consumer yet) |
| `chatSessionStore.isStopping`        | hook (writer)                                                                        | `ChatView` (visibility gate), `PendingIndicator` (forces "Stopping…" overlay) |
| `inferencing` (deferred derivation)  | `status ∉ { idle, done, failed }`                                                    | ChatScreen, model load screens |
| `isStreaming` (deferred derivation)  | `status === streaming_text`                                                          | ChatScreen, ChatView (FlatList) |
| `isGenerating` (deferred derivation) | `status ∉ { idle, done, failed }` (= `inferencing`)                                  | ChatScreen                    |
| `isGeneratingToolCall` (deprecate)   | `status === generating_tool_call`                                                    | nothing (legacy, removable)   |
| `isPending` (LANDED, ChatView-local) | `status ∈ { prefill, generating_tool_call, executing_tool } ‖ isStopping`            | ChatView (PendingIndicator visibility gate) |

Note: rows tagged `(deferred derivation)` are aspirational — today they are
still field-level state written separately by `useChatSession`. The
intention is to make them computed reads of `status`; ChatView already does
this for `isPending`. Until Cleanup-DEFERRED lands, treat the prose in this
table as "should derive from status," not "does today." `isGenerating` and
`inferencing` collapse to the same predicate; one of them should win the
rename when Cleanup-DEFERRED lands.

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
  (matches model emission order). Entry point is the `ReasoningBlock`
  component, which renders **outside the bubble shell** (no contentContainer,
  no renderBubble, no sender-name slot) — reasoning is metadata, not a chat
  post. Inside `ReasoningBlock` sits a `ThinkingBubble` (`BubbleState.PARTIAL`
  default; auto-collapses to text-only row as soon as content begins
  streaming OR `step.partial === false`; the user's manual toggle wins after
  that). See §4a auto-collapse rule.
- **D4**: Replace LoadingBubble with a subtle **dot-row indicator**
  (`PendingIndicator` component) positioned **below the latest turn**, owned
  by ChatView (I4). Visual is a low-prominence dot row (4px dots, no
  card-style background, `onSurfaceVariant` colour); minimal vertical space.
  Three content modes, single component:
  - plain dots (`prefill` / `executing_tool` without label)
  - dots + friendly label + token count + elapsed seconds, both gated on
    their own thresholds (`generating_tool_call`)
  - dots + "Stopping…" overlay (any status while `chatSessionStore.isStopping`)
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

Abort lifecycle (single flow, two visible phases):

```
TAP STOP
  │
  ├─► chatSessionStore.isStopping := true           ─── "Stopping…" overlay
  │   abortRef.current.abort()                          on PendingIndicator
  │   engine.stopCompletion()                           (covers the window
  │                                                     where native is still
  │                                                     finishing its current
  │                                                     llama_decode chunk)
  ▼
RUNNER WINDS DOWN
  │   engine.completion() resolves (or rejects with
  │   the abort error); the for-await loop in the
  │   hook exits its iteration
  ▼
CATCH / FINALLY
  │   inferencing / isStreaming / isGenerating cleared
  │   isStopping cleared
  │   agentUiState reset to idle
  │   IF turn has any visible content (text or tool calls):
  │       metadata = { interrupted: true, copyable: true }   (Scenario H)
  │   ELSE:
  │       delete the empty turn  → no row, only a system msg
```

- `step.partial` may remain `true` (no `step_finished` fired). The renderer
  treats partial steps the same as finalized ones for display.
- D1 / I1 already handle the footer correctly: copy renders because
  `metadata.copyable` is set; timing does not render because
  `metadata.timings` is not set.
- **Wire-shape consequence on the NEXT turn or on reload**: a step persisted
  with `toolCalls` but no matching `toolOutcomes` is fixed up by the orphan
  guard in `stepToApiMessages` (§1b) — every unmatched call gets a synthetic
  `{role:'tool', content:'aborted'}` response so strict-Jinja templates
  don't throw.

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

## 9f. Context-full banner / increase-context CTA

The chat input has ONE banner slot (the existing soft-cap shell). Its
content is computed by a pure resolver from a single
`CompletionResultSnapshot` written at every turn boundary. The resolver
returns exactly one of five variants in this precedence order:

1. `context-full` — `snap.contextFull === true`. Per-draft dismiss
   (reappears next turn if still full); also exits via auto-clear when
   the next turn satisfies `used < nCtx - AUTOCLEAR_RUNWAY` AND no §4a
   match, and when the snapshot is invalidated by a message edit/regenerate.
2. `context-warning` — local session, `ratio >= WARNING_THRESHOLD` (0.80),
   not `contextFull`. Per-draft dismiss, reappears next turn if still
   triggered.
3. `context-remote-hedged` — remote session, weak-signal heuristic
   (all of: `finishReason !== 'length'`, `tokensPredicted >= 500`,
   `content` doesn't end on terminal punctuation). Per-draft dismiss;
   re-derives every render.
4. `html-soft-cap` — `htmlPreviewCount >= 4`. Existing rule preserved;
   context variants take precedence so the visible bug (truncated
   replies) wins over the preventative hint.
5. `none` — banner shell hidden.

Hard invariants:

- ONE banner visible at any time (resolver short-circuits).
- `snap.contextFull === true` iff the most recent finished turn matches
  the OR predicate (`result.context_full` / `result.truncated` /
  `metadata.truncationLikely` / remote `finish_reason==='length'`).
- `lastCompletionResult` and `metadata.completionResult` are written
  together, in the same MobX action.
- The pal-load hint (`usePalLoadHint`) is a snackbar, not a banner.
  Snackbar lives on a separate surface and cannot displace a banner
  variant.
- **Reader-side freshness gate**: the resolver only returns the sticky
  `context-full` variant when the snapshot's `contextFull` flag is
  corroborated by current fullness — `used >= effectiveNCtx - AUTOCLEAR_RUNWAY`.
  When the user lifts n_ctx via the in-banner confirm, the new
  `effectiveNCtx` makes the still-persisted snapshot stale on the
  read-side and the banner falls through to warning/none without
  requiring a new inference to overwrite the snapshot.
- **Snackbar focus gate**: both the reload snackbar (raised by the
  `IncreaseContextSheet` confirm callbacks, hosted in `ChatView`) and
  the pal-load hint (`usePalLoadHint`) are gated by `useIsFocused()` in
  `ChatView`. State persists across navigation but the surface is
  suppressed when the chat screen is off-screen, so the snackbars never
  appear over drawers, settings, or model pickers. `usePalLoadHint` also
  gates its predicate evaluation by focus — it sets the per-signature
  suppressor marker only after the predicate ran, so a re-focus with the
  same signature can still raise the hint.
- **Single-surface dismiss**: when the reload snackbar fires, the
  pal-load hint snackbar is dismissed synchronously in the same React
  event handler. Both setters land in one auto-batched commit (React
  18), so no frame shows two snackbars at once. Pal-load
  `onAction()` follows the same pattern: it dismisses itself before
  returning to the caller.

The "More room" CTA opens `IncreaseContextSheet` without a precomputed
target — the sheet owns target selection. The user picks a larger context
size on a slider over `CONTEXT_LADDER`, filtered to stops above the current
n_ctx and capped at `model.ggufMetadata.context_length` (the model max is
appended as the rightmost stop). The sheet classifies each stop into three
zones via a pure, caller-injected fit helper: `fits` (`getModelMemoryRequirement(...)`
`<= max(largestSuccessfulLoad, availableMemoryCeiling)`), `tight`
(`<= DeviceInfo.getTotalMemory()`), else `wont_fit`. Confirm is disabled on
a `wont_fit` stop. When no stop above the current value `fits`, the sheet
hides confirm entirely and offers a [New chat] affordance so it is never a
dead-end (it is reachable from the pal-load hint's "More room" action even
when the banner CTA is hidden). The banner's increase CTA mirrors the same
OOM-safe intent: it is shown only when at least one ladder tier above the
current n_ctx `fits` the device; otherwise the full banner offers only
[New chat].

Confirm calls `modelStore.setNContext(chosen)` (the same global Settings
value) then `releaseContext → initContext`, while `ChatView` shows an
indefinite reload snackbar that flips to success / failure. On failure the
sheet restores the prior `n_ctx` with a second `setNContext` call AND
re-`initContext`s so the model ends up loaded, not just the setting
restored; chat history is preserved (messages live in `ChatSessionStore`,
not in `LlamaContext`). The warning and full banners also render a fullness
meter whose width is the resolver's `used / effectiveNCtx` ratio (clamped
`[0, 1]`); the meter is absent on the remote-hedged variant.

See `pals-and-talents.md` §5a I8 for the `recommendedContextTokens`
declarative hint that powers (a) the pal-load snackbar trigger and
(b) the heavy-talent sub-copy on the `context-full` banner.

---

## 10. What this doc is NOT

- not a TODO list
- not an implementation plan (those live in `how.md`)
- not a record of recent fixes (those live in commits)

When this doc and a commit disagree, the commit wins — but then this doc must
be updated in the same change. Drift is the failure mode that will bring back
the ping-pong.

**Cleanup reminders**:

- **Cleanup-DEFERRED** (was cleanup #2; still open) — `inferencing`,
  `isStreaming`, `isGenerating`, `isGeneratingToolCall` are written
  separately by `useChatSession` and should derive from
  `agentUiState.status` instead. `ChatView` already does this for the
  PendingIndicator visibility gate (`isPending`); the remaining flags are
  read by ChatScreen and model-load screens and have not been migrated.

Future stories that touch this flow should add their cleanup reminders here
and remove them as they land. Drift policy: see
`context/architecture/README.md` § Drift prevention.
