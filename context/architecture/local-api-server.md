# Local API server (pending PR)

## Purpose

PocketPal serving its loaded local model to other apps over an OpenAI-compatible HTTP API (`GET /v1/models`, `POST /v1/chat/completions`, streamed or not), off by default, loopback unless the user opts into LAN. This doc covers the listener, the HTTP layer and how a server request shares the one context with chat. The generation lease itself is in `model-loading.md`; chat's side of waiting is in `chat-flow.md`; the Settings card's place on the screen is in `settings.md`; the native dependency is in `release.md`. `remote-servers.md` is the opposite direction (PocketPal as a client) and shares no code with this flow.

## Code map

| Path | Role |
| --- | --- |
| `src/store/LocalApiServerStore.ts` | Listener lifecycle (`start` / `stop`, epoch), config setters, three-valued Keychain read (`found` / `none` / `error`), `lastError` kind (`LocalApiServerError`), iOS foreground restart, `baseUrl`, `servedModelId`, admission count |
| `src/services/localApiServer/connection.ts` | `handleConnection`: per-socket reader, 30 s deadline, connection and admission caps, the `ResponseChannel` that ends the socket only after the last write is flushed and carries the per-connection `cors` flag (`getApiKey() !== undefined` at accept); drains a head-answered body before ending |
| `src/services/localApiServer/http.ts` | Bounded request reader (`createRequestReader(onHead)`: linear head-end scan, framing, then the head hook before any body byte is kept; an answered head's body is only counted), UTF-8 decode, JSON / preflight / SSE writers; every response `Connection: close`, CORS `*` only when the sink's `cors` is set |
| `src/services/localApiServer/router.ts` | `answerHead`: Origin without a key (403), preflight, Host, Bearer auth (constant time), route, method, `GET /v1/models`, all from the head. `routeBody`: JSON parse, then `handleChat` |
| `src/services/localApiServer/wire.ts` | `validateChatRequest` (OpenAI body → `ValidatedChat`, reads no app state) and infallible `buildChatParams` (over base settings and stop words), and the response, chunk and error shapes |
| `src/services/localApiServer/chatCompletion.ts` | `serveChatCompletion`: validate, `acquireGeneration`, closed / aborted / non-local checks, params from the model active at the grant, abort wiring, stream / non-stream completion, `lease.end()` |
| `src/screens/SettingsScreen/LocalApiServerCard.tsx` | Settings card: toggle (commits a typed port first), port, LAN, key set/clear, URL, served model, localized failure copy per error kind |
| `ios/PocketPal/Info.plist` | `NSLocalNetworkUsageDescription` names serving as well as connecting |
| `__mocks__/external/react-native-tcp-socket.ts` | `FakeServer` / `FakeSocket` the suites drive |

## How it works

`setEnabled(true)` → `start()`: status `starting`, epoch bumped, Keychain key read into private memory (a read error fails the start with `key_unavailable`, no listener), LAN address read (`DeviceInfo.getIpAddress`) when LAN is on, then `TcpSocket.createServer(...).listen({port, host})` with host `127.0.0.1`, or `0.0.0.0` with LAN on. `listening` → `running`; `error` → `failed` + `lastError` (`port_in_use` when the native text names `EADDRINUSE` / address already in use, else `listen_failed`); `close` while running → `failed` (`stopped_listening`). `stop()` bumps the epoch, closes the listener and destroys every open connection.

```
stopped ─start→ starting ─listening→ running ─error/close→ failed ─start→ starting
starting ─key read error→ failed(key_unavailable)
starting|running|failed ─stop→ stopped      stale epoch event → no change
app active ∧ enabled ∧ (stopped|failed) → start
iOS: background, then active ∧ enabled → stop(); start()   (whatever the status)
```

Per connection (`handleConnection`): bytes → `createRequestReader` → framing (400/411/413) → `answerHead` (Origin → OPTIONS → Host → auth → route → method → `/v1/models`). A head answer is written at once; the body is then drained to `Content-Length` (or the deadline) and the socket ends. Otherwise the body is buffered and decoded, `routeBody` parses JSON, chat requests pass admission (≤ 2), then `serveChatCompletion` validates the body, waits on `modelStore.acquireGeneration()` (FIFO with chat), checks the grant (closed, aborted, non-local), builds params over the global chat settings and the active model's stop words read now, runs `lease.engine.completion`, writes JSON or SSE frames, ends the lease, and the channel ends the socket once its writes are flushed.

## Contracts and invariants

- **No server completion outside a held, unaborted lease** taken with `acquireGeneration`, and only on `lease.engine` (`chatCompletion.ts`).
- **A server request ends its lease exactly once, last, after the completion settles,** on every path (success, error, abort, disconnect). It never awaits `contextOperationMutex`.
- **Any `lease.abort()` stops the request:** socket close, `stop()`, a context release, `abortActiveGeneration` (VideoPal). It calls `stopCompletion` once and writes only the terminal frame (stream: one `data: {error}` frame, no `[DONE]`; non-stream: 503 `generation_aborted`).
- **A lease granted to a closed socket is ended at once,** with no completion, so the next waiter proceeds.
- **Every guard runs before `acquireGeneration`:** reader limits and the head guards (Origin, Host, auth, route, method) before any body byte is buffered, then JSON and `validateChatRequest`. A rejected request never queues for the model (`router.ts`, `wire.ts`). Params are built only after the grant, by the infallible `buildChatParams`, so there is no failure path after a grant.
- **At most one response per connection, and the socket ends once:** a head answer does not clear the deadline; the drain ending or the deadline ends the socket with no second answer.
- **No key → no CORS headers anywhere and no `Origin` request reaches a route** (403 `forbidden_origin`, preflight included). CORS comes only from the channel's `cors` flag; no writer decides it.
- **A failed Keychain read never produces a listener;** a keyless listener exists only after a `none` read.
- **With a key set, every non-`OPTIONS` route needs `Authorization: Bearer <key>`** (constant-time compare); preflight is unauthenticated by design and is answered only on a keyed listener.
- **`Host` must be an IP literal or `localhost`** (port optional), else 403.
- **Reader bounds:** head ≤ 16 KiB (scanned once, linearly), body ≤ 1 MiB (413), `Content-Length` required on POST and any `Transfer-Encoding` refused (411), request within 30 s (408), ≤ 8 open connections (excess destroyed unanswered), ≤ 2 chat requests waiting or generating (503 `server_busy`).
- **Every completion is bounded:** `n_predict` in [1, 2048], 1024 when omitted (`wire.ts`). With the admission cap, a chat send waits at most two bounded completions.
- **Only a local model is served:** no model, release in progress or benchmark → `acquireGeneration` null; a remote model → the lease's engine is not a `LocalCompletionEngine`, ended unused. Both 503 `no_model`. Never proxy a remote server or its key.
- **Loopback unless `lanEnabled`.** `enabled` is never persisted (off at launch); `port` and `lanEnabled` persist and change only while stopped.
- **The key lives in Keychain service `local_api_server_key` and in the store's private field while started;** never logged, persisted elsewhere, or rendered.
- **One request per connection, `Connection: close`.**
- **A server request writes no session, message or persisted state.**
- **Single writers:** `enabled` → `setEnabled`; `status` / `lastError` / `epoch` / listener → `start`, `stop`, listener handlers; `activeRequests` → admission; `lanAddress` → `start` and the foreground handler; `hasApiKey` → constructor and `start` (`found` / `none` only), `setApiKey`, `clearApiKey`; `wentToBackground` → `handleAppStateChange`; channel `cors` → `handleConnection` at accept; `port` → `setPort` (called by the card's blur or switch-on commit). Neither `modelStore` nor `chatSessionStore` reads this store.

## Traps and decisions

- **`react-native-tcp-socket` is a legacy bridge module running on the interop layer** (no TurboModule). Only a device build proves its events arrive; the fallback is an own TurboModule listener.
- **llama.rn's stream callback `content` / `reasoning_content` are cumulative snapshots,** not deltas (`TokenData`: "parsed content from accumulated text"). `completeStreaming` sends only the unsent suffix, skips a snapshot that rewrote sent text, and flushes the tail from the final result before the finish chunk.
- **Servers are created with `allowHalfOpen: true`:** the library otherwise `end()`s a socket when the client half-closes after its request (toybox `nc`, some scripts), before the reply is written.
- **The native `error` event carries a string** (Android `e.getMessage()`), not an `Error`. It maps by pattern to a `LocalApiServerError` kind and goes to `console.warn`; the card renders only localized copy for the kind, never the native text.
- **The Wi-Fi URL needs `ACCESS_WIFI_STATE` on Android:** `DeviceInfo.getIpAddress()` reads `WifiManager` and returns `0.0.0.0` without it, so the card would always say "not on Wi-Fi".
- **Writes and `end()` race on Android:** `end` goes to a different executor than writes, so the channel ends the socket only from the last write's callback. Writing after the peer closed throws (`destroyed`); the channel drops writes once closed.
- **Data crosses the bridge base64-encoded per chunk;** `decodeUtf8` uses percent-decoding rather than relying on a runtime `TextDecoder`. A large body is slow to decode (~400 ms per 4 MiB on desktop V8), hence the 1 MiB cap and the head guards before any body is read.
- **A head-rejected request is drained, not closed:** Android `end()` is a full `close()`, so closing mid-upload resets the connection and the client never reads the 401/403. The 30 s deadline keeps running through the drain and ends the socket without a 408.
- **The listener's `error` event closes the server first;** a running listener emits `close` before `error`, so `close` only fails a `running` store and `error` always sets `lastError`. A `close()` on a half-open listener is a no-op, so a stale `listening` closes it.
- **Server completions evict chat's cached prompt and state checkpoints;** the next chat turn re-processes its prompt.
- **Base params are the global chat settings (`defaultCompletionSettings` + `newChatCompletionSettings`, tools removed),** not `activeModel.completionSettings`, which is written once at model creation and never updated.
- **The admission cap bounds generated tokens, not prompt processing.** A long client prompt adds its prefill to chat's wait; chat shows the existing "Stopping…" state meanwhile. Measured: a ~1,400-token prompt on Gemma 3 1B (Android, 2,048 context) held a chat send ~44 s, ~23 s of it prefill.
- **iOS suspends the app shortly after backgrounding:** requests stall and the listener may die while the store still says `running`, so a return from `background` restarts it whatever the status (an `inactive`-only blip such as Control Center does not, to keep live streams). The restart re-reads the Keychain; a read error fails closed (`key_unavailable`). LAN is the practical iOS mode. Android keeps serving in the background until the OS reclaims the process; Auto-release still releases the model (→ 503).
- **LAN mode binds `0.0.0.0`, so the server is reachable on every interface** (Wi-Fi, mobile data, hotspot, VPN); the card copy says so and recommends a key. Wi-Fi-only binding is not built.
- **`react-native-tcp-socket`'s manifest adds `CHANGE_NETWORK_STATE`;** the app manifest removes it (`tools:node="remove"`). `ACCESS_NETWORK_STATE` (normal) stays. Its BouncyCastle jars serve TLS only and are excluded from the runtime classpaths: −3,339,061 bytes of APK, 5,720 classes (`release.md`).
- **The listener does not stop on background** (Android same-phone clients need it). Foreground service, autostart, mDNS, Ollama `/api/chat`, tools and images are not built.
- **Tools, `tool_choice` ≠ `none`, `n` > 1, `logprobs` and non-text parts are rejected with 400,** not ignored, so a client never mistakes an ignored field for model behaviour. `model` is ignored.

## Verification

- Unit: `src/services/localApiServer/__tests__/{http,wire,router,chatCompletion,connection}.test.ts`, `src/store/__tests__/LocalApiServerStore.test.ts`, `src/screens/SettingsScreen/__tests__/LocalApiServerCard.test.tsx`. `chatCompletion.test.ts` uses the mock store's real `GenerationSlot` for lease order. Scenarios covered: linear head scan (copied bytes ≤ 4 × head), 1 MiB boundary, Origin/CORS by key, head reject + drain and the drain deadline (fake timers), params after the grant, abort at the grant, key read error, error kinds, iOS foreground restart, port commit without blur. `connection.test.ts` destroys every connection in `afterEach`; run the suites with `--detectOpenHandles`.
- Build: `aapt2 dump permissions` on the release APK (no `CHANGE_NETWORK_STATE`); `dexdump` class counts for `Lorg/bouncycastle/` (0) and `Lcom/asterinet/react/tcpsocket/`.
- Device: Android: toggle on, `adb forward tcp:8080 tcp:8080`, `curl localhost:8080/v1/models`, then a streamed `curl -N` chat request; send from chat during a stream (waits, then runs); Auto-release mid-stream ends the stream with an error frame. iOS: LAN mode from a laptop on the same Wi-Fi, noting the local-network prompt (the simulator showed none for a loopback listener). On this aarch64 Linux host the APK builds only with the reduced variant list and a local `hermesCommand` (`release.md`).
