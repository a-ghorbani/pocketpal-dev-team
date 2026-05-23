# Measurement run 1: local mode, no tools

Date: 2026-05-20. Device: OnePlus (mid-range Android).

## Raw numbers

`stop-completion-resolved` (5030 ms after send):

```
consumer:    events=53, tokens=51, toolCallTokens=0
             avgEventMs=73.96, maxEventMs=152.12
queue:       shifts=0, waiters=52, maxDepth=0, bufferedPct=0
toolCallDelta: count=0
chunkCallback: count=51
stop:        tapToHandlerMs=1
             nativeTapToHandlerMs=2751  ⚠ clock-base mismatch, ignore
             writeToCommitMs=null
             abortToFirstChunkMs=null
             abortToStopResolveMs=76
             chunksAfterAbort=0
onprogressAfterAbort: 0
```

`run-finished` (8390 ms after send, 3360 ms after stop tap):

```
consumer:    events=104, tokens=100, toolCallTokens=0
             avgEventMs=68.51, maxEventMs=164.43
queue:       shifts=0, waiters=101, maxDepth=0, bufferedPct=0
toolCallDelta: count=0
chunkCallback: count=100
stop:        tapToHandlerMs=1
             nativeTapToHandlerMs=2751
             writeToCommitMs=null
             abortToFirstChunkMs=85
             abortToStopResolveMs=76
             chunksAfterAbort=49
onprogressAfterAbort: 0
```

## What the numbers say

### 1. JS thread is NOT starved — microtask-starvation hypothesis rejected for this case

- `tapToHandlerMs = 1` — JS-thread dispatch of Stop tap to handler entry
  is 1 ms.
- `queue.bufferedPct = 0%`, `waiters = 101`, `maxDepth = 0` — the queue
  was empty **every single time** the consumer called `next()`. The
  for-await loop suspends on every iteration. The reviewer's
  microtask-starvation mechanism does not apply here.
- Implication: a cooperative-yield in the consumer loop **wouldn't
  change anything** in this scenario. The loop already yields.

### 2. Per-event work is ~74 ms per token — a real, separate problem

- `avgEventMs = 68-74`, `maxEventMs = 152-164`.
- For text-only streaming this should be sub-millisecond (sync reducer,
  ref-deduped MobX write, throttled streaming update). Something else
  is happening per iteration — possibly React commit work landing
  inside the iteration window, MobX scheduler overhead, or repository
  DB writes from `applyStreamingUpdate` (which fires fire-and-forget
  but allocates a promise + sets up the call).
- **This is not what's making Stop slow** (tap-to-handler is 1 ms),
  but it's a real perf issue worth investigating separately — it
  probably contributes to overall streaming feel on this device.

### 3. The smoking gun for "Stop has delay" in LOCAL mode: native wind-down

- `engine.stopCompletion()` returned in **76 ms**.
- Between stop-press and run-finish: **49 more chunk callbacks arrived
  from native**, over **~3.36 seconds**.
- First post-abort chunk arrived 85 ms after the abort call.
- Each of those 49 chunks ran through the full consumer pipeline
  (~74 ms each → ~3.6 s of JS work tracking the data exactly).

This is **hypothesis D** from the review confirmed for local mode:
`llama.rn`'s `stopCompletion()` is non-blocking — it sets a flag, but
the native generation loop takes several seconds to wind down. During
that wind-down, native keeps firing chunk callbacks and JS keeps
processing them.

### 4. The clock-base mismatch on native-tap-time

`nativeTapToHandlerMs = 2751` is meaningless: `nativeEvent.timestamp`
on Android is `SystemClock.uptimeMillis()` (ms since boot);
`performance.now()` in Hermes is JS-engine relative. They share no
origin. Ignore this number; we'd need either both clocks normalised
(possible via `Date.now()` on both sides) or a different probe (e.g.
an `onResponderGrant` event in `View` with manual timestamp).

### 5. writeToCommitMs = null — instrumentation gap

`PendingIndicatorView`'s `useEffect` never set the value. Two possible
causes:

- The component never mounted with `isStopping === true` in the
  observable window (unlikely — `isStopping` was true for ~3.4 s).
- MobX's React scheduler ran the re-render but my `useEffect` capture
  didn't land before `dumpMetrics` fired at run-finished.

Either way it's a probe-correctness question, not a fix-direction
question. Worth checking on the next run (a `console.log` inside the
useEffect would confirm).

## What this means for fixes

| Fix in `stop-button-delay.md` | Evidence in this run |
|---|---|
| #1 per-chunk abort guard in runner | **Worth doing.** Cuts the 49-chunk tail — those would become no-ops instead of triggering 49 React commits. Doesn't shorten native wind-down but stops the chat from updating after Stop. |
| #2 abort guard in drain loop | **Worth doing.** Same as #1 but at the consumer side. |
| #3 throttle `setAgentUiState` | Not applicable here (toolCallTokens = 0). Re-evaluate after server + tool-calling run. |
| #4 gate TTS hook | Confirmed minor — TTS was off, no contribution. |
| #5 tool-call snapshot fix | Not applicable here. Re-evaluate after server + tool-calling run. |
| #6 xhr.onprogress abort guard | Not applicable (local mode). |
| #7 drop second `stopCompletion` call | Cosmetic — the await was 76 ms, not material. |

**The dominant local-mode cost is native wind-down (3.4 s)**. JS-side
fixes shorten the *tail* (chunks-after-abort become no-ops, so the
chat stops updating immediately) but the native floor stays at ~76 ms
flag-set + however long llama.rn takes to actually exit its decode
loop.

## What we still need to know

1. **Server mode, no tools** — does `chunksAfterAbort` show network-buffer
   tail? Does `bufferedPct` rise (more chunks than the consumer can
   drain)?
2. **Server mode, with tools (especially `render_html`)** — does
   `toolCallDelta.maxArgsLen` grow into KBs? Does `avgMs` per delta
   grow with args length (O(N²) confirmation)? Does `bufferedPct` go
   above 0% — i.e., the consumer actually falls behind?
3. **Local mode, with tools** — does the runner's `projectStreamChunk`
   show the same O(N²) shape for local tool-calling? (No openai.ts
   accumulator there, but the projection itself does
   `tc.function.arguments` per chunk.)
4. **Why is per-event 74 ms?** Add a sub-measurement that excludes the
   `await applyEventToStore` to see if the wait itself accounts for
   most of it. Probably worth a separate instrumentation pass.

## Next step

Re-run with:
- server (llama.cpp) mode, plain text, mid-tap stop
- server (llama.cpp) mode, with a `render_html` tool call, mid-tap stop

Then re-evaluate which fix is highest-leverage. Right now the local
data alone says: **#1 + #2 first (kills the post-stop chat-update
tail), and native llama.rn wind-down is the floor we can't fix at the
JS layer**.
