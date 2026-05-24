# Agent Runner

**Purpose**: cumulative architecture truth for the **AgentRunner** — the
event-producing core of every chat turn. Documents what `runAgent()` emits, the
turn loop, and the abort / error / follow-up contracts.

Consumers (downstream):

- `chat-flow.md` — rendering, status, `AssistantTurn` shape
- `pals-and-talents.md` — talent engines + dispatch

Convention: **(C)** = current behaviour, **(D)** = resolved decision.

Source of truth in code:

- `src/services/agent/AgentRunner.ts` — the loop
- `src/services/agent/AgentRunner.types.ts` — events / options / result
- `src/services/agent/agentStateReducer.ts` — pure reducer (consumer-side)
- `src/services/agent/triggerMarkers.ts` — per-context marker cache
- `src/services/agent/index.ts` — public surface (re-exports)
- `src/hooks/useChatSession.ts` — sole consumer

---

## 1. Data model

### 1a. `AgentEvent` — the wire format

Discriminated union, `AgentRunner.types.ts:41-63`.

| Variant                | Shape                          | When emitted                                                                                  |
| ---------------------- | ------------------------------ | --------------------------------------------------------------------------------------------- |
| `run_started`          | `{ messageId }`                | Once, top of `runAgent` (`AgentRunner.ts:254`)                                                |
| `step_started`         | `{ turn, isFollowUp }`         | Top of each loop iteration (`:294`); `isFollowUp = turn > 0`                                  |
| `token`                | `{ delta: TokenDelta }`        | Each engine stream chunk with non-empty content / reasoning / tool_calls                       |
| `marker_seen`          | `{ marker }`                   | First time accumulated `content` matches one of `triggerMarkers` in this step (≤ 1 per step)  |
| `step_finished`        | `{ turn, toolCalls? }`         | After engine `.completion()` resolves; `toolCalls` carries normalized ids when tools fired    |
| `tool_call_started`    | `{ call }`                     | Just before `engine.execute(args)`                                                            |
| `tool_call_finished`   | `{ outcome }`                  | Always after `executeOne` resolves — engine throws are captured as error outcomes              |
| `run_finished`         | `{ result: AgentRunResult }`   | Clean exit (text-only step, hit max turns, or aborted between turns)                          |
| `run_failed`           | `{ error: Error }`             | Engine rejects, or any uncaught throw inside the generator                                    |

### 1b. Supporting shapes

```
TokenDelta                         // AgentRunner.types.ts:18
  content?           : string                    // parsed text only (no markers/JSON)
  reasoningContent?  : string                    // <think>...</think> stream
  toolCalls?         : AgentToolCall[]           // parsed when present

AgentRunOptions                    // AgentRunner.types.ts:109
  engine             : CompletionEngine          // wire boundary (llama.rn / remote OpenAI)
  initialParams      : ApiCompletionParams       // first-turn messages + tools + params
  allowedTalentNames : string[]                  // PACT whitelist (§ pals-and-talents I2)
  talentLookup       : (name) => TalentEngine | undefined
  triggerMarkers     : string[]                  // precomputed sentinels; [] disables
  messageId          : string                    // pre-created by the hook
  maxTurns?          : number                    // default 5 (DEFAULT_MAX_TURNS)
  signal?            : AbortSignal               // user-tap-stop wiring

AgentRunResult                     // AgentRunner.types.ts:29
  steps        : AgentStep[]    // (C) ALWAYS [] — hook reconstructs from events
  hitMaxTurns  : boolean        // turn >= maxTurns at exit
  finalResult  : CompletionResult   // engine's last result (timings, content, etc.)
```

The runner has **zero** imports from React, MobX, or any store
(`AgentRunner.ts:1-15`). All dependencies arrive through `AgentRunOptions`.

### 1c. Glossary

- **Turn** — one outer-loop iteration: one `engine.completion()` call plus
  any tool dispatch after. Zero-based `turn` index travels on
  `step_started` / `step_finished`.
- **Step** — the persisted slice of a turn. 1 step per turn; the hook
  appends to `AssistantTurn.steps[turn]` on `step_started`.
- **Follow-up** — any turn with `turn > 0`. Exists only when the previous
  step actually invoked a tool; otherwise the loop breaks at `:416`.
- **Pending tool call** — a `tool_call_started` without its matching
  `tool_call_finished` yet. Serial within a step (D1).
- **Synthetic id** — `call_<seed>_<idx>` written by `normalizeToolCallIds`
  (`:105-117`) when llama.rn returns `id: null`. Seed is `Date.now() + turn`.

---

## 2. State machine — run lifecycle

Runner's own emission order. Consumer-side mapping to `AgentUiState.status`
lives in **`chat-flow.md` §3** — not duplicated here.

```
              ┌───────────────────────────────────────────────────┐
              │            run_started  (once per run)            │
              └───────────────────────┬───────────────────────────┘
                                      ▼
                 ┌────────── step_started (turn=N) ──────────┐
                 │                                            │
                 │     token+   (zero or more streamed chunks)│
                 │     [marker_seen]  (≤ 1 per step)          │
                 │                                            │
                 │     step_finished (turn=N, toolCalls?)     │
                 └─────────────────────┬──────────────────────┘
                                       │
                ┌──────────────────────┴──────────────────────┐
                │                                             │
          has toolCalls?                                no toolCalls
                │                                             │
                ▼                                             ▼
       for each call (serial):                       run_finished
         tool_call_started                              (done)
         tool_call_finished
                │
                ▼
        (back to step_started, isFollowUp=true,
         unless turn+1 >= maxTurns or signal.aborted)

  Any point: engine throws / generator throws  ──►  run_failed (final event)
```

Hard sequencing rules (verified in `AgentRunner.ts`):

- **I1**: exactly one `run_started` precedes any other event (`:254`).
- **I2**: every `step_started(turn=N)` is paired with exactly one
  `step_finished(turn=N)` BEFORE any `tool_call_*` for that step
  (`:294`, `:410`).
- **I3**: `token` events for a step arrive before `step_finished`. Within
  one chunk, `token` enqueues **before** `marker_seen` (`:333-348`).
- **I4**: each `tool_call_started` is followed by exactly one
  `tool_call_finished` for the same `call.id` before the next
  `tool_call_started` or `step_started` (`:421-431`).
- **I5**: the run terminates with **exactly one** of `run_finished` or
  `run_failed` (`:478`, `:480`).

---

## 3. Contract

### 3a. What the runner DOES

| Responsibility                                          | Site                                                |
| ------------------------------------------------------- | --------------------------------------------------- |
| Produce every `AgentEvent` for the run                  | `runAgent` generator (`AgentRunner.ts:240`)         |
| Bridge sync engine callback → iterator                  | `EventQueue` (`:28-70`)                             |
| Translate `signal.abort` → `engine.stopCompletion`      | `onAbort` IIFE (`:266-275`)                         |
| Accumulate `content`, scan `triggerMarkers`             | Per-step locals; first match enqueues `marker_seen` (`:301-350`) |
| Normalize tool-call ids (fill `null` with synthetic)    | `normalizeToolCallIds` (`:105-117`)                 |
| Attach per-step generation metrics                      | `:393-408` (only when tool-call tokens were seen)   |
| Whitelist tool name + JSON-parse arguments              | `executeOne` (`:124-186`)                           |
| Wrap engine throws as error outcomes (never throws out) | `executeOne` catch (`:176-186`)                     |
| Build next-turn `ChatMessage[]`                          | `buildNextTurnMessages` (`:194-233`)                |
| Enforce `maxTurns` budget                                | `while (turn < maxTurns)` (`:289`)                  |

### 3b. What the runner DOES NOT

- **Persist anything.** No DB, no MobX writes — hook does that on each event.
- **Render anything.** No React imports.
- **Touch any store directly.** No `chatSessionStore` / `modelStore` /
  `ttsStore` imports.
- **Hold UI status.** `AgentUiState.status` lives on `chatSessionStore`,
  written by the hook via `agentStateReducer`.
- **Decide which talent runs.** Mapping `name → TalentEngine` is injected
  via `talentLookup` — the runner never imports `talentRegistry`.
- **Track its own step list.** `AgentRunResult.steps = []` always (`:469`).
- **Cancel in-flight tool execution.** Once `engine.execute(args)` is
  awaited, it runs to completion (D3).
- **Cache `triggerMarkers`.** Cache scoped to the hook's `useRef`
  (`triggerMarkers.ts`); runner only sees the resolved `string[]`.

### 3c. Consumer-side wiring (one site)

```ts
// useChatSession.ts:521-540
for await (const event of runAgent(opts)) {
  uiState = agentStateReducer(uiState, event);   // pure
  chatSessionStore.setAgentUiState(uiState);     // status write
  await applyEventToStore(event, ctx);           // persistence write
  if (event.type === 'run_failed') throw event.error;
}
```

Two writers consume the same stream but touch disjoint fields (see §4).

---

## 4. Single-writer rule

Runner is the canonical producer at the wire level. Hook is the canonical
writer into the store. Both hold simultaneously.

| Field / signal                              | Single producer                                                   |
| ------------------------------------------- | ------------------------------------------------------------------ |
| `AgentEvent` stream                         | `runAgent` (`AgentRunner.ts:240`)                                  |
| `AgentToolCall.id` (synthetic backfill)     | `normalizeToolCallIds` (`AgentRunner.ts:105`)                      |
| `AgentToolCall.metrics`                     | `runAgent` post-`step_finished` attach (`:399-408`)                |
| `AgentToolOutcome`                          | `executeOne` (`:124`) — always produced, never thrown              |
| Next-turn `ChatMessage[]`                   | `buildNextTurnMessages` (`:194`)                                   |
| `triggerMarkers: string[]`                  | `triggerCacheRef.current.getMarkers(...)` (hook, before run)       |
| `AgentRunOptions`                           | `useChatSession.handleSendPress` (hook)                            |
| `AbortSignal.abort()`                       | `useChatSession.handleStopPress` (hook)                            |
| `engine.stopCompletion()` (in active run)   | runner's `onAbort` handler — sole call site mid-run                |
| `agentUiState.*`                            | `agentStateReducer` only (see `chat-flow.md` §3)                   |
| Per-event store mutations                   | `applyEventToStore` only (see `chat-flow.md` §5)                   |

Iterator returned by `runAgent` is **single-consumer**: only the hook's
`for await` reads it. `EventQueue` has a single waiter slot (`:30`) —
concurrent consumers would race.

---

## 5. Canonical scenarios

Each is an event-emission timeline. Reducer status shown for orientation only;
full reducer rules live in `chat-flow.md` §3.

### A. Single-step, no tool

```
event                                       reducer.status
─────────────────────────────────────────   ──────────────
run_started                                 prefill
step_started   turn=0  isFollowUp=false     prefill
token          delta.content="Hi "          streaming_text
token          delta.content="there."       streaming_text
step_finished  turn=0  toolCalls=undefined  streaming_text (unchanged)
run_finished   hitMaxTurns=false            done
```

Loop exits at `:416` (no tool calls in `lastResult`).

### B. Tool + follow-up (the common tool path)

```
event                                              reducer.status
─────────────────────────────────────────────      ──────────────
run_started                                        prefill
step_started   turn=0  isFollowUp=false            prefill
token          delta.content="Let me check."       streaming_text
token          delta.toolCalls=[{name:'datetime'}] generating_tool_call
marker_seen    marker="<tool_call>"                generating_tool_call
step_finished  turn=0  toolCalls=[call_NNN_0]      generating_tool_call
tool_call_started   call={id:'call_NNN_0', …}      executing_tool
tool_call_finished  outcome={callId:'call_NNN_0'}  executing_tool
step_started   turn=1  isFollowUp=true             prefill
token          delta.content="It's 8:28 AM."      streaming_text
step_finished  turn=1  toolCalls=undefined         streaming_text
run_finished   hitMaxTurns=false                   done
```

`messages` was rebuilt by `buildNextTurnMessages` between turn 0 and turn 1.

### C. Hit max turns

```
maxTurns = 5; every turn asks for another tool
turn 0..4   ── tool dispatch + follow-up each time, messages grow
turn = 5    ── while-guard fails, fall through
run_finished   result.hitMaxTurns = true   ── consumer mirrors to metadata.hitMaxTurns
```

`hitMaxTurns = (turn >= maxTurns)` computed once at `:470`.

### D. Abort mid-stream (user taps Stop)

```
hook                                       runner
────                                       ──────
handleStopPress():
  chatSessionStore.isStopping := true
  abortRef.current.abort()  ──signal.aborted──►  onAbort fires:
  engine.stopCompletion()                          engine.stopCompletion()
                                                    (idempotent — both call)

native winds down, engine.completion(...) resolves with partial result
  ─► .then: queue.finish()
drain → step_finished (toolCalls? from lastResult)
  ── if there were calls: tool_call_* pairs emit normally (D3)
  ── if none: loop breaks at no-tools branch (:416)
                                       loop top: signal.aborted check (:290) breaks
                                       OR mid-turn-end check (:438) breaks
run_finished   hitMaxTurns=false                done
```

Aborted runs land in `done`, NOT `failed` — the hook's catch path runs only if
the engine surfaces an error during shutdown. Hook then writes
`metadata: { interrupted: true, copyable: true }` if any partial content
exists; otherwise it deletes the empty turn (chat-flow.md §9a).

### E. Engine throws (network / context / OOM)

```
event                                       reducer.status
─────────────────────────────────────────   ──────────────
run_started                                 prefill
step_started   turn=0  isFollowUp=false     prefill
token          delta.content="…"            streaming_text
                                            (engine.completion rejects)
run_failed     error=Error("…")             failed
                                            (consumer re-throws; catch path
                                             writes metadata.interrupted)
```

`step_finished` is **NOT** emitted on engine failure — runner yields
`run_failed` and returns (`:378-381`). The active step keeps `partial: true`.

### F. Multi-tool in one step

```
event                                                  reducer.status
─────────────────────────────────────────────────      ──────────────
run_started                                            prefill
step_started   turn=0  isFollowUp=false                prefill
token+         delta.toolCalls=[A, B]                  generating_tool_call
step_finished  turn=0  toolCalls=[A', B']              generating_tool_call
                       ── one step_finished total,
                          payload carries BOTH calls
                          with normalized ids
tool_call_started   call=A'                            executing_tool
tool_call_finished  outcome={callId:A'.id}             executing_tool
tool_call_started   call=B'                            executing_tool
tool_call_finished  outcome={callId:B'.id}             executing_tool
step_started   turn=1  isFollowUp=true                 prefill
…
```

Calls execute **serially** in array order (D1). A failure in A produces an
error outcome but does NOT abort B.

---

## 6. Edge cases

### 6a. Concurrent run guard

(C) **No guard inside the runner.** `runAgent` is a generator factory; calling
it twice returns two independent generators. The hook is the sole concurrency
owner — the UI gates the send button on `isStopping` / `inferencing`. If a
future caller broke this, both runs would still execute correctly but their
`engine.completion` calls would race on the single-threaded native context.

### 6b. Multi-tool metrics overcount

(C) `step.toolCalls[i].metrics = { tokens, durationMs }` is replicated on every
call when N > 1 (`:401-408`). This overstates per-call cost for multi-tool
steps; the metric is really "per-step generation cost, attributed to each
call." Documented decision (D2).

### 6c. Stop-mid-tool

(C) Abort during `engine.execute(args)` does **not** interrupt the talent. The
runner awaits `executeOne` to completion, emits `tool_call_finished` with the
outcome, then checks `signal.aborted` at `:438` and breaks. (D3)

### 6d. Talent missing from registry

(C) `talentLookup(fnName)` returns `undefined`. `executeOne` returns an error
outcome with `summary = "Talent X is not available on this device"`
(`:144-153`). `tool_call_finished` still fires; follow-up proceeds. See
`pals-and-talents.md` §7C.

### 6e. Tool name not in `allowedTalentNames`

(C) Short-circuits before `executeOne` looks up the talent (`:132`). Error
outcome with `summary = "Talent X is not enabled for this Pal"`. Same
downstream flow as 6d.

### 6f. JSI cancel race (model unloaded mid-run)

(C) llama.rn's `engine.completion(...)` rejects when the context is destroyed.
The runner's `.catch` (`:358`) captures it into `engineError`, calls
`queue.finish()`, drains the (empty) queue, awaits the settled promise, and
yields `run_failed`. The `try/finally` (`:288/:481`) detaches the abort
listener either way.

### 6g. Runner exits before final `step_finished`

(C) On engine rejection (Scenario E), the runner yields `run_failed` without a
`step_finished` for the in-flight step — the consumer's persisted step keeps
`partial: true`. The `step_finished` event carries the runner's authoritative
`toolCalls` list, which is meaningless on engine failure (no valid
`CompletionResult.tool_calls`).

---

## 7. Decisions

- **D1 (serial tool dispatch)**: N tool calls in one step run sequentially via
  `await` (`:421-431`). Alternative was `Promise.all`. Decided: simpler
  semantics (paired `tool_call_started/finished` interleave cleanly with
  yields), and today's talents are pure local functions where concurrency
  doesn't help. Reassess for network-bound talents.

- **D2 (per-step metrics replicated on each call)**: see 6b. Alternative was
  per-call attribution, which would need the engine to demarcate calls in the
  stream — not feasible. Cost: rare overcount for multi-tool steps; documented.

- **D3 (no mid-execution tool cancellation)**: abort honoured at turn
  boundary, not inside `engine.execute`. Alternative was a cooperative
  `AbortSignal` on `TalentEngine`. Decided: not worth per-talent plumbing
  today; revisit when a long-running talent (web fetch) lands.

- **D4 (synthetic-then-reconciled tool-call ids)**: runner generates
  `call_<seed>_<idx>` ids in `normalizeToolCallIds` (`:105-117`) and attaches
  the normalized list to `step_finished.toolCalls`. Consumer's
  `appendToolCall` lands them on `step.toolCalls`; outcomes carry the same
  `callId` by construction. Alternative: let strict-Jinja templates fail at
  the next-turn wire boundary. Decided: synthesize early so every persisted
  shape (and the orphan-pair guard in `chat-flow.md` §1b) sees a non-null id.
  See `chat-flow.md` §5 Cleanup-LANDED.

- **D5 (iterator over callback)**: `runAgent` is an `async generator`, not
  `runAgent(opts, onEvent)`. Alternative was callback. Decided: `for await`
  lets the consumer drive the reducer and persistence in lockstep with each
  event without scheduling concerns. The hook's two-step dispatch (reducer
  first, persistence second) is trivial under iteration; callback ordering
  would be brittle.

- **D6 (turn budget = 5)**: `DEFAULT_MAX_TURNS = 5` (`:17`). Alternative was
  unbounded. Decided: cap protects against tool-call loops; 5 covers
  preamble + tool + follow-up + correction + final-summary. Overridable per
  run via `AgentRunOptions.maxTurns` (unused today).

- **D7 (partial step events)**: `token` events arrive before `step_finished`;
  the consumer's `step.partial: true` tells the renderer the step isn't
  finalized. Alternative: buffer until step end. Decided: streaming is the
  point — partial events let the renderer paint as text arrives.

---

## 8. Cross-references

- **`chat-flow.md`** — downstream consumer. Read for: rendering contract
  (§4), full `AgentUiState` and reducer status table (§3), per-event store
  mutations (§5), abort lifecycle and orphan-pair guard (§1b, §9a), canonical
  rendered scenarios (§6).
- **`pals-and-talents.md`** — talent-side. Read for: `TalentEngine` /
  `TalentUI` registries (§2), PACT → `allowedTalentNames` derivation (§3),
  per-tool-call lifecycle and event → status table (§4), engine purity (I4).
- **`tts.md`** — TTS streaming hooks ride the `token` event path inside
  `applyEventToStore` (`useChatSession.ts:228-265`). The runner itself has no
  TTS knowledge.

When this doc and the code disagree, the code wins; the same PR that lands the
change updates this file.
