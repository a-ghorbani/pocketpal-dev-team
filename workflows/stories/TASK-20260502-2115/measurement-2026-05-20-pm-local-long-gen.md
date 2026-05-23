# Measurement run 4: local mode, no tools, **long generation** before Stop

Date: 2026-05-20 ~18:55. Device: OnePlus 6 (Cortex-A75/A55). Driven
unattended via `measure-stop.sh` + manual tap recovery. Prompt: "Write
a very long detailed story about humanity colonising Mars over the
next two hundred years…". Model: gemma-4-E2B-it Q4_K_M (local).

Critical difference from run 3: streamed for **154 seconds before
Stop was processed**, producing 1430 tokens. The long generation
stresses the JS thread far more than run 3 (74 tokens).

## Raw numbers

`stop-pressed` (at 154.6 s after send):

```
consumer:    events=1432, tokens=1430, toolCallTokens=0
             avgEventMs=104.13, maxEventMs=321.88
queue:       shifts=0, waiters=1431, maxDepth=0, bufferedPct=0
chunkCallback: count=1430
stop:        tapToHandlerMs=1
             writeToCommitMs=null
             tapToLastChunkMs=63                  ← NEW PROBE
             chunksAfterAbort=0
heartbeat:   count=16
             maxGapMs=113704.4                    ← 113 SECONDS
             over100ms=7, over250ms=5, over500ms=3
             stopTapGapMs=31923                   ← 32 SECONDS
```

`run-finished` (at 165.1 s, 10.5 s after Stop):

```
consumer:    events=1434, tokens=1430              ← +0 tokens post-stop
             avgEventMs=111.26, maxEventMs=10271.4
chunkCallback: count=1430                          ← +0 chunks post-stop
stop:        writeToCommitMs=75                    ← indicator commit fast
             abortToStopResolveMs=75               ← native stop fast
             chunksAfterAbort=0                    ← abort guards working
heartbeat:   count=583                             ← drained at end
```

## Headline: Stop tap took **59 seconds** to be processed

I tapped Stop via `adb shell input tap` at wall-clock 18:55:12. The
JS handler ran at 18:56:11 — **59 seconds later**.

The instrumentation explains exactly why:

- `heartbeat.maxGapMs = 113704` — at some point during the run the
  JS thread had a **113-second period** with NO macrotask slot
  delivered. `setTimeout(0)` callbacks queued for that long.
- `heartbeat.stopTapGapMs = 31923` — at the moment the JS handler
  ran, the last heartbeat had fired **31.9 seconds prior**. So the
  JS thread had been continuously busy with chunk-processing macro-
  tasks for at least 32 s before our touch event got a slot.
- `heartbeat.count = 16` over 154 s = **one macrotask slot every
  ~10 s** while streaming was active.

Touch events from native (`adb input tap`, real finger taps —
they take the same path) sit in the **same macrotask queue** as
`setTimeout`. When chunks monopolise that queue, taps starve.

## The mechanism, confirmed

1. llama.rn fires the chunk callback via JSI on the JS thread.
2. The runner's chunk handler pushes onto the EventQueue (synchronous).
3. The consumer for-await body picks it up via microtask resumption
   and processes the event (avg 104 ms / max 322 ms).
4. The body finishes; `await queue.next()` returns a fresh **pending**
   Promise (`waiters=1431`, every iteration); JS is briefly idle.
5. Native immediately fires the next chunk callback, which restarts
   the cycle.

Steps 1–5 cycle every ~108 ms (1430 tokens / 154 s = 9.3 Hz). The
"briefly idle" window between iterations is too small for the macro-
task queue to actually drain — and over 154 s, the cumulative effect
is multi-tens-of-seconds starvation of any low-priority macrotask
(including touch dispatch from native to the React handler).

`tapToLastChunkMs = 63` is the smoking-gun confirmation: when the
JS handler finally ran, a chunk callback had completed 63 ms earlier.
The tap was queued right behind chunk processing.

## What the abort guards *did* fix

Once the handler ran, the rest worked exactly as designed:

- `chunksAfterAbort = 0` → no tokens processed after Stop
- `writeToCommitMs = 75 ms` → "Stopping…" indicator visible promptly
- `abortToStopResolveMs = 75 ms` → native cleanly stops
- `consumer.tokens` stays at 1430 from stop-pressed → run-finished

So the **tail** problem is solved. The **head** problem is the
JS-thread starvation preventing the handler from running in the
first place.

This is the *exact* mechanism the reviewer described in
`stop-button-delay-review.md` as "microtask starvation," and which
I dismissed in `measurement-2026-05-20-local-no-tools.md` because the
queue depth showed 0. The queue depth was 0 because the **consumer
was faster than the producer**; the starvation is at a different
layer (the macrotask queue between chunk-callback cycles).

## The Hermes profiler hooks didn't fire

`grep "profile saved" logcat.txt` returns nothing. No "[stream-debug]
sampling profiler started" either. Likely cause: `HermesInternal`
isn't exposing `enableSamplingProfiler` on this build's Hermes
version, and the try/catch silently swallowed the failure. The
log-level filter on warnings might also have hidden a warning.
Worth fixing next round but not blocking — the dump data alone is
diagnostic enough for the next fix.

## What this means for the next fix

**The reviewer was right.** Microtask-starvation (more precisely:
macrotask-starvation between rapid chunk-cycle iterations) is the
dominant cause of "the time before Stopping… appears feels long."
The current head latency is proportional to how long streaming has
been running before the tap — short prompts give ~hundreds of ms
delay, long prompts give tens of seconds.

The cleanest fix is a **cooperative yield** in the consumer for-await
body, e.g.:

```js
for await (const event of events) {
  // ... existing per-event work ...
  if (eventCount % 10 === 0) {
    await new Promise(r => setTimeout(r, 0));
  }
}
```

Every N events, the loop suspends on a macrotask boundary. The
macrotask queue drains. Touch events get a slot. `handleStopPress`
fires. Abort guards do their thing.

**Tradeoffs:**
- 1 extra macrotask roundtrip per N events. At N=10 and 9.3 ev/s,
  that's ~1 yield/s. Per-yield cost ~1 ms. Negligible streaming
  overhead.
- Will it slow streaming? No — the consumer was already faster than
  the producer (bufferedPct=0). It only converts "wasted JS-bound
  busy time" into "yielded to the event loop."

**N value to pick:** N=10 is conservative. N=1 (yield every event)
would maximise responsiveness but adds 9 macrotask roundtrips/s.
Worth measuring both, but N=5–10 is the sweet spot.

## Recommended next steps

1. **Land a cooperative-yield patch** (N=5 or 10). Re-run this same
   scenario. Expected: `heartbeat.maxGapMs` drops from 113 s to
   ~50 ms, `tap-to-handler` delay drops from 59 s to sub-second.
2. **Fix the Hermes profiler hook** so we can also profile the
   per-event 104 ms work. Long-term cost-reduction matters even
   after the head-latency fix lands.
3. **Long-term: figure out why per-event is 104 ms.** For text-only
   tokens it should be sub-ms. The 104 ms is the underlying problem
   making streaming feel sluggish even when not tapping Stop.
