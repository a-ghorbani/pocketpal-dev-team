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

ServerStore                           // src/store/ServerStore.ts
  remoteReasoning: Record<modelId, ReasoningCapability>  // (C) remote reasoning caps,
                                      //   keyed by `${serverId}/${remoteModelId}`; persisted
  remoteCaps: Record<modelId, RemoteModelCaps>           // (C) /props caps, same key
                                      //   shape (`${serverId}/${remoteModelId}` = Model.id); persisted

RemoteModelCaps                       // src/utils/types.ts
  contextLength?: number              // (C) /props n_ctx; ONLY ever a finite number > 0
  supportsVision?: boolean            // (C) /props modalities.vision; definite (true/false) only on a
                                      //   model-describing response; undefined = unknown
  probedUrl?: string                  // (C) the backend these describe; absent = written before the
                                      //   field existed, taken at face value

ModelStore                            // src/store/ModelStore.ts
  activeRemoteBinding?: RemoteSessionBinding             // (C) the backend the live remote session
                                      //   talks to; set with the engine, cleared with it; NOT persisted

RemoteSessionBinding                  // src/utils/types.ts
  modelId: string                     // (C) `${serverId}/${remoteModelId}` = Model.id
  serverId / remoteModelId: string    // (C)
  url: string                         // (C) the url the engine was built from
  serverType?: string                 // (C) idem
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
was probed first". The pre-per-model `ServerConfig.contextLength` /
`supportsVision` fields are **gone** (D24/D25 superseded): they had no writer
after the move, and the writer that filled them shipped after the last release,
so no persisted store can carry them. Nothing reads a per-server capability any
more.

**A configured server and a live session are different things.** `ServerConfig`
is mutable; the completion engine captures `url` / `serverType` when it is built
and is not rebuilt when the record changes, so after an in-session url edit the
session still posts to the old backend until the model is selected again.
`ModelStore.activeRemoteBinding` is that captured backend as readable state, and
`RemoteModelCaps.probedUrl` is the backend an entry describes. Resolution
compares the two (§8 Read side); without them the comparison can only be
approximated from the mutable record, which is where the caps of one backend
could be attributed to a session on another.

Persisted: `requestTimeoutMs` rides the already-persisted `ServerConfig` inside
`ServerStore.servers`; `remoteCaps` is its own entry in the `ServerStore`
`makePersistable` `properties` list (mobx-persist-store → AsyncStorage, key
`ServerStore`). No migration — an absent field hydrates as undefined (unknown),
including `probedUrl`. The binding is deliberately **not** persisted: a session
does not survive a launch. Derived: the resolved caps of the active model (§8),
computed at read time by `resolveRemoteCaps`, never stored.

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

### 1c. Three tiers of `/props` answer

One `GET /props` response carries facts with three different lifetimes, and they
are stored separately because a fact that can change while the url stays the
same must not be persisted alongside one that cannot.

```
RemoteModelCaps                       // src/utils/types.ts — PERSISTED, GATING
  tier?: 'probe'                      // (C) discriminant, never written or read
  contextLength?: number              // (C)
  supportsVision?: boolean            // (C)
  supportsAudio?: boolean             // (C) modalities.audio; vision's definite-only rule
  probedUrl?: string                  // (C)

RemoteModelProps                      // src/utils/types.ts — PERSISTED, NON-GATING
  tier?: 'props'                      // (C) discriminant, mirrors RemoteModelCaps'
  samplerDefaults?: SamplerDefaults    // (C) the server's own generation defaults
  slotCount?: number                  // (C) total_slots; finite integer > 0 only
  chatTemplateCaps?: {                // (C) narrow projection, not the whole wire struct
    supportsTools?: boolean           //     description tier; gates nothing (I8)
    supportsThinking?: boolean }
  probedUrl?: string                  // (C) same provenance semantics as RemoteModelCaps (D31)
// No server-supplied free text is written here: every field is a number, a
// boolean, or the url the user typed. `build_info` and `model_alias` were read
// once and removed — nothing consumed them, and an unbounded string in a
// persisted map is an amplification budget the server chooses, since the map is
// keyed per model and the model list is also the server's. Re-add either only
// together with the code that displays it, bounded, and answer the aggregate
// question at that point.
//
// The merge carries forward only the fields named above, by name. A hydrated
// entry written by an older build can therefore still hold a removed field
// until its next probe, which drops it — so the invariant is about what is
// written, and becomes true of a stored entry one probe later. Spreading the
// hydrated object instead would make removing a field from this schema
// impossible: it would be copied forward for the life of the entry.

RemoteModelPresence                   // src/utils/types.ts — NOT PERSISTED
  tier?: 'presence'                   // (C) discriminant; without it this record
                                      //     is structurally assignable into
                                      //     either persisted tier, since every
                                      //     field of both is optional
  isSleeping: boolean                 // (C) definite only; absent entry = unknown
  probedUrl: string                   // (C) the backend observed
  at: number                          // (C) observation timestamp (ms)

SamplerDefaults = Partial<Record<SamplerParam, number>>  // (C) keyed by INTERNAL
                                      //   param names, never wire names

ServerStore
  remoteProps: Record<modelId, RemoteModelProps>        // (C) persisted; same key shape
  remotePresence: Record<modelId, RemoteModelPresence>  // (C) NOT persisted
```

All three maps are keyed `${serverId}/${remoteModelId}` (= `Model.id`, D19),
written from one response in one `runInAction` by one writer (§3), sharing one
`probedUrl` snapshot — so they cannot disagree about the backend they describe.

**Tier routing rule.** The axis is *how long the fact stays true*. A new `/props`
field goes to **caps** if a send-path or affordance gate reads it (fail-closed
required), to **props** if it is descriptive and stable for a server process's
life, to **presence** if it can change while the url stays the same. Only the
caps tier may gate anything (I8).

Persisted: `remoteProps` joins `remoteCaps` in `ServerStore.makePersistable`. No
migration — an absent entry hydrates as undefined (unknown). `remotePresence` is
deliberately not persisted (D36).

### 1d. Router mode

A `llama-server` started with `--models-dir` / `--models-preset` serves many
models from one port, loading and unloading them on demand under `--models-max`.
It exposes `POST /models/load`, `POST /models/unload`, `POST /models` (fetch a
model to the server) and `GET /models/sse`. Everything below is **live-only**,
rebuilt each launch: a router's state belongs to a desktop this app may not
reach next launch, and a persisted copy of it is only a stale claim.

```
RouterStatus    = 'unloaded'|'loading'|'loaded'|'sleeping'|'downloading'  // (C) wire values
RouterRowState  = RouterStatus | 'absent' | 'failed' | 'unknown'          // (C) what consumers branch on
                  //   absent: no row. failed: the row says so. unknown: row present, state unreadable.
RouterStreamCap = 'unknown' | 'present' | 'absent'   // (C) what THIS BUILD has (D-RT48)

RouterLive                            // src/utils/routerState.ts — NOT PERSISTED
                  //   detail only: no state, so no surface can read one (D-RT67)
  progress?: {stages?, current?, value?}  // (C) load only; `value` is a fraction
  bytes?: {done, total, urls}         // (C) download only, summed across URLs
  exitCode?: number                   // (C) attaches a reason, never a verdict
  at: number                          // (C) when it was written; what the prune measures

RouterOp                              // src/utils/routerState.ts — NOT PERSISTED
  kind: 'load'|'unload'|'download'    // (C) each kind has exactly one verdict rule
  attempt: number                     // (C) store-wide; a late answer places itself by it (I-RT25)
  phase: 'requested'|'active'         // (C) 'active' only on server corroboration (D-RT27)
  serverId / key: string              // (C) key is `${serverId}/${remoteModelId}`; rekeyable (D-RT33)
  startedAt / lastEvidenceAt: number  // (C) lastEvidenceAt arms W2
  requestSeq: number                  // (C) which models fetch preceded this request (D-RT53)
  attemptEndedAt? / armedAt?: number  // (C) a terminal download event; the last watchdog arm
  verdictRequested?: boolean          // (C) a watchdog has asked; the next reconcile may settle
  cancelled?: boolean                 // (C) the user stopped it, so its ending is not a failure
  reason?: string                     // (C) the server's own words, passed through only

RouterFailure                         // src/utils/routerState.ts — NOT PERSISTED
  cause: 'load-failed'|'unload-not-released'|'download-not-fetched'  // (C) carries the copy
       | 'server-unreachable'|'wait-stopped'  // (C) about our request, never the model
  message?: string                    // (C) the server's words where it gave any

ServerStore                           // src/store/ServerStore.ts — NONE OF IT PERSISTED
  routerEvents: Record<modelId, RouterLive>      // (C) the live overlay
  routerOps: Record<modelId, RouterOp>           // (C) settled ops are deleted, never marked
  routerReasons: Record<modelId, RouterFailure>  // (C) until the user dismisses it (D-RT54)
  routerStream: {serverId, state:'connecting'|'open'|'reopening'} | null  // (C) the one stream, a scheduled reopen included (D-RT7, D-RT63)
  routerPolls: Set<serverId>                     // (C) the poll tier (D-RT31)
  routerStreamCap: Record<serverId, RouterStreamCap>  // (C) session-scoped (D-RT48)
  routerObservedEviction: Set<serverId>           // (C) an unrequested unload was seen (D-RT32)
  routerListShape: Record<serverId, {hasModelsKey, seq, stale}>  // (C) see below
```

`routerListShape` is what a `GET /v1/models` fetch found about the **response**
rather than about any row, plus which fetch it was. It carries no clock reading:
the one it used to hold was read only by the ranking rule D-RT67 deleted, and a
timestamp left beside `seq` invites that rule back. `hasModelsKey` is the
router/direct discriminator (§9); `seq` is a counter, not a clock reading, so
"the list was re-read after that request" is exact however coarse the clock is
(D-RT53). The entry is written in the **success branch only**, because that fetch
leaves the previous rows in place on failure: without the stamp a reconcile that
never happened is indistinguishable from one that found the old row, and every
bound in §9 turns on that difference. The failure branch writes one thing into an
entry already there — `stale`, meaning the last read failed and none has
succeeded since, which is what stops the rows it could not refresh being read as
a current claim (D-RT67).

**Both branches ignore a read another has already overtaken** (D-RT72).
Concurrent reads of one server are ordinary — the tiers hold separate in-flight
guards, and the foreground path fires two in the same tick — and `seq` exists to
make their order decidable, so a branch that does not consult it is deciding by
arrival time. A slow *failure* landing after a fast success marked the
just-installed list stale: every row `unknown`, the resident count zero, and Load
offered for models the server was holding, until the next success. The mirror is
a slow *success* installing an older list over a newer one.

`routerServers` and `routerRowState` are **computeds with no writer**, exactly
like `listCaps`.

The **Absent is not zero** rule of §8a governs the router's numeric wire fields
too, and is not restated here: `progress.value` is `0.0` on the first tick of a
real load and `download_progress`'s `done` is `0` on the first event of a real
download, so both are admitted on `typeof === 'number'` and never on truthiness.
A falsy guard renders no bar at all for work that has just started.

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
  downwards: every **detached, non-user-initiated** probe clamps to
  `PROPS_TIMEOUT_MS` before calling — the `/props` capability probe (§8 Bound)
  and the detached presence probes (§10b) — no other path caps a user-visible
  request. A user-initiated request, completions and explicit retries included,
  still forwards the raw `requestTimeoutMs`.
- **I2**: `ServerStore` (`addServer` / `updateServer`) is the only writer of
  `requestTimeoutMs`, and `ServerStore.fetchRemoteModelCaps` is the sole writer
  of `remoteCaps` (§3). No per-server capability field exists any more.
  `openai.ts`, `ModelStore`, `OpenAICompletionEngine`, `BannerRow`, and both
  sheets only read/forward.
- **I3**: A persisted `ServerConfig` from a prior app version (no
  `requestTimeoutMs`) behaves identically to before (defaults apply). No
  migration, no crash.
- **I4**: The configured timeout bounds individual phases (connect,
  idle-between-chunks), NOT the total wall-clock of a long successful stream. A
  healthy stream emitting tokens within the timeout interval runs indefinitely
  (the idle timer resets on each chunk).
- **I5**: Capabilities are never read on behalf of a backend they were not
  probed against. An entry whose `probedUrl` disagrees with
  `activeRemoteBinding.url` for that model resolves to unknown, which fails
  closed: attach off, no window for the banners. The binding is defined exactly
  while a remote engine exists, so "no binding" and "no live session" are the
  same state, and an entry is then taken at face value.

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

### 2d. Sampler forwarding

Two name tables, deliberately not one, because the read side and the write side
answer different questions.

**`PARAM_WIRE_NAME`** (`src/api/openai.ts`) — the **read** side, over **every**
numeric completion control. It is the anti-drift guarantee: the name a server
default is read from is the name a value is sent under.

| internal | llama.cpp wire name |
| --- | --- |
| `temperature` `top_p` `top_k` `min_p` `typical_p` `xtc_threshold` `xtc_probability` `mirostat` `mirostat_tau` `mirostat_eta` `seed` `n_predict` | identity |
| `penalty_last_n` / `penalty_repeat` / `penalty_freq` / `penalty_present` | `repeat_last_n` / `repeat_penalty` / `frequency_penalty` / `presence_penalty` |

One exception to read-name = send-name: `n_predict` is read from
`default_generation_settings.params.n_predict` (where llama.cpp reports it) but
is *sent* as `max_completion_tokens`. It is in no allow-list today; the note
exists so whoever adds it inherits the right send name.

**`FORWARD_ALLOWLIST`** — the **write** side, per `serverType`. `llama.cpp` lists
**thirteen** (the sixteen above minus `temperature`, `top_p` and `n_predict`);
`vLLM` ships **empty** (D38); every other type, `unknown` included, has no row
(I-RS2, I7). `n_probs` is in neither (D39).

`buildSamplerPayload(serverType, params)` is pure: it walks
`FORWARD_ALLOWLIST[serverType]`, resolves each name through `PARAM_WIRE_NAME`,
and emits one entry per param whose value is a **finite number** —
`undefined`/`NaN`/non-finite are omitted, never coerced, and `0` is a value like
any other. Its output merges into `requestBody` immediately **before** the
`buildReasoningPayload` merge, so a reasoning key can never be overwritten.
Gating is on the persisted `serverType` the engine was built with (I-RS1) —
never live detection, never a probe result.

`OpenAICompletionEngine` maps the thirteen straight from `ApiCompletionParams`
onto `StreamChatParams` with no filtering, defaulting or renaming: the engine
forwards intent, `openai.ts` owns the wire shape (D12).

**Outside the write gate**: `temperature`, `top_p`, `max_completion_tokens`
(from `n_predict`), `stop`, `stream`, `tools`, `tool_choice` and
`response_format` are OpenAI-standard and stay unconditional for every server
type — gating them would silently stop sending them to OpenAI / Ollama / unknown
(I9). They sit on the **read** side, so they carry a server-default indicator
like every other control.

**The hazard is asymmetric — it lives on the write side.** Every `/props` read
has a resource to reconcile: the body is the answer, so a wrong assumption shows
up as an absent field and lands on unknown. A forwarded parameter has no
resource in the response at all. llama-server accepts unknown body keys and
returns `200`, so a wrong or misspelled wire name ships completely green and
does nothing; the control moves, the turn succeeds, and a silently-ignored
parameter is indistinguishable from an honoured one.

Nothing at runtime can close that gap, and this doc does not pretend otherwise:
reading `/slots` per turn would be a second request per completion for a fact
that cannot change between turns. The verdict is read **at build time, once** —
`GET /slots?model=<id>` after a completion sent with distinctive values, on the
slot with the highest `id_task`, comparing against the server defaults. The
standing rule: **a new forwarded field is not done until its value has been
observed in `/slots`**; a field that cannot be observed there is dropped rather
than shipped as a documented no-op (D44 is this rule applied).

### 2e. Server defaults as a reference tier

`default_generation_settings` gives a *reference* for the settings UI. It is
never a layer in settings resolution (D40): `session.completionSettings` is
baked at birth and persisted, so a server's values written into a session that
may later run locally would outlive the server that suggested them.

`CompletionSettings` takes one optional `serverDefaults?: SamplerDefaults` prop
and stays presentational — no store import, no MobX read, no wire names. Per
rendered control `p`:

| `serverDefaults[p]` | render |
| --- | --- |
| absent | nothing extra |
| present and equal to the editor value | a "server default" indicator |
| present and different | a reset affordance **carrying the value** ("Server default: 0.8 · Reset"), calling the existing `onChange(p, serverDefaults[p])` |

The reset affordance shows the number because acceptance is "shown *and*
resettable": a bare Reset button displays nothing in the one state where the
user wants to see what they would be going back to.

Equality is **per control kind**, since float equality and enum equality are
different questions (D41): sliders use `|value − default| < step / 2`, so a
quantised float does not read as a deliberate edit; discrete controls
(`mirostat`, `seed`) compare exactly. `step` lives in
`COMPLETION_PARAMS_METADATA` (`src/utils/modelSettings.ts`) rather than at the
call site, making that record the single source of min/max/step/default;
`renderSlider` reads `metadata.step ?? 0.01` and derives
`precision = Number.isInteger(step) ? 0 : 2` from the same value.

Both hosts — `ChatGenerationSettingsSheet` and `PalGenerationSettingsSheet` —
read `modelStore.activeSamplerDefaults` and pass it down; neither reads
`serverStore`, and both are wrapped in `observer` so a default landing from the
detached probe re-renders an open sheet. `ModelSettingsSheet` is **not** a
sampler surface: it renders `screens/ModelsScreen/ModelSettings` (context/load
params), not `CompletionSettings`.

`settings.md` carries no delta for this: it owns the Settings tab root and its
pushed sub-screens, and neither sampler sheet is a Settings route.

### 2f. Hard invariants (sampler forwarding and the three tiers)

- **I6**: the sampler payload is a pure function of `(serverType, params)` —
  never store state, a probe result, or `RemoteModelProps`. The same settings
  and persisted `serverType` produce the same body every run, whether or not a
  probe landed (extends I-RS1).
- **I7**: a `serverType` with no `FORWARD_ALLOWLIST` row — `unknown`,
  `LM Studio`, `Ollama`, `OpenAI`, vLLM today — receives **no** new field
  (I-RS2).
- **I8**: only the **capability** tier may gate an action or affordance.
  `RemoteModelProps` / `RemoteModelPresence` are descriptive: no send-path
  decision, attach gate, banner or context number reads them. The `tier`
  discriminants make the records mutually non-assignable, so a descriptive value
  cannot be passed where a probed capability is expected.
- **I9**: the eight fields forwarded before this delta (`temperature`, `top_p`,
  `max_completion_tokens`, `stop`, `stream`, `tools`, `tool_choice`,
  `response_format`) stay unconditional for every server type;
  `FORWARD_ALLOWLIST` governs only the fields the delta added.
- **I10**: a probe that resolves nothing new writes nothing, in every tier. A
  `{}`, a timeout, a non-2xx and a malformed body are indistinguishable and all
  leave every prior value untouched (extends D17/D31). **Only a definite,
  capability-shaped answer may enter a capability cache; everything else leaves
  it unknown** — a failure is never evidence of absence. Two realistic paths
  this covers: a **401** on a keyed server the user has not yet supplied a key
  for is a statement about credentials, not about the build, and returns unknown
  at the `!response.ok` guard before any parse; a **non-JSON error body** (a
  sleeping router child answering `500` with plain text) hits the same guard,
  and a malformed body on a `200` throws into the same unknown result.
- **I11**: `ServerStore.fetchRemoteModelCaps` is the **only** writer of all
  three maps (with the `removeServer` / `updateServer` prefix prunes, §3), and
  concurrent calls for one key collapse into one request. No caller writes, none
  reaches a map directly.
- **I12**: nothing derived from `/props` is ever written into
  `ServerStore.remoteReasoning` — it carries user declarations and has its own
  single writer (chat-flow §9g). This is why `chatTemplateCaps.supportsThinking`
  can be captured safely: it is recorded, never wired in.
- **I13**: `ServerConfig.url` is **canonical at rest**, and every identity
  comparison compares the persisted value verbatim. No site normalises a url —
  see 2g.

### 2g. Canonical `ServerConfig.url`

Url identity is load-bearing in three places — `capsMatchBinding`
(`probedUrl === binding.url`), `lastObservedSleepState` (`probedUrl === server.url`), and
`updateServer`'s prune on a url change. All three are safe today because each
reads the same `ServerConfig.url` string: `fetchRemoteModelCaps` records
`probedUrl = server.url` raw, so the comparisons are self-consistent in whatever
form that string takes. This clause exists so they stay safe when a **new url
provenance** arrives.

**Canonical form** — `scheme://host[:port][/base-path]`, with **no trailing
slash** and **no `/v1` suffix** (the API layer appends `/v1/...` itself). This is
not a new convention: §1's own documented example
(`http://192.168.1.100:1234`) is already this shape.

| Rule | |
| --- | --- |
| normalised | **once**, at the `ServerConfig.url` write boundary (`addServer` / `updateServer` — §3's single writer) |
| everywhere else | **nothing normalises.** `probedUrl` keeps recording `server.url` verbatim; the three comparisons stay plain string equality |
| scope | **writes only** — hydrated records are not rewritten, so no migration and no behaviour change for an existing server |

The canonicaliser itself lands in the lane that introduces the new provenance (a
paired-server url derived from a QR payload, which carries a trailing slash);
the rule is recorded here because this doc owns `probedUrl` and the equality.
**Realised** as `canonicalizeServerUrl` in `src/utils/serverUrl.ts`, called from
`addServer` and `updateServer` and from nowhere else. In `updateServer` it runs
on `updates.url` **before** `invalidatesDiscovery` is computed; run after the
assign, a no-op trailing-slash edit compares raw against canonical, reads as a
repoint, and silently drops `remoteCaps`, `serverModels` and the presence entry.
A url the canonical grammar cannot express — one carrying userinfo, or one that
does not parse — is returned unchanged rather than rewritten.
Two measured facts behind the shape: a trailing slash breaks nothing today —
`openai.ts`'s private `normalizeUrl` strips it at all four request-construction
sites, so it is request-time hygiene, not identity — but a `/v1` suffix **is**
fatal and is not stripped (`…:8080/v1/props` → `404`), which a hand-copied
"Base URL" from a desktop app reaches today with no pairing involved.

---

## 3. Single-writer rule

| Field | Single writer |
| --- | --- |
| `ServerConfig.requestTimeoutMs` | `ServerStore.updateServer` / `ServerStore.addServer` |
| `ServerStore.remoteCaps` | `ServerStore.fetchRemoteModelCaps` (+ the `removeServer` / `updateServer` prefix prunes) |
| `ServerStore.serverModels` | **two, not one**: `ServerStore.fetchModelsForServer` and `RemoteModelSheet.handleServerChipPress`, which writes it directly (+ the same two prunes). Both store the identical `fetchModels()` output for the same server id, so anything derived from the list is source-identical either way. The sheet's own probe, `probeServer`, writes nothing — its rows stay local to the sheet. |
| `ServerStore.listCaps` | **none — a computed** over `serverModels` and `servers[].serverType`. No setter exists and it is not persisted (§8, list tier). |
| `ModelStore.activeRemoteBinding` | `ModelStore.setRemoteModel` (set) / the engine-clearing paths in `initContext` and `releaseContext` (clear) |
| `ServerStore.remoteProps` | `ServerStore.fetchRemoteModelCaps` (+ the same two prunes) |
| `ServerStore.remotePresence` | `ServerStore.fetchRemoteModelCaps` (+ the same two prunes) |
| `RemoteModelCaps.supportsAudio` | `ServerStore.fetchRemoteModelCaps` (unchanged owner) |
| the remote request body's sampler fields | `src/api/openai.ts` `buildSamplerPayload` (single wire-shape owner, D12) |
| the editor value behind a "reset to server default" | unchanged — the host sheet's existing `setSettings` via `CompletionSettings.onChange` |
| `ServerStore.routerEvents` | `ServerStore.applyRouterEvent` (+ the same two prunes, + the stale-entry prune at fetch) |
| `ServerStore.routerOps` | `ServerStore.setRouterOp` — called by the load / unload / download actions, the settle path and the watchdogs |
| `ServerStore.routerReasons` | the settle path (write) / `ServerStore.dismissRouterReason` (clear) |
| `ServerStore.routerStream` | `ServerStore.setRouterStream`, from `openRouterStream` / `closeRouterStream` |
| `ServerStore.routerPolls` | `ServerStore.setRouterPoll`, driven by `syncRouterTiers` |
| `ServerStore.routerStreamCap` | `ServerStore.setRouterStreamCap` — only the stream-open path, only from that request's own status, and only a 404 writes `'absent'` |
| `ServerStore.routerObservedEviction` | `ServerStore.applyRouterEvent` |
| `ServerStore.routerListShape` | `ServerStore.fetchModelsForServer` — the success branch writes the entry, the failure branch only marks the existing one stale |
| `ServerStore.routerServers`, `ServerStore.routerRowState` | **none — computeds** over `servers` + `serverModels` + `routerListShape` |

Cross-store reads: `ModelStore.setRemoteModel` reads
`serverStore.servers[].requestTimeoutMs` to build the engine (one direction,
ModelStore ← ServerStore — the same place it already reads `url`/apiKey). It
also *calls* `serverStore.fetchRemoteModelCaps` on activation and on foreground
without valid caps for the binding (§8) — a call in the same direction, never a write:
`ModelStore` never writes `remoteCaps`.
`ModelStore` reads one more `ServerStore` map (`remoteProps`, beside
`remoteCaps` / `listCaps` already in `capabilityEnv`) to expose
`activeSamplerDefaults` — same direction, still no write. `lastObservedSleepState` stays
on `ServerStore`: it is server-scoped, and `ModelStore` has no part in it.

`ModelStore` is, however, its only reader: it assembles them, with
`activeRemoteBinding` and the local-session fields, into the env that
`resolveModelCaps` (`src/utils/modelCaps.ts`) resolves against, and exposes the
answer as `activeModelCaps` / `capsFor(model)`. No component builds that env or
reaches `remoteCaps` itself, so the UI and the send path cannot disagree — with
each other or with the backend they are describing.

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
| Server url edited while a remote model is active | The session keeps posting to the old backend (the engine is not rebuilt), so its capabilities stay bound to that url: pruned entries are not re-probed while the two disagree, and a probe that did land from the new url does not resolve for this session (I5). Re-selecting the model rebuilds the binding and re-probes (§8). |
| Server url or type edited, or the server removed, while a router operation is in flight | The router maps are pruned alongside `remoteCaps` and `serverModels`. The operation is abandoned rather than reported failed: its waiter is released so nothing hangs, and no reason is recorded, because there is no outcome to report about a backend that is no longer configured (§9). |
| iOS Local Network permission, for the long-lived router stream | Same grant, new request shape: `GET /models/sse` is held open for minutes rather than a short request/response. A missing grant fails it as if the server were dead, and the operation settles as a **request** failure — never a claim that the model failed to load (§9). |

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
| llama.cpp | `chat_template_kwargs:{enable_thinking:false}` + `reasoning_format:'auto'` | `reasoning_format:'auto'` | `reasoning_format:'auto'` + `chat_template_kwargs:{reasoning_effort:<lvl>}` + `reasoning_budget_tokens:<budget(lvl)>` | ignores unknown → safe |
| vLLM (modern) | `chat_template_kwargs:{enable_thinking:false}` | (omit) | `chat_template_kwargs:{reasoning_effort:<lvl>}` | ignores unknown → safe |
| LM Studio | `chat_template_kwargs:{enable_thinking:false}` | (omit) | (none; its chat API ignores `reasoning_effort`) | ignores unknown → safe |
| Ollama (/v1) | `reasoning_effort:'none'` (safe no-op) | (omit; never `think:true`) | (omit — deferred) | hard-400 on `think:true` / non-`none` effort to a non-thinking model |
| OpenAI | (omit) | (omit) | `reasoning_effort:<value>` only when axis-2 known for the model id | 400 on any misapplied param |
| unknown / old vLLM | (omit everything) | (omit) | (omit) | 400 on extras → send nothing |

`reasoning_budget_tokens` is the wire name `master`'s `server-schema.cpp`
defines (bounded `-1 .. INT32_MAX`, `-1` disabling); llama.rn's
`thinking_budget_tokens` is a separate local name for the on-device path. It is
**inert on b9976** and honoured on newer builds, and an ignored numeric field
cannot break a request, so it is safe on both. `budget(lvl)` is monotone over
the canonical `EFFORT_LEVELS` (`src/utils/reasoningCapability.ts`): `minimal
256 · low 512 · medium 2048 · high 8192 · xhigh 16384 · max -1`.

**A top-level `reasoning_effort` is NOT sent to llama.cpp** (D44). It is absent
from `master`'s `server-schema.cpp` and measured to be silently ignored: the
request returns `200` and `reasoning_content` is still emitted, with or without
`reasoning_format:'auto'`. `chat_template_kwargs:{enable_thinking:false}` is
what actually switches thinking off (measured: `reasoning_content` null,
content present), which is I-RS4 restated from evidence rather than inference.
llama.cpp's real failure mode is a silent no-op, not a `400`; I-RS2's "omit
beats a 400" governs every other server type unchanged.

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
(model-loading — the remote leg of `activeModelCaps.vision`).

Capabilities are **per model**, not per server: a multi-model router (llama-swap
style, lazily starting a server per model) answers bare `/props` with a
placeholder describing nothing (`role: 'router'`, `model_path: 'none'`, `n_ctx:
0`, `modalities` **absent** — not null), while `?model=<id>` returns that
model's real properties. A single-model `llama-server` answers the bare form
with its loaded model.

```
user selects a remote model (ModelStore.selectModel → setRemoteModel; binding set)
  OR app returns to foreground with no caps valid for the active model's binding
  serverType === 'llama.cpp'  ───────────────────────────────── else: no request
    ServerStore.fetchRemoteModelCaps(serverId, remoteModelId, apiKey?)  // DETACHED
      (apiKey forwarded on the activation path; undefined for a keyless server,
       which the probe cannot tell from "not supplied", so it reads the Keychain)
      fetchServerProps(url, apiKey, min(requestTimeoutMs, PROPS_TIMEOUT_MS), remoteModelId)
        GET {baseUrl}/props?model=<encodeURIComponent(remoteModelId)>
          [caps resolved] → remoteCaps[`${serverId}/${remoteModelId}`] = merge + probedUrl
          [{}] and single-model gate passes → GET {baseUrl}/props (bare, ONE retry)
            [caps resolved] → merged as above
            [{}]            → no-op; prior entry (if any) untouched
          [{}] and gate fails → no bare request at all; no write
```

- **Trigger is model activation**, not the models fetch. `fetchModelsForServer`
  issues no `/props` request. Capability is a property of a model, and only the
  active model is ever read.
- **Second trigger: foreground with no valid caps.** `ModelStore`'s existing
  foreground `AppState` branch calls `fetchRemoteModelCaps` for the active
  remote model **iff** `remoteCaps` holds no entry valid for its binding —
  absent, or present with a `probedUrl` describing another backend (detached,
  `.catch`-guarded, and `ModelStore` still never writes caps). It is skipped
  outright once the server record has been repointed away from the binding:
  the probe would read a backend this session never talks to, and could not
  produce caps this session could use. Without it, activation is
  the sole trigger and remote models are exempt from auto-release
  (model-loading), so one torn-down probe leaves caps unknown for the whole
  session with no recovery but manually re-selecting the model — the likeliest
  case being iOS Local Network (§ permissions), where the first probe is the
  request that raises the prompt and nothing re-probes after the grant. The
  gate is what keeps this from becoming a racing second writer: an entry that
  is valid for the binding is never re-fetched, so a good result can never be
  clobbered back to the placeholder (the failure mode the pre-per-model shape had, where a
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
  already been pruned. That check covers an edit *during* flight only; an edit
  that happened *before* the probe started is caught on the read side instead,
  by the `probedUrl` the write records. A merge that changes no field **and no
  `probedUrl`** is not written at all, matching the `remoteReasoning` writer.
- **Write is a field-wise merge within one backend.** `remoteCaps[key] =
  {...prior, ...caps, probedUrl}`. A field the response did not resolve is
  absent from `caps`, so it leaves the prior value untouched; a `{}` result
  writes nothing. A failing or unusable probe therefore never clears, zeroes,
  or downgrades a known capability. Across backends there is nothing to merge:
  when `prior.probedUrl` differs from the url just probed, the prior entry is
  replaced rather than blended, or one entry would describe two backends while
  claiming to be one of them. A probe that resolves nothing is not retried
  in-session; the next probe is the next activation of that model, or the next
  foreground while the entry is still absent or invalid for the binding.
- **Invalidation.** Entries are pruned by `${serverId}/` prefix (shared
  `dropServerEntries` helper) on two events: `removeServer`, and an
  `updateServer` that changes `url` or `serverType`. The same `updateServer`
  branch drops `serverModels` for that server: the list describes what the old
  backend offered, `ServerDetailsSheet.handleSave` never refetches, and
  `fetchAllRemoteModels` only runs on hydration or a throttled foreground — so
  a stale single-entry list would otherwise clear the bare-retry gate against a
  new multi-model router, indefinitely, and re-attribute the resident model's
  props. `remoteReasoning` is pruned only by `removeServer`: it carries user
  declarations and is not server-reported.

  The prune is defence in depth, not the correctness argument. Editing the url
  under an active model does not move that session — the engine is not rebuilt
  by `updateServer` — and the binding is what keeps the two apart: caps probed
  against the new url carry it in `probedUrl` and do not resolve for a session
  still bound to the old one (I5). The foreground re-probe additionally
  declines to fire at all in that state (§8 second trigger), so the prune's
  practical effect is that caps stay unknown until the model is re-selected.
- **`fetchServerProps` never throws.** Timeout / non-2xx / malformed JSON all
  resolve to `{}`; a `/props` failure is invisible to the user.
- **Gating** mirrors the reasoning payload (I-RS1): keyed on the PERSISTED
  `serverType`, never live detection. A non-`llama.cpp` server issues zero
  `/props` requests, scoped or bare.
- **Read side.** One pure synchronous selector, `resolveRemoteCaps(model,
  remoteCaps, binding)` (`src/utils/remoteCaps.ts`, the shape of
  `resolveReasoningCapability` plus the binding), owns remote resolution. It has
  a single caller — the remote leg of `resolveModelCaps` — and every consumer
  reaches it through `modelStore.activeModelCaps` / `capsFor(model)`
  (model-loading §Vision). The per-model entry is
  used only when `capsMatchBinding` passes — same modelId and a `probedUrl`
  that agrees with the binding, or no binding / no `probedUrl` to contradict it
  (I5). Anything else is unknown. Attach is enabled **iff** the resolved
  `supportsVision === true`.
  `resolveRemoteCaps` owns the **probe tier** only; the remote leg of
  `resolveModelCaps` merges its answer with the list tier below, field by
  field, probe first.
  Being synchronous is load-bearing: `activeModelCaps` is a computed that runs
  `resolveModelCaps` inline, so consumers read it in the `observer` render body
  and caps landing from the detached probe re-render the affordance with no
  further user action. Resolving inside an effect or a promise body would leave
  the button stuck at its first value.
- **Token accounting** (chat-flow §token snapshot): a remote turn's used-token
  total is sourced from the server `timings` object already captured on the
  finish chunk — `timings.prompt_n + timings.cache_n → tokens_evaluated`,
  `timings.predicted_n → tokens_predicted` (server count wins over the
  per-event tally, each key guarded independently). The server evaluates only
  the part of the prompt it did not already hold in its KV cache, so `prompt_n`
  alone under-counts a cache-reusing turn by the reused prefix; a build that
  omits `cache_n` degrades to the prior value, never below it, while a reported
  `0` is a real count. No request-body change; `usage`/`include_usage` is not
  used. Absent `timings` → no count at all for a remote turn: a predicted-only
  tally carries no prompt term and is not an occupancy number.

### The list tier — a second capability source that probes nothing

`/props` can only answer about a model the server has **loaded**, and on a swap
router `?model=` *loads* it. So anything that answers "does this do vision"
while the user is still browsing must read a body the app already has. The
`GET /v1/models` response is that body, and a llama.cpp server already states
per row what the probe would confirm:

| | router (`llama-server` router mode) | direct single-model `llama-server` |
| --- | --- | --- |
| top-level keys | `data`, `object` | `data`, `models`, `object` |
| per-row `architecture.input_modalities` | every row, loaded or not; always contains `text` | *absent* |
| per-row `status.args` | every row; carries `--ctx-size` | *absent* |
| per-row `meta.n_ctx` | loaded rows only | present (the loaded model) |
| `models[].capabilities` | *absent* | `["completion"]` / `["completion","multimodal"]` |

- **One interpreter.** `deriveListCaps(row, serverType)` (`src/utils/listCaps.ts`)
  is the only reader of a `/v1/models` row, pure and synchronous, yielding at
  most `supportsVision` and `contextLength`. Vision from `input_modalities`
  including `'image'`, else — only if that key was absent — `capabilities`
  including `'multimodal'`. Context from `meta.n_ctx`, else the **last**
  `--ctx-size`/`-c` in `status.args` in either the space or `=` form, admitted
  only as an integer `> 0`. **No other argument is read**, and every failure
  lands on an absent field, never a default: `--ctx-size 0` means "the model's
  trained window", which is unknown, not `0`.
  `status.args` carries filesystem paths and could carry a credential, so this
  is the only thing permitted to read it — nothing logs, persists or serialises
  a raw row. The router form is the more precise of the two: it separates image
  from audio, which `capabilities: multimodal` cannot.
- **Gated the same way** as `/props`, on the PERSISTED `serverType ===
  'llama.cpp'` — but *inside* `deriveListCaps`, because it has two callers with
  two different sources for that type and a gate outside the function is a gate
  that can disagree with itself. The sheet passes the persisted type of the
  selected chip's server when there is one, since `handleServerChipPress` never
  sets its own `serverType` state and would otherwise suppress the answer on
  exactly the routers this exists for. Every other server type reads identically
  to before: the wire-level lift is unconditional but inert, since those servers
  emit no `models[]`.
- **Zero new requests, nothing stored.** `ServerStore.listCaps` is a computed
  over `serverModels`, whose lifecycle is already the right invalidation —
  replaced by each fetch, dropped by `updateServer` on a `url`/`serverType`
  change and by `removeServer`, absent until the post-hydration fetch. It
  therefore needs no `probedUrl`: a list cannot outlive the url it came from.
- **Precedence: probe beats list, field by field**, and the list reaches the
  **declared** axis only. `visionActive` and `effectiveContextLength` are
  computed from the probe result before the list is consulted, so no derived
  value can gate attach, the send-path image gate, the video-pal camera start,
  or the context banner. This holds structurally rather than by convention:
  there is no write path from the list into `remoteCaps`, and the two types
  carry a literal `tier` discriminant that makes them mutually non-assignable,
  so a derived value cannot be passed where a probed one is expected even by
  mistake. Freshness is not authority — the list refreshes every foreground and
  the probe still wins.
- **A single-model server needs no bare `/props` at add time.** Its own
  `/v1/models` carries both fields, in a sibling `models[]` array joined onto
  the `data[]` row by `entry.name ?? entry.model === row.id` (plus the 1×1
  degenerate pairing) at the fetch, so "is this server single-model" never has
  to be decided to read a capability.
- **Surfaces.** Remote model cards state vision and context length before
  anything is activated, and the header glyph is sourced from the same resolver
  as the cell. Add-sheet rows carry a **three-state** slot — supported, not
  supported, and a muted em-dash for "this build does not say" — because there
  presence/absence is the only other signal and three distinct populations land
  on absence. Any non-llama.cpp server renders no slot at all.

#### Edge cases

| Edge case | Behaviour |
| --- | --- |
| Router build too old for `architecture`, or a proxy emitting neither key | No vision field: card `Unknown`, sheet `—`. The whole sheet shows em-dashes rather than 47 silent rows — "this build does not tell me" is a different statement from "no vision". Context is unaffected; the rules are independent. |
| Router cannot resolve the projector offline (mmproj not cached) | `image` absent ⇒ **Not supported**, though the child would fetch it at launch. A false-negative browse impression, corrected on activation; never a broken action. |
| Direct server with an **audio-only** projector | `capabilities` contains `multimodal` ⇒ **Supported**, though `/props modalities.vision` is `false`. The direct form cannot separate image from audio; activation corrects it. |
| `--ctx-size` absent (the preset relies on the server default) | No context cell. A default is never assumed. |
| Server runs multiple slots | `--ctx-size` / `meta.n_ctx` report the **total** window, `/props` the per-slot one, so the cell may overstate until activation. The banner is unaffected — it reads the probe tier alone. |
| Model removed from the server between fetches | Its row disappears and `listCaps` loses the key; the card falls back to any probe entry, else `Unknown`. |
| Direct server whose `models[]` entry joins no `data[]` row | No vision field ⇒ `—` / `Unknown`. The tolerant join and the 1×1 pairing exist because this failure is otherwise invisible. |

**A card may read "Vision: Supported" while attach stays disabled** — for the
**active** model — whenever the list has an answer and the probe has **no
entry**. Two ways to get there, and they are the same state: the probe failed
(timeout, non-2xx, malformed — `fetchServerProps` resolves to `{}` and writes
nothing), or a url edit dropped both the entry and the list and the next
foreground fetch repopulated only the list, from the new backend, while the
session stayed bound to the old one. A *present but mismatched* entry is not
one of them: `updateServer` drops the entry on a url change and the write guard
refuses a probe whose url has moved, so nothing is left to mismatch — the
binding check is defence, not the story.

**That list of two is incomplete, and the missing path is the most common one.**
Auth gating on llama-server is **not uniform**: `/v1/models` and `/health`
answer `200` with the full model list to an unauthenticated caller, while
`/props`, `/slots` and `/v1/chat/completions` all `401` (measured). So on a
keyed server, before the user has supplied a key, the list tier populates fully
from a server whose `/props` this session cannot read, and the state above is
the normal one rather than a rare accident. Behaviour is unchanged and correct —
the probe tier gates, the list tier only describes (I8), and the `401` leaves
capabilities unknown rather than recording absence (I10). This is
**server-type dependent**, not a rule about OpenAI-compatible servers in
general: a real OpenAI endpoint does `401` on `/v1/models`.

This is the safe direction to be wrong in: the two axes describe different
things, the **configured** server and the **bound** session, and only the
second gates any action. It self-corrects on the next successful probe (§8's
second trigger). It also qualifies the claim that the card need not distinguish
an inferred value from a confirmed one because "activating is exactly what
confirms it" — activating *attempts* confirmation and can fail. That is a
tendency, not a guarantee.

### Decisions

| ID | Decision | Rationale |
| --- | --- | --- |
| D14 | ~~Caps as optional fields on `ServerConfig`~~ | **SUPERSEDED by D19** — /props answers per model; a server-scoped slot can only describe the first model probed. |
| D15 | /props gated on persisted `serverType==='llama.cpp'` | Only llama.cpp serves it; never live detection. |
| D16 | ~~/props fetch co-located in `fetchModelsForServer`~~ | **SUPERSEDED by D20** — that trigger set also let a foreground refresh clobber a good per-model result. |
| D17 | /props failure is a silent no-op | Must not break the models fetch or the connection. |
| D18 | Remote used-tokens from `timings.prompt_n/predicted_n` | **Amended by D49** — the prompt term is `prompt_n + cache_n`. Already default-emitted + captured; `usage` needs a request-body opt-in. |
| D19 | Caps keyed per `${serverId}/${remoteModelId}` in `ServerStore.remoteCaps` | Mirrors the proven persisted `remoteReasoning` map. |
| D20 | Probe trigger is remote-model activation | Capability is per model; only the active model is read; one trigger, no race. |
| D21 | Probe bound via `resolveTimeout(requestTimeoutMs, PROPS_TIMEOUT_MS)` | Lazy router starts exceed 5 s; a user-set `0` must not abort instantly. |
| D22 | Bare retry only after an unusable scoped probe **and** the single-model gate | Keeps single-model behaviour; makes mis-attribution unrepresentable. |
| D23 | An unknown/empty model list does **not** pass the gate | Unknown is exactly the router case; fail closed instead. |
| D24 | ~~Legacy `ServerConfig` caps: read-fallback, never written~~ | **SUPERSEDED by D33** — the writer never shipped, so the shape it defends cannot exist. |
| D25 | ~~Legacy `contextLength` honoured only when `> 0`~~ | **SUPERSEDED by D33** — no legacy field left to filter. |
| D26 | `contextLength` written only when `n_ctx > 0` | `0` is unknown, not a window. |
| D27 | `supportsVision` definite only on a model-describing body | A placeholder `false` would be a wrong definite answer. |
| D28 | `modalities` absent on a real model ⇒ definite `supportsVision: false` | Such builds have no vision; definite `false` fails closed. |
| D29 | One pure sync selector `resolveRemoteCaps` owns resolution | An async read point cannot re-render; UI and send path must agree. |
| D30 | The session's backend is first-class state (`ModelStore.activeRemoteBinding`), not a private engine field | Three separate approximations of it (probe snapshot, write guard, prune) each covered part of the same question; one named value covers it once. |
| D31 | Caps carry `probedUrl`; validity is `probedUrl === binding.url` | Provenance on the record makes "do these describe what we are talking to" answerable at read time instead of guarded at every mutation. Absent = pre-field, taken at face value: no migration, downgrade-safe. |
| D32 | `updateServer` prunes `serverModels` alongside `remoteCaps` | The sheet never refetches after a save, so a stale single-entry list clears the bare-retry gate against a new router — #828's failure mode through its own gate. |
| D33 | Delete the per-server `contextLength` / `supportsVision` | Zero writers, and the writer that filled them post-dates the last release, so no persisted store can hold them. Removing them takes `servers` off the resolver signature. |

---

## 8a. The three-tier `/props` parse

§8 describes the probe's trigger set, its bound, its retry gate, its write guard
and its read side. All of that is unchanged. What changed is the **shape of the
answer**: `fetchServerProps` returns `{caps, props, presence}` instead of a flat
`RemoteModelCaps`, and each part is independently absent.

An unresolved `caps` or `props` is `{}`; an unresolved `presence` is genuinely
`undefined`, because its fields are required. All three empty is the existing
unusable outcome.

### Wire → ours

Rules stay independent: a response may yield some, all or none. Two gates,
deliberately different:

- **`describesModel`** (unchanged) — `model_path` is a non-empty string other
  than `'none'`, **or** a `contextLength` resolved.
- **`isRouterPlaceholder`** — `role === 'router'`, or `model_path === 'none'`
  **and** `modalities` absent.

| ours | wire | gate |
| --- | --- | --- |
| `contextLength` | `default_generation_settings.n_ctx ?? n_ctx`, finite `> 0` | self-evidencing |
| `supportsVision` | `modalities.vision === true` | `describesModel` |
| `supportsAudio` | `modalities.audio === true` | `describesModel` |
| `samplerDefaults[p]` | `default_generation_settings.params.<wire(p)> ?? default_generation_settings.<wire(p)>`, finite number; `seed` excluded | `describesModel` |
| `slotCount` | `total_slots`, finite integer `> 0` | `describesModel` |
| `chatTemplateCaps.supportsTools` | `chat_template_caps.supports_tools`, boolean | `describesModel` |
| `chatTemplateCaps.supportsThinking` | `chat_template_caps.supports_thinking`, boolean — **build-dependent**: absent on b9976, present at `master`, so an absent key is **unknown**, never a definite `false` (D27/D28's rule, exactly as for `modalities`) | `describesModel` |
| `isSleeping` | `is_sleeping`, boolean | `!isRouterPlaceholder` |

`isSleeping` takes the weaker gate on purpose: a sleeping child may legitimately
report almost nothing else, so `describesModel` would suppress the very
observation the field exists for. The router placeholder stays excluded because
its `is_sleeping` describes the router, not the model. The `??
default_generation_settings.<name>` fallback mirrors the existing `?? n_ctx`
older-build fallback.

**Absent is not zero.** Five of the sampler defaults a current build reports are
legitimately `0` (`xtc_probability`, `mirostat`, `frequency_penalty`,
`presence_penalty`, `n_probs`), so every numeric field is admitted on
`typeof === 'number' && Number.isFinite(...)` and never on truthiness. The two
deliberate exceptions are `contextLength` (`> 0` only — D26, `0` means unknown)
and `slotCount` (a finite integer `> 0`).

`seed` is excluded from `samplerDefaults` (D48): the server reports its *live*
seed, not a default anyone should be offered a reset to, and against the app's
`-1` it would read "custom" forever.

### Writing the three tiers

- Usability is judged **per tier**. `isUnusable(caps)` keeps its exact meaning
  and still drives the bare retry and the caps-tier write; a response resolving
  only `props` or only `presence` writes those and leaves `remoteCaps`
  untouched. `CAPS_FIELDS` gains `supportsAudio`, which cannot shift the
  bare-retry gate: it shares `supportsVision`'s `describesModel` gate, and D28
  makes `supportsVision` definite on **every** such body, so `supportsAudio` can
  never be the field that alone makes `caps` usable.
- When the bare retry runs, its result merges **per tier** over the scoped one;
  a tier the bare body did not resolve leaves the scoped answer intact. The
  retry fires precisely when `isUnusable(caps)` — exactly when a scoped
  `props`/`presence` may already have resolved, which wholesale replacement
  would discard.
- `remoteProps` uses the same within-backend field-wise merge and across-backend
  replace as `remoteCaps`. Its no-op guard compares scalars by `===` and
  `samplerDefaults` / `chatTemplateCaps` by shallow key-and-value equality: a
  fresh nested object holding the same numbers is the same answer, and rewriting
  it would wake every observer for news that is not news (I10).
- `remotePresence[key]` is replaced outright per observation — a point-in-time
  fact, not something to merge — and pruned by the same `dropServerEntries` as
  the other two maps, on `removeServer` and on a `url`/`serverType`
  `updateServer`.
- Concurrent calls for one key **coalesce on an in-flight promise** (I11): a
  second call while one is in flight returns that promise. The key includes the
  server url, so a call made after a url edit does not join a probe issued
  against the old backend. The map holding them is request bookkeeping, not
  store state, and an entry leaves it two ways: when its **own** request settles
  — identity-checked, because a probe cleared while pending would otherwise
  evict the replacement registered under its key — and when the app leaves the
  foreground, so the reprobe on return issues its own request rather than
  joining one that spanned the background.

### Read side, per tier

| tier | selector | validity compared against |
| --- | --- | --- |
| caps | `resolveRemoteCaps` + one passthrough line for `supportsAudio` | `binding.url` (I5) |
| props | `resolveRemoteProps(model, remoteProps, binding)` — pure, synchronous, shaped like `resolveRemoteCaps` and reusing `capsMatchBinding` | `binding.url` — the sheet describes the **live session's** backend |
| presence | `lastObservedSleepState(serverId)` | `server.url` — a presence UI describes a **configured** server, which may have no session |

The two validity rules differ deliberately; it is not an inconsistency.

`resolveModelCaps` gains `audio: triState(confirmed.supportsAudio ??
listed?.supportsAudio)` on `ModelCapabilityView`, merged probe-over-list exactly
like `vision` — **declared axis only**: no `audioActive`, and no send path gates
on it, until an audio item defines one (I8). `ListDerivedCaps.supportsAudio` is
declared so the resolver can read it; `deriveListCaps` does not yet write it.
`modelStore.activeSamplerDefaults` is a computed over `resolveRemoteProps`, read
in an `observer` body so a landing probe re-renders (D29).

### Consumer contract (the surface sibling items build on)

Siblings read **only** what is listed here, never `serverStore.remoteCaps` /
`remoteProps` / `remotePresence` directly.

| Consumer need | Read this | Persisted? | Guaranteed | Unknown when |
| --- | --- | --- | --- | --- |
| `n_ctx` | `modelStore.activeModelCaps.contextLength` / `capsFor(model)` | yes | finite `> 0` or absent; never `0` | no probe entry valid for the binding |
| `modalities.audio` | `modelStore.capsFor(model).audio` → `'yes' \| 'no' \| 'unknown'` (declared axis only) | yes | definite only from a model-describing body | placeholder body, or no valid entry |
| per-model `/props?model=<id>` refresh | `serverStore.fetchRemoteModelCaps(serverId, remoteModelId, resolvedApiKey?)`; read back through `capsFor(model)` | — | the three gates below | — |
| server sleep state | `serverStore.lastObservedSleepState(serverId)` → `'awake' \| 'asleep' \| 'unknown'` | **no** | tri-state; volatile | no observation this session, or the url moved |
| sampler defaults for a settings surface | `modelStore.activeSamplerDefaults` | yes | internal param names, numbers only | no valid props entry for the binding |

Every writer above is `fetchRemoteModelCaps` (I11). **A pre-activation picker is
a LIST-tier consumer**: the probe tier describes a *loaded* model and on a swap
router `?model=` *loads* it, so a browse-time question reads the list tier
(§8, list tier) — reached the same way, through `capsFor(model)`.

**`is_sleeping` is per model, not per server, and never derived.** `/props`
answers per model, and a bare `/props` against a router describes nothing, so a
server-scoped slot would take whichever body arrived — the router's own state
included — and attribute it to every model. In router mode `?model=<id>` proxies
to that model's child server, so the wire's sleep state *is* per model.
`lastObservedSleepState(serverId)` returns the **most recently observed** (`max at`)
entry under the `${serverId}/` prefix whose `probedUrl` equals the server's
current `url`, else `'unknown'`. It answers "is the model we last looked at here
sleeping", **not** "is this server reachable", and gates nothing (I8). A
sleeping child that answers with the router placeholder records nothing and
stays `'unknown'`; inventing `true` there would be D27/D28's error.

**`slotCount` is descriptive and never reconciles a context number** (D37). It
does not fix the list-tier edge case where a multi-slot `--ctx-size` /
`meta.n_ctx` reports the total window while `/props` reports the per-slot one:
`contextLength` stays the per-slot window and the only context number any gate
reads, and dividing one by the other would put a derived number in the
capability tier (I8).

**On-demand re-probe** is the existing writer, not a new entry point. Its gates
are internal and a caller cannot bypass them: the persisted
`serverType === 'llama.cpp'`; in-flight coalescing per key; and the
non-downgrading write (an unusable answer writes nothing, a partial one clears
nothing). The one unenforced part is the caller's own discipline: call it **only
after an event that can have changed the answer** (a load or unload completing,
a wake), never on a timer or on render. **A refresh is not a free observation** —
on a swap router `?model=<id>` *loads* the model, so a speculative call starts
real work on the server. Awaiting the promise proves nothing about a write (the
guard may discard a result whose server was repointed mid-flight); results are
observed by reading `capsFor(model)` / `lastObservedSleepState(serverId)` in an
`observer` body.

The trigger set is therefore **activation + gated foreground + sibling-initiated
post-event refresh**, which amends D20's "one trigger, no race" (D45). The race
D20 guarded is now closed structurally rather than by scarcity of triggers:
per-model keys make placeholder mis-attribution unrepresentable, `isUnusable`
returns early, the merge is field-wise, and I11 coalesces per key.

Coalescing settles write correctness, not freshness. A refresh asked for while a
probe is already in flight joins that probe and receives its answer, so a caller
firing after a load or unload can be handed a reading taken before the event. It
is the caller's job to decide whether that is recent enough — which is the same
obligation `lastObservedSleepState` states for the presence tier, and for the
same reason: the store reports the newest observation it holds, never a live
state.

### Remote per-turn timings

`streamChatCompletion` already assigns the server `timings` object to
`CompletionResult.timings`, and `run_finished` already spreads it into
`metadata.timings` with `time_to_first_token_ms` — there is no new capture path
and no new component. §8's "Token accounting" bullet documents only the three
token counts lifted out of that object; the object itself carries more, and
`AssistantTurnFooter` now renders two parts of it under the existing
field-presence rule (chat-flow D1): prompt speed from `timings.prompt_per_second`
and cached tokens from `timings.cache_n`.

Both are **origin-agnostic** (D42): local turns gain prompt speed too, since
llama.rn reports the same key, while `cache_n` is server-only so local turns show
no cached part. Presence-gated means presence, `0` included — a build that does
not report prompt-cache reuse omits the key entirely, while a cold prompt on a
build that does reports `0`, and those are different facts.

`usage.cached_tokens` is **not** used (D43): it requires a
`stream_options.include_usage` opt-in, which is D18's own reason for sourcing
from `timings`. Measured: no `usage` object appears anywhere in the stream
without that opt-in.

### Edge cases

| Edge case | Behaviour |
| --- | --- |
| User never opened the settings sheet | App defaults are forwarded. Measured on b9976: `defaultCompletionParams` is value-identical to the server's own defaults for all twelve newly forwarded fields **except `seed`**, reported as `4294967295` (`LLAMA_DEFAULT_SEED`) against PocketPal's `-1` — only *effect*-equivalent, through the server's unsigned cast. (`temperature` differs too, `0.8` vs `0.7`, but it was already forwarded.) |
| A response resolves only a descriptive or presence field | That tier is written; `remoteCaps` is untouched and `isUnusable(caps)` still drives the bare retry unchanged. A body that describes no model resolves no descriptive field either — every `props` field is `describesModel`-gated. |
| Probe returns `{}` / times out / 4xx, or a router placeholder body arrives | Nothing written in any tier; every gate rejects the placeholder (D17, I10, D27/D28 extended). |
| Operator restarts the server with different flags at the same url | Persisted `samplerDefaults` are briefly stale, so an indicator can be wrong; cosmetic only (I8), self-corrects on the next probe. |
| Pal sheet edits a Pal whose model is not active | No binding → `activeSamplerDefaults` undefined → no indicator, no reset. Fails closed (I5). |
| Server url edited while a remote model is active | Unchanged (§5): the session stays on the old backend and entries probed from the new url do not resolve for it (I5), in all three tiers. |
| Build reports no `cache_n` / no `prompt_per_second` | Those parts do not render; the rest of the footer is unchanged (chat-flow D1). |
| `mirostat` off (`0`) forwarded | A no-op on the server; the control is honest either way. A value is never suppressed for being a default (I6). |
| Sibling calls the refresh twice in one tick | One request; both callers await the same promise (I11). |
| Old persisted store with no `remoteProps` | Hydrates as undefined → unknown; no migration, no crash (I3). |
| Bare retry resolves caps but not props | Merged per tier over the scoped result; a scoped `props`/`presence` that already resolved survives. |
| Keyed llama.cpp server before a key is supplied | The list tier populates fully and the probe tier stays unknown — see §8's third path. Correct by construction, and the common route to it. |

### Decisions

| ID | Decision | Rationale |
| --- | --- | --- |
| D34 | Three tiers — capability / description / presence — split by lifetime | Volatile facts must not persist; gating facts must stay narrow. |
| D35 | One writer fills all three tiers in one `runInAction` | They describe one backend; separate writes could disagree. |
| D36 | `remotePresence` is not persisted | A hydrated "asleep" is an unverified claim about now. |
| D37 | `slotCount` is descriptive; never reconciles a context number | A derived window in the capability tier would gate on arithmetic. |
| D38 | vLLM's allow-list row ships empty | Unverified against a live vLLM; omit beats a 400. |
| D39 | `n_probs` is not forwarded | No control renders it and no surface displays probabilities. |
| D40 | Server defaults are a reference tier, not a resolution layer | Session settings are baked and persisted; a server's values must not be. |
| D41 | Equality is per control kind: sliders `step/2`, discrete controls `===` | Float and enum equality are different questions. |
| D42 | Footer additions are origin-agnostic | Field presence already decides; an origin branch is new complexity. |
| D43 | Cached tokens come from `timings.cache_n`, never `usage.cached_tokens` | `usage` needs a request-body opt-in — D18's own reason. |
| D44 | Top-level `reasoning_effort` is **not** sent to llama.cpp | Not a llama-server request field; silently ignored, so not delivered. |
| D45 | Trigger set gains a sibling-initiated post-event refresh | Coalescing plus the non-downgrading write make the added trigger raceless. |
| D46 | `chat_template_caps` captured on the description tier; `ListDerivedCaps.supportsAudio` declared but unwritten | Both are named scope; declaring the shape keeps siblings out of it. |
| D47 | One read-side name table (`PARAM_WIRE_NAME`), one write-side allow-list (`FORWARD_ALLOWLIST`) | A single table would force `temperature`/`top_p` off the read side purely to keep them out of the write gate (I9), losing the indicator on the two controls it has most to say about. |
| D48 | `seed` is excluded from `samplerDefaults` | The server reports its live seed, not a default worth returning to. |
| D49 | The remote prompt term is `timings.prompt_n + timings.cache_n`, each key guarded on its own | The server evaluates only what it did not already hold cached, so `prompt_n` alone under-counts a reusing turn. An absent `cache_n` degrades to the prior value; a reported `0` is a real count, and the two are different facts. |

**Amends D20** (probe trigger is remote-model activation, "one trigger, no
race"): the set is now activation + gated foreground + sibling refresh, per D45.
Nothing in I1–I5 or I-RS1–I-RS4, or in D1–D33, is amended by this delta;
I-RS4 in particular stands as written, and is now measured rather than inferred.

**The remote token-accounting delta amends D18**, and is a later and separate
delta from the three-tier parse described above: the prompt term becomes
`prompt_n + cache_n` per D49, while D18's own `usage`/`include_usage`
rationale — and D43, which rests on it — stand unchanged. It also replaces
D18's absent-`timings` fallback: a remote turn with no `timings` object now
reports no count rather than a predicted-only tally, since that tally carries
no prompt term at all.

**Wire verification.** Every claim in §2d, §8a and the `/props` table was
measured against a running `llama-server` in router mode, build
`b9976-e3546c794`, model `bartowski/Qwen_Qwen3-1.7B-GGUF:Q4_K_M`, 4 slots. The
four `penalty_*` renames are **required**: sent under PocketPal's own names the
slot kept its defaults and the request still returned `200`; re-sent under
`repeat_last_n` / `repeat_penalty` / `frequency_penalty` / `presence_penalty`
all four landed in `/slots`, as did the twelve identity names. Three things
remain **unverified** and are treated as such: `reasoning_budget_tokens` and
`chat_template_caps.supports_thinking` on a build newer than b9976 (both defined
at `master`, both inert or absent here), and vLLM's acceptance of `top_k` /
`min_p` / `repetition_penalty`, which is where whoever fills D38's empty row
starts.

---

## 9. Router mode: load, unload, and fetching a model to the server

Everything in this section is measured against one build, `llama.cpp` b9976
(`e3546c794`), and is therefore **unverified across builds**; every rule resting
on it fails safe in the unverified direction (D-RT51). Four of the rules stand
higher, being asserted by llama.cpp's own regression suite
(`tools/server/tests/unit/test_router.py`) — a maintained commitment its CI
enforces rather than a snapshot. **The published router documentation is wrong on
five load-bearing points**: the SSE event name, what a load posted at a sleeping
model returns, what `POST /models` returns for a bad reference, what the two
terminal download events mean, and where `download_progress` nests its URL map.
The verbatim captures are committed at `jest/fixtures/router-wire/`; where the
documentation and a capture disagree, the capture wins, and the mapping layer is
written from the measured shapes throughout.

### Detection, and what it does not prove

A server is a router iff **both**: its persisted `serverType` is `llama.cpp`
(never live detection), **and either** at least one row of its
`GET /v1/models` body carries a `status` **object**, **or** that body has no
top-level `models` key.

- Object presence, not the readability of `status.value`, is the discriminator
  (D-RT29): keying on the known strings would let one wire change kill the
  feature silently, whereas object presence degrades per row.
- The second disjunct exists because **detection must be a property of the
  response, not of a sample of its rows** (D-RT46). A rule that inspects rows can
  only classify a body that has rows, so it is defeated by any well-formed
  response whose list is empty, filtered, truncated or paginated. Measured: a
  router's body has top-level keys `data`, `object`; a single-model server's has
  `data`, `models`, `object`. That the key still discriminates at zero rows is
  **reasoned, not measured** — no zero-row router has been produced.
- The obvious alternative does not work and is recorded so it is not retried:
  probing the router-only `GET /models` and reading a 404 as "direct" fails,
  because a single-model server answers **200** there with a body byte-identical
  to its `/v1/models`.
- Detection costs **zero extra requests**: the evidence is in a body the app
  already fetches for the list.
- **No evidence ⇒ inert.** Not "assume direct", not "try and see": zero router
  requests, no groups, no actions, the picker exactly as it was.

**Endpoint age is a different question, and only the endpoint answers it**
(I-RT15). Router mode with load and unload landed 2025-12-01 (`ec18edfcb`);
`GET /models/sse` and `POST /models` landed 2026-06-17 (`4b4d13ae7`), in the
**same commit**. Every router built in that six-and-a-half-month window passes
detection cleanly, loads and unloads correctly, and has neither a stream nor a
download endpoint. So `routerStreamCap` starts `'unknown'`, becomes `'present'`
on a 2xx from the stream, and `'absent'` **only on a 404** — a fact about the
build, which is why it may be remembered for the session (D-RT48). A 401 is a
fact about credentials, a 400 about that one request, a 500 about that moment:
none of them is remembered. The condition is decidable rather than guessed: an
unregistered route answers a clean JSON envelope, `404` with
`{"error":{"message":"File Not Found","type":"not_found_error","code":404}}`,
which is distinguishable from a dropped stream, a 401 and a timeout. Measured
with a same-instance control (`--api-prefix /shifted`) proving the routes exist
on that binary and only the path was unregistered.

Because the two endpoints shipped together, the stream's own status answers for
the download endpoint at no extra request, and the download field renders only
while the cap is `'present'` (D-RT49). Both `'unknown'` and `'absent'` hide it, so
a 401 hides it too: an affordance that always fails is worse than an absent one.
The inference is licensed in the **hiding** direction only — passing detection is
never evidence of a stream, and no operation's success is evidence of another
endpoint's existence.

### The event stream is an accelerant; the reconciled row is the authority

At most one `GET /models/sse` connection app-wide, against the focused server —
the picker's while it is open, otherwise the server of the most recently started
operation (D-RT7). **Two things hold it and the connection is derived from them**
(D-RT62): something on screen watching a server, and an operation waiting on one.
A stream nobody holds is closed, which is what closes the one a chat activation
opened — otherwise one remote message buys a socket for the life of the process,
reopened on every foreground — and a stream something still holds survives the
picker's release. The focused server is read from the holders on every change to
either, never latched. It also closes on background and on error.

On foreground the list is reconciled **first** and only then does the stream reopen (D-RT8): the event that
would have said a load finished may already have happened while it was closed,
and asking answers where waiting for a past event does not. A byte and duration
budget closes and reopens it, because a long-lived XHR accumulates the whole
response and a download stream can run for an hour (D-RT9); holding it open does
**not** hold the desktop awake — a model still slept on schedule at its
`--sleep-idle-seconds` mark with the stream open throughout.

**Closing the stream and the stream ending are different events and do not share
a signal** (D-RT56). On the wire they are indistinguishable, so the transport
separates them at the source: the handle's `close()` reaches no handler, and only
an ending nobody asked for is reported. A single signal for both means the
cleanup that closes the stream reopens it in the same tick, and the picker's
unmount leaves one connection to the user's desktop for the rest of the
foreground session. For the same reason the picker **releases** the server it was
watching rather than merely closing the transport: the background transition
closes a stream it fully intends to reopen, and a close cannot mean both.

**What reopens it is a transport ending, not a refusal** (D-RT57). An HTTP status
is a refusal — about this build, or these credentials — and answers the same way
next time. Everything else is transport, and on iOS that covers the ordinary
case: React Native maps `xhr.timeout = 0` onto Foundation's 60-second **idle**
default, so a stream that merely went quiet ends as an error carrying no status.
Reopening only on a clean end therefore never reconnects on that platform at all.
Reconnects are bounded per peer by a rate rather than a total — a server that
answers 200 and hangs up immediately would otherwise be a hot loop costing a
Keychain read and a token-bearing request per round trip — and the bound lifts by
itself once its window passes.

**A scheduled reopen is part of the stream's state, not a timer beside it**
(D-RT63). Written as a bare timer it was unreachable by every release path by
construction: the state was nulled before the reopen was armed, so throughout
the reopen window "this store holds nothing for that server" and "this store is
about to open a socket for that server" were both true, and the reopen re-armed
the focus on the way in — a server the user had released stayed connected for
the rest of the process. The state carries `reopening`, armed and cleared with
the timer in one action, so every path that closes a server's stream closes its
pending reopen with it.

One request per peer, guaranteed by claiming the connection **before** the
Keychain read rather than after it (D-RT58): two callers arriving during that
await each opened a request, and only the later handle was retained, leaving a
token-bearing connection no close could reach.

**The transition carrier is `status_change`, not the documented `model_status`.**
On the wire `model_status` fires exactly once, as the opening acknowledgement
carrying no progress, and every transition after it — progress, completion,
sleep, failure — arrives under `status_change`. A reducer written to the
documentation shows the opening spinner and nothing after it, yet still ends
correctly on watchdog timing: it reviews clean and ships with a progress bar that
never moves. Both names therefore enter the same path (I-RT13), and neither may
be dropped: one measured build emits both, and the two endpoints have different
ages, so builds exist whose event vocabulary is not this one's.

`download_progress` nests its per-URL map at **`data.progress`**, one level below
where the reference prints it; a parser written to the documented shape reads an
empty map and renders the same dead bar (D-RT42).

The event type is read from the payload's `event` field, never from SSE framing.
A payload with no recognised event, or one whose shape does not parse, is
ignored — it never settles anything.

### One presenter per row, and the list may only claim what we believe

A row had two sources answering "what is this model doing" — the event overlay
carried a status and so did the list — with a recency rule deciding between them.
Three attempts to tune that rule failed in the same place: after a desktop
stopped answering there is no later fetch to overtake the overlay, so a row went
on showing a frozen determinate bar and counting as resident underneath the note
saying the server could not be reached.

The question is deleted rather than arbitrated, by giving the two sources
disjoint jobs and disjoint moments (D-RT67):

- **While this app has an operation on a key, the operation presents the row.**
  The label comes from `op.kind`, the operation owns the progress bar, and it
  offers Cancel. The list is not read for a label at all.
- **With no operation, the list presents it** — and may make a state claim only
  while the app currently believes it. If the last read of that server's list
  failed and none has succeeded since, the row is passed on without its state,
  which maps to `unknown` and renders as **no claim**: no state label, grouped
  under Available, not counted resident, with the existing reason row beneath it.
- **The overlay is detail about the attempt in hand, and does not outlive it.**
  It is keyed by model, not by attempt, so what one load left behind was still
  there for the next: a retry opened a determinate bar at the previous
  attempt's fraction, and a fresh failure carried the previous exit code as its
  message. Starting an operation clears the key. The prune cannot cover this —
  a retry's row is listed, so it is never pruned.
- **The overlay is not a state source at all.** `RouterLive` carries a progress
  fraction, a byte map and an exit code, and nothing that could be read as a
  verdict. The reducer still reads a status off one event, for its own transient
  decisions — whether to reconcile, and whether an unrequested unload is eviction
  evidence — but nothing stores it, so `live.status` is a compile error in every
  file, present and future.

This is not a new pattern: the chat's preparing affordance already gated on the
operation and took only the fraction from the overlay. The picker row was the one
place that did not follow it.

Two consequences. A model the server is already loading offers **no Load** — the
post would collide with the load in flight, and that load is not this app's to
cancel — and neither does a model with no row at all. And "the server could not
be reached" renders as one thing rather than two: the row makes no claim, and the
reason row says why.

### The op state machine

An operation is `requested` until the server **states** that it is under way, by
an event or by a reconciled row, and only then becomes `active` (D-RT27). An
HTTP `{"success":true}` is **acceptance, never acknowledgement**: the child can
still fail to launch with nothing further on the wire.

| Watchdog | Arms on | Fires after | Does |
| --- | --- | --- | --- |
| W1 | phase `requested` | `ROUTER_ACK_MS` | one models fetch, then reads **that kind's** verdict off the row |
| W2 | phase `active`, from `lastEvidenceAt`, re-armed by every corroboration | `ROUTER_EVIDENCE_MS` | the same |

**A watchdog only ever asks** (D-RT28). Expiry issues one reconcile and nothing
else; the verdict is read off the row and never inferred from the silence. So
neither interval is correctness-critical: too short costs a request, too long
delays the answer, and neither can falsify it. There is no app-side deadline on a
load the server reports as in progress — what is bounded is the app's ignorance,
not the load.

An unload arms neither watchdog: there is no acknowledgement to wait for and no
evidence to re-arm from, only convergence, so it carries its own settle bound
instead. A download carries an absolute ceiling as well.

**Tiers.** The stream gives fractional progress, stages and byte maps for the
focused server. The **poll tier** covers any server holding an operation with no
stream: it is reconciled through the existing models fetch every
`ROUTER_POLL_MS` while foregrounded, one read in flight per server, and the entry
drops when that server's last operation settles (D-RT31). It exists because the
only other reconcile fires on a background-to-foreground transition and is
throttled to a minute, so a foregrounded app would otherwise never re-read at
all. It adds no second list source and no third writer of `serverModels`. On a
build whose stream 404s the poll tier is the only tier and the load affordance is
**indeterminate by design**, which is stated here so a test can assert it rather
than leaving it to luck (D-RT50): the operation still settles off the row, the
send gate still resolves, and the first message still goes through.

While backgrounded the stream is closed, the poll is suspended, no watchdog is
armed and **every settle bound is suspended with them** — nothing may expire
against silence the app could not have heard. The guaranteed foreground reconcile
carries the invariant instead: every in-flight operation is re-evaluated against
fresh rows before any watchdog re-arms.

**Every operation settles** (I-RT12), by terminal status, reconcile verdict, user
cancel, or abandonment when its server is removed or repointed. A **cancel is a
withdrawal and settles at the reconcile it asks for**, surfacing nothing,
whatever the row goes on saying — what the caller is waiting on is the request,
not the model, and a cancelled load left reading in flight is a chat that hangs
with no error and no spinner (D-RT66).

**Settling an operation and answering its caller are two questions, and one
event was serving both** (D-RT80). D-RT66 governs the first and is unchanged:
whether the model loaded is a fact about the model, so an operation settles on a
read of the list. The caller is waiting on something else — whether the request
is still being pursued — and a tap on Cancel establishes that outright, with
nothing left for a read to add. Tied together, a withdrawal on a server that had
stopped answering left the send path suspended for the ninety seconds the reach
bound takes, for a request the user had already retracted. The waiter is
released at the tap; the operation goes on asking the other question until a
read confirms the row. **This does not weaken D-RT66** — it separates a second
question that rule was covering by accident, and the accident was the same one
this section exists to remove, one layer down: an ending about our own request
derived from evidence about the model. A waiter is resolved once per key, so the
later settle finds none. A load also carries **its own ceiling**,
`ROUTER_LOAD_MAX_MS`: a row wedged at `loading` is re-armed by every healthy
list read, so the bound below can never reach it, and unbounded it holds the
send path for ever. The ceiling reads the row exactly as the reconcile verdict
does, so it settles the operation without recording anything the row does not
support (D-RT68). One further bound covers the case none of the above
reaches: an operation whose watchdog has asked
and for which **no models fetch has succeeded since it started** settles failed
at `ROUTER_UNREACHABLE_MS` (D-RT55), carrying a request failure and never a claim
about the model. That is a **cause of its own** and not the kind's own failure
copy: "this model did not load" about a request that never arrived is a claim the
app is in no position to make, and it is the same cause whichever kind of
operation could not be sent. A transport throw at the request itself resolves the
same way. **Both of those writers drop the record for a request the user
withdrew** — a cancel on a server that has stopped answering is not news about
the server — which the reach bound did not do, so a cancelled load announced
"could not reach this server" ninety seconds later. Without this bound, a server that stops answering entirely leaves an
operation in flight for ever.

### Three verdict rules, one principle

> The event is a prompt to reconcile. It is never an outcome.
> The row in the reconciled list is the only evidence.

This holds for **every** kind, read off the list and never off the live overlay
(D-RT59) — and since the overlay carries no state at all (D-RT67), an event has
nothing a verdict could mistake for one. Splitting the rule by kind is a
convention, and the convention drifted: a `status_change` arriving mid-fetch
could settle a load **failed** off the event that carried it.

**No verdict is read from a list read that began before the request, in either
direction** (D-RT76). Gating only the *success* on that and letting the rest
fall through was worse than not gating at all: control reached the failure
branch with a row reading `loaded`, and the row rendered "Loaded", an Unload
button and "this model did not load" at once — with the server's own *"model
already loaded"* printed underneath where a 400 had supplied it. An
uncorroborated success means **keep waiting**, never declare failure. The
record constructor declines a `ready` row as well, so the precondition its one
caller used to guarantee is stated rather than assumed.

**An operation is identified by its attempt, not by the key it sits on**
(D-RT77). A key carries one operation at a time, but a request already replaced
by another is still in flight and still answering: a superseded load's
transport failure settled the **unload that replaced it** as
`server-unreachable`, and its refusal settled that unload **ready** while the
row still said the model was resident. Every operation carries an attempt
number and every late answer places itself before settling. Round four stopped
*detail* leaking across attempts on one key; this stops *outcomes* doing it.

**A failure record is built from the row the operation settled on, not chosen
beside it** (D-RT68). "This model did not load" is a claim about the model, and
only a row the app both **believes** and reads as **settled** supports one. The
constructor returns nothing for a row still reading `loading` or `downloading`,
and nothing for a row reading `unknown` — the one state whose whole meaning is
that the list is not believed, so a claim derived from it is a claim derived
from the absence of one. No caller can write one either way.

**Recording nothing is not the same as having nothing to say** (D-RT71). The
ceiling first read that rule as licence for silence: stopping a ten-minute wait
is a fact about this app's patience, not a fault of the model's, so it settled
with no record at all. But a message is on screen waiting for an answer, and
silence is not one of the answers available — the user is left with an
unanswered turn and no account of why. The ceiling records `wait-stopped`, which
I4′ permits precisely because it asserts nothing about the model, and the row
goes on saying whatever the desktop says. The rule the constructors enforce is
about *what may be claimed*, never about *whether to speak*.

The `unknown` case was reachable only through the ceiling, and only because the
reach bound at `ROUTER_UNREACHABLE_MS` fires long before `ROUTER_LOAD_MAX_MS`.
That is two constants with nothing relating them, and a safety property resting
on an unstated numeric relationship is not one: it returns silently the moment
somebody tunes a number. The constructor refuses the state instead.

Each kind has exactly one verdict rule and borrows no other's; they are three
functions with distinct return types, so borrowing one is a compile error.

**Which state a verdict may be read from is a type, not a convention** (D-RT64).
A row state read off a reconciled list is its own type, produced only by the
mapper that reads a list row, and every verdict — and the send gate, which is a
verdict in all but name — takes that and not the union the screen reads. A
convention held at each call site drifted twice: a whole-file correction still
left a refusal settling `ready` off an event and the gate skipping the request
off one, and reverting the corrected call site left the suite green. Passing the
widened state the screen reads to a verdict no longer compiles, and the label an
operation presents is a different union again, so it cannot be passed where a
state is expected.

| Kind | Reads | Settles |
| --- | --- | --- |
| load | the row's state | `loaded` or `sleeping` ⇒ ready; `loading` or `downloading` ⇒ stay in flight, re-arm; anything else ⇒ failed |
| unload | the observed **end state** | `unloaded`, `absent` or `failed` ⇒ success; still resident ⇒ not yet converged, wait to the bound |
| download | the model's **presence** in the list | a row that is not `downloading` ⇒ success; a `downloading` row ⇒ corroborated; no row, after a terminal event and a grace window ⇒ failed; no row with the ceiling unspent ⇒ still in flight |

**`sleeping` is ready, not a failure.** It means resident: the process is alive
and only the weights are released. `POST /models/load` at a sleeping model answers
`400 "model is already running"`, does **not** wake it, and leaves the row
`sleeping` — so the operation settles ready at once, on the response, and
**nothing is surfaced** (D-RT34). The completion performs the wake. Generalised so
one more 4xx does not reopen it: a non-2xx from a load is resolved by the
**observed row state**, never by the message text (D-RT36). Row `loaded` or
`sleeping` ⇒ ready, silently; row `loading` or `downloading` ⇒ the operation stays
in flight, which is both correct and the better outcome because progress keeps
working; anything else ⇒ one reconcile, then the load mapping.

**The unload verdict is inverted, and it is stated separately so it can never be
reused from the load mapping** (D-RT37). Run through the load mapping, an unload
would settle ready on a row reading `loaded` — reporting success on exactly the
failure being guarded against. `POST /models/unload` is **asynchronous**: a 200
means *accepted, now converge*, and the row lags after every unload, the
unambiguously correct ones included, so a verdict taken from the response would
report a correct unload as a failure (D-RT38). A model the server had already
evicted answers `400 "model is not running"` — the operation failed while the end
state the user wanted is already true, so it settles **success** and shows
nothing (I-RT14). The bound is `ROUTER_UNLOAD_SETTLE_MS`, which must clear the
wire's ten-second `stop-timeout` default or a slow-stopping child reads as a
refusal; it is evaluated **only against a list read that began after the request**,
because a row nobody managed to re-read is not an unconverged row.

**The bound reads the row, exactly as the reconcile does** (D-RT70). It once
settled on `hasReconciledSince` alone, which proves only that *some* fetch
succeeded after the request and says nothing about what that fetch found: a
later failed read leaves the check satisfied while the rows it could not refresh
are no longer ones the app believes, so "the server did not release this model"
was asserted about a row nobody had looked at. At the bound, a row still holding
the model settles the operation failed, **stays in Loaded** — never offered as
free while the server still holds it — and carries a dismissible reason with
Unload one tap away; a row that has released it settles **ready**, because the
end state the user asked for is true; and a row this build cannot read settles
the operation, so nothing hangs, and records **nothing**. Nothing auto-retries.

**The download verdict is the same principle a third time.** Neither terminal
event is an outcome: `download_finished` fires identically for a download that
succeeded and for one of a repository that does not exist, with no distinguishing
field, and `download_failed` was observed only on **cancel** (D-RT43). Wire the
obvious handlers and the result reports failures as successes *and* cancellations
as failures, in opposite directions. Upstream behaves the same way — its own
download test waits for `download_finished` and then *separately* asserts the row
in the list — so this is the producer's committed practice, not our inference,
and it is the strongest-standing rule here.

The reference is posted **exactly as typed**; a 200 is acceptance and not
validation, since a repository that does not exist is accepted with the same
shape. Absence from the list is not failure while the ceiling is unspent
(D-RT47): a model being fetched need not be listed until it lands, and on a
server with no stream there is nothing else to corroborate it. A terminal event
starts a short grace window of re-reconciles before the operation may be called
failed, which is *observable* — it either finds the row or it does not — in a way
a reload flag never was. **`GET /models?reload=1` is never issued** (I-RT6): its
effect cannot be attributed, upstream's own post-download assertion finds the
model without it, and it can unload a running model whose source changed, which
on a `--models-max` router is a cold reload someone else pays for. Cancelling
either a load or a download is an unload of that model — the wire's own contract,
not derivable from the endpoint's name.

### Readiness: four triggers, one request

`ensureRouterModelLoaded` is the only issuer of a load and is idempotent per
model (D-RT11): called again while one is in flight it returns the same promise
and posts nothing.

| Trigger | Call site | Behaviour |
| --- | --- | --- |
| activation | `ModelStore.setRemoteModel` | detached and `.catch`-guarded, exactly as it already calls `fetchRemoteModelCaps`. Activation, engine build and chat never wait (D-RT12) |
| send | `useChatSession.handleSendPress` → `ModelStore.ensureActiveRemoteModelReady`, which reads `activeRemoteBinding` and never the mutable server record | awaited after the user's turn is added, before the runner starts |
| picker | the row's Load action | the same call |
| engine backstop | `OpenAICompletionEngine`, through an `ensureReady` primitive `ModelStore` injects at construction | awaited before the request; the engine gains no store handle |

The backstop exists because the chat send path is **not** the only production
caller of a completion: structured output reaches the engine directly and would
otherwise keep the spinner-until-timeout this work exists to remove (D-RT26). Both
firing is free — idempotence joins the second await to the same promise — and the
send trigger is kept as well, because only that path can tell "waiting for
weights" from "waiting for the first token" and offer progress with a way out.

**No production completion is posted at a model the app believes is unloaded,
failed, absent or unknown, and none ever pays for a cold load** (I-RT5), enforced
structurally at the engine rather than per call site. The one named exception is
the sleeping wake above, bounded by `requestTimeoutMs`.

### `--models-max` and eviction

`--models-max` is **not on the wire**, and neither is LRU recency: `status.args`
are the child's arguments, not the router's, and no row carries a last-used
timestamp. Design for permanently unavailable. So the app **never names a victim,
never asserts an eviction and shows no confirmation dialog on load** (I-RT10); the
Loaded group carries the resident count, which is a fact: it counts the models
the server says it is holding — `loaded` and `sleeping` — and nothing it is
merely on its way to holding.

There is **no unconditional advisory** (D-RT32). An unfalsifiable "loading another
model may unload one of these", shown for ever on an unlimited router, is the same
cry-wolf failure as the rejected dialog one severity lower. The note appears only
once this app has **observed** an unrequested unload on that server this session,
which takes **both** halves: a transition to `unloaded` for a model with **no
operation of ours at all** on it, while an operation of ours other than an unload
was in flight on that server. Without the first it fires on our own load failing;
without the second, on the ordinary `--sleep-idle-seconds` exit that every one of
these servers performs unprompted — and both are present verbatim in the
captures. It can therefore only ever say less than it knows.

### Invariants

- **I-RT1**: every router request is gated on the **persisted** `serverType ===
  'llama.cpp'` **and** router evidence. Without both: zero router requests, and
  today's picker exactly.
- **I-RT2**: `serverModels` gains **no third writer** — the event reducer writes
  only the overlay, and the poll tier calls the existing fetch.
- **I-RT3**: a stream that drops, errors or is closed is **never** reported as a
  failed load. Only a reconciled **row** settles an operation, of any kind, in
  either direction — never the live overlay, and never a transport failure.
- **I-RT4**: at most one load in flight per model, never one not traceable to a
  user action, and no automatic retry after a failure.
- **I-RT5**: no production completion is posted at a model believed unloaded,
  failed, absent or unknown, and none pays for a cold load. One named exception:
  the sleeping wake, bounded by `requestTimeoutMs`.
- **I-RT6**: the app never issues `GET /models?reload=1`.
- **I-RT7**: at most one SSE connection app-wide, none while backgrounded; the
  poll tier likewise runs only while foregrounded and only for servers with work.
- **I-RT8**: every consumer branches on an explicit `RouterRowState` member and an
  explicit presence member — no truthiness, no `!== 'loaded'`. A sixth row state
  must fail to compile or land in an explicit branch.
- **I-RT9**: the picker reads the **list tier** only (§8) — never `/props`, never
  `remoteCaps`. On a swap router `?model=<id>` *loads* the model, so a probing
  picker would load every model on the desktop just by being opened.
- **I-RT10**: the app never states that a load will evict a model.
- **I-RT11**: this work adds no writer of `remoteCaps`, `listCaps`, favourites,
  last-used or presence — it reads those surfaces and calls their owners' actions.
- **I-RT29**: an operation settles on a read; its caller is answered as soon as
  the answer is known. A withdrawal is known at the tap. Each waiter is
  resolved once, and a later settle of the same key answers nobody twice.
- **I-RT12**: **every operation settles**, every kind, with no exception —
  including one **superseded** by a second operation on the same model, which is
  answered rather than left waiting. The send path awaits that promise before it
  starts inferring, so an unresolved one is a chat that hangs with no error and
  no spinner.
- **I-RT13**: the reducer accepts **both** `status_change` and `model_status` on
  the same path. Neither may be dropped, and a build emitting only one must still
  reach a correct outcome — on reconcile timing, without live progress.
- **I-RT14**: **an operation whose desired end state is already true settles
  success and surfaces nothing.** A load at a resident row and an unload of an
  already-gone model both answer 4xx and both settle silently. An error shown for
  an action the user got what they wanted from is a user-facing defect, and both
  cases are on the ordinary path.
- **I-RT15**: endpoint existence is never inferred from router detection, nor from
  another endpoint's success. Only the stream's own status writes the cap, only a
  404 sets `'absent'`, and only `'present'` renders the download field.
- **I-RT16**: a row has **exactly one presenter**. An operation on the key
  presents it and the list is not read for a label; with no operation the list
  presents it. No stored state derives from an event: `RouterLive` has no
  `status`, so reading one does not compile.
- **I-RT17**: the list may claim a state only while the app believes it. Last
  fetch failed and none succeeded since ⇒ the row reads `unknown`, which renders
  as no claim.
- **I-RT18**: **a failure reason is never recorded from a row the app does not
  believe or reads as still in flight.** Every such record is built by a
  constructor over a row state — `loadFailureFrom`, `unloadFailureFrom` — never
  chosen beside one and never by a timing bound, which is what made the
  `unknown` case look unreachable rather than impossible. Both yield nothing for
  `unknown`; the load's also yields nothing while the row is still in flight.
- **I-RT19**: the resident count counts `loaded` and `sleeping` only.
- **I-RT20**: a list read that another has overtaken changes nothing — neither
  its rows nor its `stale` mark. Ordering is decided by `seq`, never by which
  read happened to answer last.
- **I-RT21**: overlay detail is scoped to the attempt in hand: starting an
  operation on a key clears what the previous one left there.
- **I-RT22**: **an operation the user withdrew records nothing, at every
  writer** — the reconcile verdict, the reach bound and the ceiling alike.
- **I-RT23**: server-supplied text reaches a surface as one capped line of
  plain text. The chat renders markdown, and a server's words are neither ours
  nor a stable contract.
- **I-RT24**: a surface that says nothing does so because it recognised a
  withdrawal, never because a string was empty. A withdrawal is a **fourth
  outcome**, `withdrawn`, set only where `op.cancelled` already gates; the
  engine's refusal carries it as a type. A `failed` that left no record is a
  different thing — superseded, abandoned, or settled off a row this build
  cannot read — and still owes the waiting turn an account.
- **I-RT25**: an operation is identified by its **attempt**, not by its key. A
  request that has been replaced settles nothing, writes nothing on the
  operation that replaced it, and asks the server for nothing. Every op start
  binds its attempt where a guard can reference it; inlining it into the
  literal is what left two writes unguarded.
- **I-RT30**: releasing a caller does not release the key. A withdrawal owes an
  unload, and no load is posted for that key until it lands — otherwise the two
  race on the wire and the second replaces the operation carrying the
  withdrawal.
- **I-RT26**: no verdict is read from a list read that began before the
  request — in **either** direction. An uncorroborated success means keep
  waiting, never declare failure.
- **I-RT27**: server-supplied text is escaped, never rewritten, for a markdown
  surface; **every** surface gets it as one line with nothing invisible in it,
  and quoted rather than run together with the app's own words. Identifiers a
  user retypes survive intact, and a bare address does not autolink. Escaping
  `.` is load-bearing beyond markdown: it is what defeats the link-preview
  path's own URL pattern, which never reaches the markdown renderer.
- **I-RT31**: the readiness outcome is read in exactly one exhaustive place.
  The union is not compiler-enforced on its own, and both consumers were
  if-chains whose fall-through meant **ready** — the most dangerous default
  available.
- **I-RT28**: nothing this work renders sits at the window's bottom edge. The
  navigation bar draws there, and a control under it cannot be tapped.

### Component renders

| Component | Renders | Does NOT render |
| --- | --- | --- |
| the picker (`RemoteModelSheet`) | on a router, **including one listing nothing**, where the groups render empty: Loaded / Downloading / Available; **a row for every model the server lists plus every model this app has an operation or an unread failure about**, since a download has no row of its own until the weights land; per row, whichever of the operation or the list is presenting it — its label, its progress bar and its one action; an Unloading… affordance while an unload converges; the resident count; the download field **only** while the cap is `'present'` | anything at all on a non-router server; the download field on a server whose stream has not answered 2xx; the word "sleeping"; a named eviction victim; an unconditional advisory; a slot count; any `/props`-derived value; **any error for a load at a resident row or an unload of a model already gone**; a state label for a row whose last fetch failed; a Load for a model the server is already loading or has no row for; **two labels for one row** |
| chat, while the send gate waits | a preparing affordance from the same operation state — determinate when `progress.value` is present, indeterminate otherwise, with a cancel — rendered **inside the chat input container**, above the input, where that container's own safe-area padding keeps it clear of the system navigation bar | a second progress source; a retry button; anything at the window's bottom edge; anything at all for an operation the user withdrew |
| chat, when the gate refuses | the failure record the operation left, through the same label the picker row uses, with any server-supplied words as one capped line of plain text | any copy of its own; **anything at all where the operation left no record** — a withdrawn request is not news about the server; unbounded or markdown-active server text |
| chat, when the engine backstop refuses | nothing for a withdrawal, which the catch recognises **by type**; the record's text otherwise | a decision taken from the message being empty — the generic arm still reports an error that happens to carry none |
| `ModelCard`, `ChatPalModelPickerSheet` | unchanged | router status |

A row is **not** one accessibility target. Each control in it — Load, Unload,
Cancel, the favourite star — is reached on its own, because a focusable row
swallows all of them and activating any one of them selects the model instead.

Rows group by state **first** — Loaded, then Downloading, then Available — and
sort inside each group by favourites, then last-used, then existing order. A
favourite that is not loaded stays in its group. Downloading is a third group
between the other two because a downloading row is not selectable and Available
would offer a dead action (D-RT25). Per-model copy must **not** use the word
"sleeping": that word is reserved for whether a whole server is awake, and the
two would read as contradicting each other (D-RT17). Server presence is the outer
state; a row's state is only meaningful inside a server that answers.

### Edge cases

| Edge case | Behaviour |
| --- | --- |
| A build emits `status` with no `value` | Still router evidence; the row reads `unknown` — Available, Load offered, **no state claim rendered**. Degrades per row rather than dying silently. |
| A router listing no models at all | Detected anyway, by the absent `models` key. The picker renders its groups empty and, on a build with a download endpoint, a first model can be fetched from the phone. Never reproduced; kept fail-open. |
| A sixth `status.value` in a future build | Maps to `unknown`. Detection is unaffected because it keys on the object, not the value. |
| `progress.value` stalls or jumps | Rendered as reported. A stalled value is never read as failure; only a reconciled row settles anything. |
| The server stops answering mid-load | The operation settles at `ROUTER_UNREACHABLE_MS` carrying the request failure. The row is then presented by a list nothing has corroborated since, so it reads `unknown`: no state label, under Available, not counted resident, with the reason row saying the server could not be reached. |
| The load ceiling fires with the row still `loading` | The operation settles and stops holding the send path, recording `wait-stopped` — the wait was ours and its ending is what is reported, with no claim about the model. The row goes on saying `loading` — presented by the list now — and offers no Load. |
| A cancel on a server that has stopped answering | Nothing is recorded, at any writer. The reach bound would otherwise announce "could not reach this server" ninety seconds after a request the user retracted. |
| Two reads of one server overlap and the slower fails | The failure is discarded: a later read already answered. Without that, the list a success had just installed was marked stale by a failure that predated it. |
| A load is retried after one that reported progress | The bar opens indeterminate. Detail is cleared when the operation starts, so the previous attempt's fraction cannot render as this one's. |
| The user cancels a load from the chat screen | The operation settles with no record, and neither surface says anything about the server. The send simply does not proceed. |
| A load settles on a row whose status value this build cannot read | The row reads `unknown`, the operation settles failed so nothing hangs, and **no reason is recorded** — the app has no reading to blame the model with. |
| `model_remove` for the model the session is bound to | The row leaves the picker, the binding is untouched, and the next send's gate finds no row and fails with an explicit reason. |
| Two servers with work in flight | Only the focused one streams; the other is on the poll tier. |
| An unrelated model changes state while a download is in flight | Adoption is declined: only an event of the **download** family can carry a download's id, and only while nothing has been heard about that download yet. A status transition moving the operation makes the next reconcile read the verdict off some other model's row, ending the download `ready` with the reference gone and no trace of it. |
| Two downloads started before either emits an event | Adoption is disabled — it needs exactly one in flight — so only an exact id match joins, and an unjoined operation stays `requested` and is bounded by W1 **under the download verdict**, never the load verdict, which would fail it at `ROUTER_ACK_MS` while it is in fact running. |
| A build that does not refresh its own list after a download | The grace window's re-reconciles are the only remedy; if the row never appears the operation settles failed. The reload flag is not used to rescue it: an unobservable write that can unload a running model is a worse trade than a rare honest failure on a build not yet seen. |
| The stream 401s on a key-protected server | The cap stays `'unknown'` — a 401 is about credentials, never about the build. No stream, poll tier only, download field still hidden. |
| `POST /models` 404s although the stream answered | Only reachable if a build ever ships the two endpoints apart. It settles as an ordinary definite failure carrying the server's reason; the shared-provenance inference is used only to hide the field, never to promise the endpoint. |

### Named residual — carried, not fixed

**An authenticated server renders a picker whose every action 401s.** Measured,
and **structural rather than incidental**: llama-server's auth is a
deny-by-default allowlist whose public set is exactly `/health`, `/v1/health`,
`/models`, `/v1/models` plus the embedded UI assets, so the reads this picker
needs are open by design while every router action is gated. The picker therefore
renders a complete and correct grouping on a server where nothing it offers will
work.

Nothing here is unsound: a non-2xx load settles as a definite failure carrying
the server's reason, an unload settles off the row, the stream's 401 is a stream
error and never a failed load, and the 401 leaves the cap `'unknown'` so the
download field is hidden rather than offered. What is missing is that a 401 has a
**different user remedy** — supply or fix the key — from a generic failure, and no
copy distinguishes the two. Recommended, not adopted: treat 401/403 on any router
action as its own reason class, resolved once per server rather than once per row.

**Absence is corroborated less than presence.** A stale list drops a present
row's *state*, but a model with no row still reads `absent`. `downloadVerdict`
distinguishes `absent` from every other state — a row that is not `downloading`
means arrived — so degrading absence would settle an in-flight download as a
success. Absence therefore stays a claim the app makes from a list it has just
failed to refresh. Unreachable today, because a download settles only from the
fetch success branch.

### Decisions

| ID | Decision | Rationale |
| --- | --- | --- |
| D-RT1 | Router detected from an already-fetched `/v1/models` body; no evidence ⇒ inert | Direct evidence, zero extra requests; unknown must not enable actions. |
| D-RT2 | `serverModels` stays the single list; `/models` is never a list source | A second list can disagree with the one capabilities derive from. |
| D-RT3 | `GET /models?reload=1` is never issued | Unobservable write, measured unnecessary, and it can unload a running model. |
| D-RT4 | The stream is an accelerant; outcome truth is the reconciled list | Stream failures must cost progress detail, never outcome. |
| D-RT5 | The live overlay is its own map, not a write into `serverModels` | A third writer of the list is how the stale-list defect happened. |
| D-RT6 | ~~An overlay entry wins while newer than the fetch that started before it~~ — **superseded by D-RT67** | The ranking was the second answer; three rounds of tuning it failed in the same place. |
| D-RT7 | At most one SSE connection app-wide, scoped to a focused server | N sockets to N desktops is unacceptable on a phone. |
| D-RT8 | Stream closed on background; reconcile-then-reopen on foreground | The event may already have happened; reconciling answers, waiting does not. |
| D-RT9 | Stream bounded by a byte and duration budget, then reopened | A long-lived XHR accumulates the whole response; reopening is safe. |
| D-RT10 | Event type read from the payload's `event` field, not SSE framing | One representation; the existing parser yields `data:` lines only. |
| D-RT11 | One idempotent readiness entry point; four triggers, one request | Activation, picker, send and engine must never double-post a load. |
| D-RT12 | The load fires detached at activation and is awaited at send | Activation stays instant; the first message cannot outrun the load. |
| D-RT13 | An explicit load precedes the completion | No sane request timeout covers a multi-gigabyte load. |
| D-RT14 | No app-side deadline on a load the server reports as in progress | A deadline there recreates the spinner-until-timeout defect. |
| D-RT15 | Watchdogs bound the app's ignorance, not the server's work | They arm on phase and only ever ask. |
| D-RT16 | `sleeping` counts as resident for grouping, and a load is still attempted | Waking re-reads weights; grouping and readiness are different questions. |
| D-RT17 | Per-model copy never uses the word "sleeping" | Reserved for server-scoped presence; the two must not read as contradictory. |
| D-RT18 | No eviction dialog; resident count only | `--models-max` and LRU recency are not on the wire, permanently. |
| D-RT19 | Unload confirmed only for the bound model; the session is not torn down | The next send re-loads it; nothing is destroyed. **Deferred, not shipped** — the copy is not carried, because a string with no caller reaches translators as work on a screen nobody can open. |
| D-RT20 | The download entry is one `owner/repo[:QUANT]` field | The model browser's unit is a file; the wire's is a repo-and-quant tag. |
| D-RT21 | Download progress aggregated; the denominator may grow; the bar is determinate once a total is in hand and the byte totals are shown beside it | Parallel files arrive late; bytes explain the movement honestly, and a bar left indeterminate beside a parsed total is throwing away what was measured. |
| D-RT22 | Cancelling a download posts to `/models/unload` | The wire's own contract; not derivable from the endpoint's name. |
| D-RT23 | A post-load capability refresh is a gated caller into the existing writer | Must be correct without it; never a second writer. |
| D-RT24 | Slot count is surfaced nowhere here | Probe-tier, and no pre-activation surface may read it. |
| D-RT25 | Downloading is a third group between Loaded and Available | A downloading row is not selectable; Available would offer a dead action. |
| D-RT26 | A send-path gate **and** an injected engine-level backstop | Structured output is a second production caller; the gate must be structural. |
| D-RT27 | An operation is `active` only on server corroboration, never on a 200 | The 200 says accepted; the child can still never start. |
| D-RT28 | Every watchdog expiry issues a reconcile and reads the verdict off the row | Silence is not evidence; only the list may settle an operation. |
| D-RT29 | Router evidence keys on a `status` **object**, or on the absent `models` key | Keying on the value would let one wire change silently kill the feature. |
| D-RT30 | `RouterRowState` is the modelled union; the wire value maps totally, `unknown` is a member | Exhaustiveness must aim at the states consumers actually branch on. |
| D-RT31 | A poll tier for any server with work in flight and no stream | The only existing reconcile fires on a foreground transition, throttled to a minute. |
| D-RT32 | The eviction note appears only after an observed unrequested unload | An unfalsifiable permanent warning is the rejected dialog, one severity down. |
| D-RT33 | A lone in-flight download adopts the id of its first event | The server may normalise the typed reference; otherwise the row strands. Narrowed by D-RT60. |
| D-RT34 | A load at a resident row settles ready on the 400, silently | Measured: a sleeping model answers "already running"; resident is not failure. |
| D-RT35 | The reducer takes `status_change` **and** `model_status`, the former primary | Measured: the documented name carries the acknowledgement only, no transitions. |
| D-RT36 | A non-2xx router operation is resolved by the observed row, never by the message | Message strings are not a contract; the row is. |
| D-RT37 | The unload verdict is inverted, separate, and read off the end state | The load mapping would report success on the exact failure being guarded against. |
| D-RT38 | A 200 on any router operation means "accepted, now converge", never "done" | Measured: the row lags after every unload, correct ones included. |
| D-RT39 | The unload is bounded by a settle window clearing the wire's 10s stop timeout | A never-terminating operation is worse than the defect being fixed. |
| D-RT40 | A `requested` download is bounded by W1 under the **download** verdict | The load verdict would fail the second of two simultaneous downloads. |
| D-RT41 | Measured wire facts cite the committed captures, not the published reference | The reference is wrong on five points; re-derivation already produced one error. |
| D-RT42 | The download payload map is read from `data.progress`, not `data` | Measured: the reference nests it one level too shallow. |
| D-RT43 | No download verdict from either terminal event; presence in the list decides | Measured: both fire for outcomes opposite to their names. |
| D-RT44 | A grace window of re-reconciles, not a reload call, guards the empty first look | Observable, side-effect-free, and it prevents a false download failure. |
| D-RT45 | A write whose effect cannot be observed landing is not shipped | This server accepts regardless; an ignored write would ship green for ever. |
| D-RT46 | A body with no top-level `models` key is router evidence on its own | Detection must be a property of the **response**, not of a sample of its rows. |
| D-RT47 | A download settles off fresh corroboration or its own absolute ceiling | The poll tier has no events and an unverified row, so silence there is not evidence. |
| D-RT48 | Only a **404** on the stream is remembered; 401 / 400 / 500 never are | A 404 is a fact about the build; the others are about credentials, the request, the moment. |
| D-RT49 | The download field renders only while the stream has answered 2xx | Both endpoints shipped in one commit; an affordance that always fails is worse than an absent one. |
| D-RT50 | Indeterminate progress on a no-stream build is stated and tested | Luck that works is still luck; only designed behaviour survives a refactor. |
| D-RT51 | Per-build behaviour measured once is labelled unverified and fails safe | "Unverified, fails safe" is an engineering answer; "measured" is not, when one build was measured. |
| D-RT52 | Numeric wire fields are presence-checked, never truthiness-checked | Measured: the first tick of a real load reports `0.0` and of a real download `0`. See §8a's *Absent is not zero*. |
| D-RT53 | "Reconciled after this request" is a fetch **counter**, not a clock comparison | Two events in one millisecond are ordinary; a counter is exact whatever the clock's resolution. |
| D-RT54 | A failure's cause is modelled; the server's words ride alongside as a message | The copy belongs to the app and the wording does not; a cause also survives a reworded refusal. |
| D-RT56 | A deliberate close and a stream ending are separated in the transport, not downstream | One signal for both makes the cleanup that closes the stream reopen it. |
| D-RT57 | Reopen on a transport ending, never on an HTTP status, at a bounded per-peer rate | iOS ends an idle stream as an error with no status; a refusal only refuses again. |
| D-RT58 | The stream is claimed before the Keychain read, not after | Two callers in that window each opened a request and only one handle survived. |
| D-RT59 | Every verdict reads the reconciled row; none reads the live overlay | Settling off the overlay is settling off an event, which no verdict may do. |
| D-RT60 | A download's key is adopted only from a download event about a model the list does **not** carry, only from its first, and only when it is the server's only download | A wrong adoption reads the verdict off another model's row: the operation settles ready and disappears while the fetch runs untracked. Counting only the operations nothing has been heard from lets a fetch the desktop started rekey ours. |
| D-RT62 | The stream is derived from what holds it — a watcher on screen, an operation in flight — and closed when nothing does | An opener with no owner leaves one chat message holding a socket for the life of the process. |
| D-RT63 | A scheduled reopen lives in the stream's state, not in a timer beside it | Nulling the state before arming the timer put the reopen beyond every release path by construction. |
| D-RT64 | A state read off the reconciled list is its own type; verdicts and the send gate take only that | A call-site convention drifted twice, and reverting the corrected site left the suite green. |
| D-RT65 | ~~An in-progress overlay ends with the operation that produced it~~ — **superseded by D-RT67** | It existed only to defuse a stored status, and the overlay no longer carries one. |
| D-RT66 | A cancel settles the operation; a load carries its own ceiling | The send path waits on the promise, and every healthy list read re-arms the watchdog of a wedged load. |
| D-RT61 | Reconcile requests coalesce per server; the overlay is pruned by the list that just answered | A progress stream is many prompts a second, and the overlay is keyed by ids the server chooses. |
| D-RT55 | An operation the app could never re-read the list for settles failed at its own bound | Otherwise a server that stops answering entirely leaves work in flight for ever, breaking I-RT12. |
| D-RT67 | A row has one presenter at a time: the operation while there is one, else the list — and the list may claim a state only while the app believes it | Two sources answering one question needed a tie-break, and the tie-break is what failed three times. Deleting the overlay's status makes reading one a compile error rather than a rule to remember. |
| D-RT68 | A failure record is built from the row the operation settled on; a row in flight or `unknown` yields none | "This model did not load" is a claim about the model; stopping our own wait is a fact about us, and `unknown` is the absence of a claim to derive one from. Making the record unconstructible removes both the call-site judgement that got it wrong and the reliance on one bound firing before another. |
| D-RT71 | Recording nothing and having nothing to say are different questions: a wait that ends records that it ended | A message on screen waiting for an answer makes silence unavailable. The constructors govern what may be *claimed*, not whether to speak. |
| D-RT75 | A withdrawal reaches the chat's error handling as a type, not as an empty message | Suppressing on an empty string reads an outcome out of an absence, and the absence has a second cause — a native throw carrying no message — which would then disappear silently. Discriminated the way a cancelled download already is. |
| D-RT72 | A list read another has overtaken changes nothing, in either branch | `seq` exists to decide their order; a branch that ignores it decides by arrival time, and the tiers plus the foreground path make overlap ordinary. |
| D-RT73 | Overlay detail is cleared when an operation starts | It is keyed by model, not by attempt, and the prune cannot reach a retry's row because that row is listed. |
| D-RT74 | Server-supplied text is **escaped, not stripped**, for the markdown surface only, and bounded at the parse boundary | Stripping the characters that spell a link left the attack — an address autolinks without them — and destroyed identifiers people retype. Escaping keeps every character on screen and gives none of them meaning; escaping the colon is what stops the autolink. Verified by rendering through the pinned renderer, not by reading the pattern. |
| D-RT76 | No verdict is read from a list read that began before the request, in either direction | Gating only the success left the failure branch reachable with a `loaded` row, which is a worse answer than the false success it replaced. |
| D-RT77 | An operation is identified by its attempt, not by its key | A replaced request is still in flight and still answering, and its answer landed on the operation that replaced it — a false failure at one site, a false success at the other. |
| D-RT78 | The preparing affordance renders inside the chat input container, never at the window's bottom edge | Measured: at the edge the navigation bar draws over it and takes the tap, so the cancel was unreachable under three-button navigation. That container already derives its padding from the reported inset, so no value is assumed. |
| D-RT81 | The bottom inset of the chat input container is unconditional | It is load-bearing twice: the keyboard translation already subtracts it, and it is what keeps the container's contents clear of the navigation bar. The branch that skipped it when the keyboard was open was dead, and wiring it up would have restored a measured unreachable control. |
| D-RT82 | A withdrawn operation presents as the unload it posted, not as nothing | Removing a false affordance twice left a row that said nothing at all for as long as the reach bound took. Cancelling posts an unload; saying so is both true and an acknowledgement. |
| D-RT80 | Releasing the caller and settling the operation are separated: a withdrawal answers the caller at the tap, the operation still settles on a read | Two questions ran through one event, so a withdrawal on a quiet server suspended the send path to the reach bound. D-RT66 is unchanged and still governs settling; this removes a second question it was covering by accident. |
| D-RT79 | A withdrawn operation stops presenting, though the store keeps it until a read confirms the row | On a server that has gone quiet the reach bound takes ninety seconds, and presenting it offers a cancel that cancels nothing for a request already retracted. |
| D-RT70 | The unload's settle bound reads the row and builds its record through a constructor, the mirror of the load's | A bound that consults only "a fetch succeeded since" claims something about a model it has not looked at. Two writers of one record class, one guarded and one not, is how the guarded one silently stops mattering. |
| D-RT69 | Both surfaces render the one record, through one shared label, and say nothing where there is none | Chat had copy of its own, so a load the user cancelled told them the server had failed to make the model ready. The engine's refusal, which must carry a message, names the wait instead of the server. |

---

## 10. Pairing a server, and per-server presence

Scanning a QR code (or opening a `llama://` link) to add a server, the
four-value presence a server carries afterwards, and the per-server model
declarations that ride along. Ids here are prefixed: **`D-QR` / `I-QR`** for
pairing, **`D-PR` / `I-PR`** for per-server runtime state.

### 10a. Pairing

**One grammar, four forms, one parser.** `parsePairingURL` in
`src/services/pairingLink.ts` is the only site that parses or validates a
pairing payload, for both the scanned string and the deep link. Pure, never
throws.

| Form | Example | Maps to |
| --- | --- | --- |
| absolute http(s), path optional | `http://192.168.1.5:9931/` — what the producer actually emits | the url as parsed |
| `llama://` route | `llama://add-server?url=&key=&name=` | url / key / name |
| `llama://` authority | `llama://192.168.1.5:9931`, `llama://host` | `http://host[:port]`, port 9931 when absent |
| bare authority, scanner only | `192.168.1.5:9931` | `http://host:port`; an explicit port is required |

A trailing slash and an empty path are accepted, never disqualifying; a
non-empty path is kept; query and fragment are dropped; userinfo rejects the
whole payload. **The producer read from source** encodes the web-UI root —
`http://<host>:<port>/` — with no key, token or query parameter, so no test may
assume a key-bearing QR. The route's optional `key` exists because that scheme
is ours, not because anything emits one.

**Delivery is three registrations, and any one of them silently voids the other
two**: the Android intent-filter (`scheme="llama"`, `host="add-server"`), the
app's own `CFBundleURLTypes` dict, and `AppDelegate`'s scheme allow-list, which
carries the **warm** path only — a cold launch is already forwarded unfiltered.
A typo in any of them produces no error at all; the link simply never arrives.

**The verdict is proved on a resource the server actually gates, and gatedness
is measured on *this* server.** Presence and pairing ask different questions at
different moments, and the pairing answer is not reachability: a 401 server is
`reachable` **and** not pairable.

At most four requests, in order:

| # | Request | Answers | Issued when |
| --- | --- | --- | --- |
| 1 | `GET /v1/models`, key attached | reachable? readable? how many models? which type? | always |
| 2 | `GET /` — `detectServerType`'s Ollama probe, **no key attached** | is this Ollama? | step 1 was readable and neither the `Server` header nor `owned_by` settled the type |
| 3 | the type's gate, key attached | are these credentials *refused*? | the detected type has a measured gate |
| 4 | the same gate, **key omitted** — the control | is that resource gated on this server at all? | step 3 returned 2xx **and** a key is held |

Step 2 belongs to `detectServerType`, not to `probePairingTarget`, which is why
counting from the pairing function alone gives three. It carries no
credentials, so the confirm step can put **four** unauthenticated requests to
an attacker-chosen host before the user has agreed to anything.

The gate is a **bare, status-only `GET /props`** for a detected `llama.cpp` and
for the unknown type, and **none** for `LM Studio` / `Ollama`, whose gating this
lane has not measured. It is keyed on the **detected** type, never the seeded
one: seeding maps unknown to `'unknown'`, which matches no row and would issue
no gate at all — silently, because "no gate" is a normal passing verdict.

Step 1 yields one of `usable` / `unauthorized` / `unreadable` / `server-error` /
`unreachable`. `unreadable` is a **third bucket, not a stricter empty rule**: a
2xx whose body does not parse, or parses without an array `data`, is not an
empty server. Collapsing the two pairs a captive portal as an empty router.

**The scanner has two independent preconditions, and permission is the one that
bites.** `useCameraDevice('back')` reports **hardware**; it says nothing about
permission, so a sheet gated on it alone mounts `<Camera>` unpermitted and
renders a black rectangle with no system prompt — on every fresh install.

`react-native-vision-camera`'s status enum is
`granted | not-determined | denied | restricted` (`src/Camera.tsx:30`), but
`useCameraPermission()` exposes none of it: it collapses to
`hasPermission = status === 'granted'` and re-reads on every `AppState` change,
so a grant made in Settings while backgrounded lands by itself. iOS produces all
four values; **Android produces three** — `restricted` never occurs
(`core/types/PermissionStatus.kt:5-8`) — and Android reports **`denied` on a
fresh install**, indistinguishable from a permanent block, because
`getPermission` downgrades to `not-determined` only while
`shouldShowRequestPermissionRationale` is true (`CameraViewModule.kt:196-203`).

That is why the sheet **asks the OS and then reports**, reading only the boolean:
copy keyed on the enum would tell a first-run Android user to visit Settings
before anything had asked them.

| Camera state | Sheet |
| --- | --- |
| `granted` + back camera | `scanning`; the only path that mounts `<Camera>` |
| `not-determined` | request on open; `manual` meanwhile, **no permission sentence** until the request settles |
| `denied` | request on open; once it settles unsuccessfully, `manual` with the Settings sentence |
| `restricted` (iOS only) | the two-valued request result resolves `denied`; same as above |
| no back camera (orthogonal) | `manual` with the hardware sentence, which **takes precedence** — a device with no camera is not told to visit Settings |

Two sentences, never one: "no camera on this device" is false about a camera the
user declined to share, and "allow it in Settings" is false advice on a device
that has none. Hardware absence is currently near-unreachable on a real device —
the manifest declares `android.permission.CAMERA` but no
`<uses-feature … required="false"/>` — so **permission** is what makes manual
entry reachable today.

**Where the sheet lives, and where a link therefore lands.** The sheet is
mounted by the Models screen — the same screen the FAB opens it from — because
pairing does not end at the sheet: `onPaired` hands the new server's id to the
remote-model picker so the user chooses a model on the server they just added,
and that picker lives there too. A `llama://` link consequently **navigates to
Models** as it parks its request; parking alone would foreground the app
wherever it already was, most often Chat, and the sheet would surface only once
the user happened to walk to Models. This is the opposite choice from
`hub/run`, whose host is global (`context/architecture/deep-linking.md`): that
route's flow ends inside its own sheet, so it has nothing to be near.

**The confirm step is a form the user leaves by pressing a button, and no
operation that press starts may decide whether the press counts.** The key
field sits above Add, so the press that reaches Add leaves the field first. Any
design in which leaving the field starts a probe, and a probe in flight
disables Add, loses that press — user-visibly, "Add does nothing the first
time". Narrowing *when* the blur re-probes only narrows who hits it: an
untouched key is a no-op, but the key-protected flow (scan, type a key, press
Add) is precisely the one that touches the field.

So the trigger is removed rather than conditioned. A probe is started by
exactly two things — accepting a payload, and pressing Add — and the press
awaits its own answer:

- The settled verdict is stored **with the key it ran with**. It is displayed,
  and it enables or blocks Add, only while that key is still the one in the
  field. A key edited past a verdict leaves the sheet making no claim, which is
  the honest state: nothing has checked it.
- Add is disabled only by a **settled refusal for the text now in the field**,
  never by an operation in flight. Pressing it re-checks the typed key when no
  settled verdict covers it, joins the probe already running when one is in
  flight for that key, and saves or returns to the confirm step on the answer.
- The sheet's scroll view keeps taps while the keyboard is up, so the press is
  not spent dismissing it instead.

**Focus follows the verdict, not the mount.** `autoFocus` on the key field
raised the keyboard as the sheet opened, which pushed the address behind the
opaque header: on the deep-link path the user pressed Add on a host they could
not see. The field is focused imperatively, and only once the server has
**refused** the credentials — the one moment the key is what the user has to
change. Both entry steps are reachable from each other, and the confirm step
has a way back to the one it came from, so a stale code is not a dead end.

**Superseded.** The imperative focus was removed once it was measured landing
in one device attempt out of five; I-QR16 and D-QR24 are the current state.

#### Invariants

- **I-QR7 — The camera mounts behind both preconditions.** `<Camera>` renders
  only when `hasPermission && device`. There is no other route into the scanning
  state, and no render path shows a camera surface without both.
- **I-QR1 — Single parse point.** One helper parses and validates a pairing
  payload for both the QR and the deep-link path. `DeepLinkService.parseURL` is
  not extended and `parseHubRunURL` is not widened.
- **I-QR2 — The dispatcher is scheme-scoped, and each route parser is
  additionally scheme-gated.** `handleDeepLink` rejects any scheme it does not
  route before reaching a route branch — that is what covers the `chat` route,
  which is selected by host alone and has no parser. `parseHubRunURL` /
  `isHubLink` / `parsePairingURL` each reject a url whose scheme is not their
  own — that covers the raw-`Linking` path, which never enters the dispatcher,
  and the iOS cold launch, where no native code filters the url at all. The
  per-parser gate is **must-not-remove**, not defence in depth.
- **I-QR3 — Validation precedes side effects.** A parsed request produces zero
  store writes; `addServer` / `setApiKey` run only from the user's confirm tap.
  A scanned API key reaches only the Keychain, never `ServerConfig`.
- **I-QR4 — `authorised` requires an explicit refusal of the control, and
  nothing weaker.** Exactly 401 or 403, and only when a control was issued.
  Every other outcome — any 2xx, 404, any other status, a transport failure, a
  timeout, no control at all — is `unconfirmed`. **`!control.ok` is the
  forbidden predicate**: the control clamps to `PROPS_TIMEOUT_MS`, so a timeout
  on a slow LAN server is ordinary, and reading a non-answer as a refusal pairs
  a key-protected server as authorised whose first chat then 401s.
- **I-QR5 — At most two `/props` requests, both bare and status-only.** The gate
  and the control. Neither parses a body, neither writes `remoteCaps`, and
  neither carries `?model=`. The capability model keeps sole ownership of that
  surface.
- **I-QR6 — No pairing verdict is remembered.** It lives in sheet state and is
  recomputed by every re-probe. Only the `serverType` **seed** persists, and it
  is not a verdict.
- **I-QR8 — A verdict is about a key, and speaks only for that key.** Every
  settled probe is stored with the key it ran with. It may be rendered, and may
  enable or block Add, only while that key is still the one in the field.
- **I-QR9 — No press is invalidated by work the press itself starts.** Add is
  disabled by a settled refusal for the text in the field and by nothing else —
  never by a probe in flight, and never by a blur. Leaving the key field starts
  no request at all.
- **I-QR10 — The newest probe settles the verdict.** Each probe carries a
  generation; one that returns after a newer one started writes nothing. Order
  of settling is not order of starting, and a stale `usable` landing after a
  fresh `unauthorized` would leave Add enabled on credentials the server has
  refused.
- **I-QR11 — Camera permission is requested only where the camera can be
  reached.** A sheet opened at the confirm step by a link never asks: iOS
  prompts once for the life of the install and two Android denials are
  permanent, so spending the prompt on a path that mounts no camera spends it
  for good.
- **I-QR12 — The delivery paths gate on the scheme, the scanner on the
  grammar.** `isPairingLink` (scheme `llama:` only) is what the raw-`Linking`
  route tests. `parsePairingURL` also accepts an absolute http(s) url and a
  bare `host:port`, which are scanner payloads; routing on a successful parse
  opens the pairing sheet for any http link the OS hands the app.
- **I-QR13 — A deep link never reaches a log line intact.** Both deep-link log
  sites render params through one helper that keeps the scheme, the host and
  the **names** of the query parameters. The raw url is never logged: it
  carries the same query string the pairing route puts an API key in, and the
  app strips no console calls in release.

#### Decisions

| ID | Decision | Rationale |
| --- | --- | --- |
| D-QR1 | `llama://add-server?url=…` is our route; the QR carries http(s) | The scheme is ours to define; the producer emits a plain url. |
| D-QR2 | Registration host-scoped on Android, parsing liberal | Every form still ends at the same user confirm. |
| D-QR3 | Port 9931 defaults only for the `llama://` authority form | An `http://host` payload must keep URL semantics. |
| D-QR4 | Scheme-gate the dispatcher, and each route parser as well | Android and the iOS cold launch bypass the dispatcher; `chat` has no parser. |
| D-QR5 | A schemeless bare authority requires an explicit port | Portless dotted text would surface a sheet for any QR. |
| D-QR6 | `AppDelegate`'s allow-list is exact-match, never a wildcard | A catch-all diverts Google Sign-In callbacks out of the `return false` path its SDK needs. |
| D-QR7 | Authorisation is never inferred from a **2xx** on `GET /v1/models` | Measured: llama.cpp answers 200 with the full catalogue to an unauthenticated caller. |
| D-QR8 | The gate is bare `GET /props`, status only, never `?model=` | A scoped `/props` **loads** an unloaded model on a swap router, and pairing cannot tell an unloaded model from a sleeping one. |
| D-QR9 | Gatedness is measured per server via a keyless control, not inherited | The upstream allowlist has moved between builds, and non-llama.cpp servers have no such allowlist at all. |
| D-QR10 | Authorisation is three-valued; `unconfirmed` pairs without claiming a check | The ordinary working case — a keyless server — produces `unconfirmed` permanently; blocking it would block the headline path. |
| D-QR11 | A 2xx without an array `data` is `unreadable`, a third bucket | A lenient parse turns a captive portal into an empty router with Add enabled. |
| D-QR12 | A duplicate url offers the saved server and writes nothing | A silent url / key overwrite is the worse failure. |
| D-QR13 | A new sheet, not an extension of the model picker | That file is a sibling item's; a rewrite exceeds the one-touch budget. |
| D-QR14 | Ask the OS, then report: `requestPermission()` on open, and only `hasPermission` is ever read | The hook exposes no more than the boolean, and the underlying enum conflates a fresh install with a permanent block on Android. |
| D-QR15 | Leaving the key field starts no probe; pressing Add re-checks the typed key and awaits the answer | Conditioning the blur only narrows who loses the press: the key-protected flow always touches the field. Nothing an Add press starts may decide whether that press counts. |
| D-QR17 | The verdict is keyed on the API key it ran with, and shown only for the key in the field | A verdict about a different key is a claim nobody checked; silence is the honest state. |
| D-QR18 | Focus is imperative and driven by a refusal, replacing `autoFocus` — **superseded by D-QR24**: the request was removed, and I-QR16 is the current state | Focusing on mount raised the keyboard over the address the user is agreeing to trust, on the one path where an arbitrary link chose that address. |
| D-QR19 | Camera permission is requested only at an entry step, never on the link path | The prompt is one-shot on iOS and two denials are permanent on Android; the link path mounts no camera. |
| D-QR20 | The trust notice is shown on the pairing confirm, ungated by the acknowledgement flag | This is the one sheet an arbitrary link can open; a dismissal made in the sibling sheet was not a decision about this host. |
| D-QR21 | The raw-`Linking` routes gate on `isPairingLink`, not on a successful parse | The grammar is the scanner's and accepts any absolute http(s) url; a router built on it opens the pairing sheet for links addressed elsewhere. |
| D-QR22 | Deep-link logs carry the scheme, the host and parameter **names** only | The pairing route puts an API key in the query string, and no console stripping runs in release. |
| D-QR16 | A pairing link navigates to Models; the sheet is not hosted globally | Pairing continues into the remote-model picker, which is on that screen, as is the FAB opening the same sheet. A global host would strand the user after the save, or drag the picker out with it, and would give one sheet two mount sites. |

#### The action row, and the one thing focus cannot promise

**I-QR14 — Every button in the pairing sheet lives inside
`Sheet.ScrollView`, and the scroll body carries the bottom inset.** Two things
have to hold at once — clear of the keyboard, clear of the navigation bar — and
the shared footer delivers only the second.

`Sheet` sets no `android_keyboardInputMode`, so on Android the sheet window
pans and never resizes, and `Sheet.Actions` is a plain sibling pinned to the
sheet's bottom edge with nothing keyboard-aware about it. Measured on device
with the key field focused, the confirm step's Add sat 732 px below the top of
the keyboard: `waitForDisplayed` timed out at 30 s, and a raw display tap at
the button's own reported centre landed on the keyboard and saved nothing. Not
a lost first press — the button could not be pressed at all. `Sheet.ScrollView`
is a `KeyboardAwareScrollView`, and a control inside it is what scrolls clear.
Being inside it also puts those buttons back under
`keyboardShouldPersistTaps="handled"`, so the press is delivered on the first
tap instead of being spent dismissing the keyboard (D-QR15).

The navigation bar is **not** settled by that placement. `styles.body`, the
scroll view's `contentContainerStyle`, carries `paddingBottom: 10 +
insets.bottom` — the same number `Sheet/Actions.tsx` applies — but the same
number does not buy the same lift inside a scroll body, and it arrives short.
Measured at rest under three-button navigation on a 1080x2340 device, Add ends
at 2205 and Back at 2202 against a `navigationBarTop` of 2196: a 6–9 px
overlap, and a settled layout rather than an animation artifact. The controls
are still operable — a raw tap at the reported centre works — but a control
over the navigation bar is a defect. I-QR15 has the mechanism.

**`ServerDetailsSheet` has the keyboard defect and ships it.** Its
`save-server-button` sits in a `Sheet.Actions` footer, behind the keyboard by
the same measurement. Copying it is how the defect arrived here; a sibling is
an argument only once its behaviour has been checked. The wider repair —
`android_keyboardInputMode="adjustResize"` on the shared `Sheet`, with
`Sheet.Actions` offset — would fix both surfaces and needs device evidence
across every sheet in the app, which is why it is not made here.

**A refusal asks for focus; the platform may decline.** The imperative
`focus()` on the key field (D-QR18) is a convenience, not a contract. It has
been seen to land in one run and not in the two that followed, on the same
build and the same device — a first-frame race between the settled verdict and
the native view being ready to take focus, at its worst against a LAN server
that refuses in a millisecond or two.

It is left alone, deliberately:

- The failure degrades to **no keyboard**, which is the state the
  address-hidden defect wanted in the first place. The refusal text is on
  screen either way and the field is one tap from the user.
- Every available hardening is timing-shaped — a frame's delay, an `onLayout`
  hook, `runAfterInteractions` — and none can be shown to work. A unit test
  observes the `focus()` call, not whether the platform honoured it, and a
  one-in-three device flake cannot confirm a fix in any run count we would
  realistically do.
- `autoFocus` is not the fallback. It is the mechanism D-QR18 removed, and
  three separate defects traced back to it.

The three bullets above are the record of why the focus was kept while it still
worked sometimes; the rate has since been measured lower and the focus is gone.
"The refusal step asks the platform for nothing" below is the current state.

| ID | Decision | Rationale |
| --- | --- | --- |
| D-QR23 | The pairing sheet's action rows stay inside `Sheet.ScrollView`, which takes the bottom inset on its content | A `Sheet.Actions` footer is outside the only keyboard-aware container the sheet has, and the sheet pans rather than resizes: measured, its buttons are unreachable with the keyboard up. |
| D-QR24 | The key field is not focused on a refusal — the request is removed rather than hardened | It landed once in five device attempts, which is a promise the code cannot keep; hardening it is timing-shaped and unverifiable, and its absence is the state the sheet wanted anyway. See "The refusal step asks the platform for nothing". |
| D-QR25 | The shared `Sheet` keeps panning, and `ServerDetailsSheet`'s footer defect is left standing | Teaching `Sheet` to resize changes every sheet in the app; that is a wider claim than one pairing surface can evidence. |

#### Why a bottom inset inside `Sheet.ScrollView` arrives short

**I-QR15 — Inside a `Sheet`, anything at the tail of the scroll content is
pushed down by the height of the sheet's own header, and no amount of bottom
padding takes it back.** `Sheet` lays out its title/close header and the
scrollable as siblings inside gorhom's content mask, and that mask's height is
`sheetHeight - handleHeight`. Under `enableDynamicSizing` the sheet's detent is
`contentHeight + handleHeight`, where `contentHeight` is **only** what the
scrollable reports through `onContentSizeChange`. The header is inside the mask
but outside that budget, so the scroll viewport is permanently shorter than its
own content by the header's height, and the mask clips (`overflow: hidden`). At
rest the scroll offset is 0, so what is clipped is the *tail* of the content —
which is exactly where a bottom inset is put.

The geometry reduces to one line. With `H` the header's height and `T` the
content pixels that follow the control:

    control bottom on screen = sheet bottom + H - T

Measured on a Galaxy S23 (1080x2340, 480 dpi, three-button navigation) with the
sheet open at the confirm step: sheet bottom 2340, handle `[1327,1411]`, mask
top 1411, first content child top 1501 — so `H` is 90 px, a 72 px `titleMedium`
row plus the header's 6 dp margin. `T` is 225 px: `paddingBottom: 10 +
insets.bottom` (174 px), plus the 48 px that `styles.body`'s `gap: 16` puts
between the action row and the 1 px spacer view `KeyboardAwareScrollView`
appends after its children. `2340 + 90 - 225 = 2205`, which is Add's measured
bottom to the pixel. Dragged to the end of the scroll the same control sits at
2115 with all 225 px visible; the 90 px it gains is the clipped part, and it
equals `H`. The same equation puts `ServerDetailsSheet`'s `Sheet.Actions` — a
sibling laid out after the scroll view, so anchored to the mask's bottom edge
with `H` never entering — at `2340 - 174 = 2166`, which is what that sheet
measures.

Three consequences, and they are the trap:

- **Growing the content buys nothing.** The detent tracks the scroll content
  one for one, so every pixel added to the padding also lengthens the sheet.
  The shortfall stays exactly `H` however large the padding gets — a fixed
  point, not a constant waiting to be tuned.
- **Moving the inset between the content container and the action row changes
  nothing.** Padding after the last child and padding inside the last child put
  the same pixels after the control, so `T` is identical and so is the
  control's position. Padding on a bottom-anchored child lifts it off its
  container's bottom edge; padding on a child of an over-long scroll content
  does not, because the clip is at the content's tail rather than at the
  child's box.
- **The condition is `T >= H + insets.bottom`**, not `T >= insets.bottom`. Here
  that is 234 px against the 225 px on offer, which is the 9 px measured.

The clean repair is to make `H` zero by rendering the header inside
`handleComponent`: `handleHeight` is measured separately and *added* to the
sheet, so anything living there grows the sheet instead of taking from the
scroll viewport. That changes the shared `Sheet` and every surface built on it
— the same wider claim D-QR25 declined to make from one pairing surface.

Also noted, because it is a change to a case the inset does not appear in:
`styles.body`'s bottom padding went from a flat `24` to `10 + insets.bottom`,
so where there is no bottom inset the body's tail padding is now 10 rather than
24. That is `Sheet.Actions`'s own constant, which is the point — the two action
rows sit the same distance off the bottom edge either way — but the zero-inset
surface did move.

Worth knowing for whoever picks this up: the overlap is only 9 px because
`styles.body`'s `gap: 16` happens to fall between the action row and the
keyboard spacer and donates 48 px of lift by accident. Nothing declares that,
and nothing preserves it.

| ID | Decision | Rationale |
| --- | --- | --- |
| D-QR26 | The 6–9 px navigation-bar overlap is recorded and left standing rather than closed with a larger constant | The only local lever is the padding, and what it fights is a header height the sheet does not count; a number that clears it on one device is wrong on the next. The repair belongs in the shared `Sheet`. |

#### The refusal step asks the platform for nothing

**I-QR16 — Nothing in the pairing sheet takes focus on its own.** No
`autoFocus`, and no imperative `focus()`. A refused key is corrected by tapping
the field, which sits on the same step as the refusal that named it.

The imperative focus is gone rather than hardened. Across device runs it landed
in **one attempt out of five** — one of three, then none of two. D-QR18 kept it
on the reasoning that its failure mode was safe and no hardening could be
shown to work; the second half of that still holds, but "safe when it fails" is
a property of a fallback, not of something that fails four times in five, so the
first half was only doing work while the behaviour was real. Code that announces
an intent it does not deliver is worse than code that never claimed it: it
invites the next reader to tune a timing constant against a base rate that
cannot answer.

What that costs, and what it buys:

- **Nothing becomes unreachable.** The key field and the verdict are both
  children of `Sheet.ScrollView` on the confirm step, the field directly above
  the verdict text. Neither needs focus to be on screen, and neither can be
  scrolled to without the other.
- **The keyboard was not free here.** The sheet pans rather than resizes
  (I-QR14), so a keyboard nobody asked for covers the tail of the same scroll
  body the verdict and the action row live in. Removing the request makes the
  no-keyboard state the only state — which is what D-QR24 already called the
  safe one, and what D-QR18 wanted when it took the keyboard off the address
  the user is agreeing to trust.
- **The alternatives are still the alternatives.** `autoFocus` is the mechanism
  D-QR18 removed after three defects. Every remaining hardening is
  timing-shaped — a frame's delay, an `onLayout` hook, `runAfterInteractions` —
  and a unit test cannot separate them (the `focus()` spy fires identically
  with and without a delay) while a one-in-five base rate cannot be moved
  convincingly in any run count that is realistic to do.

The assertions now match what is actually observable: that no focus is
requested, and that the refusal text and the key field both render. Both fail
if the effect comes back.

**I-QR17 — The manual step's hint names a camera the user cannot use, and says
nothing when the camera works.** Three states, three renders: no hardware →
"no camera on this device"; hardware present with permission refused → "camera
access is off"; hardware present with permission granted → no hint at all,
because manual entry was reached by choice from a working scanner and the Scan
a code button next to it still works.

The selector is a **settled refusal** — the question answered, and the answer
no. Both halves are load-bearing, and each one alone is a different way of
saying something the device never said. `permissionSettled` alone printed
"Camera access is off. Allow it in Settings" directly above a scan route that
worked, for every user who typed an address by hand, because it turns true on a
grant as well as a refusal. `!hasPermission` alone prints that same sentence
while the OS dialog is still on screen, blaming the user for a refusal that has
not happened on the very frame the question is being asked. The hint is a claim
about the device, and a claim about the device may consult only what the device
has actually reported.


### 10b. Presence

Two types, and the split is the point. **Reachability** is what the last probe
learned and is stored: `unknown | reachable | unreachable`. **Presence** is the
public answer and is derived: `unknown | reachable | asleep | unreachable`,
folding the server's sleeping flag in at read time.

| reachability | sleeping flag | presence |
| --- | --- | --- |
| `unknown` | anything | `unknown` |
| `reachable` | `true` | `asleep` |
| `reachable` | `false` / `undefined` | `reachable` |
| `unreachable` | anything | `unreachable` |

The flag is read through one function, `readServerIsSleeping` in
`src/utils/serverPresence.ts`, which returns `boolean | undefined` and is
`undefined` for every server until the capability model carries the flag. Absent
is **unknown**, never *awake*.

`probeServerReachability` classifies at the wire layer — `/health` on llama.cpp,
`/v1/models` elsewhere — because the model-fetch path reduces a 401 and a dead
socket to two plain `Error`s differing only by message string, and a store must
not match on message text.

**Triggers, and no others**: the pairing confirm, remote-model activation,
foreground, a remote completion settling with an error, an explicit retry, and
the watch. The **watch** is owned by `ModelStore`, because every gate it reads
already lives there; it only *calls* the store's probe, so the write stays in
one place. It re-probes the active remote model's server on a 2/5/10/20/30-then-30 s
backoff while the app is foregrounded, a remote model is active, the bound
server is still configured and not reachable, and fewer than ten consecutive
failures have occurred. A **failure is any tick that did not end reachable**,
not only one that answered `unreachable`: a probe that cannot say what happened
is exactly the case the cap exists for.

Three implementation facts that are not free:

- The observable gates are read through **one reaction**; the failure cap is
  read **imperatively**, because the counter is deliberately non-observable and
  each tick re-enters the scheduler anyway.
- The timer handle stays set for the **whole tick**, not only until it fires, so
  it reads as "a tick is scheduled or running". Cleared when the timer fires,
  the probe's own presence write re-arms through the reaction *before* the
  failure is counted, and the cap never closes.
- **The watch is a record, not a bare handle.** A single nullable timer was
  asked to say three things at once — a tick is scheduled, a tick is running,
  and which server it is for — and it can carry only the first two. Missing the
  third produced three separate defects: a tick scheduled before the binding
  moved probed the **previous** server and charged the **new** one; a
  background/foreground blip during a probe left the in-flight tick to null a
  handle that by then belonged to a freshly armed timer, doubling the chain;
  and a probe that could not answer at all was never counted as a failure, so
  the cap never closed.

  The record names its server and is **replaced, not mutated**, when the
  binding moves, so a tick already scheduled can ask whether it still owns the
  watch — before it probes, and again before it re-arms. The failure counter
  stays outside the record, so backgrounding retires the generation without
  forgetting how many attempts have failed.

#### Invariants

- **I-PR1 — Presence is a named union and `unknown` is a member.** No API here
  returns a boolean about reachability, and no fold maps `unknown` to
  `unreachable`. Pre-probe and no-evidence are the same value, and it does not
  say "offline".
- **I-PR2 — An HTTP response proves reachability regardless of status.** A 401,
  a 404 and a 503 are all `reachable`; only a transport failure or abort is
  `unreachable`.
- **I-PR3 — `serverPresence` has one assign site and two callers**: the probe
  and a successful `fetchModelsForServer` promotion. Both snapshot `url` +
  `serverType` before the request and discard on a mismatch or a removed server.
  The `checkedAt` rule is **asymmetric** — a `checkedAt` that moved forward
  while the request was in flight discards the **probe's** answer only, from a
  baseline of `-Infinity` when no entry existed at start, and never the
  promotion's, which always writes because an arrived response outranks a
  transport failure. Read symmetrically the rule inverts into a second bug.
- **I-PR4 — Presence never gates an action.** It never disables Send, never
  blocks activation, never suppresses a request. It labels.
- **I-PR5 — Presence is not persisted.** A hydrated `asleep` is a claim about
  now that nobody checked.
- **I-PR6 — The wake is the completion.** No wake request exists, and no second
  timeout concept: a waking server is bounded by the same **raw**
  `requestTimeoutMs` as any other completion, never by the detached clamp.
- **I-PR8 — The watch's identity is checked, not assumed.** A scheduled tick
  probes the server named on the watch record it was scheduled with, and only
  while that record is still the live one. A tick whose record has been retired
  neither probes, nor counts a failure, nor re-arms.
- **I-PR9 — Discovery is invalidated by comparing canonical against canonical.**
  `updateServer` canonicalises the stored url as well as the incoming one. A
  record persisted before canonicalisation existed still holds its raw url, and
  comparing against it reads the first save of an unchanged server as a repoint.
- **I-PR7 — Two prune helpers, one per key shape.** `dropServerEntries` for maps
  keyed `${serverId}/${modelId}`; `dropServerKey` for maps keyed by the bare
  server id, on which the prefix test is a silent no-op.

#### Decisions

| ID | Decision | Rationale |
| --- | --- | --- |
| D-PR1 | Probe the server; no connectivity mirror | Transport state is a proxy; the server is the question. |
| D-PR2 | Classify transport-failure vs HTTP response at the wire layer | Stores must not classify on an error-message string. |
| D-PR3 | Four-value presence union, `asleep` folded in at read time | Unknown must never assert offline. |
| D-PR4 | Presence is not persisted | A session's reachability does not survive a launch. |
| D-PR5 | `/health` for llama.cpp, `/v1/models` otherwise | Cheap, and it cannot load a model. |
| D-PR6 | A bounded foreground watch, capped at ten failures | It is the network-change detector; unbounded polling is a bug. |
| D-PR7 | Detached probes clamp to `PROPS_TIMEOUT_MS`; user-initiated do not | An unclamped 600 s probe would hold the single-flight promise and swallow every tick. |
| D-PR8 | `ModelStore` owns the watch scheduler; `ServerStore` owns the write | Its gating inputs already live there, and the direction stays one-way. |
| D-PR9 | The failure counter is reset by the *answer*, not by the caller | A retry lives in a sheet and cannot reach a private scheduler field. |
| D-PR10 | The banner resolves inside the existing resolver, branch 0 | Two decision sites would break the one-banner invariant. |
| D-PR11 | A second prune helper for bare-server-id maps | The prefix helper no-ops on them, silently. |
| D-PR12 | The watch is a record carrying its server id, replaced when the binding moves | One nullable handle cannot say *which server* as well as *scheduled* and *running*; three defects came out of the missing third. |
| D-PR13 | The failure counter lives outside the watch record | A backgrounding must retire the generation without forgetting the attempts (edge case 10-h). |
| D-PR14 | Any tick that did not end reachable counts as a failure | Counting only `unreachable` leaves a probe that cannot answer uncounted, and the cap never closes. |
| D-PR15 | The watch stops as soon as the bound server is no longer configured | `removeServer` does not clear `activeRemoteBinding`, so the binding outlives the record it names. |

### 10c. Per-server model preferences

**Carried debt, stated rather than hidden.** At this revision this section
describes a surface with **no production reader**: `toggleFavourite` and
`remoteModelPrefsFor` have no caller, and `lastUsedRemoteModel` is written on
activation and never read. Both maps are nonetheless persisted, and the
signatures are frozen for the sibling item that consumes them. Two consequences
worth carrying forward: a persisted key with no reader is a migration liability
if the shape moves before the consumer lands, and the `asleep` presence string
plus the waking banner reach every locale for a state `readServerIsSleeping`
cannot report at this revision. Both are held for the consuming item, not
forgotten.

`favouriteRemoteModels` (keyed `${serverId}/${remoteModelId}`) and
`lastUsedRemoteModel` (keyed by the bare server id), both persisted, each with
exactly one writer. They are read through **one computed** and one accessor
returning a module-level frozen empty entry, so a row re-rendering for an
unrelated reason sees the same array identity. Favourites hold **bare** remote
model ids, so a picker row tests `includes(row.id)`; key order is not a
contract.

Both are pruned **only** by `removeServer` — favourites via the prefix helper,
last-used via the key helper. A url or `serverType` edit does **not** drop them:
they are user declarations, like the reasoning overrides. `lastUsedModelId` on
`ModelStore` stays untouched and is still never set for a remote model; it
drives local auto-reload at launch and is a deliberately different slot.

### Edge cases

| ID | Edge case | Behaviour |
| --- | --- | --- |
| 10-a | A QR that is not a server (Wi-Fi config, arbitrary text) | Fails the grammar → the scanner keeps scanning with a hint; no writes. |
| 10-b | A payload carrying userinfo | The whole payload is rejected; credential smuggling is not a supported form. |
| 10-c | `llama://<authority>` opened on Android | Never delivered — the intent-filter is host-scoped. Deliverable on iOS, where a scheme cannot be host-scoped; the per-parser gate is what makes that safe. |
| 10-d | Two rapid pairing links | The later one overwrites the parked request; both navigations resolve to the same screen. |
| 10-m | A pairing link fired while the app is on another screen, or cold | The handler navigates to Models, so the sheet opens where the link asked for it rather than waiting for the user to arrive. Before onboarding completes there is no such route and the navigation is dropped; the request stays parked and opens when the screen is first reached. |
| 10-e | No camera device, or camera permission not granted in any of its states | The sheet requests permission on open, opens on manual entry, and pairing still completes. The two causes carry different sentences: hardware absence never advises Settings, and permission never claims the device has no camera. |
| 10-f | A probe in flight when url or `serverType` is edited | The snapshot guard discards the answer and the prune drops the entry. |
| 10-g | The sleeping flag is unknown — always at this revision, and on any build predating server-side sleep | Presence reads `reachable`, never `asleep` and never `unreachable`. |
| 10-h | The app is backgrounded while the watch is running | The watch is cancelled and the timer cleared; the counter is kept; foreground re-probes. |
| 10-i | A favourite naming a model the server stopped listing | The key survives and is returned as-is; the picker simply has no row to mark. |
| 10-j | A freshly paired server too slow to wake | The default connection timeout applies to the first completion; the remedy is the per-server timeout on the server sheet, deliberately absent from the pairing sheet, which is a confirm and not a settings form. |
| 10-k | The gate answers 404, 400, 5xx, or times out | `unconfirmed`, and pairable: only a 401/403 blocks. |
| 10-l | The detected type is wrong, or is `LM Studio` / `Ollama` | No gate is issued and authorisation is `unconfirmed` — pairable, with no claim made. A mis-detected llama.cpp still gets the `/props` gate, because the unknown type shares its policy. |
| 10-n | `llama://host:9931/` — the authority form with a trailing slash | Accepted, like every other form; the authority and what follows it are separated before the grammar runs. A real path (`llama://host/v1`) is still refused, because the authority form has no slot for one. |
| 10-o | A server record persisted before canonicalisation, saved again unchanged | Both urls are canonicalised for the comparison, so caps, models and presence survive. |
| 10-p | A code that scans but names a dead server, or manual entry once the camera works | Both entry steps reach each other, and the confirm step steps back to the one it came from with what was typed intact, so neither is a dead end. |
| 10-q | A key typed into the confirm step and Add pressed straight away | The press re-checks that key and decides on the answer: saved when `usable`, back to the confirm step with the refusal otherwise. The press is never spent on the re-check itself. |
