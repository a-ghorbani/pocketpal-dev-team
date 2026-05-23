# Patch 1: Stop-button abort guards

Lands the three smallest fixes the measurement run pointed at. Keeps
all instrumentation in place so we can A/B with a re-run.

## Changes

### 1. Per-chunk abort short-circuit in the runner
**File:** `src/services/agent/AgentRunner.ts`

Added `if (signal?.aborted) return;` at the top of the engine's
streaming chunk callback (after the instrumentation counters). When
the user taps Stop, native generation can keep firing this callback
for several seconds during wind-down (~319 chunks measured on the
OnePlus). Each chunk used to flow through `projectStreamChunk` →
`queue.push` → consumer pipeline → MobX writes → React renders. Now
the callback returns immediately and the chat freezes at the moment
of stop. Native still runs to its natural finish, but invisibly.

### 2. Post-abort short-circuit in xhr.onprogress
**File:** `src/api/openai.ts`

Same shape for the server-mode SSE path. After `xhr.abort()` the OS
can still deliver bytes already queued in the receive buffer via
further `onprogress` firings. The handler now consumes the buffer
offset (so any later `onload` doesn't double-process) and returns
without parsing.

### 3. Drop the redundant `engine.stopCompletion` call in handleStopPress
**File:** `src/hooks/useChatSession.ts`, `src/services/agent/AgentRunner.ts`

The runner's `signal.addEventListener('abort', onAbort)` already
calls `engine.stopCompletion()` when the abort signal fires. The
explicit `await modelStore.engine.stopCompletion()` in
`handleStopPress` was a redundant second hop that added ~90 ms of
await to the handler before subsequent cleanup (TTS stop,
deactivateKeepAwake). Removed. `stopCompletionResolveTs` is now
captured in the runner's `onAbort` instead, so the metric remains
available in the run-finished dump.

## Expected behavior change

Before: after Stop, the chat continues to render tokens for the full
native wind-down duration (21 s observed on OnePlus). User sees
"Stopping…" but the chat keeps moving.

After: at the moment of Stop, the chat freezes. Native still
generates internally but JS does no further work. The indicator
stays on "Stopping…" until native truly exits and the runner
resolves, then the message finalizes with whatever content was
already streamed.

## What we expect the next measurement to show

| Metric | Before | After (predicted) |
|---|---|---|
| `chunksAfterAbort` | 319 | ~319 (native still fires, but JS no-ops them) |
| `consumer.events` post-stop | grows by 319 | ~0 — chunks bail before queueing |
| Time from stop → run-finished | 21 s | similar (bounded by native wind-down) |
| Indicator visible time | 21 s | similar (gated on native) |
| `heartbeat.maxGapMs` during post-stop window | 20 s | should drop significantly — JS thread freed |
| Subjective Stop responsiveness | "chat keeps streaming" | "chat freezes immediately" |

Native wind-down (the 21 s floor) is unchanged — that's a llama.rn
concern outside this patch. We're addressing the JS-visible damage,
which is what the user perceives as "Stop has delay."

## Follow-up probes added 2026-05-20

After run #3 confirmed the abort guard worked but the user reported
that the time **before** "Stopping…" appears still feels long, two
small probes were added on top of the same patch:

1. **`tapToLastChunkMs`** in the dump. `stopTapJsTs - lastChunkTs`.
   Tells us whether the Stop tap landed mid-iteration (small to
   ~maxEventMs → tap waited for the current chunk's downstream work)
   or when JS was idle (large → chunk-queueing isn't the cause).

2. **Hermes Sampling Profiler hooks**.
   `startJsProfile()` fires from `resetMetrics()` (per send);
   `stopJsProfile('session')` fires from `dumpMetrics('run-finished')`.
   Output is written to `RNFS.DocumentDirectoryPath/session-<ts>.
   cpuprofile` and the path is logged. Pull with:
   ```
   adb shell run-as com.pocketpalai ls files/
   adb exec-out run-as com.pocketpalai cat files/<name>.cpuprofile > local.cpuprofile
   ```
   Then load in Chrome DevTools → Performance → Load Profile.
   Expected to settle "where does the 90 ms per token actually go".

## Out of scope (not in this patch)

- Tool-call snapshot fix (§5 in the review) — defer until server-mode
  measurement confirms it's still relevant.
- `setAgentUiState` dedupe — reviewer showed it's mostly redundant for
  text streams (MobX ref-dedup). Re-evaluate after the server
  + render_html scenario.
- TTS hook gating — confirmed minor.
- Cooperative yield in the consumer loop — measurement showed
  microtask starvation is not the dominant mechanism for this case.
  Skip unless evidence emerges later.

## Verification

- `yarn tsc --noEmit`: passes.
- `yarn jest src/services/agent/__tests__/AgentRunner.test.ts`:
  (running at write time)
- On-device re-run: pending. Expected log shape — `consumer.events`
  matches `chunkCallback.count` minus `chunksAfterAbort`, instead of
  matching `chunkCallback.count`.
