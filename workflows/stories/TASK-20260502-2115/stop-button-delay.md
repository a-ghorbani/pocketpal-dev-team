# Stop button delay & streaming jank on low-end Android

## Symptom

On a OnePlus device (mid-range, not high-end):

- Tapping **Stop** has a large delay. It eventually stops, but late.
- The "Stopping…" indicator itself appears with a delay.
- Server mode + tool-calling: Stop appears to do nothing, app becomes non-responsive.
- Same delay regardless of local vs remote → JS-side problem, not native.
- Raising `STREAMING_THROTTLE_MS` did **not** help.

## Root cause

The streaming hot path keeps the JS thread busy on per-token work that
**bypasses the throttle**. Touch events for Stop queue behind that work. After
Stop is signaled, more chunks (already buffered on the OS socket or in JSI
callbacks) keep being processed end-to-end because there is no per-chunk
cancel guard.

## Findings (file:line)

1. **No per-chunk abort guard in the runner.** `src/services/agent/AgentRunner.ts:321-353`
   The chunk callback projects, accumulates, and `queue.push`es every chunk.
   Abort is only checked at turn boundaries (`:290`, `:438`), never per chunk.
2. **No abort guard in the runner's queue drain.** `src/services/agent/AgentRunner.ts:366`
   The inner `while (true)` only exits when `queue.finish()` is called, which
   only happens when the engine promise settles — i.e. after every buffered
   chunk has been processed.
3. **`setAgentUiState` fires per event, no throttle.** `src/hooks/useChatSession.ts:535`
   Every `token` event writes to MobX → any observer of `agentUiState`
   re-renders per token. The `STREAMING_THROTTLE_MS` only covers
   `updateActiveStepStreaming`, not this write.
4. **TTS forwarding runs per token.** `src/hooks/useChatSession.ts:235-265`
   String slicing and `ttsStore.onAssistantMessageChunk(...)` execute per
   token even when TTS is not enabled.
5. **OpenAI tool-call accumulator copies the growing args string per chunk.**
   `src/api/openai.ts:90-131`
   For tool calls with large JSON arguments (e.g. `render_html`), each delta
   reallocates the full snapshot. O(N²) over the stream. Explains the
   server-mode + tool-calling lockup.
6. **`xhr.onprogress` has no abort guard.** `src/api/openai.ts:510-518`
   After `xhr.abort()`, any onprogress queued for already-buffered bytes
   still calls `processChunk` → `onToken` → runner chunk handler.
7. **Redundant double-abort in `handleStopPress`.** `src/hooks/useChatSession.ts:657,660`
   `abortRef.abort()` triggers the runner's `onAbort`, which calls
   `engine.stopCompletion()`. The handler then awaits `engine.stopCompletion()`
   again. The second call is unnecessary and the `await` blocks the handler.

## Why raising `STREAMING_THROTTLE_MS` doesn't help

The throttle only covers `updateActiveStepStreaming`. Everything in §3-§7
above runs per chunk regardless. You'd have to push the throttle past the
stream duration to mask it.

## Suggested fix, ranked by impact

1. **Add abort guards at three places (small diff, biggest effect):**
   - `AgentRunner.ts:321` chunk handler, top: `if (signal?.aborted) return;`
   - `AgentRunner.ts:366` drain loop: `if (signal?.aborted) break;`
   - `openai.ts:510` `xhr.onprogress`: `if (signal?.aborted) return;`
   Buffered chunks become no-ops the instant Stop fires.

2. **Throttle / dedupe `setAgentUiState`.** Either shallow-compare before
   writing, or only call from events that actually change status
   (`step_started`, `tool_call_started`, `step_finished`) — skip on `token`
   and `marker_seen`.

3. **Gate the TTS hook on `ttsStore.isActive` (or equivalent).** Skip the
   whole block when TTS is not in use for this run.

4. **Stop snapshotting growing tool-call args per chunk.** Emit a lightweight
   "tool-call started" event with `{index, id, name}` once per index, and
   only assemble the final `arguments` string after `finish_reason`. The
   runner only consumes the final args via `lastResult.tool_calls`.

5. **Drop the second `stopCompletion` call** in `handleStopPress`. The
   runner's `onAbort` already handles it.

## Recommended order

Land **#1** first as a standalone fix — small, low-risk, directly addresses
the Stop responsiveness symptom. Measure on the OnePlus before deciding
whether to do #2-#5. If Stop is then acceptable, #2 and #4 are the next-best
candidates for general streaming smoothness on low-end devices.

## Out of scope

- Moving Stop's `onPress` to a `react-native-gesture-handler` worklet so it
  runs on the UI thread. Would make Stop instantaneous on any device, but
  is a bigger structural change. Reconsider if #1 alone isn't enough.
- Device-class-based throttle floor. Defer until the per-event work above
  is brought down.
