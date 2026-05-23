# Independent review of `stop-button-delay.md`

Method: I read the proposed findings/fixes in `stop-button-delay.md`, then
traced the actual code paths in the worktree without relying on the doc's
reasoning. Sources verified:
`src/services/agent/AgentRunner.ts`,
`src/hooks/useChatSession.ts`,
`src/api/openai.ts`,
`src/api/completionEngines.ts`,
`src/services/agent/agentStateReducer.ts`,
`src/store/TTSStore.ts`,
`src/store/ChatSessionStore.ts`.

## Bottom line

The doc correctly identifies that this is a JS-thread problem and several
findings are genuinely real — but it **misdiagnoses which mechanism produces
the most visible symptom**, and as a result its "land #1 first" recommendation
does not address the "Stop indicator appears late" complaint. There is a
structural root cause the doc never names: the consumer `for await` loop in
`handleSendPress` never yields to the macrotask queue while the event queue
is non-empty, so the Stop touch handler is starved.

The proposed fixes are mostly correct and worth doing, but they treat the
*tail* (work happening after Stop is signalled) more than the *head*
(latency until Stop is even acknowledged).

## Finding-by-finding verdict

### §1 No per-chunk abort guard in the runner — REAL, but mis-ranked

Factually true (`AgentRunner.ts:321-353` projects/pushes every chunk,
abort only checked at turn boundaries at `:290` and `:438`). But the guard
only does anything **after** `signal.aborted` is true, which requires
`handleStopPress` to have run. If the JS thread is starved (see "the gap"
below), the handler hasn't run yet, so this guard cannot shorten time-to-
acknowledge. It shortens the *post-abort tail* (buffered chunks become
no-ops), not the *head*. Worth doing, lowest risk — but "biggest effect"
is wrong for the user-visible symptom.

### §2 No abort guard in the drain loop — REAL, the better of the two guards

Adding `if (signal?.aborted) break;` at `AgentRunner.ts:366` is sound. I
checked the control flow after `break`: it falls to `await
completionPromise`, the `engineError` check, then the `!calls` / `signal?.
aborted` breaks at `:416` and `:438` exit the turn loop cleanly. Decouples
consumer draining from the engine promise settling. Same caveat as §1:
only helps once the signal is set.

### §3 `setAgentUiState` per event — OVERSTATED for the common case

This is the doc's weakest finding. I checked the reducer: for a plain
content/reasoning token after the first, `agentStateReducer` returns the
**same `state` reference** (`return state;` at `agentStateReducer.ts:97`).
`setAgentUiState` does `this.agentUiState = state;` — MobX's default
`===` comparer **does not fire reactions when the reference is unchanged**.
So during normal text streaming there is no per-token re-render.

The claim is only true for **tool-call tokens**, where the reducer returns
a fresh object every token (`pendingToolTokens: state.pendingToolTokens +
1`) → re-render per tool-call token. So §3's real cost is concentrated
exactly in the server-mode + tool-calling scenario, and there it overlaps
heavily with §4 (doc-numbering) / §5 here. The "throttle/dedupe
setAgentUiState" fix is harmless but largely redundant for text; its
value collapses into the tool-call fix below.

### §4 TTS forwarding per token — REAL but minor, mis-ranked

`ttsStore.onAssistantMessageChunk` early-returns immediately when not in
streaming mode (`TTSStore.ts:543`: `state.mode !== 'streaming'`). The
residual per-token cost in the hook is two `String.slice` calls of length
O(delta), not O(N). Gating it is a fine, low-risk micro-opt but should
not be ranked #3 — it is not a plausible contributor to a multi-second
lockup.

### §5 OpenAI tool-call accumulator O(N²) — REAL and the actual lockup cause

This is the strongest finding. `existing.function.arguments +=
delta.function.arguments` each chunk, plus a fresh snapshot object per
chunk carrying the **full accumulated args string**, forwarded as a
`token` event every chunk. For a large `render_html` payload over
hundreds of chunks, combined with §3's per-tool-call-token MobX write
(new object each chunk → reaction fires every chunk), this is genuinely
quadratic and explains "server mode + tool-calling: app non-responsive."

I confirmed the runner only needs the **final** args — it executes from
`finishedResult.tool_calls` / `normalizeToolCallIds`, not the streamed
snapshot — so the proposed fix (emit a lightweight tool-call-started
once per index, assemble final args only at `finish_reason`) is
structurally valid.

### §6 `xhr.onprogress` no abort guard — REAL, low-risk, correct

After `xhr.abort()` the already-buffered `responseText` can still drive
a queued `onprogress` → `processChunk`. The guard is cheap and safe;
`onabort` (not `onload`) handles teardown so nothing is lost.

### §7 Double `stopCompletion` in `handleStopPress` — REAL but the rationale is wrong

The redundancy is real (runner's `onAbort` already calls
`engine.stopCompletion`). But the doc's claim that the second `await`
"blocks the handler" and delays feedback is incorrect:
`chatSessionStore.setIsStopping(true)` is called **before** the abort
and the await (line 656). The "Stopping…" flip is already queued
regardless of what the await does afterward. Removing the second call
is a clean simplification with effectively zero perf impact. Do not
sell it as a responsiveness fix.

## The gap the doc misses (most important)

The doc never explains *why* the Stop handler itself is late. The
consumer loop is:

```js
for await (const event of events) {
  uiState = agentStateReducer(uiState, event);   // sync
  chatSessionStore.setAgentUiState(uiState);     // sync MobX write
  await applyEventToStore(event, ...);           // token path: no internal await
}
```

`EventQueue.next()` returns `Promise.resolve(...)` whenever an item is
buffered. `await` on a resolved promise schedules a **microtask**, not a
macrotask. Microtasks run to exhaustion before the next macrotask. RN
delivers touch / `onPress` callbacks as **macrotasks**. So as long as the
engine pushes events at least as fast as the loop drains them, the queue
never empties, the loop spins entirely in microtasks, and
`handleStopPress` cannot run. **The JS thread is starved.** This, not
"per-token work bypasses the throttle," is the precise mechanism behind
both "Stopping… appears late" and the server-mode lockup.

Consequences for the proposed fixes:

- **#1 / #2 (abort guards)** can't fire until the handler runs → they
  don't reduce head latency under starvation. They reduce the tail.
- **#3 / #4 / #5** help **indirectly**: cheaper iterations drain the
  queue faster → the queue empties sooner → the loop parks on a pending
  promise → the JS thread frees → the starved handler finally runs.
  **#5 helps most** because it removes a per-iteration O(N) factor
  (quadratic → linear drain time). The doc's instinct that #5 matters
  is right, but for the *opposite* reason it states (drain-faster-so-
  thread-frees, not throttle-bypass).
- The cleanest direct fix for head latency — a **cooperative yield** in
  the consumer loop (e.g., `await new Promise(r => setTimeout(r, 0))`
  every ~16 ms of accumulated work, or every N events) — is **not
  mentioned anywhere in the doc**. It's a small diff that breaks the
  microtask-starvation property at the root and would make Stop
  responsive on any device, independent of #1–#5. The doc lists the
  gesture-handler worklet as the only "instantaneous Stop" option and
  defers it as too big, while missing this much cheaper alternative.

### Separately: a competing hypothesis for local mode

For **local** mode the doc asserts "same delay → JS-side" purely from
the user's report. The other very common real cause of a slow local
Stop — `context.stopCompletion()` only sets a flag and native must
finish the current `llama_decode`, which during long-prompt **prefill**
can be multi-second and is not interruptible at flag granularity — is
plausible and **not investigated or ruled out**. None of #1–#7 touch
it. Worth at least acknowledging as a competing hypothesis before
claiming #1 "directly addresses the Stop responsiveness symptom."

## Are the fixes "the right thing" regardless?

- **#1, #2, #6**: Yes — correct, low-risk, defense-in-depth that should
  exist regardless of the perf story. Do them. Just don't expect them
  to fix indicator latency.
- **#4 (doc) / §5 here — tool-call snapshot fix**: Right direction and
  the highest-value change, but it's a **contract change** to the
  streaming event payload, and **the same O(N²) shape exists on the
  local llama.rn tool-call path too**: `projectStreamChunk` forwards
  `tc.function.arguments` every chunk regardless of engine. The fix
  should be applied at the projection boundary (or otherwise covered)
  for **both** engines, or the local tool-call path keeps the
  quadratic. This is "standard" complexity, not the "small, low-risk"
  framing the doc implies.
- **#2 (doc) — throttle `setAgentUiState`**: Mostly unnecessary for
  text (MobX reference dedupe already covers it); only matters for
  tool-call tokens where the snapshot fix removes the per-chunk event
  anyway. Low priority once the snapshot fix lands.
- **#3 (doc) — gate TTS**: Fine micro-opt, lowest priority. Not a
  lockup contributor.
- **#5 (doc) — drop second `stopCompletion`**: Do it as a
  correctness/clarity cleanup, not as a perf fix.

## Recommended order (my revision)

1. **Cooperative yield in the consumer loop** (the missing root-cause
   fix for head latency) — small, addresses the actual starvation,
   helps every device/mode.
2. **Tool-call snapshot fix (§5 here / doc #4)**, applied at the
   projection boundary so it covers both local and remote — removes
   the quadratic; the real lockup fix. Treat as standard complexity
   with a `what.md`.
3. **§1 + §2 + §6 abort guards together** — low-risk tail reduction.
4. **§7 cleanup**.
5. **§3 / §4 (doc) dedupe / TTS gate** — only if measurement still
   shows residual jank.

Then measure on the OnePlus, including a long-prompt local case, to
settle whether a native prefill component remains.
