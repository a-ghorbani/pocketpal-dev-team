# Remote Servers Flow

## Purpose

Remote (OpenAI-compatible) model traffic: the `ServerConfig` record and its Keychain API key, the `src/api/openai.ts` request layer (timeouts, the per-`serverType` reasoning wire), llama.cpp capability discovery (the `/props` probe tier and the `/v1/models` list tier), and the binding between a live remote session and its backend. Not covered: the reasoning capability model and pill (`chat-flow.md`, "Contracts and invariants", "Reasoning"), remote token accounting and the context banner (`chat-flow.md`, "Contracts and invariants", "Context banner", and the Traps entry "`used` counts the whole prompt, and unknown is not zero"), local-model capabilities (`model-loading.md`).

**Not on `main` yet:** #896 (llama-server router mode) and #897 (QR/link pairing, presence) add behaviour this doc leaves out. The sampler and `/props` layer described below arrives with the request-path restructure, which is stacked on #895; only `hasRouter` / `healthPath` are stated ahead of their PRs. The previous version of this doc described it, including measured router wire facts (`git show 1ad6ce1:context/architecture/remote-servers.md`); distill each part back in when its PR lands.

## Code map

| Path | Role |
| --- | --- |
| `src/api/openai.ts` | transport only: `fetchModelsWithHeaders` / `fetchModels` / `testConnection` (`GET /v1/models`), `streamChatCompletion` (XHR + SSE, transport body keys, two-phase timeouts) |
| `src/api/http.ts` | `normalizeUrl`, `buildHeaders`, `resolveTimeout`, `CONNECTION_TIMEOUT_MS`, `IDLE_TIMEOUT_MS` |
| `src/api/remoteImages.ts` | `encodeMessagesForRemote`, `hasLocalImageAttachment`, the base64 cache and its byte bounds |
| `src/api/servers/` | the dialect layer: `dialect.ts` (`ServerDialect`, `RemoteEndpoint`), `base.ts` (`openAICompatible`, `BASE_SEND_NAMES`, `sendSamplers`, `readTimingsFinish`), one file per type, `index.ts` (`DIALECTS`, `dialectFor`), `detect.ts` (`detectServerType`, `DETECT_TIMEOUT_MS`), `listCaps.ts` (`deriveListCaps` / `deriveListCapsMap`), `llamaCppListRow.ts` (the `/v1/models` row parser) |
| `src/api/llamaServer/props.ts` | `fetchServerProps` (`GET /props`), `PROPS_READ_NAMES`, `PROPS_TIMEOUT_MS` |
| `src/api/sseParser.ts` | SSE `data:` line parser for the completion stream |
| `src/api/completionEngines.ts` | `OpenAICompletionEngine`: captures one `RemoteEndpoint` at construction, fills `samplers` via `pickSamplers`, forwards intent; optional `ensureReady` hook |
| `src/store/ServerStore.ts` | servers, Keychain keys, `serverModels`, `userSelectedModels`, `remoteReasoning`, `remoteCaps`, computed `listCaps`; `fetchModelsForServer`, `fetchRemoteModelCaps`, prunes, throttled foreground refresh |
| `src/store/ModelStore.ts` | `setRemoteModel` (engine + `activeRemoteBinding` + detached probe), `reprobeRemoteCapsIfUnknown`, `remoteModels`, `capsFor` / `activeModelCaps` |
| `src/utils/types.ts` | `ServerConfig`, `RemoteModelCaps`, `RemoteSessionBinding` |
| `src/utils/remoteCaps.ts` | probe-tier read side: `resolveRemoteCaps`, `capsMatchBinding` |
| `src/utils/modelCaps.ts` | `resolveModelCaps`: merges probe over list, declared vs session axes |
| `src/utils/serverTypes.ts` | `SERVER_TYPE_OPTIONS`, `ServerType`, `toServerType`, `seedServerType` |
| `src/utils/samplerParams.ts` | `SAMPLER_PARAMS`, `SamplerParam`, `Samplers`, `pickSamplers` (app names only; wire names belong to a dialect) |
| `src/utils/timeout.ts` | `parseTimeoutMs`: sheet seconds → whole ms, invalid → `undefined` |
| `src/components/RemoteModelSheet/` | add a remote model: manual `probeServer`, known-server `handleServerChipPress`, type seeding, list-tier vision slot |
| `src/components/ServerDetailsSheet/` | edit url / key / timeout / type; edit-time `testConnection` probe |
| `ios/PocketPal/Info.plist` | `NSLocalNetworkUsageDescription` |

## How it works

1. **Add.** `RemoteModelSheet.probeServer` (debounced) calls `fetchModelsWithHeaders` with the in-edit timeout, then `detectServerType` (`api/servers/detect.ts`) → `seedServerType` seeds the type dropdown. `handleAddModel` calls `serverStore.addServer`, `setApiKey`, `addUserSelectedModel`, `fetchModelsForServer`. The chip path (`handleServerChipPress`) re-fetches a saved server.
2. **Models.** `ModelStore.remoteModels` is derived from `userSelectedModels` × `servers`; ids are `${serverId}/${remoteModelId}`, and remote models never enter the persisted `models` array. `fetchAllRemoteModels` runs after hydration and on foreground (throttled by `FETCH_THROTTLE_MS`).
3. **Activate.** `selectModel` → `setRemoteModel`: release any context, read the key, build `OpenAICompletionEngine`, set `activeRemoteBinding`, then fire `fetchRemoteModelCaps` detached, so a lazily starting server never delays activation.
4. **Probe.** `fetchRemoteModelCaps` (gated on `dialectFor(serverType).discovery.hasProps`) → `fetchServerProps(?model=<id>)`; if unusable and `servesOnlyModel`, one bare `/props`; a guarded merge into `remoteCaps` stamped with `probedUrl`. `reprobeRemoteCapsIfUnknown` re-fires it on foreground.
5. **Read.** Every consumer goes through `modelStore.capsFor` / `activeModelCaps` → `resolveModelCaps` → `resolveRemoteCaps` (probe) field-by-field over `listCaps` (list).
6. **Send.** `engine.completion` → `pickSamplers(params)` → `streamChatCompletion(params, endpoint)`: local image paths inlined as base64 data URIs (`encodeMessagesForRemote`; the server cannot read the device filesystem, and a file over 12 MB is sent unchanged), then body = `dialectFor(endpoint.serverType).bodyExtras({samplers, reasoning})` with the transport's own keys written last, streamed over XHR under two-phase timeouts.
7. **Read.** Every valid chunk goes to `dialect.readFinish`; the latest read that carried `timings` wins, and the token counts come off it (`chat-flow.md`, "Completion timings").

## Contracts and invariants

**Timeouts**

- `ServerConfig.requestTimeoutMs` is the one per-server duration; `undefined` means the defaults (30 s connection, 60 s idle). It replaces both phases of `streamChatCompletion`; `fetchModelsWithHeaders` has only the connection phase (`openai.ts`).
- Normalisation happens only in `resolveTimeout`: `undefined` / `NaN` / non-finite / `≤ 0` → default. Stores, engine and sheets forward the raw value.
- The idle timer resets on every valid chunk, so the timeout bounds phases, never a healthy stream's total wall-clock.
- The one downward exception: `fetchRemoteModelCaps` clamps to `min(requestTimeoutMs ?? PROPS_TIMEOUT_MS, PROPS_TIMEOUT_MS)` so detached work stays bounded. Completions and user-initiated probes forward the raw value.
- Edit-time probes honour the in-edit value: `ServerDetailsSheet.probeServer` (in-edit, else saved), `RemoteModelSheet.probeServer` (in-edit); the chip path uses the saved one. `DETECT_TIMEOUT_MS` is fixed.

**Session binding**

- The engine captures one `RemoteEndpoint` (url, model, key, timeout, normalised `serverType`) when built and is never rebuilt by `updateServer`: every server edit applies on the next `setRemoteModel`.
- An engine may carry an `ensureReady` hook, awaited before the request. Its `AbortController` is created **before** that await and held in a local, so a stop during readiness resolves `{interrupted: true}` without opening a request and without surfacing a readiness error for a turn the user stopped.
- `activeRemoteBinding` is that captured backend. `setRemoteModel` sets it; `initContext` / `releaseContext` clear it; it is not persisted.
- `capsMatchBinding`: an entry is used only if its `probedUrl` equals `binding.url`, or there is no binding for that model, or it has no `probedUrl` (older entry). Anything else resolves unknown and fails closed (`remoteCaps.ts`).

**Single writers**

| State | Writer |
| --- | --- |
| `servers[]` fields (`url`, `serverType`, `requestTimeoutMs`) | `addServer` / `updateServer` (`lastConnected`: `fetchModelsForServer`) |
| API key | `setApiKey` → Keychain service `pocketpal-server-<id>`; never on `ServerConfig` |
| `remoteCaps` | `fetchRemoteModelCaps`, plus the prunes |
| `serverModels` | **two**: `fetchModelsForServer` and `RemoteModelSheet.handleServerChipPress`, both storing `fetchModels` output; `probeServer` writes nothing to the store |
| `listCaps` | none: a computed over `servers` + `serverModels`, not persisted |
| `remoteReasoning` | the reasoning writers in `chat-flow.md`; nothing derived from `/props` is ever written there |
| `activeRemoteBinding` | `setRemoteModel` / `initContext` / `releaseContext` |

`ModelStore` reads `ServerStore` and calls its actions and never writes its maps. No component builds the capability env or reads `remoteCaps` directly.

**Every type decision goes through `dialectFor`**

- The only input is the **persisted** `serverType`, never live detection, and it is normalised by `toServerType` at every writer (hydration, `addServer`, an `updateServer` that carries the key, `setRemoteModel`). An unrecognised value — a legacy `''`, a case variant, a free string — is `'unknown'` and speaks the base dialect.
- **I-V1**: outside `src/api/servers/` (and tests and mocks) there is no literal compare or `switch` on a server-type string. A `no-restricted-syntax` pair in `.eslintrc.js` enforces it; because an override *replaces* the base selector list rather than merging with it, the shared selectors are spread into every `no-restricted-syntax` list the config has. Known evasions: a type held in a variable, or tested with `includes` / a `Set`. Review catches those.
- `DIALECTS` is a `Record<ServerType, ServerDialect>`, so a new type offered in the UI cannot compile until it has a dialect. Each dialect is written with `satisfies`, never annotated `: ServerDialect` — the annotation would widen its `sendNames` and defeat the compile-time check below.
- `bodyExtras` and `readFinish` are pure: no store, no clock, no network, and no type input other than `endpoint.serverType`.
- What the call sites ask for: `discovery.hasProps` gates the `/props` request, `discovery.listReportsCaps` gates the sheet's vision slot, and `readModelEntry` replaces the type gate that used to live inside `deriveListCaps`. `discovery.healthPath` and `discovery.hasRouter` are stated facts with no consumer yet — #897 and #896 own those call sites.
- Sampler wire (`sendNames`; app name → wire name, emitted only for a **finite** number, never coerced to `null`):

| Type | `sendNames` beyond the base |
| --- | --- |
| base / `unknown` (and `LM Studio`, `Ollama`, `OpenAI`, `vLLM`) | none. The base is `temperature→temperature`, `top_p→top_p`, `n_predict→max_completion_tokens` |
| llama.cpp | `top_k`, `min_p`, `typical_p`, `xtc_threshold`, `xtc_probability`, `seed`, `n_probs`, `mirostat`, `mirostat_tau`, `mirostat_eta` under their own names; `penalty_last_n→repeat_last_n`, `penalty_repeat→repeat_penalty`, `penalty_freq→frequency_penalty`, `penalty_present→presence_penalty` |

- `vLLM` sends nothing beyond the base until its names are verified live; it spells at least one of them differently (`repetition_penalty`).
- The `/props` read map is **derived** from the send map: `PROPS_READ_NAMES = {...llamaCpp.sendNames, n_predict: 'n_predict'} satisfies Record<SamplerParam, string>`. `n_predict` is the one param whose read name is not its send name. The `satisfies` makes a param added to `SAMPLER_PARAMS` without a llama.cpp name a compile error on the read side, so send and read cannot drift; a cast anywhere in that expression defeats it.
- Reasoning wire (each dialect's `bodyExtras`; samplers are emitted first, so a reasoning key wins a collision):

| Type | OFF | ON | ON + effort |
| --- | --- | --- | --- |
| llama.cpp | `reasoning_format:'auto'` + `chat_template_kwargs.enable_thinking:false` | `reasoning_format:'auto'` | + `chat_template_kwargs.reasoning_effort` and `reasoning_budget_tokens` (omitted when the effort is not a known level) |
| vLLM | `enable_thinking:false` kwarg | nothing | `reasoning_effort` kwarg |
| LM Studio | `enable_thinking:false` kwarg | nothing | nothing |
| Ollama | `reasoning_effort:'none'` | nothing, never `think:true` | nothing |
| OpenAI | nothing | nothing | top-level `reasoning_effort` |
| unknown / other | nothing | nothing | nothing |

- Unknown or strict servers receive no reasoning controls: omitting beats a 400. `temperature`, `top_p`, `max_completion_tokens` (from `n_predict`), `stop`, `tools`, `tool_choice`, `response_format` are sent for every type.
- `chat_template_kwargs` is merged inside `bodyExtras`. The transport merges nothing, and a dialect may never return a transport-owned key (`model`, `messages`, `stream`, `stop`, `tools`, `tool_choice`, `response_format`) — one parameterised test checks every dialect.

**Probe tier (`/props`)**

- Parse: `contextLength ← default_generation_settings.n_ctx ?? n_ctx`, only when finite and `> 0`. `supportsVision ← modalities.vision === true`, set only on a model-describing body (`model_path` non-empty and not `'none'`, or a context resolved); there, a missing `modalities` is a definite `false`.
- `fetchServerProps` never throws: timeout, non-2xx (a 401 included) and malformed JSON all resolve `{}`. A failure is never evidence of absence.
- Non-downgrading write: `{}` writes nothing; a field the response did not resolve keeps its prior value; an entry probed against another url is replaced, not blended; an unchanged merge is not written.
- The write re-checks the server's `url` / `serverType` against the pre-flight snapshot inside `runInAction` and discards on mismatch or removal.
- Bare `/props` is issued only when the scoped answer was unusable **and** `serverModels` for that server is exactly `[that model]`. An absent or empty list is unknown and does not pass.
- Triggers are activation and a foreground with no entry valid for the binding (skipped once the server url has moved off the binding). A valid entry is never re-fetched, so a good answer cannot be clobbered back to a placeholder. `fetchModelsForServer` issues no `/props`.

**List tier and precedence**

- `readLlamaCppListRow` (reached through `deriveListCaps` → `readModelEntry`): vision from `architecture.input_modalities` containing `image`, else `capabilities` containing `multimodal`; context from `meta.n_ctx`, else the last `--ctx-size` / `-c` in `status.args` (space or `=` form, integer `> 0`). No other argument is read, and every failure is an absent field.
- `status.args` carries filesystem paths and could carry a credential: nothing logs, persists or serialises a raw row.
- `liftModelEntryCapabilities` joins a single-model server's sibling `models[]` onto its `data[]` row (`name ?? model === id`, or the 1×1 pairing).
- Probe beats list, field by field, on the declared axis (`vision`, `contextLength`) only. `visionActive` and `effectiveContextLength` read the probe alone, so no list value gates attach, the send path, the camera or the banner. `RemoteModelCaps.tier` / `ListDerivedCaps.tier` make the two types mutually non-assignable.
- `resolveModelCaps` is pure and synchronous and is read in `observer` bodies, so a landing probe re-renders; `capsFor` must not be annotated as an `action`.

**Invalidation**

- `removeServer` drops `serverModels`, `userSelectedModels`, `remoteReasoning`, `remoteCaps` (prefix `dropServerEntries`) and the Keychain key.
- An `updateServer` that changes `url` or `serverType` drops `remoteCaps` and `serverModels`, but keeps `remoteReasoning`, which holds user declarations. The list must go too: the sheet never refetches after a save, so a stale one-entry list would pass the bare-retry gate against a new multi-model server.

## Traps and decisions

- **llama-server silently accepts unknown body keys** (`200`, no effect). A misspelled or unsupported field ships green. Verify any new forwarded field in `GET /slots?model=<id>` after a completion. Measured: a top-level `reasoning_effort` is ignored by llama.cpp, which is why it is not sent there; `chat_template_kwargs.enable_thinking:false` is what actually turns thinking off.
- **A hand-built `/slots` check proves the wrong thing.** Curling the server with a field and reading it back in `/slots` shows the server accepts the name. It does not show the app sends it: the send map, `pickSamplers`, the finite rule and the call site all sit in between. A forwarded name counts as delivered only when `/slots` shows it for a request **the app built**, from a build of the app.
- **Wire names live per dialect, never in a shared map.** The same control is spelled differently by different servers — llama.cpp's `repeat_penalty` is vLLM's `repetition_penalty` — and llama-server's 200-on-unknown-key means a name borrowed from the wrong dialect silently keeps the server's default. Each dialect names its own params, even where the names agree.
- **`reasoning_format` is never `'none'`**: it leaves raw channel/think markers in `content` (gemma-4 emits an empty thought block even with thinking off).
- **Ollama hard-400s** on `think:true` or a non-`'none'` effort to a non-thinking model; OpenAI 400s on misapplied params. So payloads are per-type, not universal.
- **`/props` is per model.** A multi-model router answers bare `/props` with a placeholder (`role:'router'`, `model_path:'none'`, `n_ctx:0`, `modalities` absent), and on a swap router `?model=<id>` **loads** the model. That is why caps are keyed per model, why the bare retry is gated, and why a browse surface (the add sheet, model cards) reads the list tier and never probes.
- **llama-server auth is not uniform** (measured). `/v1/models` and `/health` answer 200 to an unauthenticated caller; `/props`, `/slots` and `/v1/chat/completions` 401. On a keyed server with no key yet, the list tier fills while the probe stays unknown, so a card reading "Vision: Supported" with attach disabled is the normal state, and it is correct. A real OpenAI endpoint 401s `/v1/models`.
- **The list can disagree with the probe.** On multi-slot servers `--ctx-size` / `meta.n_ctx` are the total window while `/props` is per slot. A direct server with an audio-only projector reports `multimodal`. A router that cannot resolve an uncached mmproj omits `image`. `--ctx-size 0` means the trained window, so it is unknown, never `0`. Activation corrects all of these.
- **Url shape.** A trailing slash is harmless because `normalizeUrl` strips it at every request site. A `/v1` suffix (a hand-copied "Base URL") is fatal (`…/v1/props` → 404) and is not stripped. Nothing canonicalises at write, and `updateServer` compares raw strings, so a slash-only edit reads as a repoint and drops caps and the list.
- **A url edit does not move a live session**: it keeps posting to the old backend until the model is re-selected, and caps stay unknown meanwhile.
- **iOS Local Network.** `NSLocalNetworkUsageDescription` is required. Without it, iOS 18 silently denies (NSURLError -1009, indistinguishable from a dead server; Safari is exempt, so it misleads). A denied device never re-prompts (Settings → Privacy & Security → Local Network). The simulator never enforces it. The first probe is the request that raises the prompt and fails, which is why the foreground re-probe exists: remote models are exempt from auto-release, so nothing else would retry. It lives in `ModelStore` because `ServerStore` cannot see the active model without an import cycle.
- **Detection only seeds.** `detectServerType` cannot identify OpenAI or vLLM, so the type is user-selectable. Only the add path detects, and `ServerDetailsSheet` never re-detects. The Ollama probe (`GET /`) carries no key.
- **`ServerDetailsSheet`'s Save sits in `Sheet.Actions`**, and `Sheet` pans rather than resizes on Android. Measured: with a field focused, the button is behind the keyboard.
- **Decisions.** One timeout for both phases, because both end the same conversation and a second knob buys nothing. Persisted type, never detection, because detection is incomplete and the user override is the escape hatch. `remoteCaps` persists but the binding does not, since a session does not survive a launch. `lastUsedModelId` is never set for a remote model, because the server may be offline next launch. Token counts come from `timings`, not `usage`, because `usage` needs a `stream_options.include_usage` opt-in and no `usage` object appears without it.

## Verification

- Unit: `src/api/__tests__/openai.test.ts`, `src/api/__tests__/completionEngines.test.ts`, `src/api/__tests__/remoteRequestPath.characterisation.test.ts` (request body × every type × reasoning state × sampler set, the three `/props` tiers, list-row caps, and the legacy persisted types), `src/api/servers/__tests__/{dialects,bodyExtras,listCaps,llamaCppListRow,detect}.test.ts`, `src/api/llamaServer/__tests__/props.test.ts`, `src/store/__tests__/ServerStore.test.ts`, `src/store/__tests__/ModelStore.test.ts`, `src/utils/__tests__/{remoteCaps,modelCaps}.test.ts`, `src/components/{RemoteModelSheet,ServerDetailsSheet}/__tests__/`.
- The characterisation suite compares **parsed** bodies, never raw strings: moving keys into `bodyExtras` changes key order without changing the request.
- Fixtures: `jest/fixtures/remoteModelList.ts` holds verbatim router and direct `/v1/models` captures. Add wire fixtures only as real captures, never hand-written.
- E2E (needs a live server): `e2e/specs/features/remote-server.spec.ts`, `remote-reasoning.spec.ts`, `remote-vision.spec.ts`, via `REMOTE_SERVER_URL`, `REMOTE_SERVER_API_KEY`, `REMOTE_VISION_URL`, `REMOTE_NONVISION_URL` and the `*_MODEL_HINT` variables.
- By hand: run `llama-server` (single-model and `--models-dir` router), add it, activate a vision and a text model, and check attach. For any wire change, confirm delivery in `/slots`. iOS Local Network behaviour only reproduces on a physical device.
