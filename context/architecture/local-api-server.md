# Local API server (pending PR)

## Purpose

PocketPal serving its loaded local model to other apps over an OpenAI-compatible HTTP API (`GET /v1/models`, `POST /v1/chat/completions`, streamed or not), off by default, loopback unless the user opts into LAN. This doc covers the listener, the HTTP layer and how a server request shares the one context with chat. The generation lease itself is in `model-loading.md`; chat's side of waiting is in `chat-flow.md`; the Settings card's place on the screen is in `settings.md`; the native dependency is in `release.md`. `remote-servers.md` is the opposite direction (PocketPal as a client) and shares no code with this flow.

## Code map

| Path | Role |
| --- | --- |
| `src/store/LocalApiServerStore.ts` | Listener lifecycle (`start` / `stop`, epoch), config setters, Keychain key, `baseUrl`, `servedModelId`, admission count |
| `src/services/localApiServer/connection.ts` | `handleConnection`: per-socket reader, 30 s deadline, connection and admission caps, the `ResponseChannel` that ends the socket only after the last write is flushed |
| `src/services/localApiServer/http.ts` | Bounded request reader (`createRequestReader`), UTF-8 decode, JSON / preflight / SSE writers; every response `Connection: close` + CORS `*` |
| `src/services/localApiServer/router.ts` | `routeRequest`: preflight, Host check, Bearer auth (constant time), route and method, JSON parse, then `handleChat` |
| `src/services/localApiServer/wire.ts` | `mapChatRequest` (OpenAI body → llama.rn params) and the response, chunk and error shapes |
| `src/services/localApiServer/chatCompletion.ts` | `serveChatCompletion`: base params, `acquireGeneration`, abort wiring, stream / non-stream completion, `lease.end()` |
| `src/screens/SettingsScreen/LocalApiServerCard.tsx` | Settings card: toggle, port, LAN, key set/clear, URL, served model, last error |
| `ios/PocketPal/Info.plist` | `NSLocalNetworkUsageDescription` names serving as well as connecting |
| `__mocks__/external/react-native-tcp-socket.ts` | `FakeServer` / `FakeSocket` the suites drive |

## How it works

`setEnabled(true)` → `start()`: status `starting`, epoch bumped, Keychain key read into private memory, LAN address read (`DeviceInfo.getIpAddress`) when LAN is on, then `TcpSocket.createServer(...).listen({port, host})` with host `127.0.0.1`, or `0.0.0.0` with LAN on. `listening` → `running`; `error` → `failed` + `lastError`; `close` while running → `failed`. `stop()` bumps the epoch, closes the listener and destroys every open connection.

```
stopped ─start→ starting ─listening→ running ─error/close→ failed ─start→ starting
starting|running|failed ─stop→ stopped      stale epoch event → no change
app active ∧ enabled ∧ (stopped|failed) → start
```

Per connection (`handleConnection`): bytes → `createRequestReader` → `routeRequest`. Chat requests pass admission (≤ 2), then `serveChatCompletion` maps the body over the global chat settings, waits on `modelStore.acquireGeneration()` (FIFO with chat), checks the grant, runs `lease.engine.completion`, writes JSON or SSE frames, ends the lease, and the channel ends the socket once its writes are flushed.

## Contracts and invariants

- **No server completion outside a held, unaborted lease** taken with `acquireGeneration`, and only on `lease.engine` (`chatCompletion.ts`).
- **A server request ends its lease exactly once, last, after the completion settles,** on every path (success, error, abort, disconnect). It never awaits `contextOperationMutex`.
- **Any `lease.abort()` stops the request:** socket close, `stop()`, a context release, `abortActiveGeneration` (VideoPal). It calls `stopCompletion` once and writes only the terminal frame (stream: one `data: {error}` frame, no `[DONE]`; non-stream: 503 `generation_aborted`).
- **A lease granted to a closed socket is ended at once,** with no completion, so the next waiter proceeds.
- **Every guard runs before `acquireGeneration`:** reader limits, Host, auth, route, JSON, field mapping. A rejected request never queues for the model (`router.ts`, `wire.ts`).
- **With a key set, every non-`OPTIONS` route needs `Authorization: Bearer <key>`** (constant-time compare); preflight is unauthenticated by design.
- **`Host` must be an IP literal or `localhost`** (port optional), else 403.
- **Reader bounds:** head ≤ 16 KiB, body ≤ 4 MiB (413), `Content-Length` required on POST and any `Transfer-Encoding` refused (411), request within 30 s (408), ≤ 8 open connections (excess destroyed unanswered), ≤ 2 chat requests waiting or generating (503 `server_busy`).
- **Every completion is bounded:** `n_predict` in [1, 2048], 1024 when omitted (`wire.ts`). With the admission cap, a chat send waits at most two bounded completions.
- **Only a local model is served:** no model, release in progress or benchmark → `acquireGeneration` null; a remote model → the lease's engine is not a `LocalCompletionEngine`, ended unused. Both 503 `no_model`. Never proxy a remote server or its key.
- **Loopback unless `lanEnabled`.** `enabled` is never persisted (off at launch); `port` and `lanEnabled` persist and change only while stopped.
- **The key lives in Keychain service `local_api_server_key` and in the store's private field while started;** never logged, persisted elsewhere, or rendered.
- **One request per connection, `Connection: close`.**
- **A server request writes no session, message or persisted state.**
- **Single writers:** `enabled` → `setEnabled`; `status` / `lastError` / `epoch` / listener → `start`, `stop`, listener handlers; `activeRequests` → admission; `lanAddress` → `start` and the foreground handler. Neither `modelStore` nor `chatSessionStore` reads this store.

## Traps and decisions

- **`react-native-tcp-socket` is a legacy bridge module running on the interop layer** (no TurboModule). Only a device build proves its events arrive; the fallback is an own TurboModule listener.
- **llama.rn's stream callback `content` / `reasoning_content` are cumulative snapshots,** not deltas (`TokenData`: "parsed content from accumulated text"). `completeStreaming` sends only the unsent suffix, skips a snapshot that rewrote sent text, and flushes the tail from the final result before the finish chunk.
- **Servers are created with `allowHalfOpen: true`:** the library otherwise `end()`s a socket when the client half-closes after its request (toybox `nc`, some scripts), before the reply is written.
- **The native `error` event carries a string** (Android `e.getMessage()`), not an `Error`; `lastError` shows it (e.g. `bind failed: EADDRINUSE`).
- **The Wi-Fi URL needs `ACCESS_WIFI_STATE` on Android:** `DeviceInfo.getIpAddress()` reads `WifiManager` and returns `0.0.0.0` without it, so the card would always say "not on Wi-Fi".
- **Writes and `end()` race on Android:** `end` goes to a different executor than writes, so the channel ends the socket only from the last write's callback. Writing after the peer closed throws (`destroyed`); the channel drops writes once closed.
- **Data crosses the bridge base64-encoded per chunk;** `decodeUtf8` uses percent-decoding rather than relying on a runtime `TextDecoder`. A 4 MiB body is slow to decode; the cap keeps it bounded.
- **The listener's `error` event closes the server first;** a running listener emits `close` before `error`, so `close` only fails a `running` store and `error` always sets `lastError`. A `close()` on a half-open listener is a no-op, so a stale `listening` closes it.
- **Server completions evict chat's cached prompt and state checkpoints;** the next chat turn re-processes its prompt.
- **Base params are the global chat settings (`defaultCompletionSettings` + `newChatCompletionSettings`, tools removed),** not `activeModel.completionSettings`, which is written once at model creation and never updated.
- **The admission cap bounds generated tokens, not prompt processing.** A long client prompt adds its prefill to chat's wait; chat shows the existing "Stopping…" state meanwhile. Measured: a ~1,400-token prompt on Gemma 3 1B (Android, 2,048 context) held a chat send ~44 s, ~23 s of it prefill.
- **iOS suspends the app shortly after backgrounding:** requests stall and the listener may die → `failed`; foreground restarts it. LAN is the practical iOS mode. Android keeps serving in the background until the OS reclaims the process; Auto-release still releases the model (→ 503).
- **The listener does not stop on background** (Android same-phone clients need it). Foreground service, autostart, mDNS, Ollama `/api/chat`, tools and images are not built.
- **Tools, `tool_choice` ≠ `none`, `n` > 1, `logprobs` and non-text parts are rejected with 400,** not ignored, so a client never mistakes an ignored field for model behaviour. `model` is ignored.

## Verification

- Unit: `src/services/localApiServer/__tests__/{http,wire,router,chatCompletion,connection}.test.ts`, `src/store/__tests__/LocalApiServerStore.test.ts`, `src/screens/SettingsScreen/__tests__/LocalApiServerCard.test.tsx`. `chatCompletion.test.ts` uses the mock store's real `GenerationSlot` for lease order.
- Device: Android: toggle on, `adb forward tcp:8080 tcp:8080`, `curl localhost:8080/v1/models`, then a streamed `curl -N` chat request; send from chat during a stream (waits, then runs); Auto-release mid-stream ends the stream with an error frame. iOS: LAN mode from a laptop on the same Wi-Fi, noting the local-network prompt (the simulator showed none for a loopback listener). On this aarch64 Linux host the APK builds only with the reduced variant list and a local `hermesCommand` (`release.md`).
