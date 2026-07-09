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
  contextLength?: number              // (C) llama.cpp /props n_ctx; undefined = unknown/not probed
  supportsVision?: boolean            // (C) llama.cpp /props modalities.vision; undefined = unknown/not probed

ServerStore                           // src/store/ServerStore.ts
  remoteReasoning: Record<modelId, ReasoningCapability>  // (C) remote reasoning caps,
                                      //   keyed by `${serverId}/${remoteModelId}`; persisted
```

`serverType` is one of `{llama.cpp, LM Studio, Ollama, OpenAI, vLLM, unknown}`,
chosen via a compact dropdown on both the add-remote and server-details sheets.
`detectServerType` (+ an `api.openai.com → OpenAI` host heuristic) only **seeds**
it on the server sheet; the user's selection wins, and the persisted value (never
live detection) gates the payload. Both `serverType` and `remoteReasoning` ride
the existing `ServerStore` persisted properties — no migration. The reasoning
capability model itself lives in `chat-flow.md` §9g (resolver, two axes,
learn-from-stream, single-writer); this doc covers only the remote wire side.

`contextLength` and `supportsVision` are server-reported capabilities
discovered from a llama.cpp `GET /props` response (§8). They are optional and
ride the same already-persisted `servers` list — no new persisted key, no
migration; an absent field hydrates as undefined (unknown → pre-discovery
behaviour). `ServerStore` is their sole writer (I2).

Persisted: `requestTimeoutMs` is part of the already-persisted `ServerConfig`
inside `ServerStore.servers` (mobx-persist-store → AsyncStorage, key
`ServerStore`). (C) `servers` is already in the persisted `properties` list —
no new persisted key, no migration. Derived: none.

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
  The API layer never sets a deadline of 0 or negative.
- **I2**: `ServerStore` (`addServer` / `updateServer`, incl. the `/props`
  writer in `fetchModelsForServer`) is the only writer of `requestTimeoutMs`,
  `contextLength`, and `supportsVision`. `openai.ts`, `ModelStore`,
  `OpenAICompletionEngine`, `BannerRow`, and both sheets only read/forward
  them.
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

Cross-store reads: `ModelStore.setRemoteModel` reads
`serverStore.servers[].requestTimeoutMs` to build the engine (one direction,
ModelStore ← ServerStore — the same place it already reads `url`/apiKey).

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

```
serverType === 'llama.cpp' (add / hydration / throttled foreground refresh)
  ServerStore.fetchModelsForServer(serverId)
    (after the /v1/models write)
    fetchServerProps(url, apiKey, requestTimeoutMs)   // pure; openai.ts
      GET {baseUrl}/props
        [ok]   → { contextLength?, supportsVision? }
                 → ServerStore.updateServer(serverId, caps)   // re-found by id
        [fail] → {}  → no-op; caps unchanged; models + connection intact
  serverType !== 'llama.cpp' → /props never requested
```

- **Wire → ours** (key names verified against a live llama.cpp build, b9910):
  - `contextLength ← default_generation_settings.n_ctx ?? n_ctx` (top-level
    `n_ctx` is an older-build fallback; b9910 nests it under
    `default_generation_settings`).
  - `supportsVision ← modalities.vision === true`. Absent/unmapped → undefined
    → vision off.
- **`fetchServerProps` never throws.** Timeout / non-2xx / malformed JSON all
  resolve to `{}`; the caps stay whatever they were and the models fetch and
  connection are untouched (I3-adjacent — a `/props` failure is invisible).
- **Gating** mirrors the reasoning payload (I-RS1): keyed on the PERSISTED
  `serverType`, never live detection. The fetch is co-located in
  `fetchModelsForServer`, reusing the add / hydration / throttled-foreground
  triggers — no new scheduler.
- **Token accounting** (chat-flow §token snapshot): a remote turn's used-token
  total is sourced from the server `timings` object already captured on the
  finish chunk — `timings.prompt_n → tokens_evaluated`, `timings.predicted_n →
  tokens_predicted` (server count wins over the per-event tally, each key
  guarded independently). No request-body change; `usage`/`include_usage` is
  not used. Absent timings → prior behaviour (predicted-only per-event count).

### Decisions

| ID | Decision | Rationale |
| --- | --- | --- |
| D14 | Caps as optional fields on `ServerConfig` | /props is server-scoped; reuses the persisted single-writer. |
| D15 | /props gated on persisted `serverType==='llama.cpp'` | Only llama.cpp serves it; never live detection. |
| D16 | /props fetch co-located in `fetchModelsForServer` | Reuses add/hydration/foreground triggers; no new scheduler. |
| D17 | /props failure is a silent no-op | Must not break the models fetch or the connection. |
| D18 | Remote used-tokens from `timings.prompt_n/predicted_n` | Already default-emitted + captured; `usage` needs a request-body opt-in. |
