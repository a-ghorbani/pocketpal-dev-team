# Streaming / stop-button instrumentation

Companion to `stop-button-delay.md` and `stop-button-delay-review.md`.
Goal: collect evidence before choosing the most valuable fix.

## What's instrumented

All gated on `STREAM_DEBUG = __DEV__ && true` in
`src/utils/streamingDebug.ts`. Flip to `false` (or revert the patch) to
remove every call.

| Probe | File | Captures |
|---|---|---|
| Native + JS tap timestamps | `StopButton.tsx` | `nativeEvent.timestamp` and JS `performance.now()` at handler entry |
| Stop handler entry | `useChatSession.ts:handleStopPress` | JS time when `handleStopPress` actually runs |
| `setIsStopping(true)` write | `useChatSession.ts:handleStopPress` | JS time MobX write fires |
| Indicator commit | `ChatView.tsx:PendingIndicatorView` | JS time the `useEffect` for `isStopping → true` runs (React commit landed) |
| `abortRef.abort()` time | `useChatSession.ts:handleStopPress` | JS time abort signal fires |
| `engine.stopCompletion()` resolve | `useChatSession.ts:handleStopPress` | JS time stop actually returns (LOCAL: native batch finish floor) |
| Per-event iteration time | `useChatSession.ts` for-await | count, total/avg/max ms per event; token vs tool-call-token split |
| Queue shift vs waiter | `AgentRunner.ts:EventQueue` | how often `next()` finds a buffered item (consumer never suspends) vs goes to the waiter (truly idle); max depth |
| Chunk callback count + cancel state | `AgentRunner.ts` chunk lambda | total chunks; first chunk after abort; count of chunks after abort |
| `applyToolCallDelta` cost | `openai.ts` | count, total/avg ms, max args length |
| `xhr.onprogress` post-abort | `openai.ts` | count, total ms of onprogress firings after `signal.aborted` |

## How to read the output

Two log lines per session:

1. `[stream-debug] stop-pressed-no-engine` (no native context — server only)
   or `[stream-debug] stop-completion-resolved` (after stopCompletion returns)
2. `[stream-debug] run-finished` (after the for-await loop exits)

### Which fix wins, by the numbers

**A. Microtask-starvation hypothesis (reviewer):** cooperative-yield fix is the leverage point.

Signal:
- `queue.bufferedPct` close to 100% → consumer effectively never
  suspends → microtask-starved loop.
- `stop.tapToHandlerMs` is large (hundreds of ms) → handler is queued
  behind the loop's microtasks.
- `stop.writeToCommitMs` is large → the MobX write was fast but the
  React commit waited behind streaming microtasks.

**B. Per-event-work hypothesis (original doc):** snapshot fix + abort guards are the leverage point.

Signal:
- `consumer.avgEventMs` or `consumer.maxEventMs` is high (tens of ms
  per event) → each iteration alone is expensive.
- `consumer.toolCallTokens` count is large AND `toolCallDelta.avgMs`
  grows with `maxArgsLen` → the O(N²) accumulator dominates.

**C. Tail-drain (post-abort buffered work):**

Signal:
- `stop.chunksAfterAbort` > 0 → buffered chunks still being processed
  after Stop fires. Affects "Stopping… stays visible for ages" more
  than "Stopping… appears late."
- `onprogressAfterAbort.count` > 0 with non-zero `totalMs` → the OS
  buffered network data is being processed after `xhr.abort()`.

**D. Local-mode native prefill (uninvestigated competing hypothesis):**

Signal:
- `stop.abortToStopResolveMs` large (>500 ms) in **local** mode while
  `stop.chunksAfterAbort` ≈ 0 → native is the floor, JS-side fixes
  won't help local-mode stop latency.

## How to run

1. Confirm `STREAM_DEBUG` is `true` in `src/utils/streamingDebug.ts`.
2. Run the worktree on the OnePlus (or any device).
3. Reproduce in each mode and tap Stop mid-stream:
   - local, no tools (long content stream)
   - local, with tools (a Pal that uses `datetime` / `calculate`)
   - server (llama.cpp), no tools
   - server (llama.cpp), with tools — especially `render_html` (long args)
4. Run `adb logcat | grep stream-debug` (Android) or watch Metro on iOS.
5. Compare the four runs side by side. The shape of the numbers picks
   the hypothesis.

## After measurement

- If **A**: land the cooperative-yield in the for-await loop first.
- If **B**: land the tool-call snapshot fix at the projection boundary
  (covers both local + remote per the review).
- If **C**: land the three abort guards (§1, §2, §6 of the doc).
- If **D**: scope is native; document and de-prioritise the JS fixes
  for local-mode stop latency.

Most likely the numbers show a mix. The point is we pick the leverage
point with evidence, not by argument.
