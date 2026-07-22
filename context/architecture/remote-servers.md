# Remote Servers Flow

**Purpose**: cumulative architecture truth for remote (OpenAI-compatible)
model traffic — the `ServerConfig` model, the `src/api/openai.ts` request
layer, and the per-server network timeout that bounds every remote request.
Bootstrapped from TASK-20260614-1334 (issue #776). Other parts of the remote-
server subsystem (server-type detection heuristics, model reconciliation,
keychain API-key storage) are documented only where this story touched them;
future stories extend the rest.

Convention used in this doc:

- **(C)** = current behaviour, documented from code
- **(D)** = decision (was an open question, now resolved)

---

## 1. Data model

```
ServerConfig                          // src/utils/types.ts
  id: string                          // (C)
  name: string                        // (C)
  url: string                         // (C) base URL, e.g. "http://192.168.1.100:1234"
  lastConnected?: number              // (C) timestamp
  requestTimeoutMs?: number           // (C) per-server network timeout, whole ms; undefined = use API default
  serverType?: string                 // (C) user-selectable; gates the reasoning wire payload; undefined = unknown
  contextLength?: number              // (C) LEGACY. Read-fallback only; no writer.
  supportsVision?: boolean            // (C) LEGACY. Read-fallback only; no writer.

ServerStore                           // src/store/ServerStore.ts
  remoteReasoning: Record<modelId, ReasoningCapability>  // (C) remote reasoning caps,
                                      //   keyed by `${serverId}/${remoteModelId}`; persisted
  remoteCaps: Record<modelId, RemoteModelCaps>           // (C) /props caps, same key
                                      //   shape (`${serverId}/${remoteModelId}` = Model.id); persisted

RemoteModelCaps                       // src/utils/types.ts
  contextLength?: number              // (C) /props n_ctx; ONLY ever a finite number > 0
  supportsVision?: boolean            // (C) /props modalities.vision; definite (true/false) only on a
                                      //   model-describing response; undefined = unknown
```

`serverType` is one of `{llama.cpp, LM Studio, Ollama, OpenAI, vLLM, unknown}`,
chosen via a compact dropdown on both the add-remote and server-details sheets.
`detectServerType` (+ an `api.openai.com → OpenAI` host heuristic) only **seeds**
it on the server sheet; the user's selection wins, and the persisted value (never
live detection) gates the payload. Both `serverType` and `remoteReasoning` ride
the existing `ServerStore` persisted properties — no migration. The reasoning
capability model itself lives in `chat-flow.md` §9g (resolver, two axes,
learn-from-stream, single-writer); this doc covers only the remote wire side.

Capabilities discovered from a llama.cpp `GET /props` response (§8) live in
`ServerStore.remoteCaps`, keyed per model. `/props` answers per model, so on a
multi-model server a server-scoped slot can only ever describe "whichever model
was probed first". The two `ServerConfig` fields of the same name are the
pre-per-model shape: they have **no writer** left (§2b I2) and are read only as
a fallback for a config persisted before the move — a persisted
`contextLength: 0` (a router placeholder) is ignored, since 0 is an unknown
window, not an empty one.

Persisted: `requestTimeoutMs` rides the already-persisted `ServerConfig` inside
`ServerStore.servers`; `remoteCaps` is its own entry in the `ServerStore`
`makePersistable` `properties` list (mobx-persist-store → AsyncStorage, key
`ServerStore`). No migration — an absent field hydrates as undefined (unknown).
Derived: the resolved caps of the active model (§8), computed at read time by
`resolveRemoteCaps`, never stored.

### 1a. Glossary

- **request timeout** — the single per-server duration that bounds a remote
  request. It replaces BOTH the connection-phase guard and the idle
  (no-data-between-chunks) guard when supplied.
- **default timeout** — the value `src/api/openai.ts` applies when no per-server
  value is supplied: `CONNECTION_TIMEOUT_MS` (30000) for the connection phase,
  `IDLE_TIMEOUT_MS` (60000) for the idle phase.

### 1b. External shape

No wire-format change. `requestTimeoutMs` never leaves the device; it only sets
the local `AbortController`/`setTimeout` deadlines on the existing HTTP/SSE
calls to `/v1/chat/completions` and `/v1/models`. The Ollama server-type probe
(`detectServerType`) and its `DETECT_TIMEOUT_MS` (5000) are out of scope.

---

## 2. Contract

### 2a. Timeout resolution

1. (C) `ServerConfig.requestTimeoutMs` is the single source of a server's
   timeout. `undefined` means "unset → API default".
2. (C) `src/api/openai.ts` functions `streamChatCompletion`,
   `fetchModelsWithHeaders`, `fetchModels`, and `testConnection` accept an
   optional `timeoutMs` parameter. When omitted/undefined they apply their
   existing defaults.
3. (C) When `timeoutMs` is supplied to `streamChatCompletion`, it replaces BOTH
   the connection-phase timeout and the idle-phase timeout for that call. The
   two-phase structure (connection guard until headers, idle guard between
   chunks) is preserved; only the duration each phase waits is overridden to the
   single resolved value.
4. (C) `fetchModelsWithHeaders` has only a connection-phase guard; it uses the
   resolved `timeoutMs` when supplied, else `CONNECTION_TIMEOUT_MS`.
   `fetchModels`/`testConnection` forward their `timeoutMs` to it unchanged.
5. (C) `ServerStore` reads `server.requestTimeoutMs` and passes it into
   `fetchModels` (`fetchModelsForServer`) and `testConnection`
   (`testServerConnection`). `ModelStore.setRemoteModel` reads it and passes it
   into the engine so `streamChatCompletion` receives it.
6. (C) `OpenAICompletionEngine` carries the stored `timeoutMs` as a constructor
   field and forwards it to `streamChatCompletion`. The engine is rebuilt per
   `setRemoteModel` call, so an edited timeout takes effect on the next model
   (re)selection.
7. (C) The live edit-time probe in both server sheets passes the in-edit timeout
   value directly: `ServerDetailsSheet.probeServer` reads the in-edit field
   (falling back to the saved `server.requestTimeoutMs`) and passes it to
   `testConnection`; `RemoteModelSheet.probeServer` (manual add path) passes the
   in-edit timeout field to `fetchModelsWithHeaders`. A slow cold-start server
   being edited does not red-X on a probe that exceeds the default.
8. (C) `RemoteModelSheet`'s known-server **chip-press** path
   (`handleServerChipPress`) probes an already-saved server via `fetchModels`
   directly (not through `ServerStore`). It reads that server's stored
   `server.requestTimeoutMs` (raw; normalized only in `openai.ts`) and passes it
   into `fetchModels`. Tapping a saved slow-timeout server's chip does not red-X
   at the default.
9. (C) `DETECT_TIMEOUT_MS` (5s server-type probe) is NOT configurable.

### 2b. Hard invariants

- **I1**: Normalization happens exactly once, in `src/api/openai.ts`
  (`resolveTimeout`): a `timeoutMs` argument that is `undefined`, `≤ 0`, `NaN`,
  or non-finite maps to the supplied default. Stores, the engine, and both
  sheets forward the raw stored/in-edit value (possibly undefined) untouched.
  The API layer never sets a deadline of 0 or negative. One exception, and only
  downwards: the detached `/props` capability probe clamps to
  `PROPS_TIMEOUT_MS` before calling (§8 Bound) — no other path caps a
  user-visible request.
- **I2**: `ServerStore` (`addServer` / `updateServer`) is the only writer of
  `requestTimeoutMs`. `ServerConfig.contextLength` and
  `ServerConfig.supportsVision` have **no writer at all** — they are read-only
  legacy, superseded by `ServerStore.remoteCaps`, whose sole writer is
  `ServerStore.fetchRemoteModelCaps` (§3). `openai.ts`, `ModelStore`,
  `OpenAICompletionEngine`, `BannerRow`, and both sheets only read/forward.
- **I3**: A persisted `ServerConfig` from a prior app version (no
  `requestTimeoutMs`) behaves identically to before (defaults apply). No
  migration, no crash.
- **I4**: The configured timeout bounds individual phases (connect,
  idle-between-chunks), NOT the total wall-clock of a long successful stream. A
  healthy stream emitting tokens within the timeout interval runs indefinitely
  (the idle timer resets on each chunk).

### 2c. Component renders

| Component | Renders | Does NOT render |
| --- | --- | --- |
| `ServerDetailsSheet` | a timeout input (seconds) for the existing server (edit path), placed after the URL input with helper text | a second/idle timeout field; a global setting |
| `RemoteModelSheet` | a timeout input (seconds) on the manual add-server path, inside the post-probe server-fields block; left empty persists `requestTimeoutMs` undefined → defaults apply | a timeout field for the chip path; a second/idle timeout field; a global setting |

`ServerDetailsSheet` save path: the timeout input is persisted through the
existing `handleSave → serverStore.updateServer(serverId, {...})` call, with the
seconds→ms conversion applied at that save boundary (D6). `RemoteModelSheet`
add path: persisted through the existing `serverStore.addServer({...})` call,
same conversion. No new save/persist mechanism is introduced. Conversion uses a
component-local `parseTimeoutMs(seconds)`: empty/invalid/non-positive →
`undefined`, else `round(seconds * 1000)`.

---

## 3. Single-writer rule

| Field | Single writer |
| --- | --- |
| `ServerConfig.requestTimeoutMs` | `ServerStore.updateServer` / `ServerStore.addServer` |
| `ServerStore.remoteCaps` | `ServerStore.fetchRemoteModelCaps` (+ the `removeServer` / `updateServer` prefix prunes) |
| `ServerConfig.contextLength` / `supportsVision` | none — read-only legacy |

Cross-store reads: `ModelStore.setRemoteModel` reads
`serverStore.servers[].requestTimeoutMs` to build the engine (one direction,
ModelStore ← ServerStore — the same place it already reads `url`/apiKey). It
also *calls* `serverStore.fetchRemoteModelCaps` on activation and on foreground
with unknown caps (§8) — a call in the same direction, never a write:
`ModelStore` never touches `remoteCaps`.
`ChatScreen`, `BannerRow` and `ModelStore.isMultimodalEnabled` reach
`remoteCaps` and `servers` only through `resolveRemoteCaps`
(`src/utils/remoteCaps.ts`), so the UI and the send path cannot disagree.

---

## 4. Canonical scenarios

### A. Slow cold-start succeeds with raised timeout
```
ServerConfig.requestTimeoutMs = 600000; remote chat sent; server takes 200s to first byte
─────
connection guard waits up to 600s → headers arrive at 200s → stream proceeds (no premature "Connection timed out")
```

### B. Unset server keeps default behaviour
```
ServerConfig.requestTimeoutMs = undefined; remote chat sent; no headers within 30s
─────
streamChatCompletion rejects "Connection timed out" at 30s (existing default unchanged)
```

### C. Edited timeout applies on reselect
```
user edits requestTimeoutMs in ServerDetailsSheet → saves → reselects the remote model
─────
new OpenAICompletionEngine built with updated timeoutMs; next completion uses it
```

### D. Idle stall still aborts
```
requestTimeoutMs = 120000; stream connects, then emits no chunk for >120s
─────
idle guard fires at 120s → reject "Idle timeout: no data received"
```

### E. Edit-time probe honours the in-edit timeout
```
user editing a slow cold-start server sets timeout field to 600s; debounced probe fires; server takes 200s to first models response
─────
probe passes 600000 ms to testConnection / fetchModelsWithHeaders → success (no premature red-X at 30s)
```

### F. Known slow server selected from chip succeeds
```
saved ServerConfig.requestTimeoutMs = 600000; user taps that server's chip in the add-model sheet; server takes 200s to first /v1/models response
─────
handleServerChipPress reads server.requestTimeoutMs → passes 600000 ms to fetchModels → models load (no premature red-X at 30s)
```

---

## 5. Edge cases

| Edge case | Behaviour |
| --- | --- |
| `requestTimeoutMs` / `timeoutMs` ≤ 0 / NaN / non-finite | Normalized in `openai.ts` to the supplied default (I1). |
| Old persisted config without the field | Defaults apply; no migration (I3). |
| Timeout edited while a completion is in flight | Active engine keeps its value; new value applies on next (re)selection (scenario C). |
| Very large value (e.g. 600000) on a genuinely hung connection | Connection guard waits the full configured duration before aborting — accepted trade-off of a user-set high timeout (I4). |
| Server-type detection probe (`detectServerType`) | Unaffected — keeps fixed `DETECT_TIMEOUT_MS`. |
| Healthy long stream exceeding the timeout in total wall-clock | Runs indefinitely; idle timer resets per chunk (I4). |
| Edit-time field empty / mid-typing on the probe | Falls through to undefined → probe uses API default (I1); no crash. |
| iOS Local Network permission (any LAN-address server) | All flows in this doc presuppose the OS grant. `NSLocalNetworkUsageDescription` in `ios/PocketPal/Info.plist` makes iOS prompt on the app's first LAN request; on iOS 18.x a missing key silently denies instead (no prompt, toggle off in Settings, NSURLError -1009 — indistinguishable from a dead server; Safari is exempt, so it's a misleading control). Already-denied devices don't re-prompt — recovery is Settings → Privacy & Security → Local Network. Simulator never enforces; physical-device-only behaviour. |

---

## 6. Decisions

| ID | Decision | Rationale |
| --- | --- | --- |
| D1 | Per-server field, not app-global | Timeout is a property of a server's network + model speed. |
| D2 | One `requestTimeoutMs`, not split connect/idle | Issue describes one duration; avoid a needless second knob. |
| D3 | One value overrides BOTH phase guards | Both phases currently terminate the same conversation. |
| D4 | Optional field, no migration | mobx-persist-store hydrates an absent field as undefined → default. |
| D5 | Normalization + default live solely in `openai.ts` | Single owner; keeps the timeout floor with the enforcing code. |
| D6 | UI stores/edits seconds; persists whole ms | Seconds is the user's mental unit; ms is the API unit. |
| D7 | `DETECT_TIMEOUT_MS` stays fixed | Server-type probe is internal, not user-facing latency. |
| D8 | Edit-time probe uses the in-edit timeout | The probe is the same symptom; it must not red-X early. |
| D9 | Render an add-path timeout input in `RemoteModelSheet` | A new slow server's probe must honor an in-edit value. |
| D10 | Chip-press probe reads the saved server's `requestTimeoutMs` | Same symptom on an already-saved slow server. |

---

## 7. Reasoning wire gating

`src/api/openai.ts` is the single owner of the reasoning wire shape. The
reasoning **intent** (on/off + optional effort) is carried internally on
`StreamChatParams.reasoning` (mirrored on `ApiCompletionParams.reasoning`);
`OpenAICompletionEngine` forwards both the carrier and its constructed
`serverType` into `streamChatCompletion`, which calls the pure
`buildReasoningPayload(serverType, reasoning)` to produce the per-server body.
The engine forwards intent; `openai.ts` decides the wire shape. There is no
universal payload — each server family has a different 400 posture, so gating is
mandatory and keyed on the persisted `serverType`.

Effort is graded on the servers that read it (llama.cpp, vLLM, OpenAI). When
ON with an effort the effort cell **replaces** the plain ON cell.

| serverType (persisted) | axis-1 OFF → wire | axis-1 ON → wire | axis-2 ON+effort → wire | posture |
| --- | --- | --- | --- | --- |
| llama.cpp | `chat_template_kwargs:{enable_thinking:false}` + `reasoning_format:'auto'` | `reasoning_format:'auto'` | `reasoning_format:'auto'` + `chat_template_kwargs:{reasoning_effort:<lvl>}` | ignores unknown → safe |
| vLLM (modern) | `chat_template_kwargs:{enable_thinking:false}` | (omit) | `chat_template_kwargs:{reasoning_effort:<lvl>}` | ignores unknown → safe |
| LM Studio | `chat_template_kwargs:{enable_thinking:false}` | (omit) | (none; its chat API ignores `reasoning_effort`) | ignores unknown → safe |
| Ollama (/v1) | `reasoning_effort:'none'` (safe no-op) | (omit; never `think:true`) | (omit — deferred) | hard-400 on `think:true` / non-`none` effort to a non-thinking model |
| OpenAI | (omit) | (omit) | `reasoning_effort:<value>` only when axis-2 known for the model id | 400 on any misapplied param |
| unknown / old vLLM | (omit everything) | (omit) | (omit) | 400 on extras → send nothing |

### Invariants

- **I-RS1**: gating is keyed on the PERSISTED `serverType`, never live detection.
- **I-RS2**: an unknown / strict server receives NO reasoning controls — omit
  beats a 400.
- **I-RS3 (Ollama)**: never send `think:true` or a non-`'none'` `reasoning_effort`
  to Ollama. OFF sends only `reasoning_effort:'none'` (a safe no-op even for a
  non-thinking model); ON sends nothing.
- **I-RS4 (llama.cpp `reasoning_format`)**: always `'auto'`, including OFF — a
  no-op for non-reasoning models and the value that extracts reasoning into
  `reasoning_content`. `'none'` is never sent: it leaves the model's raw
  channel/think markers inline in `content` (e.g. gemma-4 emits an empty
  `<|channel>thought` block even when thinking is off), which leaks into the
  rendered answer. On/off is carried solely by `enable_thinking`.

### Decisions

| ID | Decision | Rationale |
| --- | --- | --- |
| D11 | `serverType` user-selectable; `detectServerType` only seeds it | Detection can't classify OpenAI / vLLM; user override is the escape hatch. |
| D12 | Wire payload gated in `openai.ts` by `serverType`; intent carried on `reasoning` | Single wire-shape owner; co-locate the per-server 400 postures. |
| D13 | Ollama graded-effort path deferred; OFF = `reasoning_effort:'none'` only | No `/api/show` capability probe yet; `'none'` is a safe no-op, never a 400. |

### Edge cases

| Edge case | Behaviour |
| --- | --- |
| Old persisted server without `serverType` | Treated as unknown → omits all reasoning controls (I-RS2). No migration. |
| Old persisted server / model without reasoning fields | Resolver fails open via `supportsThinking` / `'unknown'`; no crash (see chat-flow §9g). |
| Ollama OFF `reasoning_effort:'none'` rejected by some non-thinking model | On-device flag: if it 400s, omit `'none'` entirely (omit beats 400). |

---

## 8. Capability discovery (llama.cpp GET /props)

llama.cpp serves `GET {baseUrl}/props`; LM Studio / Ollama / vLLM / OpenAI do
not. The response carries the server's context window and multimodal support,
which unlock remote context banners (chat-flow §4a) and remote image attach
(model-loading — `isMultimodalEnabled` remote fallback).

Capabilities are **per model**, not per server: a multi-model router (llama-swap
style, lazily starting a server per model) answers bare `/props` with a
placeholder describing nothing (`role: 'router'`, `model_path: 'none'`, `n_ctx:
0`, `modalities` **absent** — not null), while `?model=<id>` returns that
model's real properties. A single-model `llama-server` answers the bare form
with its loaded model.

```
user selects a remote model (ModelStore.selectModel → setRemoteModel)
  OR app returns to foreground with the active remote model's caps unknown
  serverType === 'llama.cpp'  ───────────────────────────────── else: no request
    ServerStore.fetchRemoteModelCaps(serverId, remoteModelId, apiKey?)  // DETACHED
      (apiKey passed on the activation path — already resolved for the engine)
      fetchServerProps(url, apiKey, min(requestTimeoutMs, PROPS_TIMEOUT_MS), remoteModelId)
        GET {baseUrl}/props?model=<encodeURIComponent(remoteModelId)>
          [caps resolved] → remoteCaps[`${serverId}/${remoteModelId}`] merged field-wise
          [{}] and single-model gate passes → GET {baseUrl}/props (bare, ONE retry)
            [caps resolved] → merged as above
            [{}]            → no-op; prior entry (if any) untouched
          [{}] and gate fails → no bare request at all; no write
```

- **Trigger is model activation**, not the models fetch. `fetchModelsForServer`
  issues no `/props` request. Capability is a property of a model, and only the
  active model is ever read.
- **Second trigger: foreground with unknown caps.** `ModelStore`'s existing
  foreground `AppState` branch calls `fetchRemoteModelCaps` for the active
  remote model **iff** `remoteCaps` has no entry for it (detached, `.catch`-
  guarded, and `ModelStore` still never writes caps). Without it, activation is
  the sole trigger and remote models are exempt from auto-release
  (model-loading), so one torn-down probe leaves caps unknown for the whole
  session with no recovery but manually re-selecting the model — the likeliest
  case being iOS Local Network (§ permissions), where the first probe is the
  request that raises the prompt and nothing re-probes after the grant. The
  gate is what keeps this from becoming a racing second writer: a populated
  entry is never re-fetched, so a good result can never be clobbered back to
  the placeholder (the failure mode the pre-per-model shape had, where a
  throttled foreground *models* refresh re-probed unconditionally). It lives in
  `ModelStore`, not in `ServerStore`'s own foreground branch, because
  `ServerStore` cannot see the active model without a `ServerStore` →
  `ModelStore` import cycle.
- **Detached probe.** `setRemoteModel` calls it off its awaited path
  (`.catch`-guarded), so a lazily-starting server cannot delay model activation,
  the engine build, or the chat screen. Worst case is two sequential requests,
  i.e. 2× the resolved bound; nothing user-facing waits on it.
- **Bound.** `PROPS_TIMEOUT_MS` (5000) is both floor-fallback and ceiling for
  the probe, and this is the one place where a caller does *not* forward the
  server's raw `requestTimeoutMs` (the I1 exception). `fetchRemoteModelCaps`
  clamps with `Math.min(requestTimeoutMs ?? PROPS_TIMEOUT_MS,
  PROPS_TIMEOUT_MS)` — a shorter server timeout is honoured, a longer one is
  not — and `fetchServerProps` still resolves the clamped value through the
  shared `resolveTimeout(timeoutMs, PROPS_TIMEOUT_MS)`, so an unusable `0` /
  `NaN` / negative falls back to 5000 rather than aborting instantly. Without
  the ceiling, `requestTimeoutMs` being a free unclamped numeric input would
  put an unbounded amount of detached in-flight work behind every activation.
- **Bare retry is gated (single-model gate).** The bare form is issued only when
  the scoped probe yielded `{}`, a model id was supplied, and
  `serverModels.get(serverId)` is an array of length exactly 1 whose `[0].id`
  is that model. `serverModels` is not persisted, so an absent or empty list
  means *unknown*, and unknown does **not** pass — mis-attributing a resident
  model's props to the selected one is unrepresentable, not merely unlikely.
- **Wire → ours** (key names verified against live llama.cpp builds b9910,
  b9976). Rules are independent; a response may yield one field, both, or
  neither:
  - `contextLength ← default_generation_settings.n_ctx ?? n_ctx` (top-level
    `n_ctx` is an older-build fallback), set **only** when that is a finite
    number `> 0`. `0` is unknown, not a window.
  - `supportsVision ← modalities.vision === true`, set (to `true` or `false`)
    **only** on a model-describing response: `model_path` is a non-empty string
    other than `'none'`, or a `contextLength` resolved. On such a body a missing
    `modalities` key is a definite `false` — those builds have no vision path,
    and a definite `false` fails closed. `role: 'router'` corroborates the
    placeholder but is not what the rule tests.
- **Write is guarded and re-checked.** Inside the `runInAction`, the server is
  re-read and its `url` / `serverType` compared against the values snapshotted
  when the probe started; a mismatch (or a gone server) discards the answer,
  because it describes a backend that is no longer configured and its key has
  already been pruned. A merge that changes no field is not written at all,
  matching the `remoteReasoning` writer.
- **Write is a field-wise merge.** `remoteCaps[key] = {...prior, ...caps}`.
  A field the response did not resolve is absent from `caps`, so it leaves the
  prior value untouched; a `{}` result writes nothing. A failing or unusable
  probe therefore never clears, zeroes, or downgrades a known capability — and
  it is not retried in-session; the next probe is the next activation of that
  model.
- **Invalidation.** Entries are pruned by `${serverId}/` prefix (shared
  `dropServerEntries` helper) on two events: `removeServer`, and an
  `updateServer` that changes `url` or `serverType`. Caps describe the
  configured backend, and `resolveRemoteCaps` consults neither field, so a
  repointed url or a type flipped away from `llama.cpp` would otherwise freeze
  stale caps permanently — the writer is gated on `serverType`, the reader is
  not. `remoteReasoning` is pruned only by `removeServer`: it carries user
  declarations and is not server-reported. Editing the url under an active
  model is not a correctness hole in the other direction either — the
  completion engine is not rebuilt by `updateServer`, so that session still
  talks to the old url; the pruned caps are re-probed on the next activation.
- **`fetchServerProps` never throws.** Timeout / non-2xx / malformed JSON all
  resolve to `{}`; a `/props` failure is invisible to the user.
- **Gating** mirrors the reasoning payload (I-RS1): keyed on the PERSISTED
  `serverType`, never live detection. A non-`llama.cpp` server issues zero
  `/props` requests, scoped or bare.
- **Read side.** One pure synchronous selector, `resolveRemoteCaps(model,
  remoteCaps, servers)` (`src/utils/remoteCaps.ts`, shaped after
  `resolveReasoningCapability`), owns resolution for all three consumers:
  `ChatScreen`'s attach affordance, `BannerRow`'s `effectiveNCtx`, and
  `ModelStore.isMultimodalEnabled`'s remote branch. Per-model entry first, then
  the legacy `ServerConfig` fields (context length only when `> 0`), then
  unknown. Attach is enabled **iff** the resolved `supportsVision === true`.
  Being synchronous is load-bearing: consumers call it in the `observer` render
  body, so caps landing from the detached probe re-render the affordance with no
  further user action. Reading them inside an effect or a promise body would
  leave the button stuck at its first value.
- **Token accounting** (chat-flow §token snapshot): a remote turn's used-token
  total is sourced from the server `timings` object already captured on the
  finish chunk — `timings.prompt_n → tokens_evaluated`, `timings.predicted_n →
  tokens_predicted` (server count wins over the per-event tally, each key
  guarded independently). No request-body change; `usage`/`include_usage` is
  not used. Absent timings → prior behaviour (predicted-only per-event count).

### Decisions

| ID | Decision | Rationale |
| --- | --- | --- |
| D14 | ~~Caps as optional fields on `ServerConfig`~~ | **SUPERSEDED by D19** — /props answers per model; a server-scoped slot can only describe the first model probed. |
| D15 | /props gated on persisted `serverType==='llama.cpp'` | Only llama.cpp serves it; never live detection. |
| D16 | ~~/props fetch co-located in `fetchModelsForServer`~~ | **SUPERSEDED by D20** — that trigger set also let a foreground refresh clobber a good per-model result. |
| D17 | /props failure is a silent no-op | Must not break the models fetch or the connection. |
| D18 | Remote used-tokens from `timings.prompt_n/predicted_n` | Already default-emitted + captured; `usage` needs a request-body opt-in. |
| D19 | Caps keyed per `${serverId}/${remoteModelId}` in `ServerStore.remoteCaps` | Mirrors the proven persisted `remoteReasoning` map. |
| D20 | Probe trigger is remote-model activation | Capability is per model; only the active model is read; one trigger, no race. |
| D21 | Probe bound via `resolveTimeout(requestTimeoutMs, PROPS_TIMEOUT_MS)` | Lazy router starts exceed 5 s; a user-set `0` must not abort instantly. |
| D22 | Bare retry only after an unusable scoped probe **and** the single-model gate | Keeps single-model behaviour; makes mis-attribution unrepresentable. |
| D23 | An unknown/empty model list does **not** pass the gate | Unknown is exactly the router case; fail closed instead. |
| D24 | Legacy `ServerConfig` caps: read-fallback, never written | The fallback *is* the migration; zero migration code. |
| D25 | Legacy `contextLength` honoured only when `> 0` | A pre-per-model router persisted `0`; that must not resurface. |
| D26 | `contextLength` written only when `n_ctx > 0` | `0` is unknown, not a window. |
| D27 | `supportsVision` definite only on a model-describing body | A placeholder `false` would be a wrong definite answer. |
| D28 | `modalities` absent on a real model ⇒ definite `supportsVision: false` | Such builds have no vision; definite `false` fails closed. |
| D29 | One pure sync selector `resolveRemoteCaps` owns resolution | An async read point cannot re-render; UI and send path must agree. |
